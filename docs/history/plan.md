# Project Plan: Controlled Comparison of Ethical Frameworks

> Historical record, kept as written. Paths and environment names (for example `gpu_env`) describe the setup at the time.
> Current docs: [README](../../README.md).

## Project direction

Build an interactive system in which independent agents apply different ethical frameworks to the same trolley-style dilemma and explain their decisions.

The teacher's feedback makes controlled comparison and explanation evaluation the core research contribution. The project should investigate what changes decisions, when explanations become inconsistent, and what these findings reveal about the implemented frameworks.

Implementation started on 27 September 2026. The first local prototype implements the information-seeking experiment described in Section 11. See README.md for launch instructions and current limitations.

## 1. Define the research question

**When specific features of an ethical dilemma change, how do different ethical frameworks change their decisions, and how consistent are their explanations?**

Supporting questions:

- Which changes cause frameworks to agree or disagree?
- Where does each framework switch its decision?
- Does equivalent wording produce the same decision?
- Does the explanation support the decision using the assigned principles?

## 2. Review existing work and define the contribution

Conduct a focused literature review covering:

- Computational ethics and formal representations of ethical frameworks.
- Existing comparisons using trolley-style dilemmas.
- Evaluation of agent decisions and generated explanations.

Use the review to identify a defensible contribution, such as a controlled scenario dataset or an analysis of explanation inconsistencies. Establish novelty through this review rather than assuming that multiple agents alone provide it.

**Deliverable:** A short related-work summary and a clear statement of the project's contribution.

## 3. Choose and precisely define three frameworks

Suggested initial scope:

| Framework | Proposed operational model |
|---|---|
| Utilitarian | Compare actions using a declared calculation of expected harm. |
| Deontological | Evaluate actions against explicit duties and prohibitions, with a defined approach to conflicts. |
| Fairness-oriented | Evaluate outcomes using a specified fairness criterion. |

These are simplified operational models, not complete representations of their philosophical traditions.

For each model, document:

- Principles and assumptions.
- Required scenario information.
- Decision procedure.
- Treatment of uncertainty.
- Tie-breaking rules.
- Handling of conflicting principles or cases without a unique decision.

Validate the definitions with the teacher before implementation.

**Deliverable:** A framework specification that makes each model's behavior reviewable.

## 4. Design the experiment before the interface

Create an initial dataset of approximately 20–30 scenarios. Begin with a baseline dilemma and vary one feature at a time.

| Feature | Example variation |
|---|---|
| Number affected | Change the number of people on either track. |
| Outcome uncertainty | Compare certain rescue with a stated probability of rescue. |
| Nature of intervention | Compare redirecting danger with using a person as the means of rescue. |
| Available actions | Compare two choices with an additional rescue option. |
| Wording | Express equivalent facts in different language. |

For every scenario, record:

- A unique identifier and scenario version.
- The facts and available actions.
- The consequences and any probabilities.
- The variable changed relative to the baseline.
- Expected behavior under the defined framework rules.

Include ties and cases where the rules do not determine a unique choice. Review paired scenarios to ensure that unintended differences do not confound the comparison.

Write predictions before running experiments to reduce selective interpretation.

**Deliverable:** A versioned scenario dataset and a set of recorded predictions.

## 5. Separate framework rules from agent behavior

Proposed processing flow:

```text
Scenario
  -> Independent framework agents
  -> Structured results
  -> Evaluation
  -> Comparison view
```

Each agent receives identical scenario facts and cannot see the other agents' answers. Each result contains:

- Selected action, or an explicit unresolved result.
- Relevant scenario facts.
- Applied principles.
- Justification for the decision.
- Any relevant conflicts or uncertainty.

Use explicit rules as a reference baseline. If language models are included, hold the underlying model and settings constant while varying framework instructions. Record the model version, prompts, and execution settings.

