from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from testweavex.core.config import TCMConfig
from testweavex.core.exceptions import ConfigError
from testweavex.core.models import TestCase, TestType, generate_stable_id
from testweavex.tcm import get_connector
from testweavex.tcm.builtin import BuiltinTCMConnector
from testweavex.tcm.testrail import TestRailConnector


def test_get_connector_none_returns_builtin():
    cfg = TCMConfig(provider="none")
    repo = MagicMock()
    connector = get_connector(cfg, repo=repo)
    assert isinstance(connector, BuiltinTCMConnector)


def test_get_connector_builtin_alias_raises_config_error():
    cfg = TCMConfig(provider="builtin")
    with pytest.raises(ConfigError, match="Unknown TCM provider"):
        get_connector(cfg)


def test_get_connector_unknown_raises_config_error():
    cfg = TCMConfig(provider="jira-cloud")
    with pytest.raises(ConfigError, match="Unknown TCM provider"):
        get_connector(cfg)


def test_get_connector_none_without_repo_raises():
    cfg = TCMConfig(provider="none")
    with pytest.raises(ConfigError, match="requires a StorageRepository"):
        get_connector(cfg)  # repo=None by default


def _make_tc(title: str = "Login test") -> TestCase:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return TestCase(
        id=generate_stable_id("features/login.feature", title),
        title=title,
        feature_id=generate_stable_id("features/login.feature"),
        gherkin="Scenario: Login\n  Given I am on login page",
        test_type=TestType.smoke,
        skill="builtin",
        created_at=now,
        updated_at=now,
    )


class TestBuiltinTCMConnector:
    def test_fetch_all_delegates_to_repo(self):
        repo = MagicMock()
        tc = _make_tc()
        repo.get_all_test_cases.return_value = [tc]
        connector = BuiltinTCMConnector(repo)
        result = connector.fetch_all_test_cases()
        assert result == [tc]
        repo.get_all_test_cases.assert_called_once()

    def test_health_check_always_true(self):
        connector = BuiltinTCMConnector(MagicMock())
        assert connector.health_check() is True


def _make_tr_config(suite_id: int | None = None) -> dict:
    return {
        "url": "https://company.testrail.io",
        "username": "user@test.com",
        "api_key": "secret",
        "project_id": 12,
        "suite_id": suite_id,
    }


def _mock_response(json_data: object, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    resp.raise_for_status = MagicMock()
    return resp


class TestTestRailConnector:
    def test_health_check_returns_true_on_200(self):
        mock_client = MagicMock()
        mock_client.get.return_value = _mock_response({"id": 12, "name": "MyProject"})
        connector = TestRailConnector(_make_tr_config(), client=mock_client)
        assert connector.health_check() is True
        mock_client.get.assert_called_once_with("/api/v2/get_project/12")

    def test_health_check_returns_false_on_error(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Connection refused")
        connector = TestRailConnector(_make_tr_config(), client=mock_client)
        assert connector.health_check() is False

    def test_fetch_uses_configured_suite_id(self):
        mock_client = MagicMock()
        cases_page1 = {
            "cases": [
                {
                    "id": 101,
                    "title": "User can log in",
                    "suite_id": 45,
                    "priority_id": 2,
                    "refs": "REF-1,REF-2",
                    "custom_gherkin": "Scenario: Login\n  Given I am on login page",
                    "custom_automation_type": "None",
                    "created_on": 1700000000,
                    "updated_on": 1700001000,
                }
            ],
            "offset": 0,
            "limit": 250,
            "size": 1,
        }
        cases_page2 = {"cases": [], "offset": 250, "limit": 250, "size": 0}
        mock_client.get.side_effect = [
            _mock_response(cases_page1),
            _mock_response(cases_page2),
        ]
        connector = TestRailConnector(_make_tr_config(suite_id=45), client=mock_client)
        result = connector.fetch_all_test_cases()
        assert len(result) == 1
        tc = result[0]
        assert tc.title == "User can log in"
        assert tc.tcm_id == "101"
        assert tc.gherkin == "Scenario: Login\n  Given I am on login page"
        assert tc.is_automated is False
        assert "REF-1" in tc.tags

    def test_fetch_all_suites_when_no_suite_id(self):
        mock_client = MagicMock()
        suites_resp = _mock_response([{"id": 10}, {"id": 11}])
        cases_s10_p1 = _mock_response({
            "cases": [{"id": 1, "title": "T1", "suite_id": 10, "priority_id": 1,
                        "refs": "", "custom_gherkin": None,
                        "custom_automation_type": "Automated",
                        "created_on": 1700000000, "updated_on": 1700001000}],
            "offset": 0, "limit": 250, "size": 1,
        })
        cases_s10_p2 = _mock_response({"cases": [], "offset": 250, "limit": 250, "size": 0})
        cases_s11_p1 = _mock_response({
            "cases": [{"id": 2, "title": "T2", "suite_id": 11, "priority_id": 3,
                        "refs": "", "custom_gherkin": None,
                        "custom_automation_type": "None",
                        "created_on": 1700000000, "updated_on": 1700001000}],
            "offset": 0, "limit": 250, "size": 1,
        })
        cases_s11_p2 = _mock_response({"cases": [], "offset": 250, "limit": 250, "size": 0})
        mock_client.get.side_effect = [
            suites_resp,
            cases_s10_p1, cases_s10_p2,
            cases_s11_p1, cases_s11_p2,
        ]
        connector = TestRailConnector(_make_tr_config(), client=mock_client)
        result = connector.fetch_all_test_cases()
        assert len(result) == 2
        assert result[0].is_automated is True
        assert result[1].is_automated is False

    def test_missing_gherkin_uses_fallback(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = [
            _mock_response({
                "cases": [{"id": 5, "title": "Edge case test", "suite_id": 45,
                            "priority_id": 3, "refs": "",
                            "custom_gherkin": None,
                            "custom_automation_type": "None",
                            "created_on": 1700000000, "updated_on": 1700001000}],
                "offset": 0, "limit": 250, "size": 1,
            }),
            _mock_response({"cases": [], "offset": 250, "limit": 250, "size": 0}),
        ]
        connector = TestRailConnector(_make_tr_config(suite_id=45), client=mock_client)
        result = connector.fetch_all_test_cases()
        assert 'Scenario: Edge case test' in result[0].gherkin

    def test_non_2xx_raises_tcm_connector_error(self):
        from testweavex.core.exceptions import TCMConnectorError
        mock_client = MagicMock()
        err_resp = _mock_response({"error": "Not found"}, status_code=404)
        err_resp.raise_for_status.side_effect = Exception("404")
        mock_client.get.return_value = err_resp
        connector = TestRailConnector(_make_tr_config(suite_id=45), client=mock_client)
        with pytest.raises(TCMConnectorError):
            connector.fetch_all_test_cases()
