# Before You Decide: professor demonstration

> Historical record, kept as written. Paths and environment names (for example `gpu_env`) describe the setup at the time.
> Current docs: [README](../../README.md).

## The project in one sentence

We built an interactive experiment that shows how an ethical rule changes which evidence is worth collecting, and whether a disagreement can be resolved by learning more.

**Research question:** Under a limited information budget, what must different ethical frameworks know before they can commit to a decision?

Current version: 0.2.0. Eight authored cases, three explicit ethical policies, three question strategies, and 64 equally weighted case-world combinations per policy. The investigation is a working reference simulator. The optional Model comparison tab now evaluates independently generated OpenRouter outputs against these rules; its early live checks are not a benchmark.

## Three clear contribution areas

| Area | What we built | What the professor can see | What would establish research value |
|---|---|---|---|
| **N1: Value-sensitive inquiry** | Framework-specific evidence selection with unequal disclosure costs | Different rules request different facts; an expensive report spends two credits at once | Teacher-reviewed cases and evidence that the workflow helps students explain why evidence matters under each rule |
| **N2: Complementary evidence** | A case in which two facts are useful together but neither has immediate gain, plus an exact budget planner | Greedy stops at zero gain; the planner asks both relays and resolves the decision | Held-out case families testing when planning helps, including cases where it adds no benefit |
| **N3: An inspectable evidence trail** | Read-only replay, stable possible-world identifiers, and exhaustive disagreement checks | Worlds disappear after disclosures; conditional decisions can resolve while rule disagreement remains | A comparison with a static interface measuring whether students correctly distinguish uncertainty from persistent disagreement |

These are **project contribution areas**, not claims that information gain, look-ahead planning, replay, or ethical information selection are new inventions. The candidate novelty is their focused integration into an inspectable teaching experiment, supported by our authored cases and a future evaluation.

## Six-minute live walkthrough

Open http://127.0.0.1:8000. The contribution panel has a direct button for each area.

| Time | Interaction | What to say |
|---|---|---|
| 0:00–0:45 | Show the contribution panel and the three reference rules | “We study the evidence a rule needs before a decision, with the same evidence shared across agents.” |
| 0:45–1:45 | N1: open **The expensive report**. Compare suggested questions, then reveal reliability | “The reliability report costs the entire two-credit budget. Question count and information cost are different. Each framework values evidence through its own rule.” |
| 1:45–3:15 | N2: open **Two halves of an answer**. Switch to **Greedy gain**, then **Budget planner**. Inspect the planned branch. Reveal Relay A and Relay B | “A single relay leaves rescue equally likely to be high or low. Together they determine it. Greedy stops immediately; planning recognizes the useful pair.” |
| 3:15–4:15 | Click **Replay run**. Use Next, Previous, the slider, or Play | “Replay restores the evidence available at each step. It does not reveal future answers or rewrite the run. Notice eight worlds narrow to four, then two.” |
| 4:15–4:45 | Open **Enough is already known** | “All three rules support the brake before any question. A budget is a limit, not a target.” |
| 4:45–5:30 | Open **Policy comparison**, run all 64 worlds, and inspect the relay rows | “These are exact reference-model results over every defined world, not sampled LLM accuracy.” |
| 5:30–6:00 | Return to an investigation, close the round, and export its record | “The debrief reveals full information separately. The budgeted result and disclosure history remain inspectable.” |

For N3's disagreement distinction, open **The uncertain junction** and inspect the disagreement panel before and after revealing reliability and brake availability. The sampled facts can produce different outcomes; report the displayed result rather than promising a particular live outcome. When reliability is low and the brake is absent, disagreement persists in every remaining world. The automated checks include that exact case.

## Measured reference results

Reproduced through `GET /api/benchmark` with engine 0.2.0 on 27 September 2026.

### Resolution over all 64 case-world combinations

