"""Two-lane dilemmas in the Moral Machine format and one-feature controlled variants.

Each dilemma has a "stay" lane (no intervention) and a "swerve" lane (intervention).
The car's action kills the characters in the chosen lane with that lane's probability.
Groups carry a stable tag ("A" or "B") so a mirrored variant can be compared by who is spared.
"""
from copy import deepcopy

VERSION = "decision-1.0"
KINDS = {"child": "child", "adult": "adult", "elderly": "elderly person", "dog": "dog"}
FEATURES = {
    "count": "Number of characters",
    "age": "Age of characters",
    "species": "Humans versus pets",
    "lawful": "Crossing on a red or green signal",
    "role": "Pedestrians versus passengers",
    "intervention": "Which lane needs a swerve",
    "probability": "Probability that the lane is fatal",
}


def lane(group, characters, probability=1.0):
    return {"group": group, "probability": probability, "characters": characters}


def people(kind, count, role="pedestrian", lawful=True):
    return {"kind": kind, "count": count, "role": role, "lawful": lawful if role == "pedestrian" else None}


BASES = [
    {"id": "crossing", "title": "The crowded crossing", "description": "Five pedestrians cross on a green signal ahead. Swerving hits one pedestrian, also crossing legally.",
     "stay": lane("A", [people("adult", 5)]), "swerve": lane("B", [people("adult", 1)])},
    {"id": "close-call", "title": "Three against two", "description": "Three pedestrians ahead, two in the other lane. Every rule must weigh a small difference.",
     "stay": lane("A", [people("adult", 3)]), "swerve": lane("B", [people("adult", 2)])},
    {"id": "barrier", "title": "Pedestrians or passengers", "description": "Staying hits two pedestrians. Swerving sends the car into a barrier and kills its two passengers.",
     "stay": lane("A", [people("adult", 2)]), "swerve": lane("B", [people("adult", 2, role="passenger")])},
    {"id": "generations", "title": "Old and young", "description": "Two elderly pedestrians are ahead. Two children cross in the other lane.",
     "stay": lane("A", [people("elderly", 2)]), "swerve": lane("B", [people("child", 2)])},
    {"id": "signal", "title": "Against the signal", "description": "Three pedestrians cross on a red signal ahead. Two others in the swerve lane cross legally.",
     "stay": lane("A", [people("adult", 3, lawful=False)]), "swerve": lane("B", [people("adult", 2)])},
    {"id": "dogs", "title": "A person or two dogs", "description": "One pedestrian is ahead. Swerving would hit two dogs.",
     "stay": lane("A", [people("adult", 1)]), "swerve": lane("B", [people("dog", 2)])},
    {"id": "brakes", "title": "Uncertain brakes", "description": "Staying certainly kills four pedestrians. Swerving with failing brakes kills five others with 60% probability.",
     "stay": lane("A", [people("adult", 4)]), "swerve": lane("B", [people("adult", 5)], 0.6), "risk_framed": True},
    {"id": "even", "title": "An even split", "description": "Two pedestrians in each lane, all crossing legally. Nothing but the swerve separates the lanes.",
     "stay": lane("A", [people("adult", 2)]), "swerve": lane("B", [people("adult", 2)])},
]


def _replace(characters, source, target):
    changed = False
    for item in characters:
        if item["kind"] == source:
            item["kind"], changed = target, True
    return changed


def _vary(base, feature):
    """Return (dilemma, description) changing exactly one feature, or None if not applicable."""
    d = deepcopy(base)
    stay, swerve = d["stay"]["characters"], d["swerve"]["characters"]
    if feature == "count":
        stay[0]["count"] += 2
        return d, "Two more characters in the stay lane"
    if feature == "age":
        if _replace(stay, "adult", "child") or _replace(stay, "elderly", "child"):
            return d, "Stay-lane characters become children"
        return None
    if feature == "species":
        if any(c["kind"] == "dog" for c in swerve):
            _replace(swerve, "dog", "adult")
            return d, "Swerve-lane dogs become adults"
        for c in swerve:
            c.update(kind="dog", role="pedestrian", lawful=True)
        return d, "Swerve-lane humans become dogs"
    if feature == "lawful":
        walkers = [c for c in stay if c["role"] == "pedestrian" and c["kind"] != "dog"]
        if not walkers:
            return None
        for c in walkers:
            c["lawful"] = not c["lawful"]
        return d, "Stay-lane pedestrians now cross on a " + ("green" if walkers[0]["lawful"] else "red") + " signal"
    if feature == "role":
        if all(c["kind"] == "dog" for c in swerve):
            return None
        if all(c["role"] == "passenger" for c in swerve):
            for c in swerve:
                c.update(role="pedestrian", lawful=True)
            return d, "Swerve-lane passengers become pedestrians"
        for c in swerve:
            if c["kind"] != "dog":
                c.update(role="passenger", lawful=None)
        return d, "Swerve-lane pedestrians become passengers"
    if feature == "intervention":
        d["stay"], d["swerve"] = d["swerve"], d["stay"]
        return d, "The two groups exchange lanes"
    if feature == "probability":
        target = "swerve" if d["swerve"]["probability"] == 1 else "stay"
        d[target]["probability"] = 0.5
        return d, f"The {target} lane becomes fatal with 50% probability"
    raise ValueError(feature)


def variants(base):
    result = []
    for feature in FEATURES:
        varied = _vary(base, feature)
        if varied:
            dilemma, change = varied
            dilemma.update(id=f"{base['id']}~{feature}", base=base["id"], feature=feature, change=change)
            result.append(dilemma)
    return result


def catalog():
    return [{**deepcopy(b), "base": None, "feature": None, "change": None} for b in BASES] + [v for b in BASES for v in variants(b)]


def get(dilemma_id):
    return next((d for d in catalog() if d["id"] == dilemma_id), None)


def describe_lane(option):
    parts = []
    for c in option["characters"]:
        noun = KINDS[c["kind"]] + ("s" if c["count"] != 1 and c["kind"] != "elderly" else "")
        if c["kind"] == "elderly" and c["count"] != 1:
            noun = "elderly people"
        detail = "passenger" + ("s" if c["count"] != 1 else "") if c["role"] == "passenger" else (
            "crossing on green" if c["lawful"] else "crossing on red") if c["kind"] != "dog" else ""
        parts.append(f"{c['count']} {noun}" + (f" ({detail})" if detail else ""))
    chance = "" if option["probability"] == 1 else f", fatal with {option['probability']:.0%} probability"
    return ", ".join(parts) + chance
