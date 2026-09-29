import json
from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient

from ethics_lab import comparisons, openrouter, store
from ethics_lab.app import app
from ethics_lab.scenarios import SCENARIOS

FREE = openrouter.MODELS[0]["id"]
JEV = "typesafe/jev-1.13"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("ETHICS_DB", str(tmp_path / "models.sqlite3"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-real")
    monkeypatch.setattr(openrouter, "ROOT", tmp_path)
    monkeypatch.setattr(openrouter, "_catalog", None)
    monkeypatch.setattr(openrouter, "_catalog_time", 0)
    monkeypatch.setattr(openrouter, "_calls", openrouter.deque())
    calls = []
    models = [{"id": m["id"], "pricing": {"prompt": "0", "completion": "0"},
               "supported_parameters": ["structured_outputs", "temperature", "reasoning"],
               "reasoning": {"supported_efforts": ["low"]}} for m in openrouter.MODELS if m["kind"] == "llm"]

    def fake_request(path, *, payload=None, authenticated=False, timeout=15):
        calls.append({"path": path, "payload": deepcopy(payload), "authenticated": authenticated})
        if path == "v1/models":
            return {"data": models}
        if path == "v1/key":
            return {"data": {"label": "private-key-label", "is_free_tier": True,
                             "free_model_daily_requests": {"used": 2, "remaining": 48, "limit": 50}}}
        if path == "alpha/decisions":
            answers = {"decision": {"type": "choice", "choice": "conditional", "probabilities": {"conditional": 0.9, "hold": 0.1}}}
            if "next_question" in payload["questions"]:
                answers["next_question"] = {"type": "choice", "choice": "relay_a", "probabilities": {"relay_a": 1}}
            return {"id": "jev-test", "model": "typesafe/jev-1.13-dated", "provider": "TypeSafe",
                    "answers": answers, "usage": {"input_tokens": 500, "output_tokens": 20, "cost": 0.000021}}
        return {"id": "chat-test", "model": payload["model"], "provider": "Test Provider",
                "usage": {"prompt_tokens": 700, "completion_tokens": 80, "cost": 0},
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(
                    {"decision": "conditional", "next_question": "relay_a", "explanation": "Both relay settings are needed."})}}]}

    monkeypatch.setattr(openrouter, "request", fake_request)
    with TestClient(app) as client:
        run = client.post("/api/runs", json={"scenario_id": "relays"}).json()
        yield client, run, calls, models


def compare(client, run, **kwargs):
    body = {"model_id": FREE, "framework_id": "utility", "evidence_step": len(run["events"]), **kwargs}
    return client.post(f"/api/runs/{run['id']}/comparisons", json=body)


def test_independent_packet_hides_actual_world_reference_answers_and_other_models(setup):
    client, run, calls, _ = setup
    original = store.get(run["id"])
    first = compare(client, run).json()["record"]
    payload = next(c["payload"] for c in calls if c["path"] == "v1/chat/completions")
    supplied = json.loads(payload["messages"][1]["content"])
    assert supplied["observed"] == {}
    assert supplied["remaining_credits"] == 2
    assert all(f["value"] is None for f in supplied["facts"])
    assert not any(key in supplied for key in ("actual", "debrief", "analysis", "agents", "reference", "events"))
    assert "reference_next_question" not in json.dumps(supplied)
    original["actual"] = {key: not value for key, value in original["actual"].items()}
    assert openrouter.evidence_input(original, "utility") == supplied
    assert first["assessment"]["decision_matches"]
    assert first["result"]["usage"]["cost"] == 0
    assert store.get(run["id"])["events"] == []
    assert payload["provider"]["max_price"] == {"prompt": 0, "completion": 0}
    assert "models" not in payload
    assert "Authorization" not in json.dumps(first)
    assert "test-key-not-real" not in json.dumps(first)


