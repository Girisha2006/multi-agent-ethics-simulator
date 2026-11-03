import pytest

from ethics_lab.decision import agents, dilemmas, evaluation


def test_no_agent_changes_its_decision_for_a_feature_its_rule_ignores():
    summary = evaluation.consistency()["summary"]
    assert all(s["violations"] == 0 for s in summary.values()), summary


def test_every_used_feature_changes_at_least_one_decision():
    summary = evaluation.consistency()["summary"]
    for a in agents.AGENTS:
        for feature in a["uses"]:
            assert summary[a["id"]]["by_feature"][feature]["changed"] > 0, (a["id"], feature)


def test_states_choice_reads_decision_statements():
    assert evaluation.states_choice("It chooses to stay because ...", "stay")
    assert not evaluation.states_choice("It chooses to stay because swerving costs more.", "swerve")
    assert evaluation.states_choice("Swerving is worse, so it stays.", "stay")
    assert not evaluation.states_choice("Both lanes are bad.", "stay")


def test_templated_explanations_pass_the_faithfulness_checklist():
    result = evaluation.explanation_audit()
    failures = [r for r in result["rows"] if not r["passed"]]
    assert not failures, failures[:3]


def test_audit_flags_unfaithful_explanations():
    d = dilemmas.get("generations")
    honest = agents.expected_utility(d)
    wrong_factor = {**honest, "explanation": "It stays because the elderly have fewer life-years than the children."}
    stray = {**honest, "explanation": "It stays because staying costs 7.5 lives."}
    flipped = {**honest, "choice": "swerve"}
    assert evaluation.audit(d, "expected_utility", honest)["passed"]
    assert not evaluation.audit(d, "expected_utility", wrong_factor)["checks"]["cites_no_ignored_factor"]
    assert evaluation.audit(d, "expected_utility", stray)["stray_numbers"] == [7.5]
    # A tie allows either lane for the decision check, but the explanation must still name the choice.
    assert not evaluation.audit(d, "expected_utility", flipped)["checks"]["names_its_choice"]


def test_audit_requires_influential_factors():
    d = dilemmas.get("signal")
    out = agents.satisficing(d)
    assert "lawful" in evaluation.influential_factors(d, "satisficing")
    vague = {**out, "explanation": "It chooses to stay because that lane was acceptable."}
    assert evaluation.audit(d, "satisficing", vague)["missing"]


def test_human_alignment_uses_both_lane_positions():
    result = evaluation.human_alignment()
    assert {r["contrast"] for r in result["rows"]} >= {"species-ahead", "species-aside", "intervention"}
    # Every agent spares humans over pets and more over fewer in both lane positions.
    for summary in result["summary"].values():
        assert summary["species"] == ["aligned", "aligned"] and summary["count"] == ["aligned", "aligned"]
    assert "direction only" in result["source"]


def test_evaluation_script_writes_results(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("run_evaluation", Path(__file__).parent.parent / "tools" / "run_evaluation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    module.main()
    text = (tmp_path / "results" / "decision_lab.md").read_text()
    assert "## 1. Decision consistency" in text and "| Expected utility |" in text
    assert (tmp_path / "results" / "decision_lab.json").stat().st_size > 1000


@pytest.mark.parametrize("text", ["Swerve has the lower loss, so swerve.", "Stay fails the slack, swerve is accepted.", "Accept swerve: 1 death.", "Stay loss 3, swerve loss 2. Lower loss is swerve.", "Swerve. Stay loss 1, swerve loss 0.2.", "Swerve is lower."])
def test_short_decision_phrasings_are_recognised(text):
    assert evaluation.states_choice(text, "swerve") and not evaluation.states_choice(text, "stay")


def test_rule_constants_and_signed_losses_are_traceable():
    d = dilemmas.get("crossing")
    out = {"choice": "swerve", "explanation": "Loss value -2.25 uses exponent 0.88; prospect value 1.87 is positive, so swerve."}
    assert evaluation.audit(d, "prospect_theory", out)["stray_numbers"] == []
