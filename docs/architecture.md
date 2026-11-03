# Architecture

One FastAPI process serves two labs, a JSON API and a vanilla-JS frontend. There is no build step, no model download and
no GPU. SQLite is the only storage.

```text
browser ──► FastAPI (ethics_lab/app.py)
             ├── /            static/index.html + app.js, models.js      Before You Decide lab
             ├── /decision    static/decision.html + decision.js         Decision Lab
             ├── /api/...     Before You Decide routes (app.py)
             ├── /api/decision/...      ethics_lab/decision/api.py       deterministic, offline
             └── /api/decision/llm/...  ethics_lab/decision/llm_api.py   optional, quota-safe
                                         │
                                         ├── ethics_lab/openrouter.py   HTTP client, free-price checks
                                         └── ethics_lab/store.py        SQLite (ETHICS_DB)
```

## Modules

| Path | Role |
|---|---|
| `ethics_lab/app.py` | FastAPI app, static files, Before You Decide routes, mounts the Decision Lab routers |
| `ethics_lab/scenarios.py`, `engine.py` | Before You Decide cases, reference policies, information gain, budget planner, benchmark |
| `ethics_lab/comparisons.py` | Before You Decide model-comparison attempts and reference checks |
| `ethics_lab/openrouter.py` | OpenRouter adapter: key loading, model list, live catalog and zero-price verification, request errors |
| `ethics_lab/store.py` | SQLite connection helper and run journal |
| `ethics_lab/decision/dilemmas.py` | 8 base dilemmas, one-feature variant generator (99 dilemmas), lane descriptions |
| `ethics_lab/decision/agents.py` | The four decision-theory agents, their parameters, traces and templated explanations |
| `ethics_lab/decision/evaluation.py` | Consistency, counterfactual influential factors, explanation audit, agreement, full report |
| `ethics_lab/decision/human.py` | Moral Machine preference directions and their contrast dilemmas |
| `ethics_lab/decision/api.py` | `/api/decision/catalog`, `/dilemmas/{id}`, `/report` |
| `ethics_lab/decision/llm.py`, `llm_api.py` | Batched LLM agents: quota, cooldowns, cache, replay; `/api/decision/llm/*` |
| `static/decision.*` | Decision Lab page: dilemma explorer, evaluation tab, LLM tab |
| `tools/run_evaluation.py` | Writes `results/decision_lab.md` and `.json` (`make evaluate`) |
| `tools/record_llm.py` | Records real LLM runs into `recordings/decision_llm.json` for offline replay |
| `tools/check_openrouter.py` | One explicit free live probe for the Before You Decide comparison |

## Design rules

- **Deterministic core.** Every agent decision, explanation and evaluation number comes from pure functions over the
  dilemma data, so `results/` can be regenerated at any time and the tests can check exact values.
- **Explanations from traces.** An agent's explanation is generated only from its own numeric trace. It cannot cite a
  factor or number the calculation did not use, which is what the explanation audit then verifies.
- **The LLM layer is optional.** Removing the key, or the network, changes only the LLM tab. Failures are returned as
  labelled results, never replaced by reference answers.
- **Quota is spent deliberately.** One request per dilemma for all four agents. Attempts are counted in SQLite before
  sending, results are cached, and the demo can run from real recordings.

## Storage

`ETHICS_DB` (default `data/runs.sqlite3`, git-ignored) holds the Before You Decide run journal and model attempts, plus the
Decision Lab's LLM attempt counter, cooldowns and results. Deleting the file resets everything except `recordings/`.

## Tests

`make test` runs the whole suite offline. Network calls are monkeypatched in every LLM test. `tests/browser_smoke.py` and
`tests/browser_models.py` are optional Playwright checks against a running server.
