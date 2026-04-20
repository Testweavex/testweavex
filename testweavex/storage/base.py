from __future__ import annotations

from abc import ABC, abstractmethod

from testweavex.core.models import (
    Gap,
    ScoringSignals,
    TestCase,
    TestResult,
    TestRun,
)


class StorageRepository(ABC):

    @abstractmethod
    def upsert_test_case(self, tc: TestCase) -> None: ...

    @abstractmethod
    def get_test_case(self, id: str) -> TestCase: ...

    @abstractmethod
    def save_result(self, r: TestResult) -> None: ...

    @abstractmethod
    def start_run(self, suite: str, environment: str = "local",
                  browser: str | None = None, triggered_by: str = "tw") -> TestRun: ...

    @abstractmethod
    def end_run(self, run_id: str) -> None: ...

    @abstractmethod
    def get_run(self, run_id: str) -> TestRun: ...

    @abstractmethod
    def get_gaps(self, limit: int = 50, status: str = "open") -> list[Gap]: ...

    @abstractmethod
    def save_gaps(self, gaps: list[Gap]) -> None: ...

    @abstractmethod
    def get_coverage_percentage(self) -> float: ...

    @abstractmethod
    def get_coverage_trend(self, weeks: int) -> list[dict]: ...

    @abstractmethod
    def get_flaky_tests(self, min_runs: int = 5) -> list[TestCase]: ...

    @abstractmethod
    def get_scoring_signals(self, tc_id: str) -> ScoringSignals: ...

    @abstractmethod
    def mark_uncollected_as_gaps(self, collected_ids: list[str]) -> None: ...

    @abstractmethod
    def get_all_test_cases(self) -> list[TestCase]: ...

    @abstractmethod
    def get_never_run_test_cases(self) -> list[TestCase]: ...

    @abstractmethod
    def get_always_failing_test_cases(self) -> list[TestCase]: ...

    @abstractmethod
    def list_runs(self, limit: int = 50) -> list[TestRun]: ...

    @abstractmethod
    def get_results_for_run(self, run_id: str) -> list[TestResult]: ...