def test_cache_reuses_attempt_and_explicit_repeat_preserves_both(setup):
    client, run, calls, _ = setup
    first = compare(client, run).json()
    repeated = compare(client, run).json()
    assert repeated["reused"] is True
    assert first["record"]["id"] == repeated["record"]["id"]
    assert len([c for c in calls if c["path"] == "v1/chat/completions"]) == 1
    new = compare(client, run, repeat=True).json()
    assert new["record"]["id"] != first["record"]["id"]
    assert len(comparisons.history(run["id"])) == 2
    run2 = client.post(f"/api/runs/{run['id']}/reveal", json={"fact_id": "relay_a"}).json()
    assert compare(client, run).status_code == 409
    third = compare(client, run2).json()["record"]
    assert third["state_key"] != first["record"]["state_key"]
    assert third["input"]["observed"] == run2["observed"]


def test_unknown_and_paid_models_cannot_be_called_accidentally(setup):
    client, run, calls, models = setup
    assert compare(client, run, model_id="openai/paid-model").status_code == 422
    assert compare(client, run, model_id=JEV).status_code == 400
    models[0]["pricing"]["prompt"] = "0.001"
    response = compare(client, run).json()["record"]
    assert response["error"]["code"] == "not_verified_free"
    assert not any(c["path"].endswith("completions") or c["path"] == "alpha/decisions" for c in calls)


def test_jev_uses_decisions_api_only_with_explicit_opt_in(setup):
    client, run, calls, _ = setup
    result = compare(client, run, model_id=JEV, allow_paid_jev=True).json()["record"]
    assert result["status"] == "ok"
    assert result["result"]["kind"] == "decision"
    assert result["result"]["answer"]["explanation"] is None
    assert result["result"]["answer"]["probabilities"]["decision"]["conditional"] == 0.9
    payload = next(c["payload"] for c in calls if c["path"] == "alpha/decisions")
    assert payload["state"]["observed"] == {}
    assert payload["questions"]["decision"]["type"] == "choice"
    client.post(f"/api/runs/{run['id']}/finish")
    finished = store.get(run["id"])
    packet = openrouter.jev_payload(openrouter.evidence_input(finished, "utility"))
    assert set(packet["questions"]) == {"decision"}


@pytest.mark.parametrize("case", SCENARIOS, ids=lambda s: s["id"])
def test_prompt_does_not_contain_catalog_demonstration_hints(setup, case):
    _, run, _, _ = setup
    internal = store.get(run["id"])
    internal.update(scenario=case, observed={})
    packet = openrouter.evidence_input(internal, "utility")
    assert "description" not in json.dumps(packet)
    assert "model_note" not in json.dumps(packet)
    assert "all three policies" not in json.dumps(packet).lower()
    assert len(packet["facts"]) == 3


def test_failures_are_saved_without_retry_or_reference_substitution(setup, monkeypatch):
    client, run, calls, _ = setup
    original = openrouter.request
    count = []

    def failing(path, **kwargs):
        if path.endswith("completions"):
            count.append(1)
            raise openrouter.ProviderFailure("http_429", "Provider is at capacity.", 30)
        return original(path, **kwargs)

    monkeypatch.setattr(openrouter, "request", failing)
    result = compare(client, run).json()["record"]
    assert result["status"] == "error"
    assert result["error"]["retry_after"] == 30
    assert "result" not in result
    assert compare(client, run).json()["reused"]
    assert len(count) == 1


@pytest.mark.parametrize("content,finish", [
    ("not json", "stop"),
    ('{"decision":"hold","next_question":null,"explanation":"x"}', "length"),
    ('{"decision":"invented","next_question":null,"explanation":"x"}', "stop"),
])
def test_invalid_or_truncated_output_is_not_accepted(content, finish):
    with pytest.raises(openrouter.ProviderFailure):
        openrouter.parse_chat({"choices": [{"finish_reason": finish, "message": {"content": content}}]})


def test_extra_model_metadata_is_retained_raw_but_cannot_change_evaluated_fields():
    raw = '{"decision":"hold","next_question":null,"explanation":"x","extra":true}'
    answer, saved = openrouter.parse_chat({"choices": [{"finish_reason": "stop", "message": {"content": raw}}]})
    assert answer == {"decision": "hold", "next_question": None, "explanation": "x"}
    assert saved == raw


