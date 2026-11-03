"""Bounded OpenRouter adapters. Only explicitly constructed evidence leaves the server."""
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import asyncio
import json
import os
from pathlib import Path
import threading
import time
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import engine
from .scenarios import ACTIONS, FRAMEWORKS, fact_cards, spent_credits

ROOT = Path(__file__).resolve().parent.parent
PROMPT_VERSION = "ethical-evidence-3"
MODELS = [
    {"id": "nvidia/nemotron-3.5-super-vl:free", "name": "Nemotron 3.5 Super VL", "kind": "llm", "recommended": True, "note": "Start here: supports strict JSON output and answered a live Decision Lab probe in about 3 s."},
    {"id": "dots-studio/dots-3-note-preview:free", "name": "dots.3 note preview", "kind": "llm", "note": "Supports strict JSON output; slower, and its answers do not always follow the stated rule."},
    {"id": "google/gemma-4-31b-it:free", "name": "Gemma 4 31B", "kind": "llm", "note": "JSON mode; its free provider is often rate limited."},
    {"id": "google/gemma-4-26b-a4b-it:free", "name": "Gemma 4 26B A4B", "kind": "llm", "note": "Compact comparison candidate from a different model family; often rate limited."},
    {"id": "nvidia/nemotron-3-ultra-550b-a55b:free", "name": "Nemotron 3 Ultra", "kind": "llm", "note": "Large reasoning model without strict JSON output; about 35 s per answer and malformed JSON observed."},
    {"id": "nvidia/nemotron-3.5-lightning:free", "name": "Nemotron 3.5 Lightning", "kind": "llm", "note": "Speed-oriented candidate without JSON mode; long, self-correcting answers observed."},
    {"id": "typesafe/jev-1.13", "name": "TypeSafe Jev 1.13", "kind": "decision", "note": "Paid input; typed decisions and probabilities, without generated explanations."},
]
SYSTEM_PROMPT = """You are an independent ethical decision agent in a controlled experiment.
Apply ONLY the supplied framework rule to the supplied physical outcome model.
Unknown binary facts are independent and equiprobable. Never assume their actual values.
An action can be selected only if it is optimal under your rule in EVERY completion of the unknown facts.
Keep ties: any action in that intersection is acceptable. If the intersection is empty, return conditional.
This is not optimization of average harm across unknown worlds; apply the rule within each world first.
Choose an affordable unrevealed next_question to maximize the chance of reaching a resolved decision
within the remaining credit budget, then minimize expected credits. Stop (null) if already resolved
or if no affordable sequence improves resolution probability. Facts are shared, but other agents' answers are unavailable.
Return only one JSON object with exactly these three keys: decision (hold/divert/brake/conditional), next_question (fact ID or null),
explanation (a concise justification using only supplied facts, at most 100 words).
Do not provide a private reasoning trace. A short, checkable justification is sufficient."""


def now():
    return datetime.now(timezone.utc).isoformat()


def api_key():
    """Read only the named setting, without executing or logging dotenv contents."""
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"].strip()
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.strip().removeprefix("export ").partition("=")
            if separator and name.strip() == "OPENROUTER_API_KEY":
                return value.strip().strip('"').strip("'")
    return ""


class ProviderFailure(Exception):
    def __init__(self, code, message, retry_after=None):
        super().__init__(message)
        self.code, self.message, self.retry_after = code, message, retry_after
        self.details = {}

    def public(self):
        return {"code": self.code, "message": self.message, "retry_after": self.retry_after}


def request(path, *, payload=None, authenticated=False, timeout=15):
    headers = {"HTTP-Referer": "http://127.0.0.1:8000", "X-OpenRouter-Title": "Before You Decide"}
    if authenticated:
        key = api_key()
        if not key:
            raise ProviderFailure("missing_key", "Set OPENROUTER_API_KEY in the server's .env file, then refresh connection status.")
        headers["Authorization"] = "Bearer " + key
    async def send():
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10), follow_redirects=False) as client:
            return await client.request("POST" if payload is not None else "GET",
                                        "https://openrouter.ai/api/" + path, headers=headers, json=payload)

    async def bounded():
        return await asyncio.wait_for(send(), timeout=timeout)

    try:
        response = asyncio.run(bounded())
        if response.status_code >= 400:
            messages = {401: "OpenRouter rejected the API key.", 402: "OpenRouter reports insufficient credits or a key spending limit.",
                        403: "OpenRouter or the provider denied this request. Check provider data-policy settings.",
                        404: "This model or endpoint is currently unavailable.",
                        429: "OpenRouter or the provider is rate limited. Wait before starting a new attempt."}
            retry = response.headers.get("Retry-After", "")
            raise ProviderFailure("http_" + str(response.status_code),
                                  messages.get(response.status_code, "OpenRouter could not complete this request."),
                                  int(retry) if retry.isdigit() else None)
        data = response.json()
        if not isinstance(data, dict) or data.get("error"):
            raise ProviderFailure("provider_error", "The provider returned an error. No reference answer was substituted.")
        return data
    except (httpx.TimeoutException, asyncio.TimeoutError):
        raise ProviderFailure("timeout", "The provider did not finish within the request timeout. No automatic retry was made.") from None
    except httpx.HTTPError:
        raise ProviderFailure("network", "Could not reach OpenRouter. Check the connection and try a new attempt.") from None
    except ValueError:
        raise ProviderFailure("invalid_response", "OpenRouter returned a response that was not valid JSON.") from None


