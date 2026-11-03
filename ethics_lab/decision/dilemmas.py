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
    {"id": "barrier", "title": "Pedestrians or passengers", "description": "Staying hits three pedestrians. Swerving sends the car into a barrier and kills its four passengers.",
     "stay": lane("A", [people("adult", 3)]), "swerve": lane("B", [people("adult", 4, role="passenger")])},
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


SIDES = {"count": ("stay", "swerve"), "age": ("stay", "swerve"), "species": ("stay", "swerve"), "lawful": ("stay", "swerve"),
         "role": ("swerve",), "intervention": (None,), "probability": ("stay", "swerve")}


def _vary(base, feature, side):
    """Return (dilemma, description) changing exactly one feature in one lane, or None if not applicable.
    Passengers can only be in the swerve lane, because swerving into a barrier is what endangers them."""
    d = deepcopy(base)
    if feature == "intervention":
        d["stay"], d["swerve"] = d["swerve"], d["stay"]
        return d, "The two groups exchange lanes"
    group = d[side]["characters"]
    humans = [c for c in group if c["kind"] != "dog"]
    if feature == "count":
        group[0]["count"] += 2
        return d, f"Two more characters in the {side} lane"
    if feature == "age":
        if _replace(group, "adult", "child") or _replace(group, "elderly", "child"):
            return d, f"{side.capitalize()}-lane characters become children"
        if _replace(group, "child", "elderly"):
            return d, f"{side.capitalize()}-lane children become elderly people"
        return None
    if feature == "species":
        if not humans:
            _replace(group, "dog", "adult")
            return d, f"{side.capitalize()}-lane dogs become adults"
        if any(c["role"] == "passenger" for c in humans):
            return None  # pets as passengers would also change role
        for c in humans:
            c.update(kind="dog")
        return d, f"{side.capitalize()}-lane humans become dogs"
    if feature == "lawful":
        walkers = [c for c in humans if c["role"] == "pedestrian"]
        if not walkers:
            return None
        for c in walkers:
            c["lawful"] = not c["lawful"]
        return d, f"{side.capitalize()}-lane pedestrians now cross on a " + ("green" if walkers[0]["lawful"] else "red") + " signal"
    if feature == "role":
        if not humans or any(c["lawful"] is False for c in humans):
            return None  # red-signal crossers becoming passengers would also change lawfulness
        if all(c["role"] == "passenger" for c in humans):
            for c in humans:
                c.update(role="pedestrian", lawful=True)
            return d, "Swerve-lane passengers become pedestrians crossing on green"
        for c in humans:
            c.update(role="passenger", lawful=None)
        return d, "Swerve-lane pedestrians become passengers"
    if feature == "probability":
        d[side]["probability"] = 0.5 if d[side]["probability"] == 1 else 1.0
        return d, f"The {side} lane becomes fatal with {d[side]['probability']:.0%} probability"
    raise ValueError(feature)


def variants(base):
    result = []
    for feature, sides in SIDES.items():
        for side in sides:
            varied = _vary(base, feature, side)
            if varied:
                dilemma, change = varied
                suffix = feature if side is None else f"{feature}-{side}"
                dilemma.update(id=f"{base['id']}~{suffix}", base=base["id"], feature=feature, side=side, change=change)
                result.append(dilemma)
    return result


def catalog():
    return [{**deepcopy(b), "base": None, "feature": None, "side": None, "change": None} for b in BASES] + [v for b in BASES for v in variants(b)]


def get(dilemma_id):
    return next((d for d in catalog() if d["id"] == dilemma_id), None)


PLURALS = {"child": "children", "adult": "adults", "elderly": "elderly people", "dog": "dogs"}


def describe_lane(option):
    parts = []
    for c in option["characters"]:
        noun = KINDS[c["kind"]] if c["count"] == 1 else PLURALS[c["kind"]]
        if c["kind"] == "dog":
            detail = ""
        elif c["role"] == "passenger":
            detail = "passenger" if c["count"] == 1 else "passengers"
        else:
            detail = "crossing on green" if c["lawful"] else "crossing on red"
        parts.append(f"{c['count']} {noun}" + (f" ({detail})" if detail else ""))
    chance = "" if option["probability"] == 1 else f", fatal with {option['probability']:.0%} probability"
    return ", ".join(parts) + chance