def test_invalid_fact_suggestion_and_unsupported_decision_are_scored_as_errors(setup):
    _, run, _, _ = setup
    internal = store.get(run["id"])
    verdict = openrouter.assess(internal, "utility", {"decision": "brake", "next_question": "invented"})
    assert not verdict["decision_matches"]
    assert not verdict["question_valid"]


def test_model_catalog_and_key_status_expose_no_secrets_and_no_fake_free_families(setup):
    client, _, _, models = setup
    catalog = client.get("/api/models").json()
    assert len(catalog["models"]) == 7
    assert {f["name"] for f in catalog["unavailable_families"]} == {"OpenAI", "Google Gemini"}
    assert catalog["models"][-1]["free"] is False
    status = client.get("/api/openrouter/status?check_quota=true").json()
    assert status["quota"]["remaining"] == 48
    assert "private-key-label" not in json.dumps(status)
    assert "test-key" not in json.dumps(status)
    models.append({"id": "google/gemini-test:free", "name": "Test Gemini", "pricing": {"prompt": "0", "completion": "0"}})
    refreshed = client.get("/api/models?refresh=true").json()
    assert any(m["id"] == "google/gemini-test:free" and m["verified_free"] for m in refreshed["models"])


def test_missing_key_is_explicit_and_dotenv_is_read_without_execution(setup, monkeypatch):
    client, run, calls, _ = setup
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert compare(client, run).json()["record"]["error"]["code"] == "missing_key"
    (openrouter.ROOT / ".env").write_text('IGNORED=do-not-evaluate\nOPENROUTER_API_KEY="local-test-key"\n', encoding="utf-8")
    assert openrouter.api_key() == "local-test-key"


def test_pending_attempts_are_not_duplicated_and_exports_keep_provenance(setup):
    client, run, calls, _ = setup
    internal = store.get(run["id"])
    first, reused = comparisons.start_attempt(internal, FREE, "duty")
    second, reused2 = comparisons.start_attempt(internal, FREE, "duty", repeat=True)
    assert not reused and reused2
    assert first["id"] == second["id"]
    compare(client, run)
    path = f"/api/runs/{run['id']}/comparisons/export"
    md = client.get(path).text
    assert "Reference adherence is not moral correctness" in md
    assert "Test Provider" in md
    data = client.get(path + "?format=json").json()
    assert len(data["records"]) == 2
    assert "test-key-not-real" not in json.dumps(data)
    assert all("actual" not in r["input"] for r in data["records"])


def test_local_rate_guard_makes_no_nineteenth_provider_call(setup):
    _, run, calls, _ = setup
    context = openrouter.evidence_input(store.get(run["id"]), "utility")
    openrouter._calls.extend([openrouter.time.monotonic()] * 18)
    with pytest.raises(openrouter.ProviderFailure, match="18-request"):
        openrouter.invoke(FREE, context)
    assert not any(c["path"].endswith("completions") for c in calls)


def test_http_timeout_and_auth_error_are_sanitized(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-test-value")
    actual_client = httpx.AsyncClient
    seen = []

    def transport(request):
        seen.append(request.headers["Authorization"])
        return httpx.Response(401, json={"error": {"message": "secret-test-value"}})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: actual_client(transport=httpx.MockTransport(transport), **kwargs))
    with pytest.raises(openrouter.ProviderFailure) as error:
        openrouter.request("v1/key", authenticated=True)
    assert seen == ["Bearer secret-test-value"]
    assert "secret-test-value" not in str(error.value)


def test_absolute_timeout_bounds_a_provider_even_when_connection_stays_open(monkeypatch):
    actual_client = httpx.AsyncClient

    async def delayed(request):
        await openrouter.asyncio.sleep(0.2)
        return httpx.Response(200, json={"data": {}})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: actual_client(transport=httpx.MockTransport(delayed), **kwargs))
    with pytest.raises(openrouter.ProviderFailure) as error:
        openrouter.request("v1/models", timeout=0.02)
    assert error.value.code == "timeout"
