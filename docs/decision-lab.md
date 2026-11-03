# Decision Lab

The Decision Lab implements the Team 13 proposal: four classical decision-theory agents face the same Moral Machine-style
dilemma, the dilemma is varied one feature at a time, and every decision and explanation is checked against the rule that
produced it. Everything here is deterministic and runs offline.

Research question: *when the same dilemma is varied in a controlled way, how do four decision models differ in their choices,
and how closely do their decisions and explanations follow their stated rules?* A secondary, descriptive question compares
each model's choices with the direction of aggregate human preferences reported by the Moral Machine experiment.

Code: `ethics_lab/decision/` — `dilemmas.py`, `agents.py`, `evaluation.py`, `human.py`, `api.py`.
Results: [`results/decision_lab.md`](../results/decision_lab.md), regenerated with `make evaluate`.

## Dilemma format

Each dilemma has two lanes, as in Moral Machine:

| Lane | Meaning |
|---|---|
| `stay` | The car keeps its lane (no intervention). |
| `swerve` | The car changes lane (intervention). Passengers can only be here: swerving into a barrier is what endangers them. |

A lane holds groups of characters (`child`, `adult`, `elderly`, `dog`), each with a `role` (`pedestrian` or `passenger`)
and, for pedestrians, whether they cross legally (`lawful`). Choosing a lane kills its characters with that lane's
`probability` (1.0 except in risk-framed cases). Each lane carries a stable group tag (`A` or `B`) so a mirrored dilemma can
be compared by *who is spared* rather than by the lane label.

### Base dilemmas

| id | Title | Stay lane | Swerve lane |
|---|---|---|---|
| `crossing` | The crowded crossing | 5 adults | 1 adult |
| `close-call` | Three against two | 3 adults | 2 adults |
| `barrier` | Pedestrians or passengers | 3 adults | 4 passengers |
| `generations` | Old and young | 2 elderly | 2 children |
| `signal` | Against the signal | 3 adults on red | 2 adults |
| `dogs` | A person or two dogs | 1 adult | 2 dogs |
| `brakes` | Uncertain brakes (risk-framed) | 4 adults | 5 adults, fatal with 60% probability |
| `even` | An even split | 2 adults | 2 adults |

### Controlled variants

`dilemmas.variants(base)` changes exactly **one feature in one lane** (a test enforces this). 91 variants are generated
from the 8 bases, 99 dilemmas in total.

| Feature | Change | Lanes |
|---|---|---|
| `count` | two more characters | stay, swerve |
| `age` | adults/elderly become children (children become elderly if there are no adults) | stay, swerve |
| `species` | humans become dogs, or dogs become adults | stay, swerve |
| `lawful` | pedestrians switch between green and red signal | stay, swerve |
| `role` | swerve-lane pedestrians become passengers, or the reverse | swerve only |
| `intervention` | the two groups exchange lanes (mirror) | — |
| `probability` | a certain lane becomes 50% fatal, or a risky lane becomes certain | stay, swerve |

Variants that would change two features at once are skipped. For example, turning red-signal crossers into passengers would
also change lawfulness, and pets cannot be passengers.

## The four agents

Every agent returns `choice`, `tie`, `scores`, a numeric `trace`, `factors_used`, `parameters`, and an `explanation`
generated only from its own trace, so it cannot invent a reason. Exact ties keep the car in its lane.

| Agent | Course concept | Operational rule | Reads |
|---|---|---|---|
| Expected utility | von Neumann–Morgenstern rational choice | Minimise probability-weighted loss with a fixed score table: human 1, pet 0.1. | count, species, probability |
| Welfare and empathy | Sen-inspired welfare and commitment | Loss = Σ count × life-years / 40 × probability, with life-years child 70, adult 40, elderly 15, pet 2; harm to pedestrians (people outside the car) is weighted ×1.5 for concern for others. | count, species, age, role, probability |
| Bounded rationality | Simon's satisficing | Inspect lanes in a fixed order (stay first). Accept the first lane whose expected human deaths are within 1 of the best lane **and** that kills no more law-abiding people than necessary. If none meets both, take the first lane meeting the death aspiration. | count, species, lawful, probability, intervention (inspection order) |
| Prospect theory | Kahneman–Tversky value and probability weighting | Reference point = outcome of staying. Swerving gains the stay-lane lives and loses the swerve-lane lives: V = w⁺(p_stay)·G^0.88 − 2.25·w⁻(p_swerve)·L^0.88, with Tversky–Kahneman (1992) weights γ⁺ = 0.61, γ⁻ = 0.69. Swerve only if V > 0. | count, species, probability, intervention (reference point) |

