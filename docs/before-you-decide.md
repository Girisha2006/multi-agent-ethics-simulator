# Before You Decide — information-seeking lab

The original lab in this repository, an interactive experiment in **value-sensitive information seeking**. It asks: *do different ethical frameworks differ in what they need to know before making a decision?*

A local, interactive laboratory for ethical information seeking. Three reference agents face the same partially specified trolley dilemma, recommend questions, and update their supported actions as facts are revealed.

The initial implementation follows the **information-seeking experiment** discussed after the original plan: eight authored cases, three binary facts per case, a two-credit shared disclosure budget, and exhaustive disagreement analysis. The dark dashboard runs without a model download, API key, Node build, or external font service.

Open it at `/` after starting the server (see the [README](../README.md)).

## Try an investigation

1. Choose one of the eight cases.
2. Inspect the known outcome model and each agent's suggested next question.
3. Open a fact card, or click an agent's “Ask this question” button. The fact is disclosed to all agents and spends its displayed cost of one or two credits.
4. Reveal another affordable fact if credits remain. Unresolved agents preserve conditional answers instead of inventing the remaining fact.
5. Inspect all remaining possible worlds and the disagreement analysis.
6. Close the round to reveal full information. Budget-limited results remain unchanged above the debrief.
7. Use **Replay run** to step, play, or scrub through earlier evidence without changing the journal.
8. Export the Markdown record. The JSON endpoint also includes the full diagnostic tables and question recommendations.

“New run” samples a fresh hidden world. Previous records remain in the local journal. Refreshing the browser restores the current run using its locally stored identifier.

The **Policy comparison** tab separately evaluates each framework's own two-question strategy across all 40 case–world combinations. Its random-order baseline averages all six ordered pairs of questions. This is separate from the interactive shared-question session.

## Explicit ethical models

| Reference agent | Operational rule |
|---|---|
| Utilitarian | Minimize total expected deaths with equal weight per person. |
| Duty-based | Forbid diversion if harming the side group is a necessary means of rescue; then minimize expected deaths among permitted actions. |
| Minimax risk | Minimize the greatest individual probability of death; break risk ties by expected deaths. |

All models preserve remaining exact ties. These are deliberately narrow definitions, not complete representations of the philosophical traditions. The duty policy's outcome-based secondary rule is an explicit design choice.

Actions are: do not intervene, divert, and use an emergency brake if available. Diversion's side-group risk applies whether rescue succeeds or fails. Braking gives every individual the same stated marginal risk and never uses a person as a means. Expected deaths use linearity of expectation; they do not assume independent individual outcomes.

## Information and disagreement calculations

- The first six cases hide rescue reliability, causal role of harm, and brake availability. In the relay case, two independent settings jointly determine reliability; a third sticker fact is irrelevant. In the settled case the brake is known available, and the hidden facts cannot overturn its dominance.
- These define eight equally weighted worlds. Independence and the 50/50 prior are experimental assumptions, not empirical probability estimates.
- The greedy question policy computes expected entropy reduction per credit over the framework's **optimal-action sets**, conditional on already disclosed facts. It never receives the actual unrevealed values.
- Greedy selection stops when an action is supported in every remaining world or no affordable question has positive immediate gain. Remaining ties follow the displayed fact order.
- The budget planner searches every affordable adaptive question sequence, maximizing resolution probability and then minimizing expected credits. Stopping is an option at every step. Its forecast assumes the declared independent fair-bit prior and that its full plan is followed.
- Switching strategies changes question recommendations, not the ethical rules. The three reference agents are distinct from the three question strategies.
- An agent is **Resolved** if the intersection of its supported actions across remaining worlds is nonempty. Otherwise it stays **Conditional**, including after the budget is exhausted.
- To analyze agreement, the engine intersects the three frameworks' supported-action sets separately in each remaining world. Compatibility in every world does not imply one common action across all worlds. No shared action does not imply all three pairs disagree.
- The debrief identifies the actual world after the round closes. It does not replace the experiment's observed facts, credits spent, or recorded budget-limited decisions.

The reference calculations alone do not diagnose model inconsistency. The optional model tab measures independent outputs against them; it does not yet evaluate wording robustness or independently grade explanations. Reference-rule differences are expected by construction. The authored pilot supports development and demonstration; it is not held-out evidence of research novelty or generalization.

## Data and journal

Runs are stored in `data/runs.sqlite3`, excluded from version control. Set `ETHICS_DB` to use a different journal. The journal contains hidden values because it is the experiment server's local storage; unfinished-run HTTP responses and exports omit those actual values. The application is intended for a single local research workstation and has no account system.

Version 0.2.0 preserves old SQLite records but rejects opening a run created under a different engine version. The browser starts a new run if the saved version is incompatible; old journals are not rewritten.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/catalog` | Scenarios and reference framework specifications |
| `POST /api/runs` | Start a run with `{"scenario_id": "junction"}` |
| `GET /api/runs/{id}` | Restore a run with masked hidden values |
| `POST /api/runs/{id}/reveal` | Reveal one fact with `{"fact_id": "reliability"}` |
| `GET /api/runs/{id}/replay` | Read-only historical states, masked at each disclosure step |
| `POST /api/runs/{id}/finish` | Close the round and open the full-information debrief |
| `GET /api/runs/{id}/export` | Download Markdown; add `?format=json` for structured results |
| `GET /api/benchmark` | Enumerate the independent two-credit reference-policy experiment |

The OpenRouter connection, comparison, and export endpoints are documented in [llm-agents.md](llm-agents.md). Interactive API documentation is available at `/docs`.

## Contribution and prior work

The contribution areas (N1 value-sensitive inquiry, N2 complementary evidence, N3 inspectable evidence trail), their claim boundaries and the prior-work review are in [history/plan.md](history/plan.md) §11–12. Information seeking builds on [AskBench](https://aclanthology.org/2026.findings-acl.845/) and [ethical input-selection research](https://link.springer.com/article/10.1007/s11229-021-03296-0); controlled scenario design overlaps with [OffTheRails](https://arxiv.org/abs/2404.10975).