Differences programmed into deterministic rules are expected by construction. These experiments can map decision boundaries. Language-model experiments can additionally test whether agents follow the specified rules reliably. Neither establishes which framework is morally correct.

**Deliverable:** A reproducible execution design with clear inputs, outputs, and reference behavior.

## 6. Evaluate decisions and explanations

| Evaluation dimension | What to measure |
|---|---|
| Disagreement | How often frameworks select different actions. |
| Sensitivity | Which controlled changes alter each decision. |
| Wording robustness | Whether equivalent descriptions preserve the result. |
| Repeatability | Whether stochastic agents give consistent answers across repeated runs. |
| Framework adherence | Whether decisions and justifications follow the specified rules. |
| Explanation quality | Factual accuracy, support for the selected action, and acknowledgment of relevant conflicts. |

Create a written explanation rubric before evaluation. Have two independent human reviewers evaluate a sample and report reviewer agreement.

Treat generated explanations as justifications to evaluate, rather than proof of an agent's internal reasoning.

For stochastic agents, define the number of repeated runs in advance. Preserve raw results, including failures and unresolved responses.

**Deliverable:** Evaluation results supported by tables, charts, and representative examples of agreement, disagreement, and inconsistency.

## 7. Plan the interactive interface

Keep the initial interface focused on the experiment. It should let users:

- Select a dilemma.
- Inspect its facts and available actions.
- Change one controlled factor.
- Compare framework decisions and explanations side by side.
- See how results differ from the baseline scenario.
- Inspect aggregate experiment results.

Choose the technical stack after the research design and execution requirements are clear.

**Deliverable:** A small comparison interface connected to the experiment results.

## 8. Delivery sequence

1. Finalize the research question, literature review, and framework definitions.
2. Prepare the scenario dataset, predictions, and evaluation rubric.
3. Implement reference rules and independent agent execution.
4. Run experiments and analyze the results.
5. Build the interactive comparison interface.
6. Write the final report and package reproducibility materials.

## 9. Final deliverables and completion criteria

- A documented research question and related-work review.
- Explicit, reviewable specifications for three ethical models.
- A controlled and versioned scenario dataset.
- Reproducible experiment settings and raw results.
- Decision comparisons and explanation evaluations.
- An interactive demonstration.
- A final report discussing findings, counterexamples, limitations, and future work.

The project is complete when it can show, with recorded evidence, which controlled changes affect decisions, how reliably agents follow their assigned frameworks, and where their explanations succeed or fail under the evaluation rubric.

## 10. Earlier novelty candidates: An Interactive Ethical Disagreement Debugger

**Scope:** This section preserves the earlier research ideas and prior-work review. The implemented contribution areas are N1–N3 in Section 12. Boundary search and explanation testing below are not implemented.

### Recommendation

Add a workflow that lets users investigate a disagreement: locate the scenario changes that alter it, test an agent's stated justification, and inspect evidence about whether the disagreement follows the specified frameworks or reflects inconsistent agent behavior.

The practical contribution is a usable diagnostic tool for students and teachers. The research contribution would be the original controlled cases, validated diagnostic rules, and findings produced by evaluating the tool.

**Proposed research question:** Can a controlled, interactive debugging workflow help users distinguish disagreement supported by different ethical rules from failures to follow those rules?

### What the web review found

Targeted web review conducted on 27 September 2026, covering research papers, author project pages, and public repositories. This is an initial prior-work review, not proof that no equivalent system exists. The proposed differentiation below is an inference from the reviewed sources.

