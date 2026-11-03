from ethics_lab.decision import dilemmas


def flat(d):
    return {side: (d[side]["group"], d[side]["probability"], tuple(sorted(tuple(sorted(c.items())) for c in d[side]["characters"])))
            for side in ("stay", "swerve")}


def test_catalog_ids_are_unique_and_variants_point_to_existing_bases():
    items = dilemmas.catalog()
    ids = [d["id"] for d in items]
    assert len(ids) == len(set(ids))
    bases = {b["id"] for b in dilemmas.BASES}
    assert all(d["base"] in bases for d in items if d["base"])
    assert all(d["feature"] in dilemmas.FEATURES for d in items if d["base"])


def test_each_variant_changes_exactly_one_feature_of_its_base():
    for base in dilemmas.BASES:
        for v in dilemmas.variants(base):
            before, after = flat(base), flat(v)
            assert before != after, v["id"]
            if v["feature"] == "intervention":
                assert after["stay"] == before["swerve"] and after["swerve"] == before["stay"]
                continue
            changed = [side for side in ("stay", "swerve") if before[side] != after[side]]
            assert len(changed) == 1, v["id"]
            side = changed[0]
            if v["feature"] == "probability":
                assert before[side][2] == after[side][2] and before[side][1] != after[side][1]
            else:
                assert before[side][1] == after[side][1]


def test_variants_do_not_mutate_bases():
    snapshot = [flat(b) for b in dilemmas.BASES]
    dilemmas.catalog()
    assert snapshot == [flat(b) for b in dilemmas.BASES]


def test_describe_lane_is_human_readable():
    assert dilemmas.describe_lane(dilemmas.get("signal")["stay"]) == "3 adults (crossing on red)"
    assert dilemmas.describe_lane(dilemmas.get("brakes")["swerve"]) == "5 adults (crossing on green), fatal with 60% probability"
    assert dilemmas.describe_lane(dilemmas.get("barrier")["swerve"]) == "4 adults (passengers)"


def test_role_variant_never_changes_lawfulness():
    from ethics_lab.decision import agents
    for d in dilemmas.catalog():
        varied = dilemmas._vary(d, "role", "swerve")
        if varied:
            assert agents.law_abiding(d["swerve"]) == agents.law_abiding(varied[0]["swerve"]), d["id"]
