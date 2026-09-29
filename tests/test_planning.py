"""Analytical challenge cases and agreement between forecasts and exhaustive runs."""
from itertools import combinations

import pytest

from ethics_lab.engine import (
    analyze, benchmark, decision_summary, optimal_plan, policy_trial,
    question_scores, random_trial, worlds,
)
from ethics_lab.scenarios import FRAMEWORKS, SCENARIOS, get_scenario


@pytest.mark.parametrize("framework", ["utility", "duty"])
def test_two_relays_require_looking_beyond_zero_immediate_gain(framework):
    case = get_scenario("relays")
    assert all(score["gain"] == 0 for score in question_scores(case, {}, framework))
    plan = optimal_plan(case, {}, framework, 2)
    assert plan["fact_id"] == "relay_a"
    assert plan["resolved_probability"] == 1
    assert plan["expected_cost"] == 2
    assert all(branch["plan"]["fact_id"] == "relay_b" for branch in plan["branches"])
    assert optimal_plan(case, {}, framework, 1)["fact_id"] is None
    for actual in worlds({}, case):
        assert policy_trial(case, actual, framework, "adaptive")["resolved"] == 0
        assert policy_trial(case, actual, framework, "optimal")["history"] == ["relay_a", "relay_b"]
        # Only the two orders that select both relays resolve out of six orders.
        assert random_trial(case, actual, framework)["resolved"] == pytest.approx(1 / 3)


def test_known_dominant_brake_needs_no_information():
    case = get_scenario("settled")
    for framework in FRAMEWORKS:
        assert decision_summary(case, {}, framework["id"])["robust_actions"] == ["brake"]
        assert optimal_plan(case, {}, framework["id"], 2)["expected_cost"] == 0
        for actual in worlds({}, case):
            for policy in ("adaptive", "optimal"):
                result = policy_trial(case, actual, framework["id"], policy)
                assert result["resolved"] == 1
                assert result["credits"] == 0


@pytest.mark.parametrize("case", SCENARIOS, ids=lambda case: case["id"])
def test_plan_forecasts_match_exhaustive_execution_and_respect_budget(case):
    for framework in FRAMEWORKS:
        for budget in (0, 1, 2):
            plan = optimal_plan(case, {}, framework["id"], budget)
            trials = [policy_trial(case, actual, framework["id"], "optimal", budget) for actual in worlds({}, case)]
            assert plan["resolved_probability"] == pytest.approx(sum(t["resolved"] for t in trials) / 8)
            assert plan["expected_cost"] == pytest.approx(sum(t["credits"] for t in trials) / 8)
            assert all(t["credits"] <= budget for t in trials)


def test_planner_dominates_other_strategies_on_its_stated_resolution_objective():
    for case in benchmark(SCENARIOS)["per_case"]:
        for row in case["results"]:
            assert row["optimal"]["resolved_rate"] >= row["adaptive"]["resolved_rate"] - 1e-9
            assert row["optimal"]["resolved_rate"] >= row["random"]["resolved_rate"] - 1e-9
            for policy in ("adaptive", "optimal", "random"):
                assert 0 <= row[policy]["mean_credits"] <= 2
                assert row[policy]["trials"] == 8


@pytest.mark.parametrize("case", SCENARIOS, ids=lambda case: case["id"])
def test_world_identifiers_remain_stable_across_every_disclosure_subset(case):
    original = {row["id"]: row["facts"] for row in analyze(case, {})["rows"]}
    for actual in worlds({}, case):
        for count in range(4):
            for keys in combinations(actual, count):
                for row in analyze(case, {key: actual[key] for key in keys})["rows"]:
                    assert original[row["id"]] == row["facts"]
