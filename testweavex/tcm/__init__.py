from __future__ import annotations

from testweavex.core.config import TCMConfig
from testweavex.core.exceptions import ConfigError
from testweavex.storage.base import StorageRepository
from testweavex.tcm.base import TCMConnector


def get_connector(
    config: TCMConfig,
    repo: StorageRepository | None = None,
) -> TCMConnector:
    provider = config.provider.lower()

    if provider in ("none", "builtin"):
        from testweavex.tcm.builtin import BuiltinTCMConnector
        if repo is None:
            raise ConfigError("BuiltinTCMConnector requires a StorageRepository")
        return BuiltinTCMConnector(repo)

    if provider == "testrail":
        from testweavex.tcm.testrail import TestRailConnector
        return TestRailConnector(config.testrail)

    if provider == "xray":
        from testweavex.tcm.xray import XrayConnector
        return XrayConnector(config.xray)

    raise ConfigError(f"Unknown TCM provider: {config.provider!r}")
