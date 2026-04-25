import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from testweavex.web.app import create_app
    app = create_app()
    return TestClient(app)


def test_dashboard_endpoint(client):
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "coverage_percentage" in data


def test_runs_endpoint(client):
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_test_cases_endpoint(client):
    response = client.get("/api/test-cases")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_gaps_endpoint(client):
    response = client.get("/api/gaps")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_settings_get(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert "llm" in data
