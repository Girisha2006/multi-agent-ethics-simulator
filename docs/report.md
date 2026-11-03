# Multi-agent Ethics Simulator — final report (draft)

**Team 13 — Humanity's First Exam (HFE)** · Track: **Demo** · Area: **Agents & Game Theory** (decision theory)
Repository: https://github.com/Girisha2006/multi-agent-ethics-simulator

> Draft generated from the code and from `results/decision_lab.md`. Sections marked **TEAM** must be written or checked by the
> team. Every number in §5 comes from `make evaluate`; re-run it before submission and update the numbers if the code changes.

## 1. Introduction

Autonomous systems may face situations where every available action risks harm. A single decision rule can hide
assumptions about whose welfare counts, how uncertainty is treated, and how much information a decision-maker uses. We
built an interactive simulator in which four classical decision-making models face the same trolley-style dilemmas, drawn
from or matched to the format of the Moral Machine experiment [1].

**Research question.** When the same dilemma is varied in a controlled way, how do four decision models differ in their
choices, and how closely do their decisions and explanations follow their stated rules? A secondary, descriptive question
asks how each model's choices compare with the direction of aggregate human preferences reported by Moral Machine.

The teacher's proposal feedback asked for exactly this. Novelty should come from what controlled modifications reveal and from
evaluating the consistency and justification of each explanation, not from placing several agents side by side. The project
does not claim to determine which framework is morally correct.

## 2. Background and related work

- **Moral Machine** collected about 40 million decisions on autonomous-vehicle dilemmas and reported global preferences
  for sparing humans over animals, more lives over fewer, and young over old, with weaker effects for lawfulness, status,
  pedestrians and inaction [1].
- **Expected utility** (von Neumann–Morgenstern) [2], **Sen's welfare and commitment** critique of self-interested
  rational choice [3], **Simon's bounded rationality and satisficing** [4], and **prospect theory** with loss aversion and
  probability weighting [5], with parameter estimates from Tversky and Kahneman's cumulative version [7].
- **Computational moral decision-making** has modelled Moral Machine judgments [6]. Controlled scenario variation
  overlaps with OffTheRails [8]. Our earlier information-seeking lab builds on ethical input-selection research [9] and
  clarifying-question benchmarks [10].

The course-scale contribution is a transparent, reproducible demonstration of how four specified decision procedures react
to one-feature changes, coupled with an automatic audit of whether their explanations match their rules. The same audit
also applies to explanations from free language models.

## 3. Method

### 3.1 Dilemmas and controlled variation
Eight base dilemmas use the Moral Machine format: a *stay* lane (no intervention) and a *swerve* lane (intervention), each
holding characters with age, species, role (pedestrian/passenger), lawfulness, and a fatality probability. A generator
produces **91 variants**, each changing exactly one feature in one lane (count, age, species, lawfulness, role,
intervention/mirror, probability), for **99 dilemmas**. A unit test enforces the one-feature property. Variants that would
change two features at once are skipped ("Controlled variants" in `docs/decision-lab.md`).

### 3.2 Agents
Each agent is a small deterministic module that returns a choice, a numeric trace and an explanation generated from that
trace. Full rules and parameters: `docs/decision-lab.md`.

| Agent | Concept | Rule (summary) |
|---|---|---|
| Expected utility | vNM rational choice | minimise probability-weighted loss; human 1, pet 0.1 |
| Welfare and empathy | Sen-inspired welfare & commitment | life-years lost, harm to pedestrians ×1.5 (concern for others) |
| Bounded rationality | Simon's satisficing | fixed inspection order; first lane within 1 death of best that harms no more law-abiding people than necessary |
| Prospect theory | Kahneman–Tversky | stay = reference point; v(x)=x^0.88, λ = 2.25, TK-1992 probability weights |

### 3.3 Evaluation
1. **Decision consistency.** Each agent's factor list is a pre-stated prediction. A variant of a feature the rule ignores
   must not change who is spared. Exact ties are excluded.
2. **Explanation faithfulness.** A five-item checklist: the decision matches the rule; the text names the returned choice;
   factors that are influential by one-step counterfactual change are cited; ignored factors are not cited; quoted numbers
   appear in the calculation or scenario.
3. **Human comparison.** Pure contrasts for six Moral Machine preference directions, each run with the favoured group in
   both lanes. Direction only, no magnitudes.
4. **Agreement** between the agents across all dilemmas.
5. **LLM agents (optional).** Free OpenRouter models play all four agents in a single batched request per dilemma. Their
   answers are checked against the reference choice and the same explanation audit (`docs/llm-agents.md`).

## 4. System

FastAPI backend, vanilla-JS frontend, SQLite for the run journal and LLM cache/quota. There are two labs. The **Decision Lab**
(`/decision`) implements this report. The earlier **Before You Decide** lab (`/`) studies information seeking under a
question budget (`docs/before-you-decide.md`). Architecture: `docs/architecture.md`.

## 5. Results

From `results/decision_lab.md` (engine `decision-1.0`):

**Consistency.** 0 invariance violations for all four agents. Every factor an agent reads changes at least one of its
decisions. Changed/pairs for selected features:

| Agent | count | age | species | lawful | intervention | probability | tie pairs excluded |
|---|---|---|---|---|---|---|---|
| Expected utility | 4/16 | 0/15 (I) | 6/15 | 0/14 (I) | 0/8 (I) | 5/16 | 24 |
| Welfare and empathy | 4/16 | 4/15 | 8/15 | 0/14 (I) | 0/8 (I) | 5/16 | 14 |
| Bounded rationality | 6/16 | 0/15 (I) | 8/15 | 6/14 | 2/8 | 7/16 | 0 |
| Prospect theory | 3/16 | 0/15 (I) | 8/15 | 0/14 (I) | 6/8 | 4/16 | 0 |

