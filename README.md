# Multi-agent Ethics Simulator

Team 13 (HFE) course project in **Agents & Game Theory**. Four classical decision-making models (expected utility,
Sen-inspired welfare, Simon's satisficing, prospect theory) face the same Moral Machine-style dilemmas. Each dilemma is
varied one feature at a time, and every decision and explanation is checked against the rule that produced it.

Everything runs locally and offline. Free OpenRouter language models can optionally play the same four agents within the
free quota.

## Quick start

```bash
./start.sh            # macOS / Linux: creates .venv on first run
```

```powershell
./start.ps1           # Windows PowerShell
```

Open <http://127.0.0.1:8000/decision> for the **Decision Lab** or <http://127.0.0.1:8000/> for the earlier **Before You
Decide** lab. Interactive API docs are at `/docs`. Set `PORT` to use another port.

| Command | Does |
|---|---|
| `make install` | Create `.venv` and install runtime and test dependencies |
| `make run` | Start the server (`start.sh`) |
| `make test` | Run the full test suite offline |
| `make evaluate` | Regenerate `results/decision_lab.md` and `.json` |

Requires Python 3.10 or newer. No GPU, model download, Node build or API key is needed.

## The two labs

| Lab | Question | Docs |
|---|---|---|
| **Decision Lab** (`/decision`) | When a dilemma is varied in a controlled way, how do four decision models differ, and do their decisions and explanations follow their rules? | [docs/decision-lab.md](docs/decision-lab.md) |
| **Before You Decide** (`/`) | Do ethical frameworks differ in what they need to know before deciding, under a question budget? | [docs/before-you-decide.md](docs/before-you-decide.md) |

## Results at a glance

From [results/decision_lab.md](results/decision_lab.md):

- 0 invariance violations across 99 dilemmas; every factor an agent reads changes at least one of its decisions.
- All templated explanations pass the five-item audit.
- The four agents agree on 58 of 99 dilemmas. Prospect theory shows an omission bias, satisficing is sensitive to lane
  order, and only the welfare agent follows the Moral Machine age and pedestrian preferences in both lane positions.
- LLM pilot: a free model playing all four agents on the 8 base dilemmas matches the rules 24 of 32 times, but almost none
  of its explanations pass the full audit (§5 of the results).

## Optional LLM agents

Put `OPENROUTER_API_KEY=...` in a git-ignored `.env` file. One request covers all four agents on a dilemma. Requests are
counted before sending and cached. Failing models cool down, and the 8 committed real recordings replay when there is no key or quota.
See [docs/llm-agents.md](docs/llm-agents.md).

## Documentation

| Document | Contents |
|---|---|
| [docs/decision-lab.md](docs/decision-lab.md) | Dilemma format, variants, the four agents, evaluation methods, API |
| [docs/llm-agents.md](docs/llm-agents.md) | OpenRouter setup, free-quota strategy, recordings, model-comparison details |
| [docs/architecture.md](docs/architecture.md) | Modules, design rules, storage, tests |
| [docs/before-you-decide.md](docs/before-you-decide.md) | The information-seeking lab |
| [docs/report.md](docs/report.md) | Final report draft |
| [docs/presentation.md](docs/presentation.md) | Six-slide outline and demo script |
| [docs/history/](docs/history/) | Original plan, proposal feedback, earlier presentation and implementation log |

## Repository layout

```text
ethics_lab/            FastAPI app, Before You Decide engine, OpenRouter adapter, SQLite store
ethics_lab/decision/   Decision Lab: dilemmas, agents, evaluation, human directions, API, LLM agents
static/                Frontend for both labs (vanilla JS, no build)
tests/                 Offline pytest suite, plus optional Playwright browser checks
tools/                 Evaluation, LLM recording and OpenRouter probe scripts
results/               Generated Decision Lab results
recordings/            Real LLM runs for offline replay
docs/                  Documentation
```

## References

Main sources: Awad et al., "The Moral Machine experiment", *Nature* 2018; von Neumann and Morgenstern 1944; Sen,
"Rational Fools", 1977; Simon 1955; Kahneman and Tversky 1979 and 1992. The full list is in
[docs/report.md](docs/report.md#references).
