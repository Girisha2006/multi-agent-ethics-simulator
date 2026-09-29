# OpenRouter model comparison

The dashboard's **Model comparison** tab adds independent remote model agents to the three local ethical reference policies. Pick a framework, select models, and compare them at the current disclosure state.

The same model can play any of the three framework roles. Model count, ethical-framework count, and question-strategy count are different dimensions. Each selected model receives its own request and cannot see other agents' responses.

## Configuration

The server reads `OPENROUTER_API_KEY` from its environment or the project-root `.env` file:

```dotenv
OPENROUTER_API_KEY=your_key_here
```

The user's key was copied from `env.txt` into `.env` during setup. Both files are ignored by version control and are outside the static directory. The key is never returned by the API, saved in a model record, or sent to the browser. [.env.example](.env.example) contains only the setting name.

The application uses the existing HTTPX dependency. No OpenAI SDK, separate TypeSafe SDK, model download, or GPU is required.

## Available model options

Catalog checked on 27 September 2026. The server checks current zero pricing before a free call and sets provider maximum prompt/completion prices to zero. A provider may still reject, throttle, or withdraw an endpoint.

| Model | OpenRouter ID | Current role |
|---|---|---|
| Qwen3.8 27B | `qwen/qwen3.8-27b:free` | Free reasoning comparison; rate-limited during live checks |
| Nemotron 3.5 Lightning | `nvidia/nemotron-3.5-lightning:free` | Free speed-oriented comparison; malformed output observed |
| Gemma 4 26B A4B | `google/gemma-4-26b-a4b-it:free` | Free Google model, distinct from Gemini; rate-limited during live checks |
| **Nemotron 3 Super** | `nvidia/nemotron-3-super-120b-a12b:free` | Default starting model; one successful live relay-case test |
| Nemotron 3 Ultra | `nvidia/nemotron-3-ultra-550b-a55b:free` | Larger free reasoning comparison; provider error observed |
| Inkling Small | `thinkingmachines/inkling-small:free` | Free endpoint restricted by its provider to agentic harnesses; access denied during live checks |
| TypeSafe Jev 1.13 | `typesafe/jev-1.13` | Optional paid decision-only comparison |

**Gemini and OpenAI:** no zero-priced text endpoint from these families appeared in the live OpenRouter catalog. The UI reports this explicitly. It automatically discovers an eligible `:free` endpoint from these families if one appears later and verifies its pricing before calling it. A free consumer chat plan or another provider's free tier is not evidence of free OpenRouter API access.

