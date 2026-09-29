"""Authored pilot cases. Hidden facts have no privileged values in this catalog."""

VERSION = "0.2.0"
FACTS = (
    {"id": "reliability", "title": "Rescue reliability", "question": "How likely is diversion to save the main group?", "label": "Outcome"},
    {"id": "means", "title": "The role of harm", "question": "Is harming the side group a means of rescue or a side effect?", "label": "Causation"},
    {"id": "alternative", "title": "Another way out", "question": "Is a shared-risk emergency brake available?", "label": "Alternatives"},
)
FRAMEWORKS = (
    {"id": "utility", "name": "Utilitarian", "short": "Outcomes", "principle": "Minimize expected deaths across everyone affected.", "rule": "Evaluate each available action by total expected deaths. Keep all exact ties. Each life has equal weight."},
    {"id": "duty", "name": "Duty-based", "short": "Constraints", "principle": "Do not use people as a means of rescue.", "rule": "Exclude diversion when harm to the side group is a necessary means of rescue. Among the remaining available actions, minimize expected deaths. Keep all exact ties. This is a stipulated constrained model, not all of deontology."},
    {"id": "fairness", "name": "Minimax risk", "short": "Fairness", "principle": "Protect the person facing the greatest risk.", "rule": "Minimize the largest individual probability of death. Among ties, minimize total expected deaths; keep remaining ties. This is one explicit fairness criterion."},
)
ACTIONS = {"hold": "Do not intervene", "divert": "Divert", "brake": "Use emergency brake"}
SCENARIOS = [
    {"id": "junction", "number": "01", "title": "The uncertain junction", "setting": "Rail junction", "main": 5, "side": 1, "low": 0.10, "high": 0.90, "side_risk": 0.80, "brake_risk": 0.30,
     "description": "A runaway maintenance trolley is approaching five workers. You can divert it toward a side track occupied by one worker. Three missing facts could change which action the agents support."},
    {"id": "tunnel", "number": "02", "title": "The tunnel signal", "setting": "Underground line", "main": 8, "side": 2, "low": 0.20, "high": 0.85, "side_risk": 0.70, "brake_risk": 0.35,
     "description": "A rail cart is heading toward eight tunnel workers. A switching mechanism can send it toward two others. The reliability report and the mechanism details are still sealed."},
    {"id": "bridge", "number": "03", "title": "The bridge crossing", "setting": "Freight bridge", "main": 3, "side": 2, "low": 0.15, "high": 0.75, "side_risk": 0.90, "brake_risk": 0.40,
     "description": "Three inspectors are trapped on a freight bridge. A diversion would expose two workers on a maintenance spur. The trade-off is close, and the missing facts matter."},
    {"id": "night", "number": "04", "title": "The night shift", "setting": "Maintenance depot", "main": 12, "side": 1, "low": 0.05, "high": 0.95, "side_risk": 0.85, "brake_risk": 0.25,
     "description": "A runaway trolley threatens a twelve-person night crew. One technician is working on the diversion track. You have time to open only two information cards."},
    {"id": "balance", "number": "05", "title": "An equal claim", "setting": "Two-track crossing", "main": 4, "side": 4, "low": 0.25, "high": 0.80, "side_risk": 0.60, "brake_risk": 0.45,
     "description": "Four workers occupy each branch of a crossing. Leaving the trolley on course endangers one group; diversion exposes the other. Equal group sizes do not settle the decision."},
]


SCENARIOS.extend([
    {"id": "costly", "number": "06", "title": "The expensive report", "setting": "Costly information", "challenge": "Spend carefully", "main": 5, "side": 1, "low": 0.10, "high": 0.90, "side_risk": 0.80, "brake_risk": 0.30,
     "costs": {"reliability": 2},
     "description": "The rescue reliability report consumes your entire two-credit budget. Two other facts cost one credit each. Decide whether one expensive answer is worth giving up a second question.",
     "model_note": "The reliability report costs two credits; other facts cost one. The physical outcome model is the same as the opening junction, isolating the effect of information cost."},
    {"id": "relays", "number": "07", "title": "Two halves of an answer", "setting": "Interdependent evidence", "challenge": "Plan two steps ahead", "main": 5, "side": 1, "low": 0.05, "high": 0.95, "side_risk": 0.80, "brake_risk": 0.30,
     "mechanism": "matching_relays", "fixed_means": False, "fixed_alternative": False,
     "facts": [
         {"id": "relay_a", "title": "Relay A setting", "question": "Which setting is the first relay using?", "options": ["Relay A is set to 0", "Relay A is set to 1"]},
         {"id": "relay_b", "title": "Relay B setting", "question": "Which setting is the second relay using?", "options": ["Relay B is set to 0", "Relay B is set to 1"]},
         {"id": "inspection", "title": "Inspection sticker", "question": "Which depot printed the inspection sticker?", "options": ["Printed by East depot", "Printed by West depot"]},
     ],
     "description": "Diversion depends on two independently set relays. Matching settings give a 95% rescue chance; mismatched settings give 5%. One relay setting alone tells you nothing about whether they match.",
     "model_note": "Rescue probability is 95% if the relay settings match, otherwise 5%. Harm to the side group is a foreseen side effect. No emergency brake exists. The sticker's depot has no effect on risk or permissions. Each fact costs one credit."},
    {"id": "settled", "number": "08", "title": "Enough is already known", "setting": "Knowing when to stop", "challenge": "Recognize a settled decision", "main": 5, "side": 1, "low": 0.70, "high": 0.95, "side_risk": 0.80, "brake_risk": 0.02,
     "fixed_alternative": True,
     "facts": [dict(FACTS[0]), dict(FACTS[1]),
               {"id": "inspection", "title": "Inspection sticker", "question": "Which depot printed the inspection sticker?", "options": ["Printed by East depot", "Printed by West depot"]}],
     "description": "An emergency brake is already confirmed available, with a 2% death risk per person. Three facts are still sealed, but the best supported action may already be clear. A question budget is a limit, not a target.",
     "model_note": "The emergency brake is known to be available before any disclosure. Braking gives each person a 2% risk. The inspection sticker does not change the outcome model. All three policies can resolve their decision without asking a question."},
])


def facts_for(scenario):
    return [{**fact, "cost": scenario.get("costs", {}).get(fact["id"], 1)} for fact in scenario.get("facts", FACTS)]


def fact_ids(scenario):
    return tuple(fact["id"] for fact in facts_for(scenario))


def spent_credits(scenario, observed):
    return sum(fact["cost"] for fact in facts_for(scenario) if fact["id"] in observed)


def get_scenario(scenario_id):
    return next((s for s in SCENARIOS if s["id"] == scenario_id), None)


def fact_value(scenario, fact_id, value):
    fact = next(fact for fact in facts_for(scenario) if fact["id"] == fact_id)
    if "options" in fact:
        return fact["options"][int(value)]
    if fact_id == "reliability":
        probability = scenario["high"] if value else scenario["low"]
        return f"{probability:.0%} chance of saving the main group"
    if fact_id == "means":
        return "Harm is a necessary means of rescue" if value else "Harm is a foreseen side effect"
    return "Emergency brake is available" if value else "No emergency brake is available"


def fact_cards(scenario, observed):
    return [{**fact, "revealed": fact["id"] in observed,
             "value": fact_value(scenario, fact["id"], observed[fact["id"]]) if fact["id"] in observed else None,
             "options": [fact_value(scenario, fact["id"], v) for v in (False, True)]} for fact in facts_for(scenario)]
