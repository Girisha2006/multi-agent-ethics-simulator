import pytest

from ethics_lab.decision import agents, dilemmas


def dilemma(stay, swerve, p_stay=1.0, p_swerve=1.0):
    return {"stay": dilemmas.lane("A", stay, p_stay), "swerve": dilemmas.lane("B", swerve, p_swerve)}


def choice(agent_id, d):
    return agents.RULES[agent_id](d)["choice"]


def test_every_catalog_dilemma_gets_a_valid_reproducible_choice_from_every_agent():
    for d in dilemmas.catalog():
        first, second = agents.decide(d), agents.decide(d)
        assert first == second
        assert [o["agent"] for o in first] == [a["id"] for a in agents.AGENTS]
        assert all(o["choice"] in ("stay", "swerve") for o in first)
        assert all(o["explanation"] and o["trace"] for o in first)


def test_expected_utility_minimises_probability_weighted_loss_and_scores_pets_low():
    assert choice("expected_utility", dilemma([dilemmas.people("adult", 5)], [dilemmas.people("adult", 1)])) == "swerve"
    assert choice("expected_utility", dilemma([dilemmas.people("adult", 1)], [dilemmas.people("dog", 9)])) == "swerve"
    assert choice("expected_utility", dilemma([dilemmas.people("adult", 1)], [dilemmas.people("dog", 11)])) == "stay"
    # 4 certain deaths versus 5 at 60% (expected 3).
    assert choice("expected_utility", dilemmas.get("brakes")) == "swerve"


def test_expected_utility_ties_keep_the_lane_and_ignore_age():
    result = agents.expected_utility(dilemmas.get("generations"))
    assert result["choice"] == "stay" and result["tie"]


def test_sen_welfare_weighs_life_years_and_concern_for_pedestrians():
    assert choice("sen_welfare", dilemmas.get("generations")) == "stay"      # spares the children
    assert choice("sen_welfare", dilemmas.get("barrier")) == "swerve"        # pedestrians weighted 1.5
    loss = agents.sen_welfare(dilemma([dilemmas.people("child", 1)], [dilemmas.people("adult", 1, role="passenger")]))["scores"]
    assert loss == {"stay": round(70 / 40 * 1.5, 2), "swerve": 1.0}


def test_satisficing_accepts_first_lane_within_aspiration_and_protects_law_abiding_people():
    # Staying is inspected first; three versus two deaths is within the slack of one.
    assert choice("satisficing", dilemmas.get("close-call")) == "swerve"     # stay kills more law-abiding people
    assert choice("satisficing", dilemmas.get("signal")) == "stay"           # red-signal crossers are not law-abiding
    assert choice("satisficing", dilemma([dilemmas.people("adult", 5)], [dilemmas.people("adult", 1)])) == "swerve"
    assert choice("satisficing", dilemmas.get("even")) == "stay"


def test_satisficing_counts_passengers_as_law_abiding():
    assert agents.law_abiding({"characters": [dilemmas.people("adult", 2, role="passenger")]}) == 2
    assert agents.law_abiding({"characters": [dilemmas.people("adult", 2, lawful=False)]}) == 0


def test_prospect_theory_loss_aversion_needs_about_two_and_a_half_times_as_many_saved():
    assert choice("prospect_theory", dilemma([dilemmas.people("adult", 3)], [dilemmas.people("adult", 1)])) == "swerve"
    assert choice("prospect_theory", dilemma([dilemmas.people("adult", 2)], [dilemmas.people("adult", 1)])) == "stay"
    assert choice("prospect_theory", dilemmas.get("brakes")) == "stay"


def test_probability_weighting_matches_tversky_kahneman_1992():
    assert agents.weight(1, 0.69) == 1.0 and agents.weight(0, 0.69) == 0.0
    assert agents.weight(0.01, 0.69) > 0.01          # small probabilities overweighted
    assert agents.weight(0.9, 0.69) < 0.9            # large probabilities underweighted
    assert agents.weight(0.5, 0.69) == pytest.approx(0.4540, abs=1e-3)


def test_explanations_quote_only_numbers_from_their_trace():
    import re
    for d in dilemmas.catalog():
        for out in agents.decide(d):
            cited = {round(float(n), 2) for n in re.findall(r"-?\d+(?:\.\d+)?", out["explanation"])}
            assert cited <= set(out["numbers"]), (d["id"], out["agent"], cited - set(out["numbers"]))


def test_spared_group_follows_tags_through_a_mirror():
    base = dilemmas.get("crossing")
    mirror = dilemmas.get("crossing~intervention")
    eu = agents.expected_utility
    assert agents.spared_group(base, eu(base)["choice"]) == agents.spared_group(mirror, eu(mirror)["choice"]) == "A"
