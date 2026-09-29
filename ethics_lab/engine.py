"""Pure reference policies. Planners receive observations, never the actual hidden world."""

from collections import Counter
from functools import lru_cache
from itertools import product
from math import log2

from .scenarios import ACTIONS, FACTS, FRAMEWORKS, fact_ids, facts_for, fact_value

FACT_IDS = tuple(f["id"] for f in FACTS)
EPSILON = 1e-9


def worlds(observed, scenario=None):
    keys = fact_ids(scenario) if scenario is not None else FACT_IDS
    return [dict(zip(keys, values)) for values in product((False, True), repeat=len(keys))
            if all(dict(zip(keys, values))[key] == value for key, value in observed.items())]


def physical_facts(scenario, world):
    reliable = world["relay_a"] == world["relay_b"] if scenario.get("mechanism") == "matching_relays" else world["reliability"]
    return {"success": scenario["high"] if reliable else scenario["low"],
            "means": scenario["fixed_means"] if "fixed_means" in scenario else world["means"],
            "alternative": scenario["fixed_alternative"] if "fixed_alternative" in scenario else world["alternative"]}


def outcomes(scenario, world):
    facts = physical_facts(scenario, world)
    options = {"hold": {"main_risk": 1.0, "side_risk": 0.0},
               "divert": {"main_risk": 1 - facts["success"], "side_risk": scenario["side_risk"]}}
    if facts["alternative"]:
        options["brake"] = {"main_risk": scenario["brake_risk"], "side_risk": scenario["brake_risk"]}
    for option in options.values():
        option["expected_deaths"] = scenario["main"] * option["main_risk"] + scenario["side"] * option["side_risk"]
        option["max_risk"] = max(option["main_risk"], option["side_risk"])
    return options


def allowed_actions(scenario, world, framework_id):
    options = outcomes(scenario, world)
    if framework_id == "duty" and physical_facts(scenario, world)["means"]:
        options.pop("divert")
    if framework_id == "fairness":
        best_risk = min(value["max_risk"] for value in options.values())
        options = {action: value for action, value in options.items() if abs(value["max_risk"] - best_risk) < EPSILON}
    best = min(value["expected_deaths"] for value in options.values())
    return tuple(sorted(action for action, value in options.items() if abs(value["expected_deaths"] - best) < EPSILON))


def decision_summary(scenario, observed, framework_id):
    possible = worlds(observed, scenario)
    choices = [allowed_actions(scenario, world, framework_id) for world in possible]
    robust = sorted(set.intersection(*(set(choice) for choice in choices)))
    support = {action: sum(action in choice for choice in choices) for action in ACTIONS}
    return {"robust_actions": robust, "support": support, "world_count": len(possible), "choices": choices}


def entropy(choices):
    counts = Counter(choices)
    total = sum(counts.values())
    return -sum((count / total) * log2(count / total) for count in counts.values())


def question_scores(scenario, observed, framework_id):
    summary = decision_summary(scenario, observed, framework_id)
    before = entropy(summary["choices"])
    scores = []
    for fact in facts_for(scenario):
        if fact["id"] in observed:
            continue
        conditional = sum(entropy(decision_summary(scenario, {**observed, fact["id"]: value}, framework_id)["choices"]) / 2
                          for value in (False, True))
        gain = max(0.0, before - conditional) if not summary["robust_actions"] else 0.0
        scores.append({"fact_id": fact["id"], "title": fact["title"], "question": fact["question"], "cost": fact["cost"],
                       "gain": round(gain, 6), "gain_per_credit": round(gain / fact["cost"], 6)})
    return sorted(scores, key=lambda score: (-score["gain_per_credit"], fact_ids(scenario).index(score["fact_id"])))


def optimal_plan(scenario, observed, framework_id, budget):
    """Exact adaptive finite-budget plan: maximize resolution probability, then minimize cost.

    Expectations use the independent fair-bit prior. Stopping is a candidate at every node.
    No sampled hidden values enter the search. Catalog order breaks remaining ties.
    """
    facts = facts_for(scenario)

    @lru_cache(maxsize=None)
    def solve(items, remaining):
        known = dict(items)
        resolved = bool(decision_summary(scenario, known, framework_id)["robust_actions"])
        best = {"fact_id": None, "resolved_probability": float(resolved), "expected_cost": 0.0, "branches": []}
        if resolved or remaining <= 0:
            return best
        for fact in facts:
            if fact["id"] in known or fact["cost"] > remaining:
                continue
            children = [solve(tuple(sorted({**known, fact["id"]: value}.items())), remaining - fact["cost"]) for value in (False, True)]
            probability = sum(child["resolved_probability"] for child in children) / 2
            cost = fact["cost"] + sum(child["expected_cost"] for child in children) / 2
            if probability > best["resolved_probability"] + EPSILON or (abs(probability - best["resolved_probability"]) < EPSILON and cost < best["expected_cost"] - EPSILON):
                best = {"fact_id": fact["id"], "title": fact["title"], "question": fact["question"], "cost": fact["cost"],
                        "resolved_probability": probability, "expected_cost": cost,
                        "branches": [{"answer": value, "label": fact_value(scenario, fact["id"], value), "plan": child}
                                     for value, child in zip((False, True), children)]}
        return best

    return solve(tuple(sorted(observed.items())), budget)


