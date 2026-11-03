# LLM agents (optional)

Both labs can compare free OpenRouter language models with their deterministic reference agents. **Nothing in either lab
needs a model**: every reference result, test and evaluation number runs offline. LLM results are an add-on, always labelled
with their source, and never substituted by reference answers.

## Configuration

The server reads `OPENROUTER_API_KEY` from its environment or from a project-root `.env` file (git-ignored):

```dotenv
OPENROUTER_API_KEY=your_key_here
```

The key is never returned by the API, saved in a result or recording, or sent to the browser. [.env.example](../.env.example)
contains only the setting name.

| Variable | Default | Effect |
|---|---|---|
| `OPENROUTER_API_KEY` | unset | Enables live calls. Without it the Decision Lab replays recordings only. |
| `DECISION_LLM_DAILY_LIMIT` | 45 | Local cap on Decision Lab chat requests per UTC day, kept below the provider's ~50. |
| `DECISION_RECORDINGS` | `recordings/decision_llm.json` | Recording file used for replay. |
| `ETHICS_DB` | `data/runs.sqlite3` | SQLite file holding the quota counter, cooldowns, cache and results. |

## Decision Lab: four agents in one request

Free OpenRouter models allow roughly **50 requests per day and 20 per minute**, and individual free endpoints often return
429 or disappear. The Decision Lab is built around that limit (`ethics_lab/decision/llm.py`). Accounts that have bought credits get 1000 free
requests per day (the project key reported this on 3 November 2026); the local cap stays at 45 unless
`DECISION_LLM_DAILY_LIMIT` is raised.



| Measure | How it works |
|---|---|
| One request per dilemma | The model plays all four agents at once and returns `{"answers": {agent_id: {choice, explanation}}}`. A dilemma costs 1 request, not 4. |
| Counted before sending | Every HTTP attempt is written to SQLite *before* the request goes out. The daily cap (45) and a sliding 60-second window (15) are read from that table, so they survive restarts. |
| Cache | Successful results are cached by `sha256(prompt version, agent parameters, stay lane, swerve lane)`. Clicking *Run* again costs nothing unless **Repeat** is ticked; Repeat resets after each run. |
| Fallback chain | Up to 3 models per run, recommended first, and only models the live catalog lists at zero price. Never a paid fallback. |
| Cooldowns | A failing model is benched: 429 → `Retry-After` (capped at 3600 s) or 60 s; unavailable or not free → 600 s; other errors → 120 s. A 401/402 is account-wide: the chain stops and every model cools for 600 s. A 403 only benches that model, because it usually means one provider refuses the request. Stored in SQLite. |
| Replay | With no key, quota used up, or every model failing, the newest matching **real** recording is replayed and labelled `source: "recording"` with its original model and date. If live calls were tried first, the result carries `fallback` with the reason and `requests_used` shows what was spent. |
| One at a time | A non-blocking lock allows a single live run; a second click gets a `busy` error instead of a second request. |
| Model order | The recommended model first, then models that support a strict JSON schema, then JSON mode, then the rest. |
| Strict output | The first JSON object in the reply is read (a code fence or a sentence around it is skipped). It must hold exactly the four agent ids, `stay`/`swerve`, and explanations of 1–150 words (the prompt asks for 80). Anything else, including unbalanced JSON, is an `invalid_output` failure. No repairs. |

Each answer is checked against the deterministic agent (`matches_reference`; either lane counts on a reference tie) and
put through the same five-item explanation audit as the reference explanations (`docs/decision-lab.md`, Evaluation §2).
Saved and recorded results are re-checked with the current rules and audit whenever they are shown; their text is never
changed. `make evaluate` summarises the committed recordings in `results/decision_lab.md` §5 and `results/decision_llm.json`.

### Recording real runs for the demo

Recordings make the LLM tab useful offline and on days when the free quota is gone. The repository includes 8 real runs
of the base dilemmas (Nemotron 3.5 Super VL, 3 November 2026). They must come from real runs; never
write or edit them by hand.

```bash
OPENROUTER_API_KEY=... .venv/bin/python tools/record_llm.py                  # the 8 base dilemmas (8 requests)
OPENROUTER_API_KEY=... .venv/bin/python tools/record_llm.py crossing brakes  # chosen dilemmas
```