(I) = the rule ignores this feature, so no change is expected.

**Explanations.** All 99 deterministic explanations per agent pass the checklist. This is expected by construction and
validates the audit itself. It is not evidence about free-text explanations.

**Human directions.** All agents spare humans over pets and more over fewer in both lane positions. Only the welfare agent
follows the age and pedestrian preferences in both positions. Satisficing and prospect theory follow them only when the
favoured group sits in the swerve lane, because lane order and the status-quo reference point outweigh the feature.
Expected utility is indifferent (tie) on age, role, lawfulness and intervention.

**Agreement.** All four agents spare the same group in 58 of 99 dilemmas. In the base set they split on *Three against two*
(prospect theory alone stays), *Pedestrians or passengers* (the welfare agent alone swerves into four passengers to spare
three pedestrians), *Against the signal* (satisficing and prospect theory spare the lawful pair), and *Uncertain brakes*
(prospect theory alone avoids the risky swerve).

**LLM agents (pilot).** One free model, Nemotron 3.5 Super VL, played all four agents on the 8 base dilemmas, one request
per dilemma (8 requests, recorded 3 November 2026; `results/decision_lab.md` §5):

| Agent | matches rule | audit passed | names choice | cites influential | no ignored factor | numbers traceable |
|---|---|---|---|---|---|---|
| Expected utility | 7/8 | 1/8 | 7/8 | 2/8 | 7/8 | 8/8 |
| Welfare and empathy | 7/8 | 1/8 | 7/8 | 1/8 | 8/8 | 7/8 |
| Bounded rationality | 4/8 | 0/8 | 6/8 | 1/8 | 8/8 | 8/8 |
| Prospect theory | 6/8 | 0/8 | 6/8 | 0/8 | 6/8 | 3/8 |

The model usually reproduces the simple loss-minimising rules but follows satisficing's inspection order only half the time,
and its prospect-theory arithmetic is often untraceable (for example it counts the lives saved by swerving as the difference
between lanes rather than the stay-lane total). Several explanations argue for one lane and then return the other, which
the *names its choice* check catches. Its explanations rarely cite every factor that is counterfactually influential: they
compare counts but do not say that the people are human, or that the outcomes are certain. With 8 dilemmas and one model
these are pilot observations, not estimates for language models in general.

## 6. Discussion and limitations

- Prospect theory produces an **omission bias** without any explicit rule against intervening: loss aversion relative to
  the status quo requires about 2.5× more lives saved than endangered.
- Satisficing's lane-order sensitivity is the bounded-rationality trade-off made visible. It stops at "good enough".
- The scenario set is small and authored. Parameters are modelling choices held fixed, not fitted. The Sen agent is
  Sen-inspired, not canonical. Human data is used for direction only and is descriptive, not normative.
- The explanation audit uses a keyword lexicon. It can miss paraphrases, does not detect negation, and counts a factor as
  cited when its word only describes the scenario ("4 passengers").
- Free LLM access is rate-limited (~50 requests/day). Results depend on which free models are available on the day.

## 7. Individual contributions — TEAM

| Member | ID | Contribution (fill in actual work) |
|---|---|---|
| Debanshu Ghosh | 2023A3PS0332H | |
| Girisha | 2024A8PS0497H | |
| Kirtan Rupeshbhai Bhojani | 2023A3PS0366H | |
| Priyanshu | 2023A7PS1095H | |
| Puneet Singh | 2024A8PS0507H | |
| Rithvik Reddy Manda | 2024AAPS0277H | |
| Rohan Hasharth Amathaluri | 2023A7PS0015H | |
| Venkata Krishna Kaushik Karpurapu Naga | 2023AAPS0185H | |

## 8. AI usage disclosure — TEAM (required by the course guidelines)

State which AI tools were used, for what, and how the output was verified. For example: an AI coding assistant was used to
implement and refactor parts of the code and documentation. Every result was verified by the automated test suite
(`make test`), by regenerating `results/` with `make evaluate`, and by manual review of agent rules against hand
calculations. Replace this with an accurate account.

## References

[1] E. Awad et al., "The Moral Machine experiment," *Nature*, 563, 59–64, 2018. https://doi.org/10.1038/s41586-018-0637-6
[2] J. von Neumann and O. Morgenstern, *Theory of Games and Economic Behavior*, Princeton University Press, 1944.
[3] A. Sen, "Rational Fools," *Philosophy & Public Affairs*, 6(4), 1977.
[4] H. A. Simon, "A Behavioral Model of Rational Choice," *QJE*, 69(1), 99–118, 1955. https://doi.org/10.2307/1884852
[5] D. Kahneman and A. Tversky, "Prospect Theory," *Econometrica*, 47(2), 263–292, 1979. https://doi.org/10.2307/1914185
[6] R. Kim et al., "A Computational Model of Commonsense Moral Decision Making," arXiv:1801.04346, 2018.
[7] A. Tversky and D. Kahneman, "Advances in Prospect Theory: Cumulative Representation of Uncertainty," *J. Risk and Uncertainty*, 5, 297–323, 1992.
[8] OffTheRails, arXiv:2404.10975.
[9] "Ethical machine decisions and the input-selection problem," *Synthese*, 2021. https://link.springer.com/article/10.1007/s11229-021-03296-0
[10] AskBench, Findings of ACL 2026. https://aclanthology.org/2026.findings-acl.845/