def agents(scenario, observed, remaining):
    result = []
    for framework in FRAMEWORKS:
        summary = decision_summary(scenario, observed, framework["id"])
        scores = question_scores(scenario, observed, framework["id"])
        affordable = [score for score in scores if score["cost"] <= remaining]
        next_question = affordable[0] if affordable and affordable[0]["gain"] > EPSILON else None
        plan = optimal_plan(scenario, observed, framework["id"], remaining)
        robust = summary["robust_actions"]
        if robust:
            reason = f"{', '.join(ACTIONS[action] for action in robust)} is supported in all {summary['world_count']} remaining factual possibilities under this rule."
        else:
            reason = f"No single action is supported across all {summary['world_count']} remaining factual possibilities. The decision depends on unrevealed facts."
        result.append({**framework, **{k: v for k, v in summary.items() if k != "choices"}, "reason": reason,
                       "next_question": next_question, "optimal_plan": plan, "question_scores": scores,
                       "status": "Resolved" if robust else "Conditional"})
    return result


def analyze(scenario, observed):
    rows = []
    universe = worlds({}, scenario)
    for index, world in enumerate(universe):
        if not all(world[key] == value for key, value in observed.items()):
            continue
        choices = {framework["id"]: allowed_actions(scenario, world, framework["id"]) for framework in FRAMEWORKS}
        shared = sorted(set.intersection(*(set(choice) for choice in choices.values())))
        rows.append({"id": index + 1, "facts": world,
                     "labels": {key: fact_value(scenario, key, value) for key, value in world.items()},
                     "actions": choices, "shared_actions": shared, "outcomes": outcomes(scenario, world)})
    agreements = sum(bool(row["shared_actions"]) for row in rows)
    if agreements == len(rows):
        title = "Compatible in every remaining possibility"
        description = "The three rules share at least one supported action in each possible world. The shared action can still differ between worlds."
        kind = "compatible"
    elif agreements == 0:
        title = "Disagreement survives every remaining possibility"
        description = "No remaining factual completion gives all three rules a shared action. Within these specified models and facts, more disclosure cannot remove the disagreement."
        kind = "persistent"
    else:
        title = "The missing facts can change agreement"
        description = f"The rules share an action in {agreements} of {len(rows)} remaining possibilities. Revealing facts can clarify whether their recommendations are compatible."
        kind = "contingent"
    return {"kind": kind, "title": title, "description": description, "agreement_worlds": agreements,
            "total_worlds": len(rows), "universe_count": len(universe), "rows": rows}


def policy_trial(scenario, actual, framework_id, policy="adaptive", budget=2):
    observed, history, spent = {}, [], 0
    while spent < budget:
        if decision_summary(scenario, observed, framework_id)["robust_actions"]:
            break
        if policy == "optimal":
            question = optimal_plan(scenario, observed, framework_id, budget - spent)
            if question["fact_id"] is None:
                break
        else:
            ranked = [score for score in question_scores(scenario, observed, framework_id) if score["cost"] <= budget - spent]
            if not ranked or ranked[0]["gain"] <= EPSILON:
                break
            question = ranked[0]
        observed[question["fact_id"]] = actual[question["fact_id"]]
        history.append(question["fact_id"])
        spent += question["cost"]
    return {"resolved": float(bool(decision_summary(scenario, observed, framework_id)["robust_actions"])),
            "questions": len(history), "credits": spent, "history": history}


def random_trial(scenario, actual, framework_id, observed=None, remaining=2):
    """Exact expectation of uniformly selecting an affordable undisclosed question."""
    observed = observed or {}
    if decision_summary(scenario, observed, framework_id)["robust_actions"]:
        return {"resolved": 1.0, "questions": 0.0, "credits": 0.0}
    available = [fact for fact in facts_for(scenario) if fact["id"] not in observed and fact["cost"] <= remaining]
    if not available:
        return {"resolved": 0.0, "questions": 0.0, "credits": 0.0}
    branches = []
    for fact in available:
        child = random_trial(scenario, actual, framework_id, {**observed, fact["id"]: actual[fact["id"]]}, remaining - fact["cost"])
        branches.append({"resolved": child["resolved"], "questions": 1 + child["questions"], "credits": fact["cost"] + child["credits"]})
    return {key: sum(branch[key] for branch in branches) / len(branches) for key in ("resolved", "questions", "credits")}


def benchmark(scenarios):
    def summarize(trials):
        return {"trials": len(trials), "resolved_rate": sum(t["resolved"] for t in trials) / len(trials),
                "mean_questions": sum(t["questions"] for t in trials) / len(trials),
                "mean_credits": sum(t["credits"] for t in trials) / len(trials)}

    results, per_case = [], []
    totals = {f["id"]: {policy: [] for policy in ("adaptive", "optimal", "random")} for f in FRAMEWORKS}
    for scenario in scenarios:
        case_results = []
        for framework in FRAMEWORKS:
            trials = {policy: [] for policy in ("adaptive", "optimal", "random")}
            for actual in worlds({}, scenario):
                for policy in ("adaptive", "optimal"):
                    trials[policy].append(policy_trial(scenario, actual, framework["id"], policy))
                trials["random"].append(random_trial(scenario, actual, framework["id"]))
            case_results.append({"framework": framework["name"], **{p: summarize(t) for p, t in trials.items()}})
            for policy, items in trials.items():
                totals[framework["id"]][policy].extend(items)
        per_case.append({"scenario_id": scenario["id"], "title": scenario["title"], "results": case_results})
    for framework in FRAMEWORKS:
        results.append({"framework": framework["name"], **{p: summarize(t) for p, t in totals[framework["id"]].items()}})
    return {"results": results, "per_case": per_case, "cases": sum(len(worlds({}, s)) for s in scenarios),
            "method": "Exact enumeration of equally weighted worlds. Each framework has two credits in an independent run. Greedy maximizes immediate information gain per credit and stops at zero gain. The optimal adaptive planner maximizes final resolution probability, then minimizes expected credits. Random chooses uniformly among affordable facts. All stop when resolved. These policies have different objectives; results are an authored reference demonstration, not LLM measurements or moral accuracy."}