The tool skips dilemmas already recorded, stops when the quota or key is unavailable, and prints a summary. See
[recordings/README.md](../recordings/README.md) for the file format. Recording all 99 dilemmas takes about three days of
free quota; the 8 base dilemmas fit comfortably in one.

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/decision/llm/status` | Mode, key present, daily and per-minute usage, cooldowns, recording count |
| `POST /api/decision/llm/run` | `{"dilemma_id": "crossing", "repeat": false}` → one `RunResult` (`status`, `source`, `model_id`, `answers`, `error`, `requests_used`, …) |
| `GET /api/decision/llm/results?dilemma_id=crossing` | Stored results for a dilemma, newest first |

Errors are returned as a `RunResult` with `status: "error"`, an `error.code` and `retry_after` when known. Local codes:
`missing_key`, `quota_exhausted`, `minute_limit`, `busy`, `no_model_available`, `not_verified_free`, `invalid_output`.
Provider codes are passed through: `http_429`, `http_404`, `http_401`/`402`/`403`, `timeout`, `network`,
`provider_error`, `invalid_response`.

The page labels each result *Live*, *Saved run* (from the cache, free) or *Recorded on …*, and shows how many requests the
last run used.

## Before You Decide: model comparison

The original lab's **Model comparison** tab adds independent remote model agents to the three local ethical reference
policies. Pick a framework, select models, and compare them at the current disclosure state.

The same model can play any of the three framework roles. Model count, ethical-framework count, and question-strategy count
are different dimensions. Each selected model receives its own request and cannot see other agents' responses.

### Available model options

Both labs use the same model list (`openrouter.MODELS`). Catalog and Decision Lab probes checked on 3 November 2026; free
endpoints change often, and the server re-checks zero pricing before every call. Qwen3.8 27B and Nemotron 3 Super, used in
September, have since left the free catalog.

| Model | OpenRouter ID | JSON support | Decision Lab probe (3 Nov 2026) |
|---|---|---|---|
| **Nemotron 3.5 Super VL** | `nvidia/nemotron-3.5-super-vl:free` | strict schema | Default. Valid answers in 2–7 s; made the 8 committed recordings |
| dots.3 note preview | `dots-studio/dots-3-note-preview:free` | strict schema | Valid JSON in 11 s; one choice contradicted its own calculation |
| Gemma 4 31B | `google/gemma-4-31b-it:free` | JSON mode | Rate limited (429) by its provider |
| Gemma 4 26B A4B | `google/gemma-4-26b-a4b-it:free` | JSON mode | Rate limited (429) by its provider |
| Nemotron 3 Ultra | `nvidia/nemotron-3-ultra-550b-a55b:free` | none | About 35 s; JSON missing a closing brace (invalid) |
| Nemotron 3.5 Lightning | `nvidia/nemotron-3.5-lightning:free` | none | Long self-correcting explanations over the word limit (invalid) |
| TypeSafe Jev 1.13 | `typesafe/jev-1.13` | typed | Before You Decide only; paid, opt-in |

Inkling Small was removed: its provider restricts the free endpoint to agentic harnesses and returned 403.

**Gemini and OpenAI:** no zero-priced text endpoint from these families appeared in the live OpenRouter catalog. The UI reports this explicitly. It automatically discovers an eligible `:free` endpoint from these families if one appears later and verifies its pricing before calling it. A free consumer chat plan or another provider's free tier is not evidence of free OpenRouter API access.

Sources: [live catalog](https://openrouter.ai/api/v1/models), [Nemotron Lightning](https://openrouter.ai/nvidia/nemotron-3.5-lightning:free), [Gemma](https://openrouter.ai/google/gemma-4-26b-a4b-it:free), [Jev](https://openrouter.ai/typesafe/jev-1.13).

### Jev is a separate kind of model

Jev returns typed choices and probability distributions. It does not generate explanations. Its adapter uses `POST /api/alpha/decisions`, rather than pretending it is a chat-completion model.

The model page currently lists $0.042 per million input tokens and $0 output-token cost. It is not a fully free model. Selecting the explicitly labeled **Include paid Jev** checkbox opts into that request; the server also requires `allow_paid_jev: true`. It is deselected by default, and no paid live probe was performed.

The same evidence packet is supplied to Jev. It answers a decision question and, when an affordable fact exists, a next-question choice. Returned probabilities are displayed as provider outputs, not validated ethical confidence.

Sources: [Jev documentation](https://openrouter.ai/docs/guides/community/jev), [Decisions API](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request).

### Quota and response time

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

### What each model sees and how it is evaluated

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

### Live validation record

One successful relay-case call (September 2026) to **Nemotron 3 Super**, since withdrawn from the free catalog, prompt version `ethical-evidence-3`, returned:

- Decision: `conditional`.
- Next question: `relay_a`.
- Correctly described why both relays are needed and the two diversion outcomes.
- Full API response time: **15,887 ms**.
- Reported usage: 738 prompt tokens, 1,119 completion tokens.
- Reported cost: **$0**.

The decision and suggested question matched the reference. This is a single smoke test, not an accuracy or latency benchmark. Other live probes encountered rate limits, denied access, malformed output, truncation, and a provider error. Those failures are preserved.

Automated validation includes adapter/API tests with mocked upstream responses, plus a headed browser workflow with explicitly labeled fixture outputs. Jev's request/response contract is tested with fixtures; paid live execution remains untested.

To run a small explicit free-only live probe:

```bash
.venv/bin/python tools/check_openrouter.py --models nvidia/nemotron-3-super-120b-a12b:free
```

This consumes a real free request and stores a new run. The tool never calls Jev or any paid model.

### API

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