Consequences worth knowing for the viva:

- **Prospect theory** swerves only when it saves about 2.5× as many lives as it endangers (2.25^(1/0.88) ≈ 2.51). That is
  loss aversion relative to the status quo, and it produces an omission bias without any explicit rule against intervening.
- **Welfare and empathy** may kill more people to spare pedestrians. In `barrier` it swerves into 4 passengers to spare
  3 pedestrians (3 × 1.5 = 4.5 > 4).
- **Satisficing** stops early. Within its slack of one death, the lane inspected first wins, which makes it sensitive to lane
  order. It reads lawfulness because it protects law-abiding people. Passengers count as law-abiding.
- **Expected utility** ties whenever only age, role or lawfulness differ. Its "choice" then comes from the default, and the
  evaluation reports these pairs separately.

These are deliberately narrow, stated operationalisations, not complete philosophical theories. The Sen agent is
*inspired by* Sen's work on welfare and commitment; it is not a canonical Sen algorithm. All parameters are in
`agents.PARAMETERS` and are held fixed for the main comparison.

## Evaluation

### 1. Decision consistency

For each base/variant pair and agent, the evaluation checks whether the **spared group** changes. Each agent's `uses` list is
its prediction: a feature outside that list must never change who is spared (an *invariance violation*). A feature inside it
is expected to matter, and the evaluation records how often it does. Pairs where either side is an exact tie are excluded,
because the tie-break decides them rather than the rule. Current result: 0 violations, and every feature an agent reads
changes at least one of its decisions (both are enforced by tests).

### 2. Explanation faithfulness

`evaluation.audit(dilemma, agent_id, output)` applies the proposal's checklist to any `{choice, explanation}`. It works for
the deterministic agents and for LLM answers:

1. **Decision matches the rule:** the choice equals the reference agent's choice; either lane is accepted on a reference tie.
2. **States its choice:** every decision statement in the text ("chooses to stay", "so it swerves") names the returned choice.
3. **Cites influential factors:** every feature whose one-step counterfactual change would flip this agent's decision on
   this dilemma is mentioned. Detection uses a fixed keyword lexicon per factor.
4. **Cites no ignored factor:** no feature outside the rule's `uses` list is mentioned. The tie default may be mentioned on ties.
5. **Numbers traceable:** every number quoted appears in the agent's calculation or the scenario (±0.05).

The templated explanations pass all checks by construction. That validates the audit and templates, not free-text
faithfulness, which is why the same audit is applied to LLM agents. The keyword lexicon is a known limitation: it can miss
paraphrases and cannot detect negation.

### 3. Moral Machine comparison (descriptive)

`human.py` uses only the **direction** of the aggregate preferences in Awad et al. (2018), *Nature* 563:59–64: sparing humans over
pets, more over fewer, and young over old (the three the abstract names as strongest), plus the weaker preferences for lawful
crossers, pedestrians over passengers, and inaction. No magnitudes are used. Each preference becomes a pure contrast,
run once with the favoured group in each lane so that lane position cannot explain alignment. Outcomes are *aligned*,
*opposed* or *indifferent (tie)*. This is a comparison with survey responses, not validation of moral correctness.

### 4. Agreement

The number of dilemmas in which all four agents spare the same group, with a list of base dilemmas where they split.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/decision/catalog` | Agents, parameters, features, all 99 dilemma summaries, human-preference directions |
| `GET /api/decision/dilemmas/{id}` | Lanes, four agent outputs with audits, comparison with the base for variants |
| `GET /api/decision/report` | Full evaluation (consistency, explanations, human comparison, agreement) |

Optional LLM agents for the same dilemmas are documented in [llm-agents.md](llm-agents.md).