| Existing work | Overlap with our project | Implication for the novelty claim |
|---|---|---|
| [The Moral Agent](https://github.com/Jamil-M03/TheMoralAgent) | A live app sends the same dilemma to Kantian and utilitarian agents and displays their explanations side by side. | Side-by-side philosophical agents already exist and cannot be the main novelty. |
| [OffTheRails, CogSci 2024](https://arxiv.org/abs/2404.10975) | Generates controlled moral dilemmas from causal structures and compares judgments across experimental conditions. | Controlled scenario variations and generated dilemmas are established methods. |
| [MoReBench](https://morebench.github.io/) | Evaluates moral reasoning with rubrics, includes framework-specific examples, and provides interactive model comparison. | Explanation scoring, framework adherence, and a comparison dashboard alone are insufficient differentiators. |
| [Moral Lens, 2025](https://arxiv.org/abs/2505.21479) | Analyzes consequentialist and deontological rationales across more than 600 trolley problems. | Classifying explanations by ethical theory is already studied. |
| [A Positive Case for Faithfulness, 2026](https://oxrml.com/faithfulness/) | Tests whether explanations help predict behavior on counterfactual inputs, including moral dilemmas. | Testing an explanation against changed inputs is established prior work and must be credited. |

The reviewed work does not establish that our complete proposed workflow is unique. The defensible opportunity is a focused integration with a measurable educational benefit and an original evaluation, rather than claiming invention of any individual method.

### Feature A: Find the disagreement boundary

**Visible interaction:** The user clicks "Find what changes the decision." The system varies one selected fact over a declared range and displays a row of decisions for each framework. Clicking a change point reveals the before-and-after scenarios, the changed fact, the applicable reference rule, and the agent responses.

Example controls could vary the number of people affected or the probability of successful rescue. The result might show that one implemented framework changes its answer while another keeps the same answer throughout the tested range.

**Practical implementation:** Start with a small, discrete set of valid values and evaluate every value. Use the same structured scenario and fixed text template for each run. Compare agent outputs with the explicit reference rules defined in Section 3.

**Scope limits:** Report the smallest observed change within the tested range and resolution. Do not claim a globally minimal change. Do not assume decisions change monotonically; display all observed reversals. For stochastic agents, show action frequencies and unstable regions instead of presenting every sampled reversal as an exact boundary.

**Value:** Students can discover which facts distinguish the implemented frameworks, and teachers can reproduce the exact examples behind a claim.

### Feature B: Test this reason

**Visible interaction:** Each explanation has a "Test this reason" action. It opens a test card containing the original claim, a proposed single-fact change, the expected behavior implied by a sufficiently precise claim, and the observed result.

For example, an agent might explicitly state that its decision depends only on the number of people harmed. A test can change an incidental label while preserving the numbers and all morally relevant facts under the specified model. A changed answer becomes evidence of a possible inconsistency.

**Practical implementation:** Request a short justification plus structured fields for cited facts and principles. Map a small set of explicit claims to human-reviewed test templates. Freeze the original claim before generating the changed case, and run the changed case independently without showing the agent its previous answer or the expected result.

Show one of four outcomes: "Supported in tested cases," "Potential inconsistency," "Unstable across repeats," or "Claim too vague to test." Repeat the unchanged baseline as well, so ordinary output variation is not mistaken for sensitivity to the edit.

**Value:** Users can inspect concrete evidence behind a reliability concern. The feature tests observable behavior against a stated claim; it does not prove what caused the model's internal reasoning. Counterfactual explanation evaluation is credited to prior work in the table above.

### Feature C: Explain the disagreement with evidence

**Visible interaction:** A "Why do they disagree?" panel summarizes the checks and links to the exact scenario pairs and responses supporting each finding.

| Diagnostic finding | Required evidence |
|---|---|
| Consistent with different framework rules | The reference models permit different actions, and each agent's action follows its assigned specification. |
| Framework adherence failure | An agent selects an action outside the permissible set under its own specification. |
| Potential explanation inconsistency | A precise stated claim fails a valid paired test beyond the variation observed in unchanged repeats. |
| Wording or label sensitivity | Equivalent cases produce materially different action frequencies after preserving action identity and scenario meaning. |
| Unresolved | Rules, explanations, missing facts, or repeated results do not support a clear finding. |

These findings can coexist. They are diagnostic evidence about the implemented models, not definitive accounts of philosophical disagreement or moral correctness.

**Practical implementation:** Use reference-rule checks and recorded experiment comparisons for the findings. An LLM may summarize the evidence, but should not be the sole authority assigning labels. Export a Markdown report containing the scenario pair, changed field, rules, outputs, settings, and result.

**Value:** A teacher can turn an apparent contradiction into a reproducible classroom example. A developer can identify cases where an agent fails its declared policy.

### Suggested demonstration

1. Open a trolley scenario and run the three framework agents.
2. Select a field and use "Find what changes the decision" to display the tested decisions.
3. Open one transition and inspect the exact before-and-after facts.
4. Select "Test this reason" on an explicit justification.
5. Inspect the diagnostic evidence and export the case.

Use saved experiment results for a dependable demonstration, clearly marked with their run date and settings. Provide live reruns separately. If demonstrating a deliberately faulty agent, label it as a seeded example rather than a discovered failure.

### Feasible first version

- Three precisely specified reference frameworks and corresponding agents using one underlying language model.
- Five hand-authored scenario families for the initial pilot, expanding to the planned 20–30 cases after validation.
- One numeric variable per boundary search, with at most ten candidate values initially.
- Three test types: changing a relevant quantity, changing a declared irrelevant label, and a human-reviewed equivalent paraphrase.
- Five repeated runs per evaluated input for an exploratory pilot; report counts and treat weak evidence as inconclusive.
- One combined comparison and diagnostic screen, plus report export.

For scale, five scenario families with ten values, three agents, and five repeats require 750 agent responses before additional explanation tests. Cache results by complete scenario, framework, prompt, model, and settings; set an explicit call budget for live use.

The explanation checks require independently generated agent responses. Checking deterministic template explanations against the same rules that generated them would mainly validate implementation, not discover model reasoning failures.

### How to establish a contribution

Evaluate the complete tool against a baseline that only displays decisions and explanations side by side.

- **Diagnostic validity:** Use human-reviewed cases and clearly labeled seeded faults to measure how often the tool correctly identifies problems and how often it raises false alarms. Keep naturally observed failures separate from seeded faults.
- **Educational usefulness:** Have users identify the changed fact and distinguish rule-supported disagreement from agent inconsistency. Compare accuracy and task time across matched tasks, with task order counterbalanced to reduce practice effects.
- **Empirical findings:** Report observed boundaries, rule-adherence failures, testable explanation coverage, and unresolved cases on held-out scenarios. Separate test development cases from evaluation cases.
- **Reproducibility:** Release the original scenario pairs, framework specifications, test rules, and run records where permitted.

Any small classroom study should be reported as exploratory. A useful result may be that the debugger adds little benefit; improvement must be measured rather than assumed.

### Novelty statement for the proposal

> We propose an interactive ethical disagreement debugger that combines explicit framework specifications, controlled scenario changes, and tests of stated justifications. Its contribution will be an original, reproducible set of diagnostic cases and an evaluation of whether the workflow helps users distinguish disagreements supported by different ethical rules from failures of framework adherence or explanation consistency.

Do not claim to be the first multi-agent ethics comparison, counterfactual ethics evaluator, or explanation-scoring system. Cite the overlapping work explicitly. The integrated workflow is a candidate product distinction; research novelty depends on the resulting methods, evidence, and comparison with prior work.

## 11. Implementation direction: Before You Decide

The subsequent ideation selected an information-seeking experiment as the central interaction: **Do different ethical frameworks differ in what they need to know before making a decision?**

The user authorized implementation and selected a dark technical dashboard. The initial local prototype uses the `gpu_env` Conda environment, a Python/FastAPI server, a browser interface, and a local SQLite experiment journal.

### Implemented reference experiment

- Eight authored trolley scenarios with three binary hidden facts each, including unequal disclosure costs, complementary relay evidence, and a known dominant action.
- Three explicit reference policies: expected-death minimization, a duty constraint with an outcome-based secondary rule, and minimax individual risk.
- Greedy question ranking using expected information gain per credit about each policy's optimal-action set, with an explicit equal-world prior.
- An exact adaptive planner that maximizes the chance of resolution within the remaining credits, then minimizes expected credits.
- Two shared credits; facts cost one or two credits and all agents receive identical evidence.
- Exhaustive analysis of whether a common supported action exists in each remaining factual completion.
- A separate full-information debrief that preserves the original disclosure-budget results.
- Markdown and JSON experiment export, browser run restoration, and a persistent server journal.
- An independent per-framework benchmark over all 40 case–world combinations against all six random two-question orders.

### Current research boundary

The investigation and exact benchmark remain deterministic reference simulations. The subsequent OpenRouter integration in Section 13 adds independently generated model comparisons. It does not establish explanation faithfulness or moral correctness. The reference policies do not use the GPU.

The model adapter is now implemented. The next research phase requires teacher-reviewed case definitions, held-out scenarios, repeated measurements, and a comparison against a static explanation interface. The debugger ideas in Section 10 remain research extensions rather than claims of completed features.

The novelty candidate is framework-dependent information seeking under a question budget, combined with an inspectable distinction between factual uncertainty and persistent rule disagreement. Asking clarifying questions and ethical information selection already have prior work: [AskBench](https://aclanthology.org/2026.findings-acl.845/) and [Ethical machine decisions and the input-selection problem](https://link.springer.com/article/10.1007/s11229-021-03296-0). Uniqueness of the full proposed contribution remains to be validated.

## 12. Novelty: clear contribution areas for professor review

### Current contribution statement

> Before You Decide is an interactive experiment in value-sensitive information seeking. It lets users compare what evidence three ethical reference policies request under a cost budget, examine cases where evidence is useful only in combination, and replay how disclosures separate factual uncertainty from persistent rule disagreement.

The practical novelty candidate is this integrated teaching workflow and its authored diagnostic cases. The algorithms used inside it are established methods. First-of-its-kind novelty, improved learning, and generalization have **not** been established.

The working prototype is version 0.2.0. Use [PRESENTATION.md](presentation-before-you-decide.md) for a six-minute walkthrough, measured results, and answers to likely professor questions.

### N1. Value-sensitive inquiry under an information budget

**Question:** Does the ethical rule change which fact is worth paying to reveal?

**Visible feature:** Three agents display different evidence requests on the same partially known case. Fact cards show costs, and every disclosure consumes shared credits. “The expensive report” changes only the cost of reliability relative to the opening junction, isolating an information-cost intervention.

**Implemented evidence:** Each strategy receives the same prior and outcome specification. The utilitarian planner initially requests the two-credit reliability report; minimax risk requests the one-credit brake fact. The duty-based planner reaches the same 50% resolution rate as greedy in this costly case while using 1.5 rather than 2 credits on average.

**Claim boundary:** Ethical input selection and information gain already have prior work. Our contribution candidate is the inspectable comparison, controlled cost case, and educational evaluation, not invention of value-dependent information relevance.

### N2. Complementary evidence and planning beyond immediate gain

**Question:** Can a budgeted question sequence help when every single question has zero immediate gain?

**Visible feature:** In “Two halves of an answer,” matching relay settings determine rescue probability. A depot sticker is irrelevant. Users switch between greedy gain and a budget planner and inspect the planner's conditional next step.

**Implemented evidence:** For the utilitarian and duty-based reference policies, greedy stops unresolved in all eight worlds; the planner asks both relays and resolves in all eight; exact random question selection resolves one third. Minimax risk is already resolved and asks nothing.

**Claim boundary:** Look-ahead planning and complementary information are established concepts. This authored case makes a specific limitation visible and reproducible. It is a deliberate diagnostic example, not held-out evidence that the planner is generally superior.

### N3. An inspectable evidence trail separating uncertainty from disagreement

**Question:** Is a conditional result caused by missing facts, and would additional facts remove disagreement between the specified rules?

**Visible feature:** Replay preserves the evidence available at each step. Stable world tiles show elimination from eight to four to two possibilities. The disagreement panel checks every remaining world. A separate debrief exposes complete information without replacing the budgeted result.

**Implemented evidence:** Earlier replay frames exclude later disclosures and the debrief; replay does not mutate the journal. In the opening junction, low reliability plus no brake leaves no action shared by all three rules in any remaining world. In “Enough is already known,” all agents support the brake with zero disclosures.

**Claim boundary:** Replay is an interface technique; world enumeration is an established analysis method. Their integration makes the project's diagnoses reviewable. It does not expose an LLM's internal reasoning or prove which ethical framework is correct.

### Implementation and research status

| Item | Status |
|---|---|
| Three explicit ethical agents | Implemented; deterministic reference policies |
| N1 cost-aware evidence requests | Implemented |
| N2 complementary-evidence case and budget planner | Implemented |
| N3 evidence replay and disagreement inspection | Implemented |
| Eight cases and exact 64-world comparison per framework | Implemented |
| Professor presentation walkthrough and exported run records | Available |
| A new planning algorithm | Not claimed |
| Independent OpenRouter model decisions and short justifications | Implemented; initial live smoke testing only |
| Explanation-faithfulness experiments | Future work |
| Held-out generalization and educational benefit | Unmeasured |
| Globally unique or first-of-its-kind system | Not established |

### What to evaluate next

1. Ask the professor to review the operational rules and the meanings of each authored case.
2. Write predictions for new case families before running them; include varied costs, alternative priors, and cases where greedy and planning perform equally.
3. Compare a static side-by-side explanation interface with this workflow using counterbalanced student tasks. Measure correct identification of relevant facts, uncertainty versus persistent disagreement, and task time.
4. Evaluate any later language-model agents independently against these references; preserve prompts, model versions, repeated outputs, errors, and unresolved answers.
5. Extend the prior-work review before making stronger originality claims. Sections 10 and 11 record overlaps; the full integrated workflow remains a novelty candidate.

## 13. Independent OpenRouter model comparison

Implemented on 27 September 2026. The three ethical roles remain fixed while users vary the model within a role. This avoids confounding an ethical-rule difference with a model difference.

- Six verified-free candidate IDs are configured: Qwen3.8 27B, Nemotron 3.5 Lightning, Gemma 4 26B A4B, Nemotron 3 Super, Nemotron 3 Ultra, and Inkling Small. Live provider availability varies.
- Nemotron 3 Super is selected by default to conserve requests. A live relay-case call matched the reference decision and next question in 15.887 seconds at a reported cost of zero.
- TypeSafe Jev is included through OpenRouter's Decisions API as an explicitly paid, opt-in, decision-only comparison. It does not generate explanations; paid live testing was not performed.
- No free Gemini or OpenAI text endpoint was found in the current OpenRouter catalog. The UI reports that limitation and can discover eligible free endpoints later.
- Masked prompts contain the same rule and disclosed evidence, without hidden values, debriefs, reference answers, other model outputs, or instructional hints from scenario descriptions.
- Versioned attempts preserve provider identity, actual response time, usage, reported cost, normalized decisions, short justifications, raw final output, failures, and external reference checks.
- Saved results, explicit reruns, two concurrent requests, a local rate guard, and an absolute deadline conserve quota. No automatic paid fallback or reference-answer substitution is used.

The current model evidence is preliminary. Live checks also produced rate limits, access denial, malformed output, truncation, and provider errors. A single correct answer is not an accuracy benchmark, and a matching decision does not establish a correct explanation.

N1–N3 remain the named contribution areas. The model layer lets us begin testing them against independent outputs; it does not make the planning algorithm new or establish general educational benefit.

See [OPENROUTER.md](../llm-agents.md) for exact IDs, source links, protocol details, configuration, and the live validation record.
