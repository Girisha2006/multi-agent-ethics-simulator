import json

import pytest
from fastapi.testclient import TestClient

from ethics_lab.app import app
from ethics_lab import store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ETHICS_DB", str(tmp_path / "test.sqlite3"))
    with TestClient(app) as client:
        yield client


def new_run(client):
    response = client.post("/api/runs", json={"scenario_id": "junction"})
    assert response.status_code == 201
    return response.json()


def test_initial_view_does_not_contain_actual_hidden_values(client):
    run = new_run(client)
    assert "actual" not in run
    assert "debrief" not in run
    assert run["observed"] == {}
    assert all(f["value"] is None for f in run["facts"])
    assert run["analysis"]["total_worlds"] == 8
    # Changing the server's secret world cannot affect initial recommendations or analysis.
    original = client.get(f"/api/runs/{run['id']}").json()
    store.update(run["id"], lambda r: r.update(actual={key: not value for key, value in r["actual"].items()}))
    assert client.get(f"/api/runs/{run['id']}").json() == original


def test_budget_duplicate_reveals_and_debrief_do_not_rewrite_observations(client):
    run = new_run(client)
    prefix = f"/api/runs/{run['id']}"
    first = client.post(prefix + "/reveal", json={"fact_id": "reliability"}).json()
    assert first["remaining"] == 1
    assert first["analysis"]["total_worlds"] == 4
    duplicate = client.post(prefix + "/reveal", json={"fact_id": "reliability"})
    assert duplicate.status_code == 409
    second = client.post(prefix + "/reveal", json={"fact_id": "means"}).json()
    assert second["remaining"] == 0
    assert len(second["events"]) == 2
    assert second["analysis"]["total_worlds"] == 2
    assert client.post(prefix + "/reveal", json={"fact_id": "alternative"}).status_code == 409
    final = client.post(prefix + "/finish").json()
    assert final["observed"] == second["observed"]
    assert final["agents"] == second["agents"]
    assert final["analysis"] == second["analysis"]
    assert final["debrief"]["analysis"]["total_worlds"] == 1
    assert all(f["value"] for f in final["debrief"]["facts"])
    assert len(client.post(prefix + "/finish").json()["events"]) == 3


def test_early_finish_closes_disclosure_and_keeps_conditional_answers(client):
    run = new_run(client)
    prefix = f"/api/runs/{run['id']}"
    final = client.post(prefix + "/finish").json()
    assert final["observed"] == {}
    assert all(a["status"] == "Conditional" for a in final["agents"])
    assert all(a["next_question"] is None for a in final["agents"])
    assert client.post(prefix + "/reveal", json={"fact_id": "means"}).status_code == 409


def test_validation_and_missing_runs(client):
    assert client.post("/api/runs", json={"scenario_id": "fake"}).status_code == 404
    assert client.get("/api/runs/nonexistent").status_code == 404
    run = new_run(client)
    assert client.post(f"/api/runs/{run['id']}/reveal", json={"fact_id": "invalid"}).status_code == 422
    assert client.post("/api/runs", json={"scenario_id": "junction", "actual": {}}).status_code == 422


def test_markdown_and_json_export_mask_unrevealed_values(client):
    run = new_run(client)
    prefix = f"/api/runs/{run['id']}"
    md = client.get(prefix + "/export")
    assert md.status_code == 200
    assert "attachment" in md.headers["content-disposition"]
    assert "# Before You Decide" in md.text
    assert "## Full-information debrief" not in md.text
    data = client.get(prefix + "/export?format=json").json()
    assert "actual" not in data
    assert data == run
    client.post(prefix + "/finish")
    assert "## Full-information debrief" in client.get(prefix + "/export").text


def test_frontend_and_benchmark_are_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert len(client.get("/api/catalog").json()["scenarios"]) == 8
    assert client.get("/api/benchmark").json()["cases"] == 64


def test_run_captures_scenario_and_rejects_mismatched_rule_version(client):
    run = new_run(client)
    saved = store.get(run["id"])
    assert saved["scenario"] == run["scenario"]
    store.update(run["id"], lambda r: r.update(version="incompatible-version"))
    prefix = f"/api/runs/{run['id']}"
    assert client.get(prefix).status_code == 409
    assert client.post(prefix + "/reveal", json={"fact_id": "means"}).status_code == 409
    assert client.post(prefix + "/finish").status_code == 409
    assert store.get(run["id"])["observed"] == {}


def test_costly_report_spends_two_credits_and_rejects_unaffordable_reveal(client):
    run = client.post("/api/runs", json={"scenario_id": "costly"}).json()
    prefix = f"/api/runs/{run['id']}"
    result = client.post(prefix + "/reveal", json={"fact_id": "reliability"}).json()
    assert result["spent"] == 2
    assert result["remaining"] == 0
    assert len(result["observed"]) == 1
    assert result["events"][0]["cost"] == 2
    assert client.post(prefix + "/reveal", json={"fact_id": "means"}).status_code == 409
    run = client.post("/api/runs", json={"scenario_id": "costly"}).json()
    prefix = f"/api/runs/{run['id']}"
    client.post(prefix + "/reveal", json={"fact_id": "means"})
    before = store.get(run["id"])
    assert client.post(prefix + "/reveal", json={"fact_id": "reliability"}).status_code == 409
    assert store.get(run["id"]) == before
    assert client.post(prefix + "/reveal", json={"fact_id": "alternative"}).json()["spent"] == 2


def test_case_specific_facts_and_replay_are_masked_immutable_snapshots(client):
    run = client.post("/api/runs", json={"scenario_id": "relays"}).json()
    prefix = f"/api/runs/{run['id']}"
    assert client.post(prefix + "/reveal", json={"fact_id": "reliability"}).status_code == 422
    first = client.post(prefix + "/reveal", json={"fact_id": "relay_a"}).json()
    second = client.post(prefix + "/reveal", json={"fact_id": "relay_b"}).json()
    final = client.post(prefix + "/finish").json()
    saved = store.get(run["id"])
    frames = client.get(prefix + "/replay").json()["frames"]
    assert [f["state"] for f in frames] == [run, first, second, final]
    assert all("actual" not in f["state"] for f in frames)
    assert all("debrief" not in f["state"] for f in frames[:-1])
    assert len(frames[-1]["state"]["debrief"]["facts"]) == 3
    assert store.get(run["id"]) == saved
    assert "Budget planner" in client.get(prefix + "/export").text
    assert "2/2" in client.get(prefix + "/export").text
    store.update(run["id"], lambda r: r.update(version="0.1.0"))
    assert client.get(prefix + "/replay").status_code == 409


def test_replay_unfinished_run_never_opens_debrief(client):
    run = new_run(client)
    prefix = f"/api/runs/{run['id']}"
    client.post(prefix + "/reveal", json={"fact_id": "means"})
    frames = client.get(prefix + "/replay").json()["frames"]
    assert len(frames) == 2
    assert frames[0]["state"]["observed"] == {}
    assert frames[0]["state"]["events"] == []
    assert all("debrief" not in f["state"] for f in frames)
