import pytest
from fastapi.testclient import TestClient

from ethics_lab.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ETHICS_DB", str(tmp_path / "test.sqlite3"))
    with TestClient(app) as client:
        yield client


def test_catalog_lists_agents_features_and_every_dilemma(client):
    data = client.get("/api/decision/catalog").json()
    assert [a["id"] for a in data["agents"]] == ["expected_utility", "sen_welfare", "satisficing", "prospect_theory"]
    assert len(data["dilemmas"]) == 99 and set(data["features"]) >= {"count", "intervention"}
    assert data["human"]["preferences"][0]["feature"] == "species"


def test_variant_view_compares_with_its_base(client):
    data = client.get("/api/decision/dilemmas/close-call~age-swerve").json()
    assert data["base"] == "close-call" and data["feature"] == "age"
    rows = {o["agent"]: o for o in data["outputs"]}
    assert rows["sen_welfare"]["base"]["changed"] is True          # children now in the swerve lane
    assert rows["expected_utility"]["base"]["changed"] is False    # age is not in its rule
    assert rows["expected_utility"]["base"]["expected"] == "invariant"
    assert all(o["audit"]["passed"] for o in data["outputs"])
    assert data["lanes"]["swerve"]["text"].startswith("2 children")


def test_base_view_has_no_comparison(client):
    data = client.get("/api/decision/dilemmas/crossing").json()
    assert data["base"] is None and "base" not in data["outputs"][0]


def test_unknown_dilemma_is_404(client):
    assert client.get("/api/decision/dilemmas/nope").status_code == 404


def test_report_summarises_all_evaluations(client):
    data = client.get("/api/decision/report").json()
    assert set(data) >= {"consistency", "explanations", "human", "agreement"}
    assert all(s["violations"] == 0 for s in data["consistency"]["summary"].values())
