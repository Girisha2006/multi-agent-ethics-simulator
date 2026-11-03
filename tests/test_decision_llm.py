import json
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ethics_lab import openrouter
from ethics_lab.decision import agents, dilemmas, llm, llm_api

LLMS = [m["id"] for m in llm.llm_models()]
D = "close-call"


def model_entry(model_id, price="0"):
    return {"id": model_id, "pricing": {"prompt": price, "completion": price}, "supported_parameters": ["temperature", "structured_outputs"]}


def good(dilemma_id=D):
    """A response in which every agent states the rule's own explanation, so audits pass."""
    d = dilemmas.get(dilemma_id)
    answers = {}
    for a in agents.AGENTS:
        out = agents.RULES[a["id"]](d)
        answers[a["id"]] = {"choice": out["choice"], "explanation": out["explanation"]}
    return {"choices": [{"message": {"content": json.dumps({"answers": answers})}}]}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ETHICS_DB", str(tmp_path / "t.sqlite3"))
    monkeypatch.setenv("DECISION_RECORDINGS", str(tmp_path / "rec.json"))
    monkeypatch.delenv("DECISION_LLM_DAILY_LIMIT", raising=False)
    monkeypatch.setattr(openrouter, "api_key", lambda: "test-key")
    catalog = {m: model_entry(m) for m in LLMS}
    calls = []
    behaviour = {"respond": lambda payload: good()}

    def fake_request(path, *, payload=None, authenticated=False, timeout=15):
        calls.append(deepcopy(payload))
        return behaviour["respond"](payload)

    monkeypatch.setattr(openrouter, "request", fake_request)
    monkeypatch.setattr(openrouter, "live_catalog", lambda refresh=False: catalog)
    return type("Env", (), {"calls": calls, "catalog": catalog, "behaviour": behaviour, "tmp": tmp_path})


def raising(code, retry=None):
    def respond(payload):
        raise openrouter.ProviderFailure(code, "failed", retry)
    return respond


def test_one_request_yields_four_audited_answers(env):
    r = llm.run(D)
    assert r["status"] == "ok" and r["source"] == "live" and r["requests_used"] == 1 and len(env.calls) == 1
    assert r["model_id"] == LLMS[0] and [a["agent"] for a in r["answers"]] == [a["id"] for a in agents.AGENTS]
    assert all(a["matches_reference"] and a["audit"]["passed"] and "checks" in a["audit"] for a in r["answers"])
    assert env.calls[0]["provider"]["max_price"] == {"prompt": 0, "completion": 0} and env.calls[0]["temperature"] == 0
    assert "expected_utility" in json.dumps(env.calls[0]["messages"])


def test_recommended_model_goes_first():
    assert llm.llm_models()[0].get("recommended") is True


def test_cache_hit_makes_no_request_and_repeat_does(env):
    llm.run(D)
    hit = llm.run(D)
    assert hit["source"] == "cache" and hit["requests_used"] == 0 and len(env.calls) == 1
    again = llm.run(D, repeat=True)
    assert again["source"] == "live" and len(env.calls) == 2
    assert len(llm.results(D)) == 2


def test_daily_limit_enforced_and_persisted(env, monkeypatch):
    monkeypatch.setenv("DECISION_LLM_DAILY_LIMIT", "2")
    env.behaviour["respond"] = lambda payload: good("crossing") if "5 adults" in json.dumps(payload) else good("barrier")
    llm.run("crossing"), llm.run("barrier")
    r = llm.run("generations")
    assert r["status"] == "error" and r["error"]["code"] == "quota_exhausted" and r["answers"] == []
    assert 0 < r["error"]["retry_after"] <= 86400 and len(env.calls) == 2
    s = llm.status()["quota"]
    assert (s["used"], s["limit"], s["remaining"]) == (2, 2, 0)


def test_minute_limit(env, monkeypatch):
    monkeypatch.setattr(llm, "MINUTE_LIMIT", 2)
    llm.run("crossing"), llm.run("barrier")
    r = llm.run("generations")
    assert r["error"]["code"] == "minute_limit" and 1 <= r["error"]["retry_after"] <= 60 and len(env.calls) == 2


def test_429_sets_cooldown_and_next_model_answers(env):
    def respond(payload):
        if payload["model"] == LLMS[0]:
            raise openrouter.ProviderFailure("http_429", "limited", 90)
        return good()

    env.behaviour["respond"] = respond
    r = llm.run(D)
    assert r["status"] == "ok" and r["model_id"] == LLMS[1] and r["requests_used"] == 2
    assert LLMS[0] in llm.status()["cooldowns"]
    again = llm.run(D, repeat=True)          # first model is cooling down, so it is skipped
    assert again["requests_used"] == 1 and env.calls[-1]["model"] == LLMS[1]
    assert llm.status()["quota"]["used"] == 3