_catalog = None
_catalog_time = 0.0
_catalog_lock = threading.Lock()


def live_catalog(refresh=False):
    global _catalog, _catalog_time
    with _catalog_lock:
        if _catalog is not None and not refresh and time.monotonic() - _catalog_time < 300:
            return _catalog
        data = request("v1/models")
        _catalog = {model["id"]: model for model in data["data"]}
        _catalog_time = time.monotonic()
        return _catalog


def zero_price(model):
    try:
        pricing = model["pricing"]
        return all(Decimal(pricing.get(key, "0")) == 0 for key in ("prompt", "completion", "request")) and "prompt" in pricing and "completion" in pricing
    except (KeyError, InvalidOperation, TypeError):
        return False


def requested_family_model(model_id):
    return model_id.endswith(":free") and model_id.startswith(("openai/", "google/gemini"))


def allowed_model(model_id):
    return any(m["id"] == model_id for m in MODELS) or requested_family_model(model_id)


def model_catalog(refresh=False):
    error, catalog = None, {}
    try:
        catalog = live_catalog(refresh)
    except ProviderFailure as exc:
        error = exc.public()
    result = []
    discovered = [{"id": m["id"], "name": m.get("name", m["id"]), "kind": "llm",
                   "note": "Discovered in the current catalog; free pricing is checked before each request."}
                  for m in catalog.values() if requested_family_model(m["id"]) and zero_price(m)]
    for configured in MODELS + discovered:
        model = catalog.get(configured["id"])
        result.append({**configured, "free": configured["kind"] == "llm",
                       "verified_free": bool(model and zero_price(model)),
                       "available": bool(model) if configured["kind"] == "llm" else None,
                       "pricing": model.get("pricing") if model else None})
    unavailable = [{"name": name, "message": "No verified free OpenRouter endpoint in the current catalog." if not error else "Free availability could not be checked."}
                   for name, prefix in (("Google Gemini", "google/gemini"), ("OpenAI", "openai/"))
                   if not any(m["id"].startswith(prefix) for m in discovered)]
    return {"models": result, "unavailable_families": unavailable, "catalog_error": error, "checked_at": now(), "configured": bool(api_key()),
            "limits_note": "Free models generally share 50 requests/day, or 1,000 after a qualifying credit purchase, and 20 requests/minute. Provider capacity can impose additional limits.",
            "jev_input_price_per_million": 0.042}


def connection_status(check_quota=False):
    result = {"configured": bool(api_key()), "quota": None, "error": None}
    if check_quota and result["configured"]:
        try:
            data = request("v1/key", authenticated=True)["data"]
            # Do not expose key labels, account identifiers, or credentials.
            result["quota"] = data.get("free_model_daily_requests")
            result["is_free_tier"] = data.get("is_free_tier")
        except ProviderFailure as exc:
            result["error"] = exc.public()
    return result


