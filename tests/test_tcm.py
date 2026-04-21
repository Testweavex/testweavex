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


def test_get_connector_builtin_returns_builtin():
    cfg = TCMConfig(provider="builtin")
    repo = MagicMock()
    connector = get_connector(cfg, repo=repo)
    assert isinstance(connector, BuiltinTCMConnector)


def test_get_connector_unknown_raises_config_error():
    cfg = TCMConfig(provider="jira-cloud")
    with pytest.raises(ConfigError, match="Unknown TCM provider"):
        get_connector(cfg)
