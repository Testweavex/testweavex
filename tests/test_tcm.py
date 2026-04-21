from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from testweavex.core.config import TCMConfig
from testweavex.core.exceptions import ConfigError
from testweavex.core.models import TestCase, TestType, generate_stable_id
from testweavex.tcm import get_connector
from testweavex.tcm.builtin import BuiltinTCMConnector


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
