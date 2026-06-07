from __future__ import annotations

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


def test_gap_generate_returns_404_when_gap_not_found(client):
    response = client.post("/api/gaps/nonexistent-gap-id/generate")
    assert response.status_code == 404


def test_test_case_get_single_not_found(client):
    response = client.get("/api/test-cases/nonexistent-id")
    assert response.status_code == 404


def test_test_case_get_single_returns_detail_with_results(client):
    from datetime import datetime, timezone
    from testweavex.core.models import TestCase, TestType, generate_stable_id
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    tc = TestCase(
        id=generate_stable_id("f", "s"),
        title="Login test",
        feature_id=generate_stable_id("f"),
        gherkin="Scenario: Login\n  Given I am on login page",
        test_type=TestType.smoke,
        skill="builtin",
        created_at=now, updated_at=now,
    )
    client.app.state.repo.upsert_test_case(tc)
    response = client.get(f"/api/test-cases/{tc.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Login test"
    assert "recent_results" in data
    assert isinstance(data["recent_results"], list)


def test_test_case_create(client):
    response = client.post("/api/test-cases", json={
        "title": "New manual test",
        "test_type": "smoke",
        "priority": 1,
        "tags": ["smoke", "manual"],
        "gherkin": "Scenario: New test\n  Given something",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New manual test"
    assert data["test_type"] == "smoke"
    assert data["priority"] == 1
    assert "smoke" in data["tags"]


def test_test_case_create_invalid_type(client):
    response = client.post("/api/test-cases", json={
        "title": "Bad test",
        "test_type": "invalid_type",
    })
    assert response.status_code == 422


def test_test_case_create_auto_generates_gherkin_when_empty(client):
    response = client.post("/api/test-cases", json={"title": "Auto gherkin test"})
    assert response.status_code == 201
    assert "Scenario:" in response.json()["gherkin"]


def test_test_case_patch(client):
    from datetime import datetime, timezone
    from testweavex.core.models import TestCase, TestType, generate_stable_id
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    tc = TestCase(
        id=generate_stable_id("f", "patch"),
        title="Original title",
        feature_id=generate_stable_id("f"),
        gherkin="Scenario: x",
        test_type=TestType.smoke,
        skill="builtin",
        created_at=now, updated_at=now,
    )
    client.app.state.repo.upsert_test_case(tc)
    response = client.patch(f"/api/test-cases/{tc.id}", json={
        "title": "Updated title",
        "priority": 1,
        "is_automated": True,
        "tags": ["regression"],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated title"
    assert data["priority"] == 1
    assert data["is_automated"] is True
    assert "regression" in data["tags"]


def test_test_case_patch_not_found(client):
    response = client.patch("/api/test-cases/nonexistent", json={"title": "x"})
    assert response.status_code == 404


def test_test_case_delete(client):
    from datetime import datetime, timezone
    from testweavex.core.models import TestCase, TestType, generate_stable_id
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    tc = TestCase(
        id=generate_stable_id("f", "del"),
        title="To delete",
        feature_id=generate_stable_id("f"),
        gherkin="Scenario: del",
        test_type=TestType.smoke,
        skill="builtin",
        created_at=now, updated_at=now,
    )
    client.app.state.repo.upsert_test_case(tc)
    response = client.delete(f"/api/test-cases/{tc.id}")
    assert response.status_code == 204
    assert client.get(f"/api/test-cases/{tc.id}").status_code == 404


def test_test_case_delete_not_found(client):
    response = client.delete("/api/test-cases/nonexistent")
    assert response.status_code == 404


def test_test_cases_search_filter(client):
    from datetime import datetime, timezone
    from testweavex.core.models import TestCase, TestType, generate_stable_id
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for title in ("Login flow", "Logout flow", "Password reset"):
        tc = TestCase(
            id=generate_stable_id("f", title),
            title=title,
            feature_id=generate_stable_id("f"),
            gherkin="Scenario: x",
            test_type=TestType.smoke,
            skill="builtin",
            created_at=now, updated_at=now,
        )
        client.app.state.repo.upsert_test_case(tc)
    response = client.get("/api/test-cases?search=login")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["title"] == "Login flow"


def test_gap_generate_returns_200_with_generation_response(client):
    from datetime import datetime, timezone
    from testweavex.core.models import (
        Gap, GapStatus, TestCase, TestType, generate_stable_id,
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    tc_id = generate_stable_id("features/login.feature", "Login test")
    gap = Gap(
        id="gap-1",
        test_case_id=tc_id,
        priority_score=0.8,
        gap_reason="never automated",
        status=GapStatus.open,
        detected_at=now,
    )
    tc = TestCase(
        id=tc_id,
        title="Login test",
        feature_id=generate_stable_id("features/login.feature"),
        gherkin="Scenario: Login\n  Given I am on login page",
        test_type=TestType.smoke,
        skill="functional/smoke",
        is_automated=False,
        created_at=now,
        updated_at=now,
    )

    with patch("testweavex.web.api.gaps.get_llm_adapter") as mock_factory:
        mock_adapter = MagicMock()
        mock_adapter.health_check.return_value = True
        mock_adapter.suggest_gap_automation.return_value = _mock_generation_response()
        mock_factory.return_value = mock_adapter

        repo = client.app.state.repo
        repo.upsert_test_case(tc)
        repo.save_gaps([gap])

        response = client.post("/api/gaps/gap-1/generate")

    assert response.status_code == 200
    data = response.json()
    assert "scenarios" in data
