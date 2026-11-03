"""Four deterministic decision-theory agents. Each returns a choice, a numeric trace,
the factors its rule read, and an explanation generated only from that trace."""

EPS = 1e-9
LIFE = {"child": 1.0, "adult": 1.0, "elderly": 1.0, "dog": 0.1}          # shared score table, human = 1
LIFE_YEARS = {"child": 70, "adult": 40, "elderly": 15, "dog": 2}          # Sen-inspired welfare stakes
PARAMETERS = {
    "expected_utility": {"score_table": LIFE},
    "sen_welfare": {"life_years": LIFE_YEARS, "normaliser_years": 40, "concern_for_others": 1.5},
    "satisficing": {"inspection_order": ["stay", "swerve"], "human_death_slack": 1.0, "lawful_victim_slack": 0.0},
    "prospect_theory": {"reference_point": "outcome of staying (no intervention)", "alpha": 0.88, "beta": 0.88,
                        "loss_aversion": 2.25, "gamma_gain": 0.61, "gamma_loss": 0.69, "score_table": LIFE},
}
AGENTS = [
    {"id": "expected_utility", "name": "Expected utility", "concept": "von Neumann–Morgenstern rational choice",
     "rule": "Choose the lane with the lower probability-weighted loss, scoring every human 1 and every pet 0.1. Ties keep the car in its lane.",
     "uses": ["count", "species", "probability"]},
    {"id": "sen_welfare", "name": "Welfare and empathy", "concept": "Sen-inspired welfare and commitment",
     "rule": "Score each group by expected life-years lost (child 70, adult 40, elderly 15, pet 2; ÷40) and weight harm to pedestrians, people outside the car, by a concern-for-others factor of 1.5. Choose the lower weighted welfare loss. A project operationalisation inspired by Sen, not a canonical Sen algorithm.",
     "uses": ["count", "species", "age", "role", "probability"]},
    {"id": "satisficing", "name": "Bounded rationality", "concept": "Simon's satisficing",
     "rule": "Inspect lanes in a fixed order, staying first. Accept the first lane whose expected human deaths are within 1 of the best lane and that kills no more law-abiding people than necessary. Age, role and pets beyond species are not inspected.",
     "uses": ["count", "species", "lawful", "probability", "intervention"]},
    {"id": "prospect_theory", "name": "Prospect theory", "concept": "Kahneman–Tversky value and probability weighting",
     "rule": "Code swerving relative to the stay outcome: lives saved are gains, lives newly endangered are losses. v(x)=x^0.88, losses ×2.25, Tversky–Kahneman (1992) probability weights. Swerve only if the prospect value is positive.",
     "uses": ["count", "species", "probability", "intervention"]},
]


def r2(x):
    return round(x + 0.0, 2)


def fmt(x):
    return f"{r2(x):g}"


def lives(option, table=LIFE):
    return sum(c["count"] * table[c["kind"]] for c in option["characters"])


def humans(option):
    return sum(c["count"] for c in option["characters"] if c["kind"] != "dog")


def law_abiding(option):
    """Humans not breaking a traffic rule. Passengers count as law-abiding."""
    return sum(c["count"] for c in option["characters"] if c["kind"] != "dog" and c["lawful"] is not False)


def weight(p, gamma):
    """Tversky–Kahneman (1992) inverse-S probability weighting."""
    if p in (0, 1):
        return float(p)
    return p ** gamma / (p ** gamma + (1 - p) ** gamma) ** (1 / gamma)


def _result(agent_id, choice, scores, trace, explanation, numbers, tie=False):
    agent = next(a for a in AGENTS if a["id"] == agent_id)
    return {"agent": agent_id, "name": agent["name"], "choice": choice, "tie": tie, "scores": scores, "trace": trace,
            "factors_used": agent["uses"], "parameters": PARAMETERS[agent_id], "explanation": explanation,
            "numbers": sorted({r2(n) for n in numbers})}


def _lower(a, b):
    if abs(a - b) < EPS:
        return "stay", True
    return ("stay" if a < b else "swerve"), False


def expected_utility(d):
    loss = {k: d[k]["probability"] * lives(d[k]) for k in ("stay", "swerve")}
    choice, tie = _lower(loss["stay"], loss["swerve"])
    trace = [f"{k}: {d[k]['probability']:.2f} × {fmt(lives(d[k]))} life-units = {fmt(loss[k])} expected loss" for k in loss]
    why = "the expected losses are equal, so the car keeps its lane" if tie else f"{fmt(loss[choice])} is lower than {fmt(loss['swerve' if choice == 'stay' else 'stay'])}"
    text = (f"Expected loss is {fmt(loss['stay'])} lives if the car stays and {fmt(loss['swerve'])} if it swerves, "
            f"counting each human as 1 and each pet as 0.1 and multiplying by the probability. It chooses to {choice} because {why}.")
    return _result("expected_utility", choice, {k: r2(v) for k, v in loss.items()}, trace, text,
                   [*loss.values(), *(lives(d[k]) for k in loss), *(d[k]["probability"] for k in loss), 1, 0.1], tie)


