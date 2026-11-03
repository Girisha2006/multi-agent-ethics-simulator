# Implementation record

> Historical record, kept as written. Paths and environment names (for example `gpu_env`) describe the setup at the time.
> Current docs: [README](../../README.md).

## 27 September 2026

Implemented the first working **Before You Decide** reference simulator in `gpu_env`.

- Dark technical dashboard selected by the user.
- Five authored cases, three binary hidden facts, three explicit reference policies.
- Two shared fact disclosures with server-side budget enforcement.
- Information-gain question recommendations and exhaustive remaining-world analysis.
- Separate full-information debrief, persistent SQLite run journal, browser restoration, and Markdown/JSON export.
- Independent per-framework benchmark against random question order across 40 case–world combinations.
- No LLM calls or GPU inference in this version. Reference agents and generated descriptions are labeled accordingly.

Validation: 18 engine/API tests pass; JavaScript syntax check passes; desktop/mobile end-to-end browser workflow passes. Screenshots and a sample exported record are in `artifacts/`.

The preinstalled Playwright 1.40 driver was incompatible with the current Edge version during browser shutdown. Updated Playwright to 1.63.0 in `gpu_env` (with its pyee and greenlet dependencies); the complete browser check now exits successfully.

Research extensions remain: teacher-reviewed definitions, independently evaluated LLM agents, explanation tests, held-out cases, repeated experiments, and a classroom usability study. See README.md and PLAN.md Section 11.

## 27 September 2026 — version 0.2.0

Implemented the approved milestone: three additional diagnostic cases, a budget planner, and animated evidence replay.

- Eight cases now include a two-credit reliability report, two complementary relay facts, and a known dominant brake that needs no disclosure.
- Two shared credits replace the uniform two-question budget; the API atomically enforces fact costs.
- Exact adaptive planning maximizes resolution probability, then minimizes expected credits. Greedy gain per credit and uniformly random affordable questions remain comparison strategies.
- The comparison enumerates all 64 case-world combinations per ethical framework and reports aggregate and per-case resolution, credits, and question counts.
- Read-only replay reconstructs each disclosure state without leaking later observations or the debrief. Stable world identifiers support elimination animation; controls include stepping, autoplay, pause, and scrubbing.
- The dashboard presents N1 (value-sensitive inquiry), N2 (complementary evidence), and N3 (an inspectable evidence trail), with direct case demonstrations.
- PLAN.md Section 12 distinguishes the implemented contribution from established methods and unvalidated novelty claims. PRESENTATION.md contains a six-minute professor walkthrough, exact reference results, and likely questions.
- There remain three ethical reference agents; question strategies are not additional agents. No LLM inference is performed.

Validation: 44 engine/API/planning tests pass; JavaScript syntax check passes. The headed Edge workflow passed the original flows plus costly disclosures, relay planning, stopping, contribution links, immutable replay, autoplay, debrief masking, mobile layout, and reduced-motion behavior. Desktop and mobile screenshots were visually inspected.

Reference result: in the relay case, the utilitarian and duty-based rules resolve 100% of worlds with the budget planner, 0% with greedy, and one third with random selection. This deliberately authored example demonstrates the mechanism; it is not evidence of generalization or moral accuracy.

Old journals are retained; version-mismatched runs are rejected rather than evaluated with changed rules.

## 27 September 2026 — OpenRouter model comparison

Added six free-model candidates and opt-in TypeSafe Jev through its distinct Decisions API. The model screen keeps the ethical role fixed, exposes the evidence supplied, records outputs and failures, and checks decisions against the reference. Jev remains deselected and was not live-tested because it charges for input tokens.

Credentials were copied from the user-provided env.txt into the server-only .env setting without displaying the key. Both files are ignored. Current catalog pricing is verified before free calls, with zero-price provider caps and no paid fallback.

The live catalog had no free Gemini or OpenAI text endpoint. The UI states this and can discover eligible free variants if they become available. Multi-account/key rotation is not implemented.

Live testing found rate limits for Qwen and Gemma, malformed Lightning output, an Ultra provider error, and denied Inkling access. Prompt revision ethical-evidence-3 clarified fixed facts after an observed misreading. Nemotron 3 Super then returned a valid relay-case decision and next question in 15,887 ms at a reported $0 cost. This model is the default starting option; broader quality and availability remain unmeasured.

Validation: 68 tests pass, including masked prompts, cache/repeat separation, stale evidence, paid opt-in, provider errors, schema validation, Jev fixtures, secret filtering, local rate guards, and absolute timeouts. The headed browser workflow passed model selection, explicit retries, escaped untrusted output, historical results, replay isolation, and mobile layout using labeled fixtures with no inference quota use.

OPENROUTER.md documents configuration, model IDs, quota constraints, sources, protocols, and live-test limitations. README.md, PLAN.md, and PRESENTATION.md distinguish the optional model comparisons from the deterministic reference benchmark.

## 3 November 2026 — Decision Lab

Implemented the proposal's four decision-theory agents as a second lab, following the teacher's feedback on controlled
variation and explanation evaluation.

- 8 Moral Machine-style base dilemmas and 91 one-feature variants (99 dilemmas), with the one-feature property tested.
- Expected utility, Sen-inspired welfare, Simon's satisficing and prospect theory agents with fixed, documented parameters
  and explanations generated from their own traces.
- Evaluation: invariance violations, counterfactual influential factors, a five-item explanation audit, Moral Machine
  directions in both lane positions, and agreement. `make evaluate` writes `results/decision_lab.md`.
- `/decision` page with dilemma, evaluation and LLM tabs.
- Optional free OpenRouter agents: one batched request per dilemma, attempts counted in SQLite before sending, cache,
  cooldowns, account-wide failure handling, and replay of real recordings only.
- Cross-platform `start.sh` / `start.ps1` with a local `.venv`; Makefile; documentation reorganised under `docs/`.

Validation: 127 offline tests pass; the page was checked in a browser at desktop and 360 px widths with no console errors
other than a missing favicon. No LLM recordings have been made yet.
