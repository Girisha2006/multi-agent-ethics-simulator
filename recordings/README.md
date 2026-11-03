# Decision Lab recordings

`decision_llm.json` (override with `DECISION_RECORDINGS`) is a JSON list of language-model results used for replay when the server has no
API key, the free quota is used up, or every model failed. Replayed results are labelled `source: "recording"` and keep their original
`model_id` and `created_at`.

Each entry is a `RunResult` (`status`, `source`, `dilemma_id`, `model_id`, `created_at`, `duration_ms`, `requests_used`, `answers`, `error`)
plus a `cache_key`: the sha256 of the prompt version, the agent parameters and the dilemma's stay and swerve lanes (`ethics_lab.decision.llm.cache_key`).
The newest `ok` entry with a matching key is replayed.

Recordings must come from real runs. Never write or edit entries by hand, and never fabricate them. To make them:

```
OPENROUTER_API_KEY=... python tools/record_llm.py                 # the 8 base dilemmas
OPENROUTER_API_KEY=... python tools/record_llm.py crossing brakes # chosen dilemmas
```

The tool runs live (one request per dilemma, within the daily limit `DECISION_LLM_DAILY_LIMIT`, default 45), appends successful results,
skips dilemmas already recorded, stops when quota is exhausted, and prints a summary.

The local daily counter covers only Decision Lab requests. The Before You Decide model-comparison tab draws on the same OpenRouter free pool, so the two together can exceed the provider limit.
