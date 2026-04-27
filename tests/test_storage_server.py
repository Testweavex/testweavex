# tests/test_storage_server.py
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def _run_json(run_id: str = "run-123") -> dict:
    return {
        "id": run_id,
        "suite": "smoke",
        "environment": "local",
        "browser": None,
        "triggered_by": "tw",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "result_ids": [],
    }


def _tc_json(tc_id: str = "tc-abc") -> dict:
    from testweavex.core.models import generate_stable_id
    return {
        "id": tc_id,
        "title": "Login test",
        "feature_id": generate_stable_id("features/login.feature"),
        "gherkin": "Scenario: Login\n  Given I am on login page",
        "test_type": "smoke",
        "skill": "functional/smoke",
        "status": "pending",
        "is_automated": False,
        "tcm_id": None,
        "tags": [],
        "priority": 2,
        "source_file": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _mock_response(data, status_code: int = 200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


def _mock_error_response(status_code: int = 500):
    import httpx
    mock = MagicMock()
    mock.status_code = status_code
    mock.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error", request=MagicMock(), response=MagicMock()
    )
    return mock


class TestServerRepository:

    @patch("testweavex.storage.server.httpx.Client")
    def test_start_run_posts_and_returns_test_run(self, mock_cls):
        mock_client = mock_cls.return_value
        mock_client.post.return_value = _mock_response(_run_json(), 201)

        from testweavex.storage.server import ServerRepository
        from testweavex.core.models import TestRun

        repo = ServerRepository("http://server:8000", "token")
        run = repo.start_run("smoke")

        assert isinstance(run, TestRun)
        assert run.id == "run-123"
        assert run.suite == "smoke"
        mock_client.post.assert_called_once_with("/runs", json={
            "suite": "smoke",
            "environment": "local",
            "browser": None,
            "triggered_by": "tw",
        })

    @patch("testweavex.storage.server.httpx.Client")
    def test_end_run_patches_run(self, mock_cls):
        mock_client = mock_cls.return_value
        mock_client.patch.return_value = _mock_response({}, 200)

        from testweavex.storage.server import ServerRepository

        repo = ServerRepository("http://server:8000")
        repo.end_run("run-123")

        mock_client.patch.assert_called_once_with("/runs/run-123")

    @patch("testweavex.storage.server.httpx.Client")
    def test_upsert_test_case_puts_test_case(self, mock_cls):
        mock_client = mock_cls.return_value
        mock_client.put.return_value = _mock_response(_tc_json(), 200)

        from testweavex.storage.server import ServerRepository
        from testweavex.core.models import TestCase, TestType, TestStatus, generate_stable_id

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        tc = TestCase(
            id="tc-abc",
            title="Login test",
            feature_id=generate_stable_id("features/login.feature"),
            gherkin="Scenario: Login\n  Given I am on login page",
            test_type=TestType.smoke,
            skill="functional/smoke",
            status=TestStatus.pending,
            is_automated=False,
            created_at=now,
            updated_at=now,
        )

        repo = ServerRepository("http://server:8000")
        repo.upsert_test_case(tc)

        mock_client.put.assert_called_once_with(
            "/test-cases/tc-abc", json=tc.model_dump(mode="json")
        )

    @patch("testweavex.storage.server.httpx.Client")
    def test_get_gaps_returns_gap_list(self, mock_cls):
        mock_client = mock_cls.return_value
        gap_data = [{
            "id": "gap-1",
            "test_case_id": "tc-abc",
            "priority_score": 0.75,
            "gap_reason": "never run",
            "suggested_gherkin": None,
            "status": "open",
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "closed_at": None,
        }]
        mock_client.get.return_value = _mock_response(gap_data)

        from testweavex.storage.server import ServerRepository
        from testweavex.core.models import Gap

        repo = ServerRepository("http://server:8000")
        gaps = repo.get_gaps(limit=10, status="open")

        assert len(gaps) == 1
        assert isinstance(gaps[0], Gap)
        assert gaps[0].priority_score == 0.75
        mock_client.get.assert_called_once_with("/gaps?limit=10&status=open")

    @patch("testweavex.storage.server.httpx.Client")
    def test_get_coverage_percentage_returns_float(self, mock_cls):
        mock_client = mock_cls.return_value
        mock_client.get.return_value = _mock_response({"percentage": 62.5})

        from testweavex.storage.server import ServerRepository

        repo = ServerRepository("http://server:8000")
        pct = repo.get_coverage_percentage()

        assert pct == 62.5
        mock_client.get.assert_called_once_with("/coverage")

    @patch("testweavex.storage.server.httpx.Client")
    def test_non_2xx_response_raises_storage_error(self, mock_cls):
        from testweavex.core.exceptions import StorageError

        mock_client = mock_cls.return_value
        mock_client.post.return_value = _mock_error_response(500)

        from testweavex.storage.server import ServerRepository

        repo = ServerRepository("http://server:8000")
        with pytest.raises(StorageError):
            repo.start_run("smoke")

    @patch("testweavex.storage.server.httpx.Client")
    def test_constructor_sets_auth_header_when_token_given(self, mock_cls):
        from testweavex.storage.server import ServerRepository

        ServerRepository("http://server:8000", "my-token")

        _, kwargs = mock_cls.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer my-token"

    @patch("testweavex.storage.server.httpx.Client")
    def test_constructor_omits_auth_header_when_no_token(self, mock_cls):
        from testweavex.storage.server import ServerRepository

        ServerRepository("http://server:8000", None)

        _, kwargs = mock_cls.call_args
        assert "Authorization" not in kwargs["headers"]
