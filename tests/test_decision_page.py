import pytest
from fastapi.testclient import TestClient

from ethics_lab.app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ETHICS_DB", str(tmp_path / "test.sqlite3"))
    with TestClient(app) as client:
        yield client


def test_decision_page_is_served(client):
    response = client.get("/decision")
    assert response.status_code == 200 and "text/html" in response.headers["content-type"]
    assert "Decision Lab" in response.text and "/static/decision.js" in response.text
    assert 'role="tablist"' in response.text


def test_decision_assets_are_served(client):
    assert client.get("/static/decision.js").status_code == 200
    assert client.get("/static/decision.css").status_code == 200


def test_index_links_to_decision_lab(client):
    assert 'href="/decision"' in client.get("/").text
