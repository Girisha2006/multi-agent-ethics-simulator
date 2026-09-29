from itertools import combinations

import pytest

from ethics_lab.engine import agents, analyze, allowed_actions, benchmark, outcomes, question_scores, worlds
from ethics_lab.scenarios import FRAMEWORKS, SCENARIOS


def test_numeric_outcomes_and_duty_constraint():
    case = SCENARIOS[0]
    world = {"reliability": True, "means": True, "alternative": True}
    result = outcomes(case, world)
    assert result["divert"]["expected_deaths"] == pytest.approx(1.3)
    assert result["brake"]["expected_deaths"] == pytest.approx(1.8)
    assert allowed_actions(case, world, "utility") == ("divert",)
    assert allowed_actions(case, world, "duty") == ("brake",)
    assert allowed_actions(case, world, "fairness") == ("brake",)


def test_low_reliability_can_make_inaction_optimal():
    world = {"reliability": False, "means": False, "alternative": False}
    assert allowed_actions(SCENARIOS[0], world, "utility") == ("hold",)
    assert allowed_actions(SCENARIOS[0], world, "fairness") == ("divert",)


def test_ties_are_preserved_instead_of_inventing_disagreement():
    case = {**SCENARIOS[0], "main": 1, "side": 1, "high": 0.5, "side_risk": 0.5}
    world = {"reliability": True, "means": False, "alternative": False}
    assert allowed_actions(case, world, "utility") == ("divert", "hold")
    assert allowed_actions(case, world, "fairness") == ("divert",)
    assert analyze(case, world)["kind"] == "compatible"


@pytest.mark.parametrize("case", SCENARIOS, ids=lambda case: case["id"])
def test_exhaustive_worlds_and_partial_observations(case):
    for actual in worlds({}, case):
        for count in range(4):
            for keys in combinations(actual, count):
                observed = {key: actual[key] for key in keys}
                possible = worlds(observed, case)
                assert len(possible) == 2 ** (3 - count)
                assert actual in possible
                report = analyze(case, observed)
                assert report["total_worlds"] == len(possible)
                for agent in agents(case, observed, max(0, 2 - count)):
                    for action in agent["robust_actions"]:
                        assert all(action in allowed_actions(case, world, agent["id"]) for world in possible)
                    if agent["next_question"]:
                        assert agent["next_question"]["fact_id"] not in observed
                        assert agent["next_question"]["gain"] > 0
                    if count == 3:
                        assert agent["status"] == "Resolved"


def test_frameworks_value_different_questions():
    suggestions = {f["id"]: question_scores(SCENARIOS[0], {}, f["id"])[0]["fact_id"] for f in FRAMEWORKS}
    assert len(set(suggestions.values())) >= 2
    assert question_scores(SCENARIOS[0], {}, "utility")[-1]["gain"] == 0


def test_persistent_and_contingent_disagreement():
    assert analyze(SCENARIOS[0], {})["kind"] == "contingent"
    assert analyze(SCENARIOS[0], {"reliability": False, "alternative": False})["kind"] == "persistent"
    assert analyze(SCENARIOS[0], {"reliability": False, "alternative": True})["kind"] == "compatible"


def test_policy_benchmark_has_equal_weight_per_world():
    result = benchmark(SCENARIOS)
    assert result["cases"] == 64
    for row in result["results"]:
        assert row["adaptive"]["trials"] == 64
        assert row["random"]["trials"] == 64
        for policy in ("adaptive", "optimal", "random"):
            assert 0 <= row[policy]["resolved_rate"] <= 1
            assert 0 <= row[policy]["mean_questions"] <= 2