def sen_welfare(d):
    p = PARAMETERS["sen_welfare"]

    def group_loss(option):
        total = 0.0
        for c in option["characters"]:
            care = p["concern_for_others"] if c["role"] == "pedestrian" and c["kind"] != "dog" else 1.0
            total += c["count"] * LIFE_YEARS[c["kind"]] / p["normaliser_years"] * care
        return option["probability"] * total

    loss = {k: group_loss(d[k]) for k in ("stay", "swerve")}
    choice, tie = _lower(loss["stay"], loss["swerve"])
    trace = [f"{k}: Σ count × life-years/40 × (1.5 for pedestrians) × {d[k]['probability']:.2f} = {fmt(loss[k])}" for k in loss]
    why = "the weighted welfare losses are equal, so the car keeps its lane" if tie else f"its weighted welfare loss of {fmt(loss[choice])} is lower"
    text = (f"Weighted welfare loss is {fmt(loss['stay'])} for staying and {fmt(loss['swerve'])} for swerving. "
            f"Each victim counts by expected life-years lost (a child 70, an adult 40, an elderly person 15, a pet 2, divided by 40), "
            f"multiplied by the probability, and harm to pedestrians outside the car is weighted 1.5 times for concern for others. "
            f"It chooses to {choice} because {why}.")
    return _result("sen_welfare", choice, {k: r2(v) for k, v in loss.items()}, trace, text, [*loss.values(), 1.5, 70, 40, 15, 2], tie)


def satisficing(d):
    p = PARAMETERS["satisficing"]
    deaths = {k: d[k]["probability"] * humans(d[k]) for k in ("stay", "swerve")}
    lawful = {k: d[k]["probability"] * law_abiding(d[k]) for k in ("stay", "swerve")}
    best_deaths, best_lawful = min(deaths.values()), min(lawful.values())
    trace, choice, reason = [], None, ""
    for k in p["inspection_order"]:
        ok_deaths = deaths[k] <= best_deaths + p["human_death_slack"] + EPS
        ok_lawful = lawful[k] <= best_lawful + p["lawful_victim_slack"] + EPS
        trace.append(f"inspect {k}: expected human deaths {fmt(deaths[k])} (aspiration ≤ {fmt(best_deaths + 1)}) "
                     f"{'met' if ok_deaths else 'failed'}; law-abiding victims {fmt(lawful[k])} (aspiration ≤ {fmt(best_lawful)}) {'met' if ok_lawful else 'failed'}")
        if ok_deaths and ok_lawful:
            choice = k
            reason = (f"it is the first lane inspected that meets both aspirations: {fmt(deaths[k])} expected human deaths, "
                      f"within 1 of the best ({fmt(best_deaths)}), and {fmt(lawful[k])} law-abiding victims")
            break
    if choice is None:
        choice = next(k for k in p["inspection_order"] if deaths[k] <= best_deaths + p["human_death_slack"] + EPS)
        reason = f"no lane meets both aspirations, so it takes the first lane inspected with expected human deaths within 1 of the best ({fmt(best_deaths)})"
        trace.append(f"fallback: no lane met both aspirations; first lane meeting the death aspiration is {choice}")
    text = (f"It inspects staying first, then swerving, and stops at the first acceptable lane. It counts only human deaths, "
            f"multiplied by the probability, and law-abiding victims. It chooses to {choice} because {reason}.")
    return _result("satisficing", choice, {k: {"human_deaths": r2(deaths[k]), "lawful_victims": r2(lawful[k])} for k in deaths},
                   trace, text, [*deaths.values(), *lawful.values(), best_deaths, best_deaths + 1, 1])


def prospect_theory(d):
    p = PARAMETERS["prospect_theory"]
    saved, endangered = lives(d["stay"]), lives(d["swerve"])
    gain = weight(d["stay"]["probability"], p["gamma_gain"]) * saved ** p["alpha"]
    loss = p["loss_aversion"] * weight(d["swerve"]["probability"], p["gamma_loss"]) * endangered ** p["beta"]
    value = gain - loss
    choice = "swerve" if value > EPS else "stay"
    trace = [f"gain: w+({d['stay']['probability']:.2f}) × {fmt(saved)}^0.88 = {fmt(gain)}",
             f"loss: 2.25 × w−({d['swerve']['probability']:.2f}) × {fmt(endangered)}^0.88 = {fmt(loss)}",
             f"prospect value of swerving = {fmt(gain)} − {fmt(loss)} = {fmt(value)}; staying is the reference point (value 0)"]
    verdict = "positive, so it swerves" if choice == "swerve" else "not positive, so it stays"
    text = (f"Staying is the reference point, and lives are scored with the shared table (human 1, pet 0.1). Swerving gains {fmt(saved)} lives in the stay lane, weighted to {fmt(gain)}, "
            f"but puts {fmt(endangered)} at risk, a loss weighted to {fmt(loss)} after loss aversion of 2.25 and probability weighting. "
            f"The prospect value of swerving is {fmt(value)}, {verdict}.")
    return _result("prospect_theory", choice, {"stay": 0.0, "swerve": r2(value)}, trace, text,
                   [saved, endangered, gain, loss, value, 2.25, 0, 1, 0.1, d["stay"]["probability"], d["swerve"]["probability"]],
                   abs(value) < EPS)


RULES = {"expected_utility": expected_utility, "sen_welfare": sen_welfare, "satisficing": satisficing, "prospect_theory": prospect_theory}


def decide(dilemma):
    return [RULES[a["id"]](dilemma) for a in AGENTS]


def spared_group(dilemma, choice):
    """The group tag that survives a choice. Mirrored variants keep tags, so this compares like with like."""
    return dilemma["swerve" if choice == "stay" else "stay"]["group"]
