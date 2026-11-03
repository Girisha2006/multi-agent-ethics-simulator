# Final presentation — six slides and a live demo

Slide outline in the order the course guidelines ask for: title, problem, related work, methods, results, project
management. Numbers come from `results/decision_lab.md`; re-run `make evaluate` before the talk.

## 1. Title

**Multi-agent Ethics Simulator: controlled variation of four decision models**
Team 13 — Humanity's First Exam (HFE) · Demo track · Agents & Game Theory

## 2. Problem

- One decision rule hides assumptions: whose welfare counts, how risk is treated, how much is inspected.
- Teacher feedback on the proposal: side-by-side frameworks are not new. The value is in **what controlled changes reveal**
  and in **checking whether explanations are consistent and justified**.
- Research question: *when a dilemma is varied one feature at a time, how do four decision models differ, and do their
  decisions and explanations follow their stated rules?*

## 3. Related work

- Moral Machine (Awad et al., 2018): ~40M human judgments; directions we compare against.
- Expected utility (von Neumann–Morgenstern), Sen's welfare and commitment, Simon's satisficing, prospect theory
  (Kahneman–Tversky 1979; parameters from 1992).
- Computational moral decision-making on Moral Machine data (Kim et al., 2018); controlled variation in OffTheRails.
- Our addition at course scale: one-feature variants + an automatic explanation audit that also applies to LLM answers.

## 4. Methods

- 8 base dilemmas in Moral Machine format → 91 one-feature variants → 99 dilemmas (test-enforced).
- Four deterministic agents with stated parameters; explanations generated from their numeric traces.
- Evaluation: invariance violations, counterfactual influential factors, 5-item explanation audit, Moral Machine
  directions in both lane positions, agreement.
- Optional free LLM agents: one batched request per dilemma, quota counted before sending, cache, cooldowns, replay of real
  recordings.

## 5. Results

- 0 invariance violations; every factor an agent reads changes at least one of its decisions.
- All 99 templated explanations per agent pass the audit (validates the audit, not free text).
- Agreement on 58 of 99 dilemmas. Splits: *Three against two*, *Pedestrians or passengers*, *Against the signal*,
  *Uncertain brakes*.
- Prospect theory shows an omission bias with no explicit rule (needs ≈2.5× lives saved). Satisficing is lane-order
  sensitive. Only the welfare agent follows the age and pedestrian preferences in both positions.
- LLM pilot (1 free model, 8 base dilemmas, 8 requests): matches the rule 7/8 for expected utility and welfare, 4/8 for
  satisficing, 6/8 for prospect theory; almost no explanation passes the full audit (missing influential factors,
  untraceable prospect-theory arithmetic, text that argues for the other lane).

## 6. Project management

- Fill in from the report's §7 (who did what) and the commit history. Mention the AI-usage disclosure (§8).
- Limits and next steps: small authored set, fixed parameters, keyword-based audit, free-model availability.

## Live demo (about 5 minutes)

The repository ships 8 real recordings of the base dilemmas, so the LLM tab works without a key or quota. With the key,
a live run costs 1 request; clicking Run again on the same dilemma reuses the saved result for free.

1. `./start.sh` → open <http://127.0.0.1:8000/decision>.
2. **Dilemmas tab:** open *Pedestrians or passengers*. Show four choices and the welfare agent's ×1.5 pedestrian weight.
3. Click the *role* variant. Show which agents change and that the base comparison marks it as expected.
4. Open *Uncertain brakes* and its *probability* variant. Prospect theory's reference point and loss aversion.
5. **Evaluation tab:** consistency table (0 violations), audit pass rates, Moral Machine matrix.
6. **LLM tab:** show the quota meter. If live quota is available, run one dilemma (1 request). Otherwise show a
   recorded result and say that it is a recording, with its date.

Backup: everything except the LLM tab works without a network. Recordings, once made, replay without a key.
