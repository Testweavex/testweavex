from __future__ import annotations

from abc import ABC, abstractmethod

from testweavex.core.models import TestCase


class TCMConnector(ABC):

    @abstractmethod
    def fetch_all_test_cases(self) -> list[TestCase]: ...

    @abstractmethod
    def health_check(self) -> bool: ...