| Framework | Budget planner | Greedy gain | Random affordable |
|---|---:|---:|---:|
| Utilitarian | 93.75% | 81.25% | 52.08% |
| Duty-based | 78.13% | 56.25% | 47.92% |
| Minimax risk | 100.00% | 100.00% | 75.00% |

“Resolved” means at least one action is supported in every world consistent with the available evidence. It does not mean morally correct, agreed upon by all frameworks, or factually omniscient.

### The strongest demonstration: complementary evidence

For the utilitarian and duty-based rules in **Two halves of an answer**:

| Strategy | Resolution | Mean credits spent | Explanation |
|---|---:|---:|---|
| Budget planner | 100% | 2 | Always asks both relays |
| Greedy gain | 0% | 0 | Every initial question has zero immediate gain |
| Random affordable | 33.33% | 2 | Only two of the six ordered pairs contain both relays |

Minimax risk already supports diversion in this case and uses zero credits. That contrast is part of the result, not an exception to hide.

In **The expensive report**, the duty-based planner and greedy strategy both resolve 50% of worlds; the planner spends 1.5 credits on average versus 2 for greedy. In **Enough is already known**, every strategy resolves every world without spending credits.

## Questions the professor may ask

**What is actually new?**  
The implemented artifact is a focused integration: framework-dependent evidence requests, diagnostic cases involving cost and complementary facts, and an inspectable distinction between missing information and persistent rule disagreement. Global originality and educational benefit still require a fuller related-work comparison and evaluation.

**Is the planning algorithm new?**  
No. Greedy information gain and finite-budget search are established techniques. Here they make a specific ethical-information experiment measurable and easy to inspect.

**Are these AI agents or programmed rules?**  
The three baseline agents are deterministic reference policies. The Model comparison tab separately calls selected OpenRouter models under one chosen ethical role at a time. Six free-model options are configured, plus paid, opt-in Jev. Model availability and failures are visible; Jev supplies decisions without explanations.

**Are more long runs needed?**  
The defined reference experiment has only 64 case-world combinations, so we enumerate all of them. Repeating the same deterministic runs does not add evidence. Broader cases, different priors, independently evaluated model behavior, and user tasks would add evidence.

**Does the planner prove better ethical reasoning?**  
No. It optimizes resolution under a specified prior and budget. Greedy optimizes immediate entropy reduction per credit. Different objectives explain some differences; resolution is not moral quality.

**Why three missing facts and two credits?**  
The small state space lets a viewer inspect every possibility and check the result. Larger budgets and cases should be added only with a declared research question and controlled evaluation.

## Next evidence needed

1. Professor review of scenario meanings and operational ethical rules.
2. Held-out cases, varied priors, and cost changes with predictions written beforehand.
3. A counterbalanced comparison of this workflow against a static decision display, measuring explanation accuracy and task time.
4. Broader evaluation of the implemented model adapter, with held-out cases, repeated runs, and failures recorded separately.

Prior-work notes and scope are maintained in [PLAN.md](plan.md), Sections 10–12. The boundary-search and explanation-faithfulness ideas in Section 10 remain proposed extensions.

## Optional independent-model demonstration

After the reference walkthrough, open **Model comparison** on the relay case. Select the utilitarian framework and Nemotron 3 Super, the default model. Click **Compare selected models**. The model receives the physical rules and budgeted evidence without the reference answer.

A successful live smoke test returned a conditional decision, requested Relay A, and explained why both relays are needed, in 15.887 seconds at a reported cost of zero. This single example is not evidence of general accuracy. Use the saved result if the provider is busy and say explicitly that it is a saved attempt.

Show the supplied-evidence/provenance panel, response time, and reference check. A mismatch or provider error is part of the recorded result. Do not describe a checked decision as proof that the explanation is faithful or morally correct.

Gemini and OpenAI currently have no verified free endpoint in the checked OpenRouter catalog. Jev is paid and produces typed choices without explanations. Exact options and live-test limitations are in [OPENROUTER.md](../llm-agents.md).
