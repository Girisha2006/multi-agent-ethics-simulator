"""Optional language-model agents for the Decision Lab, built for free OpenRouter limits.

Quota strategy (about 50 requests/day, 20/minute, frequent 429s):
- One batched request per dilemma: the model plays all four agents at once, so a dilemma costs one request, not four.
- Every HTTP attempt (success or failure) is written to SQLite before the request is sent. The daily count
  (DECISION_LLM_DAILY_LIMIT, default 45, per UTC day) and the sliding 60 s window (15 attempts) are read from that table,
  so limits survive restarts and always sit below the provider's own.
- Successful results are cached by sha256(PROMPT_VERSION, agent parameters, stay lane, swerve lane); a repeat click costs nothing
  unless the caller asks for repeat=true.
- Models are tried in order (recommended first), at most 3 per run, only when the live catalog lists them at zero price.
  A failing model gets a persisted cooldown (429 -> Retry-After or 60 s, unavailable/not free -> 600 s, other -> 120 s).
  There is never a paid fallback and never a reference-answer substitution.
- Without a key, or when quota or every model is exhausted, the newest matching real recording (recordings/decision_llm.json,
  produced only by tools/record_llm.py) is replayed and labelled source "recording". Otherwise an error is returned.
- The local daily counter covers only Decision Lab requests. The Before You Decide model-comparison tab draws on the same OpenRouter
  free pool, so the two together can exceed the provider limit. An account-wide failure (401/402) stops the chain and cools every model for 600 s.
- Only one live run at a time (non-blocking lock). The /models catalog fetch is cached for 5 minutes by openrouter.py and is
  not a free-model request, so it is not counted against the chat-completion quota.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from .. import openrouter, store
from . import agents, dilemmas, evaluation

PROMPT_VERSION = "decision-batch-1"
DEFAULT_DAILY_LIMIT = 45
MINUTE_LIMIT = 15
MAX_MODELS = 3
MAX_WORDS = 150  # the prompt asks for 80; longer answers are kept and audited, rambling ones still fail
ACCOUNT_WIDE = ("http_401", "http_402")  # a 403 is usually one provider refusing, so only that model cools down
ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_IDS = [a["id"] for a in agents.AGENTS]
SYSTEM_PROMPT = """You are simulating four decision-theory agents in a controlled experiment. For the dilemma given, answer once for EACH agent,
applying only that agent's rule and parameters exactly as written. Do not mix rules and do not use your own moral judgement.
Reply with JSON only, no markdown: {"answers": {"<agent_id>": {"choice": "stay" or "swerve", "explanation": "<= 80 words"}}}
with all four agent ids. Each explanation must name the choice, cite only the factors that agent's rule uses, and quote only numbers from its calculation."""
_busy = threading.Lock()


