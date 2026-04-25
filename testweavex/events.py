from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field


class TWEvent(BaseModel):
    event_type: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RunStarted(TWEvent):
    event_type: Literal["run_started"] = "run_started"
    run_id: str
    suite: str
    environment: str
    browser: str | None


class TestCollected(TWEvent):
    event_type: Literal["test_collected"] = "test_collected"
    test_case_id: str
    node_id: str
    source_file: str


class TestStarted(TWEvent):
    event_type: Literal["test_started"] = "test_started"
    run_id: str
    test_case_id: str
    node_id: str


class TestFinished(TWEvent):
    event_type: Literal["test_finished"] = "test_finished"
    run_id: str
    test_case_id: str
    result_id: str
    status: str
    duration_ms: int
    error_message: str | None


class SessionFinished(TWEvent):
    event_type: Literal["session_finished"] = "session_finished"
    run_id: str
    total: int
    passed: int
    failed: int
    skipped: int
    duration_ms: int
    collected_ids: list[str]


class GapAnalysisComplete(TWEvent):
    event_type: Literal["gap_analysis_complete"] = "gap_analysis_complete"
    run_id: str
    gaps_found: int
    top_gaps: list[dict[str, Any]]


class EventBus:
    """Synchronous, single-threaded pub/sub bus.

    Not thread-safe. All subscribe() and emit() calls must occur on
    the same thread. Do not share an EventBus instance across threads
    or asyncio tasks without external locking.
    """
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[TWEvent], None]]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[[TWEvent], None]) -> None:
        self._handlers[event_type].append(handler)

    def emit(self, event: TWEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)