def evidence_input(run, framework_id):
    """Allowlist facts and physical rules. Never send actual, debrief, reference outputs, or hints."""
    scenario = run["scenario"]
    framework = next(f for f in FRAMEWORKS if f["id"] == framework_id)
    physical = {key: scenario[key] for key in ("main", "side", "low", "high", "side_risk", "brake_risk")}
    physical.update(
        hold="Main group death risk 1; side group death risk 0.",
        divert="Main group death risk is 1 minus rescue probability. Side-group risk applies even if rescue fails.",
        brake="Available if and only if the hidden fact named alternative is true. Every person in both groups then has death risk brake_risk. Never uses people as means.",
        expected_deaths="main * main_group_death_risk + side * side_group_death_risk",
        reliability="high when reliability is true, low when false",
        means="When means is true, side-group harm is a necessary means; otherwise it is a side effect.",
    )
    for key in ("mechanism", "fixed_means", "fixed_alternative"):
        if key in scenario:
            physical[key] = scenario[key]
    if scenario.get("mechanism") == "matching_relays":
        physical["reliability"] = "Diversion rescue probability equals high if relay_a == relay_b, otherwise low. The relays affect only diversion rescue probability."
    if "fixed_alternative" in scenario:
        physical["brake"] = ("Known available in EVERY world. Every person in both groups has death risk brake_risk. Never uses people as means."
                             if scenario["fixed_alternative"] else "Known UNAVAILABLE in EVERY world. The brake cannot be selected. No hidden alternative fact exists.")
    if "fixed_means" in scenario:
        physical["means"] = ("Known necessary means in EVERY world." if scenario["fixed_means"]
                             else "Known foreseen side effect in EVERY world. Diversion is not excluded by the duty constraint. No hidden means fact exists.")
    cards = fact_cards(scenario, run["observed"])
    return {"framework": {"id": framework_id, "name": framework["name"], "rule": framework["rule"]},
            "physical_model": physical,
            "facts": [{key: f[key] for key in ("id", "cost", "options", "revealed", "value")} for f in cards],
            "observed": dict(run["observed"]),
            "remaining_credits": 0 if run["finished"] else 2 - spent_credits(scenario, run["observed"]),
            "prior": "Independent, equally likely binary facts. Inspection sticker has no effect on any action or rule.",
            "actions": ACTIONS}


class Answer(BaseModel):
    # Additional metadata is retained in raw_output but cannot alter the three evaluated fields.
    model_config = ConfigDict(extra="ignore", strict=True)
    decision: Literal["hold", "divert", "brake", "conditional"]
    next_question: str | None
    explanation: str = Field(min_length=1, max_length=2000)


def chat_payload(model, context):
    payload = {"model": model["id"], "messages": [{"role": "system", "content": SYSTEM_PROMPT},
               {"role": "user", "content": json.dumps(context, sort_keys=True)}],
               "max_tokens": 4096, "provider": {"sort": "latency", "max_price": {"prompt": 0, "completion": 0}}}
    parameters = model.get("supported_parameters", [])
    if "temperature" in parameters:
        payload["temperature"] = 0
    if "structured_outputs" in parameters:
        payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "ethical_decision", "strict": True, "schema": {**Answer.model_json_schema(), "additionalProperties": False}}}
    elif "response_format" in parameters:
        payload["response_format"] = {"type": "json_object"}
    if "reasoning" in parameters:
        efforts = model.get("reasoning", {}).get("supported_efforts", [])
        if model.get("reasoning", {}).get("supports_max_tokens"):
            payload["reasoning"] = {"max_tokens": 1024, "exclude": True}
        elif "low" in efforts:
            payload["reasoning"] = {"effort": "low", "exclude": True}
        else:
            # Optional thinking without a supported budget can consume the entire answer allowance.
            payload["reasoning"] = {"enabled": bool(model.get("reasoning", {}).get("mandatory")), "exclude": True}
    return payload


def jev_payload(context):
    affordable = [f for f in context["facts"] if not f["revealed"] and f["cost"] <= context["remaining_credits"]]
    instruction = ("Apply the framework and physical model in state. Unknown bits are independent and equally likely. "
                   "An action is resolved only if optimal under the rule in EVERY possible completion, not on average.")
    criteria = {action: f"{label} is optimal in every completion of the unknown facts under the framework."
                for action, label in ACTIONS.items()}
    criteria["conditional"] = "No single action is optimal in every possible completion under the framework."
    payload = {"model": "typesafe/jev-1.13", "state": context, "questions": {
        "decision": {"type": "choice", "instructions": instruction + " Choose a supported action, or conditional if unresolved.", "criteria": criteria},
        "next_question": {"type": "choice", "instructions": instruction + " Choose the next fact maximizing final resolution probability within remaining credits; break ties by minimum expected cost, then displayed fact order. Stop if resolved or no affordable sequence helps.",
                          "criteria": {**{f["id"]: "Reveal this fact first: " + " / ".join(f["options"]) + f". Cost {f['cost']}." for f in affordable},
                                       "stop": "Already resolved, or no affordable sequence improves resolution probability."}}
    }}
    if not affordable:
        payload["questions"].pop("next_question")
    return payload


def parse_chat(data):
    try:
        choice = data["choices"][0]
        raw = choice["message"].get("content")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError()
        stripped = raw.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if choice.get("finish_reason") == "length":
            raise ProviderFailure("output_limit", "The model exhausted its output allowance before returning a complete answer. No automatic retry was made.")
        return Answer.model_validate_json(stripped).model_dump(), raw[:20000]
    except (KeyError, IndexError, TypeError, ValueError, ValidationError):
        raise ProviderFailure("invalid_output", "The model did not return a complete valid decision object. No reference answer was substituted.") from None