class Entry(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    choice: Literal["stay", "swerve"]
    explanation: str

    @field_validator("explanation")
    @classmethod
    def short(cls, text):
        if not text.strip() or len(text.split()) > MAX_WORDS:
            raise ValueError(f"explanation must be 1 to {MAX_WORDS} words")
        return text.strip()


class Batch(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    answers: dict[str, Entry]

    @field_validator("answers")
    @classmethod
    def all_agents(cls, answers):
        if set(answers) != set(AGENT_IDS):
            raise ValueError("answers must contain exactly the four agent ids")
        return answers


def now():
    return datetime.now(timezone.utc).isoformat()


def daily_limit():
    try:
        return max(0, int(os.environ.get("DECISION_LLM_DAILY_LIMIT", DEFAULT_DAILY_LIMIT)))
    except ValueError:
        return DEFAULT_DAILY_LIMIT


def recordings_path():
    return Path(os.environ.get("DECISION_RECORDINGS") or ROOT / "recordings" / "decision_llm.json")


def cache_key(d):
    body = json.dumps([PROMPT_VERSION, agents.PARAMETERS, d["stay"], d["swerve"]], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def llm_models():
    """Configured language models: the recommended one first, then the declared order."""
    models = [m for m in openrouter.MODELS if m["kind"] == "llm"]
    return sorted(models, key=lambda m: not m.get("recommended"))


def utc_day(at=None):
    return datetime.fromtimestamp(at or time.time(), timezone.utc).strftime("%Y-%m-%d")


def seconds_to_midnight(at=None):
    moment = datetime.fromtimestamp(at or time.time(), timezone.utc)
    midnight = (moment + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, math.ceil((midnight - moment).total_seconds()))


def ensure_tables(db):
    db.execute("CREATE TABLE IF NOT EXISTS llm_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL, at REAL NOT NULL, model_id TEXT NOT NULL)")
    db.execute("CREATE INDEX IF NOT EXISTS llm_attempts_by_day ON llm_attempts(day, at)")
    db.execute("CREATE TABLE IF NOT EXISTS llm_cooldowns (model_id TEXT PRIMARY KEY, until REAL NOT NULL, code TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS llm_results (id INTEGER PRIMARY KEY AUTOINCREMENT, cache_key TEXT NOT NULL, dilemma_id TEXT NOT NULL, created REAL NOT NULL, body TEXT NOT NULL)")
    db.execute("CREATE INDEX IF NOT EXISTS llm_results_by_key ON llm_results(cache_key, created)")


def usage(db, at=None):
    at = at or time.time()
    day = db.execute("SELECT COUNT(*) FROM llm_attempts WHERE day = ?", (utc_day(at),)).fetchone()[0]
    window = db.execute("SELECT COUNT(*), MIN(at) FROM llm_attempts WHERE at > ?", (at - 60,)).fetchone()
    return day, window[0], window[1]


def reserve(model_id):
    """Atomically check both limits and record the attempt before the request is made. Returns None or (code, message, retry_after)."""
    at = time.time()
    with store.connect() as db:
        ensure_tables(db)
        db.execute("BEGIN IMMEDIATE")
        day, minute, oldest = usage(db, at)
        if day >= daily_limit():
            return "quota_exhausted", f"The local daily limit of {daily_limit()} model requests is used up. It resets at 00:00 UTC.", seconds_to_midnight(at)
        if minute >= MINUTE_LIMIT:
            return "minute_limit", f"The local limit of {MINUTE_LIMIT} requests per minute is reached.", max(1, math.ceil(oldest + 60 - at))
        db.execute("INSERT INTO llm_attempts (day, at, model_id) VALUES (?, ?, ?)", (utc_day(at), at, model_id))
    return None


def cooldowns():
    with store.connect() as db:
        ensure_tables(db)
        rows = db.execute("SELECT model_id, until FROM llm_cooldowns WHERE until > ?", (time.time(),)).fetchall()
    return {model_id: datetime.fromtimestamp(until, timezone.utc).isoformat() for model_id, until in rows}


def set_cooldown(model_id, failure):
    seconds = {"http_429": min(failure.retry_after or 60, 3600), "http_404": 600, "not_free": 600}.get(failure.code, 120)
    cool([model_id], seconds, failure.code)


def cool(model_ids, seconds, code):
    with store.connect() as db:
        ensure_tables(db)
        for model_id in model_ids:
            db.execute("INSERT OR REPLACE INTO llm_cooldowns VALUES (?, ?, ?)", (model_id, time.time() + seconds, code))


def recordings():
    try:
        data = json.loads(recordings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def find_recording(key):
    matches = [r for r in recordings() if usable(r, key)]
    if not matches:
        return None
    return {k: v for k, v in max(matches, key=lambda r: r["created_at"]).items() if k != "cache_key"}


def usable(r, key):
    """A recording is replayed only when it is complete and well formed."""
    answers = r.get("answers")
    if not (r.get("cache_key") == key and r.get("status") == "ok" and isinstance(r.get("model_id"), str) and isinstance(r.get("created_at"), str)
            and isinstance(answers, list) and len(answers) == len(AGENT_IDS) and all(isinstance(a, dict) for a in answers)):
        return False
    return sorted(str(a.get("agent")) for a in answers) == sorted(AGENT_IDS) and all(a.get("choice") in ("stay", "swerve") for a in answers)


def status():
    with store.connect() as db:
        ensure_tables(db)
        day, minute, _ = usage(db)
    limit, count = daily_limit(), len(recordings())
    return {"configured": bool(openrouter.api_key()), "mode": "live" if openrouter.api_key() else ("replay" if count else "offline"),
            "quota": {"day": utc_day(), "used": day, "limit": limit, "remaining": max(0, limit - day)},
            "minute": {"used": minute, "limit": MINUTE_LIMIT}, "cooldowns": cooldowns(),
            "models": [{"id": m["id"], "name": m["name"]} for m in llm_models()], "recordings": count, "prompt_version": PROMPT_VERSION}


def error_result(dilemma_id, code, message, retry_after=None, requests_used=0, duration_ms=None):
    return {"status": "error", "source": None, "dilemma_id": dilemma_id, "model_id": None, "created_at": now(), "duration_ms": duration_ms,
            "requests_used": requests_used, "answers": [], "error": {"code": code, "message": message, "retry_after": retry_after}}


def context(d):
    return {"agents": [{"id": a["id"], "name": a["name"], "rule": a["rule"], "factors_the_rule_uses": a["uses"], "parameters": agents.PARAMETERS[a["id"]]}
                       for a in agents.AGENTS],
            "dilemma": {side: {**d[side], "text": dilemmas.describe_lane(d[side])} for side in ("stay", "swerve")},
            "stay_means": "the car keeps its lane and hits the stay group", "swerve_means": "the car changes lane and hits the swerve group"}


def schema():
    entry = {"type": "object", "additionalProperties": False, "required": ["choice", "explanation"],
             "properties": {"choice": {"type": "string", "enum": ["stay", "swerve"]}, "explanation": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False, "required": ["answers"],
            "properties": {"answers": {"type": "object", "additionalProperties": False, "required": AGENT_IDS, "properties": {i: entry for i in AGENT_IDS}}}}


def payload_for(model, d):
    """Same shape as openrouter.chat_payload: temperature 0 and structured output when supported, never a priced provider."""
    payload = {"model": model["id"], "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(context(d), sort_keys=True)}],
               "max_tokens": 4096, "provider": {"sort": "latency", "max_price": {"prompt": 0, "completion": 0}}}
    parameters = model.get("supported_parameters", [])
    if "temperature" in parameters:
        payload["temperature"] = 0
    if "structured_outputs" in parameters:
        payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "decision_batch", "strict": True, "schema": schema()}}
    elif "response_format" in parameters:
        payload["response_format"] = {"type": "json_object"}
    if "reasoning" in parameters:
        info = model.get("reasoning", {})
        if info.get("supports_max_tokens"):
            payload["reasoning"] = {"max_tokens": 1024, "exclude": True}
        elif "low" in info.get("supported_efforts", []):
            payload["reasoning"] = {"effort": "low", "exclude": True}
        else:
            payload["reasoning"] = {"enabled": bool(info.get("mandatory")), "exclude": True}
    return payload


def parse(data):
    """Strict parse of one chat completion into {agent_id: Entry}; anything else is invalid_output."""
    try:
        text = str(data["choices"][0]["message"]["content"] or "")
        start = text.index("{")  # skip a code fence or a sentence before the object; the object itself is not altered
        return Batch.model_validate(json.JSONDecoder().raw_decode(text, start)[0]).answers
    except (KeyError, IndexError, TypeError, ValueError, ValidationError):
        raise openrouter.ProviderFailure("invalid_output", "The model did not return valid JSON with a stay/swerve choice and explanation for all four agents. No reference answer was substituted.") from None


def build_answers(d, entries):
    answers = []
    for agent_id in AGENT_IDS:
        ref, entry = agents.RULES[agent_id](d), entries[agent_id]
        answers.append({"agent": agent_id, "choice": entry.choice, "explanation": entry.explanation, "reference_choice": ref["choice"], "reference_tie": ref["tie"],
                        "matches_reference": ref["tie"] or entry.choice == ref["choice"],
                        "audit": evaluation.audit(d, agent_id, {"choice": entry.choice, "explanation": entry.explanation})})
    return answers


def json_tier(entry):
    """Models that can be held to a JSON schema answer most reliably, so they are tried first."""
    parameters = entry.get("supported_parameters", []) if entry else []
    return 0 if "structured_outputs" in parameters else 1 if "response_format" in parameters else 2


def available(model_id, catalog):
    entry = catalog.get(model_id)
    return entry if entry and model_id.endswith(":free") and openrouter.zero_price(entry) else None


def attempt(d, model, entry):
    """One counted HTTP attempt. Returns (result_fields, None) or (None, failure); a limit stop is raised as ('limit', ...)."""
    stop = reserve(model["id"])
    if stop:
        return None, stop
    started = time.perf_counter()
    try:
        data = openrouter.request("v1/chat/completions", payload=payload_for(entry, d), authenticated=True, timeout=60)
        entries = parse(data)
        answers = build_answers(d, entries)
    except openrouter.ProviderFailure as exc:
        return None, exc
    except Exception:  # e.g. RecursionError from a hostile JSON body: the attempt is already counted
        return None, openrouter.ProviderFailure("invalid_output", "The model response could not be processed. No reference answer was substituted.")
    return {"model_id": model["id"], "duration_ms": round((time.perf_counter() - started) * 1000), "answers": answers}, None


def live(d):
    """Try the fallback chain. Returns (result_or_None, last_error, attempts)."""
    try:
        catalog = openrouter.live_catalog()
    except openrouter.ProviderFailure as exc:
        return None, exc.public(), 0
    used, tried, error, blocked = 0, 0, None, set(cooldowns())
    for model in sorted(llm_models(), key=lambda m: (not m.get("recommended"), json_tier(catalog.get(m["id"])))):
        if tried >= MAX_MODELS:
            break
        if model["id"] in blocked:
            continue
        entry = available(model["id"], catalog)
        if not entry:
            set_cooldown(model["id"], openrouter.ProviderFailure("not_free", "not free"))
            error = {"code": "not_verified_free", "message": f"{model['name']} is not currently listed at zero price, so it was skipped. No paid fallback was used.", "retry_after": 600}
            continue
        tried += 1
        done, failure = attempt(d, model, entry)
        if isinstance(failure, tuple):
            return None, {"code": failure[0], "message": failure[1], "retry_after": failure[2]}, used
        used += 1
        if done:
            return {**done, "requests_used": used}, None, used
        set_cooldown(model["id"], failure)
        error = failure.public()
        if failure.code in ACCOUNT_WIDE:
            cool([m["id"] for m in llm_models()], 600, failure.code)
            break
    return None, error or {"code": "no_model_available", "message": "Every language model is cooling down after recent failures.", "retry_after": min(
        [max(1, math.ceil(datetime.fromisoformat(v).timestamp() - time.time())) for v in cooldowns().values()] or [60])}, used


def current(d, result):
    """Re-check a saved or recorded result with today's reference rules and audit. Choices and explanations are never changed."""
    if result.get("status") != "ok":
        return result
    entries = {a["agent"]: Entry.model_construct(choice=a["choice"], explanation=a["explanation"]) for a in result["answers"]}
    return {**result, "answers": build_answers(d, entries)}


def stored(key, newest_only=True, limit=50):
    with store.connect() as db:
        ensure_tables(db)
        rows = db.execute("SELECT body FROM llm_results WHERE cache_key = ? ORDER BY created DESC, id DESC LIMIT ?", (key, 1 if newest_only else limit)).fetchall()
    return [{**json.loads(body), "source": "cache", "requests_used": 0} for (body,) in rows]


def save(key, result):
    with store.connect() as db:
        ensure_tables(db)
        db.execute("INSERT INTO llm_results (cache_key, dilemma_id, created, body) VALUES (?, ?, ?, ?)", (key, result["dilemma_id"], time.time(), json.dumps(result)))


def run(dilemma_id, repeat=False):
    """Run (or recall) the batched language-model answers for one dilemma. Returns None for an unknown dilemma."""
    d = dilemmas.get(dilemma_id)
    if not d:
        return None
    key = cache_key(d)
    if not repeat and (hit := stored(key)):
        return current(d, hit[0])
    if not _busy.acquire(blocking=False):
        return error_result(dilemma_id, "busy", "Another language-model run is in progress. Wait for it to finish.", 10)
    try:
        if not repeat and (hit := stored(key)):  # another run may have finished while we waited for the cache check
            return current(d, hit[0])
        started, error, used, result = time.perf_counter(), None, 0, None
        if not openrouter.api_key():
            error = {"code": "missing_key", "message": "No OpenRouter key is configured on the server.", "retry_after": None}
        else:
            result, error, used = live(d)
        if result:
            result = {"status": "ok", "source": "live", "dilemma_id": dilemma_id, "model_id": result["model_id"], "created_at": now(),
                      "duration_ms": result["duration_ms"], "requests_used": used, "answers": result["answers"], "error": None}
            save(key, result)
            return result
        if error["code"] != "minute_limit":
            if recorded := find_recording(key):
                return {**current(d, recorded), "source": "recording", "requests_used": used, "fallback": {"code": error["code"], "message": error["message"]}}
        return error_result(dilemma_id, error["code"], error["message"], error["retry_after"], used, round((time.perf_counter() - started) * 1000) if used else None)
    finally:
        _busy.release()


def results(dilemma_id):
    """Stored results for a dilemma, newest first; recordings only when nothing is stored. None for an unknown dilemma."""
    d = dilemmas.get(dilemma_id)
    if not d:
        return None
    key = cache_key(d)
    found = stored(key, newest_only=False)
    if not found:
        found = [{k: v for k, v in r.items() if k != "cache_key"} for r in sorted(
            (r for r in recordings() if usable(r, key)), key=lambda r: r["created_at"], reverse=True)]
        found = [{**r, "source": "recording"} for r in found]
    return [current(d, r) for r in found]


CHECKS = ["decision_matches_rule", "names_its_choice", "cites_influential_factors", "cites_no_ignored_factor", "numbers_traceable"]


def recorded_summary():
    """Per-agent agreement and audit results over the committed recordings, re-checked with today's rules. No network."""
    rows = [(r, current(dilemmas.get(r["dilemma_id"]), r)) for r in recordings() if dilemmas.get(r["dilemma_id"]) and usable(r, cache_key(dilemmas.get(r["dilemma_id"])))]
    summary = {a: {"answers": 0, "matches_reference": 0, "audit_passed": 0, **{c: 0 for c in CHECKS}} for a in AGENT_IDS}
    for _, result in rows:
        for answer in result["answers"]:
            s = summary[answer["agent"]]
            s["answers"] += 1
            s["matches_reference"] += answer["matches_reference"]
            s["audit_passed"] += answer["audit"]["passed"]
            for c in CHECKS:
                s[c] += answer["audit"]["checks"][c]
    return {"recordings": len(rows), "models": sorted({r["model_id"] for r, _ in rows}), "dilemmas": sorted({r["dilemma_id"] for r, _ in rows}),
            "recorded": sorted({r["created_at"][:10] for r, _ in rows}), "summary": summary}