def test_invalid_output_is_an_error_without_substitution(env):
    env.behaviour["respond"] = lambda payload: {"choices": [{"message": {"content": "I would stay."}}]}
    r = llm.run(D)
    assert r["status"] == "error" and r["error"]["code"] == "invalid_output" and r["answers"] == []
    assert r["requests_used"] == 3 and len(env.calls) == 3      # at most three models
    assert llm.results(D) == []


@pytest.mark.parametrize("content", [
    json.dumps({"answers": {"expected_utility": {"choice": "stay", "explanation": "x"}}}),
    json.dumps({"answers": {a["id"]: {"choice": "left", "explanation": "x"} for a in agents.AGENTS}}),
    json.dumps({"answers": {a["id"]: {"choice": "stay", "explanation": "word " * 151} for a in agents.AGENTS}})])
def test_strict_validation(env, content):
    env.behaviour["respond"] = lambda payload: {"choices": [{"message": {"content": content}}]}
    assert llm.run(D)["error"]["code"] == "invalid_output"


def test_code_fences_are_stripped(env):
    data = good()
    data["choices"][0]["message"]["content"] = "```json\n" + data["choices"][0]["message"]["content"] + "\n```"
    env.behaviour["respond"] = lambda payload: data
    assert llm.run(D)["status"] == "ok"


def test_non_free_model_is_skipped(env):
    env.catalog[LLMS[0]] = model_entry(LLMS[0], "0.000001")
    r = llm.run(D)
    assert r["status"] == "ok" and r["model_id"] == LLMS[1] and all(c["model"] != LLMS[0] for c in env.calls)
    assert LLMS[0] in llm.status()["cooldowns"]


def test_no_free_model_means_error_and_no_request(env):
    for m in LLMS:
        env.catalog[m] = model_entry(m, "1")
    r = llm.run(D)
    assert r["status"] == "error" and env.calls == [] and r["requests_used"] == 0


def recording(dilemma_id=D, created="2026-01-01T00:00:00+00:00", model="rec/model:free"):
    """A test-only recording built in tmp_path; no recording content is committed to the repository."""
    d = dilemmas.get(dilemma_id)
    return {"status": "ok", "source": "live", "dilemma_id": dilemma_id, "model_id": model, "created_at": created, "duration_ms": 5,
            "requests_used": 1, "answers": llm.build_answers(d, llm.parse(good(dilemma_id))), "error": None, "cache_key": llm.cache_key(d)}


def test_no_key_with_recording_replays(env, monkeypatch):
    monkeypatch.setattr(openrouter, "api_key", lambda: "")
    (env.tmp / "rec.json").write_text(json.dumps([recording(model="old"), recording(created="2026-02-01T00:00:00+00:00", model="new"), recording("crossing")]))
    r = llm.run(D)
    assert r["source"] == "recording" and r["model_id"] == "new" and r["requests_used"] == 0 and env.calls == []
    assert llm.status()["mode"] == "replay" and llm.status()["recordings"] == 3
    assert [x["model_id"] for x in llm.results(D)] == ["new", "old"]


def test_no_key_no_recording_is_error(env, monkeypatch):
    monkeypatch.setattr(openrouter, "api_key", lambda: "")
    r = llm.run(D)
    assert r["status"] == "error" and r["answers"] == [] and r["error"]["code"] == "missing_key"
    assert llm.status()["mode"] == "offline" and llm.status()["configured"] is False


def test_recording_keys_do_not_collide_for_mirrored_dilemmas(env, monkeypatch):
    monkeypatch.setattr(openrouter, "api_key", lambda: "")
    (env.tmp / "rec.json").write_text(json.dumps([recording("close-call")]))
    assert llm.cache_key(dilemmas.get("close-call")) != llm.cache_key(dilemmas.get("close-call~intervention"))
    assert llm.run("close-call~intervention")["status"] == "error"


def test_quota_exhausted_falls_back_to_recording(env, monkeypatch):
    monkeypatch.setenv("DECISION_LLM_DAILY_LIMIT", "0")
    (env.tmp / "rec.json").write_text(json.dumps([recording()]))
    r = llm.run(D)
    assert r["source"] == "recording" and env.calls == []
    assert r["fallback"]["code"] == "quota_exhausted"


def test_all_models_failing_falls_back_to_recording(env):
    (env.tmp / "rec.json").write_text(json.dumps([recording()]))
    env.behaviour["respond"] = raising("timeout")
    r = llm.run(D)
    assert r["source"] == "recording" and r["requests_used"] == 3 and r["model_id"] == "rec/model:free"
    assert r["fallback"]["code"] == "timeout"


def test_busy_lock(env):
    assert llm._busy.acquire(blocking=False)
    try:
        r = llm.run(D)
    finally:
        llm._busy.release()
    assert r["error"]["code"] == "busy" and env.calls == []


