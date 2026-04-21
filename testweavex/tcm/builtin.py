from __future__ import annotations

from testweavex.storage.base import StorageRepository
from testweavex.tcm.base import TCMConnector


class BuiltinTCMConnector(TCMConnector):

    def __init__(self, repo: StorageRepository) -> None:
        self._repo = repo

    def fetch_all_test_cases(self) -> list[TestCase]:
        return self._repo.get_all_test_cases()

    def health_check(self) -> bool:
        return True
