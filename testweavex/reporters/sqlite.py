from __future__ import annotations

from testweavex.core.models import TestResult, TestStatus
from testweavex.events import EventBus, SessionFinished, TestFinished
from testweavex.reporters.base import BaseReporter
from testweavex.storage.base import StorageRepository


class SQLiteReporter(BaseReporter):

    def __init__(self, repo: StorageRepository) -> None:
        self._repo = repo

    def register(self, bus: EventBus) -> None:
        bus.subscribe("test_finished", self._on_finished)
        bus.subscribe("session_finished", self._on_session)

    def _on_finished(self, event: TestFinished) -> None:
        result = TestResult(
            id=event.result_id,
            run_id=event.run_id,
            test_case_id=event.test_case_id,
            status=TestStatus(event.status),
            duration_ms=event.duration_ms,
            error_message=event.error_message,
        )
        self._repo.save_result(result)

    def _on_session(self, event: SessionFinished) -> None:
        self._repo.end_run(event.run_id)
        self._repo.mark_uncollected_as_gaps(event.collected_ids)
