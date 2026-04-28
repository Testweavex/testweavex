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


from unittest.mock import MagicMock, patch
from testweavex.core.models import GenerationResponse


def _mock_generation_response() -> GenerationResponse:
    return GenerationResponse(
        scenarios=[],
        skill_used="functional/smoke",
        llm_model="test-model",
        tokens_used=100,
        generation_time_ms=500,
    )


def test_generate_endpoint_returns_200_with_response(client):
    with patch("testweavex.web.api.generate.get_llm_adapter") as mock_factory:
        mock_adapter = MagicMock()
        mock_adapter.health_check.return_value = True
        mock_adapter.generate_tests.return_value = _mock_generation_response()
        mock_factory.return_value = mock_adapter

        response = client.post("/api/generate", json={
            "feature_description": "User login",
            "skill": "functional/smoke",
            "n_suggestions": 3,
        })

    assert response.status_code == 200
    data = response.json()
    assert "scenarios" in data
    assert data["skill_used"] == "functional/smoke"
    assert data["llm_model"] == "test-model"


def test_generate_endpoint_returns_503_when_health_check_fails(client):
    with patch("testweavex.web.api.generate.get_llm_adapter") as mock_factory:
        mock_adapter = MagicMock()
        mock_adapter.health_check.return_value = False
        mock_factory.return_value = mock_adapter

        response = client.post("/api/generate", json={
            "feature_description": "Login",
            "skill": "functional/smoke",
            "n_suggestions": 3,
        })

    assert response.status_code == 503


def test_generate_endpoint_returns_422_on_llm_output_error(client):
    from testweavex.core.exceptions import LLMOutputError
    with patch("testweavex.web.api.generate.get_llm_adapter") as mock_factory:
        mock_adapter = MagicMock()
        mock_adapter.health_check.return_value = True
        mock_adapter.generate_tests.side_effect = LLMOutputError("bad output")
        mock_factory.return_value = mock_adapter

        response = client.post("/api/generate", json={
            "feature_description": "Login",
            "skill": "functional/smoke",
            "n_suggestions": 3,
        })

    assert response.status_code == 422


def test_generate_endpoint_returns_503_on_config_error(client):
    from testweavex.core.exceptions import ConfigError
    with patch("testweavex.web.api.generate.get_llm_adapter") as mock_factory:
        mock_factory.side_effect = ConfigError("no provider")

        response = client.post("/api/generate", json={
            "feature_description": "Login",
            "skill": "functional/smoke",
            "n_suggestions": 3,
        })

    assert response.status_code == 503