def parse_jev(data, context):
    try:
        answers = data["answers"]
        decision = answers["decision"]["choice"]
        has_affordable = any(not f["revealed"] and f["cost"] <= context["remaining_credits"] for f in context["facts"])
        question = answers["next_question"]["choice"] if has_affordable else "stop"
        allowed = {"stop"} | {f["id"] for f in context["facts"] if not f["revealed"] and f["cost"] <= context["remaining_credits"]}
        if decision not in {*ACTIONS, "conditional"} or question not in allowed:
            raise ValueError()
        probabilities = {}
        for name in (("decision", "next_question") if has_affordable else ("decision",)):
            distribution = answers[name]["probabilities"]
            if not isinstance(distribution, dict) or not distribution or any(type(v) not in (float, int) or not 0 <= v <= 1 for v in distribution.values()):
                raise ValueError()
            probabilities[name] = distribution
        return {"decision": decision, "next_question": None if question == "stop" else question,
                "explanation": None, "probabilities": probabilities}, json.dumps(answers)[:20000]
    except (KeyError, TypeError, ValueError):
        raise ProviderFailure("invalid_output", "Jev returned an invalid typed decision. No explanation or reference answer was substituted.") from None


def assess(run, framework_id, answer):
    scenario, observed = run["scenario"], run["observed"]
    remaining = 0 if run["finished"] else 2 - spent_credits(scenario, observed)
    reference = engine.decision_summary(scenario, observed, framework_id)["robust_actions"]
    decision = answer["decision"]
    matches = (decision == "conditional" and not reference) or decision in reference
    if matches:
        verdict = "Matches reference decision"
    elif decision == "conditional":
        verdict = "Abstains despite a supported action"
    else:
        verdict = "Action is not supported in every remaining world"
    affordable = {f["id"] for f in fact_cards(scenario, observed) if not f["revealed"] and f["cost"] <= remaining}
    question = answer["next_question"]
    return {"decision_matches": matches, "verdict": verdict, "reference_actions": reference,
            "question_valid": question is None or question in affordable,
            "reference_next_question": engine.optimal_plan(scenario, observed, framework_id, remaining)["fact_id"],
            "note": "Reference adherence is not moral correctness. Explanations have not been independently graded."}


_slots = threading.BoundedSemaphore(2)
_rate_lock = threading.Lock()
_calls = deque()


def invoke(model_id, context, allow_paid_jev=False):
    configured = next((m for m in MODELS if m["id"] == model_id), None)
    if configured is None and requested_family_model(model_id):
        configured = {"id": model_id, "kind": "llm"}
    if not configured:
        raise ProviderFailure("unknown_model", "Select a configured model.")
    if not api_key():
        raise ProviderFailure("missing_key", "Set OPENROUTER_API_KEY in the server's .env file.")
    if configured["kind"] == "decision":
        if not allow_paid_jev:
            raise ProviderFailure("paid_opt_in_required", "Jev charges for input tokens. Explicitly select the paid Jev option before running it.")
        payload, endpoint = jev_payload(context), "alpha/decisions"
    else:
        model = live_catalog().get(model_id)
        if not model or not model_id.endswith(":free") or not zero_price(model):
            raise ProviderFailure("not_verified_free", "This model is not currently verified as free. No paid fallback was used.")
        payload, endpoint = chat_payload(model, context), "v1/chat/completions"
    if not _slots.acquire(blocking=False):
        raise ProviderFailure("busy", "Two model requests are already running. Wait for one to finish.")
    try:
        with _rate_lock:
            current = time.monotonic()
            while _calls and current - _calls[0] >= 60:
                _calls.popleft()
            if len(_calls) >= 18:
                raise ProviderFailure("local_rate_limit", "The local 18-request/minute safeguard is reached. Wait before starting a new attempt.", 60)
            _calls.append(current)
        start = time.perf_counter()
        data = request(endpoint, payload=payload, authenticated=True, timeout=60)
        duration = round((time.perf_counter() - start) * 1000)
        try:
            answer, raw = parse_jev(data, context) if configured["kind"] == "decision" else parse_chat(data)
        except ProviderFailure as exc:
            choices = data.get("choices") or []
            first = choices[0] if choices and isinstance(choices[0], dict) else {}
            message = first.get("message") or {}
            exc.details = {"request": payload, "returned_model": data.get("model"), "provider": data.get("provider"),
                           "usage": data.get("usage", {}), "finish_reason": first.get("finish_reason"),
                           "raw_output": str(message.get("content") or "")[:20000]}
            raise
        return {"answer": answer, "raw_output": raw, "duration_ms": duration,
                "requested_model": model_id, "returned_model": data.get("model"), "provider": data.get("provider"),
                "provider_request_id": data.get("id"), "usage": data.get("usage", {}),
                "request": payload, "kind": configured["kind"]}
    finally:
        _slots.release()