Sources: [live catalog](https://openrouter.ai/api/v1/models), [Qwen](https://openrouter.ai/qwen/qwen3.8-27b:free), [Nemotron Lightning](https://openrouter.ai/nvidia/nemotron-3.5-lightning:free), [Gemma](https://openrouter.ai/google/gemma-4-26b-a4b-it:free), [Jev](https://openrouter.ai/typesafe/jev-1.13).

## Jev is a separate kind of model

Jev returns typed choices and probability distributions. It does not generate explanations. Its adapter uses `POST /api/alpha/decisions`, rather than pretending it is a chat-completion model.

The model page currently lists $0.042 per million input tokens and $0 output-token cost. It is not a fully free model. Selecting the explicitly labeled **Include paid Jev** checkbox opts into that request; the server also requires `allow_paid_jev: true`. It is deselected by default, and no paid live probe was performed.

The same evidence packet is supplied to Jev. It answers a decision question and, when an affordable fact exists, a next-question choice. Returned probabilities are displayed as provider outputs, not validated ethical confidence.

Sources: [Jev documentation](https://openrouter.ai/docs/guides/community/jev), [Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request).

## Quota and response time

OpenRouter generally permits 50 free requests per day and 20 per minute, with a higher daily allowance after a qualifying credit purchase. The authenticated `GET /api/v1/key` response is used to show this account's actual daily counter. During setup it reported a 50-request allowance. Provider capacity and data-policy requirements are additional constraints.

Additional accounts or keys are not a supported way to multiply the allowance: OpenRouter's documentation explicitly says they do not increase its rate limits. This integration uses one configured key.

The app conserves quota through:

- One model selected by default, with explicit execution.
- Reuse of the same model/framework/evidence/prompt-version attempt within a run.
- Separate **New attempt** control for a real additional request, including retries.
- At most two simultaneous requests and a local 18-request/minute safeguard.
- No automatic model fallback, paid fallback, retry loop, or calls on every fact reveal.
- A 60-second absolute request deadline, including response-body completion.

Saved attempts are not counted as independent repetitions. A timeout may leave work already submitted to an upstream provider; local cancellation cannot guarantee that the provider discards it.

Source: [OpenRouter limits](https://openrouter.ai/docs/api_reference/limits).

## What each model sees and how it is evaluated

The input is built from an explicit allowlist:

- The selected ethical rule and physical risk equations.
- Known fixed facts, available hidden-fact values, and disclosure costs.
- Only the observations actually revealed during the budgeted investigation.
- The remaining credits and the stipulated independent equal-world prior.

It excludes the secret world, debrief, reference answers, other model outputs, and scenario descriptions that announce the intended demonstration result. Even after opening the debrief, this comparison mode continues to test the original budgeted evidence.

The model returns `decision`, `next_question`, and a short `explanation`. Valid extra metadata is retained in the raw output but cannot change the evaluated fields. Invalid JSON, missing/invalid fields, truncation, and provider errors remain failures. No local answer repairs or reference substitutions are made.

The external check reports whether the decision is supported in every remaining world under the selected reference rule. It flags unaffordable or nonexistent fact suggestions and displays the reference planner's next question separately. It does not establish moral correctness or independently grade explanation quality.

Each journal entry contains the evidence snapshot, prompt version, requested/returned model, provider, request settings, final output, timing, token usage, reported cost, reference check, and any failure. Provider reasoning-only fields are not requested for display; failed final-content responses can be retained for debugging.

The UI hides prior-state outputs from the current results area and keeps them under history. Replay hides model results entirely, preventing later outputs from appearing in an earlier evidence frame.

## Live validation record

One successful relay-case call to **Nemotron 3 Super**, prompt version `ethical-evidence-3`, returned:

- Decision: `conditional`.
- Next question: `relay_a`.
- Correctly described why both relays are needed and the two diversion outcomes.
- Full API response time: **15,887 ms**.
- Reported usage: 738 prompt tokens, 1,119 completion tokens.
- Reported cost: **$0**.

The decision and suggested question matched the reference. This is a single smoke test, not an accuracy or latency benchmark. Other live probes encountered rate limits, denied access, malformed output, truncation, and a provider error. Those failures are preserved.

Automated validation includes adapter/API tests with mocked upstream responses, plus a headed browser workflow with explicitly labeled fixture outputs. Jev's request/response contract is tested with fixtures; paid live execution remains untested.

To run a small explicit free-only live probe:

```powershell
conda run --no-capture-output -n gpu_env python tools/check_openrouter.py --models nvidia/nemotron-3-super-120b-a12b:free
```

This consumes a real free request and stores a new run. The tool never calls Jev or any paid model.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/models` | Curated model options and verified live free pricing; use `?refresh=true` to refresh |
| `GET /api/openrouter/status?check_quota=true` | Key presence and sanitized account free quota |
| `GET /api/runs/{id}/comparisons` | Saved attempts and the current evidence-state identifier |
| `POST /api/runs/{id}/comparisons` | Execute or reuse one model/framework attempt |
| `GET /api/runs/{id}/comparisons/export` | Model Markdown export; `?format=json` includes detailed reproducibility fields |

Example request:

```json
{
  "model_id": "nvidia/nemotron-3-super-120b-a12b:free",
  "framework_id": "utility",
  "evidence_step": 0,
  "repeat": false,
  "allow_paid_jev": false
}
```

The evidence step must match the current run; a stale request is rejected. Model attempts live in a separate SQLite table and never rewrite the disclosure journal.