def test_router(env):
    app = FastAPI()
    app.include_router(llm_api.router)
    c = TestClient(app)
    s = c.get("/api/decision/llm/status").json()
    assert set(s) == {"configured", "mode", "quota", "minute", "cooldowns", "models", "recordings", "prompt_version"}
    assert s["mode"] == "live" and s["prompt_version"] == "decision-batch-1" and s["quota"]["limit"] == 45
    run = c.post("/api/decision/llm/run", json={"dilemma_id": D}).json()
    assert run["status"] == "ok" and set(run) == {"status", "source", "dilemma_id", "model_id", "created_at", "duration_ms", "requests_used", "answers", "error"}
    assert c.post("/api/decision/llm/run", json={"dilemma_id": D, "repeat": False}).json()["source"] == "cache"
    assert len(c.get("/api/decision/llm/results", params={"dilemma_id": D}).json()["results"]) == 1
    assert c.post("/api/decision/llm/run", json={"dilemma_id": "nope"}).status_code == 404
    assert c.get("/api/decision/llm/results", params={"dilemma_id": "nope"}).status_code == 404


def test_account_wide_failure_stops_chain_and_cools_all_models(env):
    env.behaviour["respond"] = raising("http_401")
    r = llm.run(D)
    assert r["error"]["code"] == "http_401" and r["requests_used"] == 1 and len(env.calls) == 1
    assert set(llm.status()["cooldowns"]) == set(LLMS)
    again = llm.run(D)
    assert again["requests_used"] == 0 and len(env.calls) == 1


def test_retry_after_cooldown_is_capped(env):
    from datetime import datetime, timezone
    env.behaviour["respond"] = raising("http_429", 999999)
    llm.run(D)
    until = datetime.fromisoformat(llm.status()["cooldowns"][LLMS[0]])
    assert (until - datetime.now(timezone.utc)).total_seconds() <= 3601


def test_unexpected_parse_exception_is_invalid_output(env, monkeypatch):
    def boom(data):
        raise RecursionError("deep")
    monkeypatch.setattr(llm, "parse", boom)
    r = llm.run(D)
    assert r["status"] == "error" and r["error"]["code"] == "invalid_output" and r["requests_used"] == 3


def test_cache_key_depends_on_parameters(monkeypatch):
    d = dilemmas.get(D)
    before = llm.cache_key(d)
    monkeypatch.setitem(agents.PARAMETERS, "extra", {"x": 1})
    assert llm.cache_key(d) != before


def test_malformed_recordings_are_ignored(env, monkeypatch):
    monkeypatch.setattr(openrouter, "api_key", lambda: "")
    bad_missing = recording(created="2026-09-01T00:00:00+00:00", model="bad")
    bad_missing["answers"] = bad_missing["answers"][:3]
    bad_choice = recording(created="2026-08-01T00:00:00+00:00", model="bad2")
    bad_choice["answers"][0]["choice"] = "left"
    no_model = recording(created="2026-07-01T00:00:00+00:00")
    del no_model["model_id"]
    (env.tmp / "rec.json").write_text(json.dumps([bad_missing, bad_choice, no_model, recording(model="good")]))
    assert llm.run(D)["model_id"] == "good"
    assert [x["model_id"] for x in llm.results(D)] == ["good"]


def test_forbidden_model_only_cools_itself(env):
    seen = []
    def respond(payload):
        seen.append(payload["model"])
        if len(seen) == 1:
            raise openrouter.ProviderFailure("http_403", "denied")
        return good()
    env.behaviour["respond"] = respond
    r = llm.run(D)
    assert r["status"] == "ok" and r["requests_used"] == 2 and r["model_id"] == seen[1]
    assert list(llm.cooldowns()) == [seen[0]]


def test_json_wrapped_in_prose_or_fences_is_read_unchanged(env):
    body = good()["choices"][0]["message"]["content"]
    env.behaviour["respond"] = lambda payload: {"choices": [{"message": {"content": f"Here is the answer:\n```json\n{body}\n```"}}]}
    r = llm.run(D)
    assert r["status"] == "ok" and all(a["matches_reference"] for a in r["answers"])


def test_unbalanced_json_is_not_repaired(env):
    body = good()["choices"][0]["message"]["content"][:-1]
    env.behaviour["respond"] = lambda payload: {"choices": [{"message": {"content": body}}]}
    assert llm.run(D)["error"]["code"] == "invalid_output"


def test_strict_json_models_are_tried_first(env):
    plain = [m for m in LLMS if not next(x for x in openrouter.MODELS if x["id"] == m).get("recommended")]
    for m in plain[:-1]:
        env.catalog[m]["supported_parameters"] = ["temperature"]
    env.behaviour["respond"] = raising("timeout")
    llm.run(D)
    order = [c["model"] for c in env.calls]
    assert order[0] == LLMS[0] and order[1] == plain[-1]
