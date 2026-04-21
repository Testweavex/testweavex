from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from testweavex.core.config import TCMConfig
from testweavex.core.exceptions import ConfigError
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
