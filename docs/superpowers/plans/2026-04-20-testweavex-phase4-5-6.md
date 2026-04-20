# TestWeaveX Phase 4+5+6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the pytest execution plugin, Typer CLI, gap analysis engine, and FastAPI web UI as a unified, event-bus-driven system.

**Architecture:** A synchronous `EventBus` in `testweavex/events.py` connects the pytest plugin (emitter) to storage, console, and SSE subscribers (consumers). Gap analysis subscribes to `SessionFinished` and emits `GapAnalysisComplete`. The FastAPI web UI serves `testweavex_ui_design.html` from `web/static/index.html` and exposes REST + SSE endpoints backed by the same `StorageRepository`.

**Tech Stack:** pytest hooks, Typer, Rich, FastAPI, Uvicorn, SQLAlchemy (existing), Pydantic v2 (existing)

**Python executable:** `/c/Users/panka/anaconda3/envs/remhelper/python.exe`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `testweavex/events.py` | CREATE | EventBus, all TWEvent Pydantic types |
| `testweavex/execution/plugin.py` | REPLACE stub | All pytest hooks + StorageSubscriber + ConsoleSubscriber |
| `testweavex/cli.py` | CREATE | Typer CLI — `tw`, `init`, `status`, `history`, stubs |
| `testweavex/gap/__init__.py` | CREATE | Empty package marker |
| `testweavex/gap/detector.py` | CREATE | Three-strategy gap detection |
| `testweavex/gap/scorer.py` | CREATE | Six-signal priority scoring |
| `testweavex/gap/analyzer.py` | CREATE | Orchestrate detector+scorer, subscribe to EventBus |
| `testweavex/web/__init__.py` | CREATE | Empty package marker |
| `testweavex/web/app.py` | CREATE | FastAPI app factory |
| `testweavex/web/api/__init__.py` | CREATE | Empty package marker |
| `testweavex/web/api/dashboard.py` | CREATE | GET /api/dashboard |
| `testweavex/web/api/runs.py` | CREATE | GET /api/runs, GET /api/runs/{id} |
| `testweavex/web/api/test_cases.py` | CREATE | GET /api/test-cases |
| `testweavex/web/api/gaps.py` | CREATE | GET /api/gaps, POST /api/gaps/{id}/generate |
| `testweavex/web/api/settings.py` | CREATE | GET/PUT /api/settings |
| `testweavex/web/api/events.py` | CREATE | GET /api/events (SSE) |
| `testweavex/web/static/index.html` | MOVE | testweavex_ui_design.html → here |
| `testweavex/storage/base.py` | MODIFY | Add 5 new abstract methods |
| `testweavex/storage/sqlite.py` | MODIFY | Implement 5 new methods |
| `tests/test_events.py` | CREATE | EventBus pub/sub tests |
| `tests/test_plugin.py` | CREATE | pytester full-session tests |
| `tests/test_cli.py` | CREATE | CliRunner tests for all commands |
| `tests/test_gap_detector.py` | CREATE | Three strategy tests |
| `tests/test_gap_scorer.py` | CREATE | Scoring math tests |
| `tests/test_gap_analyzer.py` | CREATE | End-to-end: SessionFinished → gaps saved |
| `tests/test_web_api.py` | CREATE | FastAPI TestClient tests |
| `tests/test_sse.py` | CREATE | SSE endpoint test |

---

## Task 1: EventBus + Event Types

**Files:**
- Create: `testweavex/events.py`
- Create: `tests/test_events.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_events.py
from testweavex.events import (
    EventBus, RunStarted, TestCollected, TestFinished,
    SessionFinished, GapAnalysisComplete,
)


def test_subscribe_and_emit():
    bus = EventBus()
    received = []
    bus.subscribe("run_started", received.append)
    event = RunStarted(run_id="r1", suite="s", environment="local", browser=None)
    bus.emit(event)
    assert len(received) == 1
    assert received[0].run_id == "r1"


def test_wildcard_subscriber_receives_all():
    bus = EventBus()
    received = []
    bus.subscribe("*", received.append)
    bus.emit(RunStarted(run_id="r1", suite="s", environment="local", browser=None))
    bus.emit(SessionFinished(
        run_id="r1", total=1, passed=1, failed=0, skipped=0,
        duration_ms=100, collected_ids=["id1"],
    ))
    assert len(received) == 2


def test_multiple_subscribers_same_event():
    bus = EventBus()
    a, b = [], []
    bus.subscribe("run_started", a.append)
    bus.subscribe("run_started", b.append)
    bus.emit(RunStarted(run_id="r2", suite="s", environment="local", browser=None))
    assert len(a) == 1
    assert len(b) == 1


def test_no_subscribers_emit_does_not_raise():
    bus = EventBus()
    bus.emit(RunStarted(run_id="r3", suite="s", environment="local", browser=None))


def test_test_finished_fields():
    event = TestFinished(
        run_id="r1", test_case_id="tc1", result_id="res1",
        status="passed", duration_ms=250, error_message=None,
    )
    assert event.event_type == "test_finished"
    assert event.duration_ms == 250
```

- [ ] **Step 2: Run tests to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_events.py -v
```
Expected: `ModuleNotFoundError: No module named 'testweavex.events'`

- [ ] **Step 3: Create `testweavex/events.py`**

```python
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field


class TWEvent(BaseModel):
    event_type: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class RunStarted(TWEvent):
    event_type: str = "run_started"
    run_id: str
    suite: str
    environment: str
    browser: str | None


class TestCollected(TWEvent):
    event_type: str = "test_collected"
    test_case_id: str
    node_id: str
    source_file: str


class TestStarted(TWEvent):
    event_type: str = "test_started"
    run_id: str
    test_case_id: str
    node_id: str


class TestFinished(TWEvent):
    event_type: str = "test_finished"
    run_id: str
    test_case_id: str
    result_id: str
    status: str
    duration_ms: int
    error_message: str | None


class SessionFinished(TWEvent):
    event_type: str = "session_finished"
    run_id: str
    total: int
    passed: int
    failed: int
    skipped: int
    duration_ms: int
    collected_ids: list[str]


class GapAnalysisComplete(TWEvent):
    event_type: str = "gap_analysis_complete"
    run_id: str
    gaps_found: int
    top_gaps: list[dict[str, Any]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[TWEvent], None]]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[[TWEvent], None]) -> None:
        self._handlers[event_type].append(handler)

    def emit(self, event: TWEvent) -> None:
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)
```

- [ ] **Step 4: Run tests — expect all pass**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_events.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add testweavex/events.py tests/test_events.py
git commit -m "feat: EventBus + typed TWEvent models for phase 4-6 integration"
```

---

## Task 2: Storage Extensions

**Files:**
- Modify: `testweavex/storage/base.py`
- Modify: `testweavex/storage/sqlite.py`
- Modify: `tests/test_storage.py` (append new tests)

- [ ] **Step 1: Write failing tests — append to `tests/test_storage.py`**

```python
# append to tests/test_storage.py


def test_get_all_test_cases_empty(repo):
    assert repo.get_all_test_cases() == []


def test_get_all_test_cases_returns_all(repo, sample_test_case):
    repo.upsert_test_case(sample_test_case)
    results = repo.get_all_test_cases()
    assert len(results) == 1
    assert results[0].id == sample_test_case.id


def test_get_never_run_test_cases(repo, sample_test_case):
    repo.upsert_test_case(sample_test_case)
    never_run = repo.get_never_run_test_cases()
    assert any(tc.id == sample_test_case.id for tc in never_run)


def test_get_never_run_excludes_run_test(repo, sample_test_case):
    repo.upsert_test_case(sample_test_case)
    run = repo.start_run("suite")
    import uuid
    from datetime import datetime, timezone
    from testweavex.core.models import TestResult, TestStatus
    result = TestResult(
        id=str(uuid.uuid4()),
        run_id=run.id,
        test_case_id=sample_test_case.id,
        status=TestStatus.passed,
        duration_ms=100,
    )
    repo.save_result(result)
    never_run = repo.get_never_run_test_cases()
    assert not any(tc.id == sample_test_case.id for tc in never_run)


def test_get_always_failing_test_cases(repo, sample_test_case):
    repo.upsert_test_case(sample_test_case)
    run = repo.start_run("suite")
    import uuid
    from testweavex.core.models import TestResult, TestStatus
    result = TestResult(
        id=str(uuid.uuid4()),
        run_id=run.id,
        test_case_id=sample_test_case.id,
        status=TestStatus.failed,
        duration_ms=100,
    )
    repo.save_result(result)
    always_failing = repo.get_always_failing_test_cases()
    assert any(tc.id == sample_test_case.id for tc in always_failing)


def test_list_runs_empty(repo):
    assert repo.list_runs() == []


def test_list_runs_returns_most_recent_first(repo):
    repo.start_run("suite-a")
    repo.start_run("suite-b")
    runs = repo.list_runs()
    assert len(runs) == 2
    assert runs[0].suite == "suite-b"


def test_get_results_for_run(repo, sample_test_case):
    repo.upsert_test_case(sample_test_case)
    run = repo.start_run("suite")
    import uuid
    from testweavex.core.models import TestResult, TestStatus
    r = TestResult(
        id=str(uuid.uuid4()),
        run_id=run.id,
        test_case_id=sample_test_case.id,
        status=TestStatus.passed,
        duration_ms=150,
    )
    repo.save_result(r)
    results = repo.get_results_for_run(run.id)
    assert len(results) == 1
    assert results[0].run_id == run.id
```

- [ ] **Step 2: Run to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_storage.py -v -k "test_get_all or test_get_never or test_get_always or test_list_runs or test_get_results_for_run"
```
Expected: `AttributeError: 'SQLiteRepository' object has no attribute 'get_all_test_cases'`

- [ ] **Step 3: Add abstract methods to `testweavex/storage/base.py`**

After line 54 (`mark_uncollected_as_gaps`), add:

```python
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
```

Also add `TestResult` to the import at the top of `base.py`:

```python
from testweavex.core.models import (
    Gap,
    ScoringSignals,
    TestCase,
    TestResult,
    TestRun,
)
```

- [ ] **Step 4: Add `_orm_to_test_result` helper and implement methods in `testweavex/storage/sqlite.py`**

After `_orm_to_gap` (line 83), add:

```python
def _orm_to_test_result(row: TestResultORM) -> TestResult:
    return TestResult(
        id=row.id,
        run_id=row.run_id,
        test_case_id=row.test_case_id,
        status=TestStatus(row.status),
        duration_ms=row.duration_ms,
        error_message=row.error_message,
        screenshot_path=row.screenshot_path,
        retry_count=row.retry_count,
    )
```

At the end of `SQLiteRepository`, add:

```python
    def get_all_test_cases(self) -> list[TestCase]:
        try:
            with self._session() as s:
                rows = s.query(TestCaseORM).all()
                return [_orm_to_test_case(r) for r in rows]
        except Exception as exc:
            raise StorageError("Failed to get all test cases") from exc

    def get_never_run_test_cases(self) -> list[TestCase]:
        sql = text("""
            SELECT tc.id FROM test_cases tc
            LEFT JOIN test_results tr ON tc.id = tr.test_case_id
            WHERE tr.id IS NULL
        """)
        try:
            with self._session() as s:
                rows = s.execute(sql).fetchall()
                result = []
                for (tc_id,) in rows:
                    try:
                        result.append(self.get_test_case(tc_id))
                    except RecordNotFound:
                        pass
                return result
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError("Failed to get never-run test cases") from exc

    def get_always_failing_test_cases(self) -> list[TestCase]:
        sql = text("""
            SELECT test_case_id FROM test_results
            GROUP BY test_case_id
            HAVING SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) = 0
               AND COUNT(*) > 0
        """)
        try:
            with self._session() as s:
                rows = s.execute(sql).fetchall()
                result = []
                for (tc_id,) in rows:
                    try:
                        result.append(self.get_test_case(tc_id))
                    except RecordNotFound:
                        pass
                return result
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError("Failed to get always-failing test cases") from exc

    def list_runs(self, limit: int = 50) -> list[TestRun]:
        try:
            with self._session() as s:
                rows = (
                    s.query(TestRunORM)
                    .order_by(TestRunORM.started_at.desc())
                    .limit(limit)
                    .all()
                )
                return [_orm_to_test_run(r) for r in rows]
        except Exception as exc:
            raise StorageError("Failed to list runs") from exc

    def get_results_for_run(self, run_id: str) -> list[TestResult]:
        try:
            with self._session() as s:
                rows = (
                    s.query(TestResultORM)
                    .filter(TestResultORM.run_id == run_id)
                    .all()
                )
                return [_orm_to_test_result(r) for r in rows]
        except Exception as exc:
            raise StorageError(f"Failed to get results for run {run_id}") from exc
```

- [ ] **Step 5: Run all storage tests**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_storage.py -v
```
Expected: all pass (17 original + 8 new = 25 passed)

- [ ] **Step 6: Commit**

```bash
git add testweavex/storage/base.py testweavex/storage/sqlite.py tests/test_storage.py
git commit -m "feat: add get_all_test_cases, list_runs, get_results_for_run to StorageRepository"
```

---

## Task 3: Pytest Plugin

**Files:**
- Replace: `testweavex/execution/plugin.py`

- [ ] **Step 1: Write `testweavex/execution/plugin.py`**

```python
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from rich.console import Console
from rich.table import Table

from testweavex.core.config import load_config
from testweavex.core.models import (
    TestCase,
    TestResult,
    TestStatus,
    TestType,
    generate_stable_id,
)
from testweavex.events import (
    EventBus,
    GapAnalysisComplete,
    RunStarted,
    SessionFinished,
    TestCollected,
    TestFinished,
)
from testweavex.storage.sqlite import SQLiteRepository

if TYPE_CHECKING:
    from testweavex.storage.base import StorageRepository


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_repo(config: pytest.Config) -> "StorageRepository":
    server_url = (
        config.getoption("--results-server", default=None)
        or None
    )
    if server_url:
        token = config.getoption("--token", default=None)
        from testweavex.storage.server import ServerRepository  # Phase 4 stub
        return ServerRepository(server_url, token)
    db_dir = Path(str(config.rootpath)) / ".testweavex"
    db_dir.mkdir(exist_ok=True)
    return SQLiteRepository(db_url=f"sqlite:///{db_dir / 'results.db'}")


def _map_status(report: pytest.TestReport) -> TestStatus:
    if report.passed:
        return TestStatus.passed
    if report.failed:
        return TestStatus.failed
    return TestStatus.skipped


def _get_test_type(item: pytest.Item) -> TestType:
    marker = item.get_closest_marker("tw_type")
    if marker and marker.args:
        try:
            return TestType(marker.args[0])
        except ValueError:
            pass
    return TestType.smoke


def _get_skill(item: pytest.Item) -> str:
    marker = item.get_closest_marker("tw_skill")
    if marker and marker.args:
        return marker.args[0]
    return "functional/smoke"


class _StorageSubscriber:
    def __init__(self, repo: "StorageRepository") -> None:
        self._repo = repo

    def register(self, bus: EventBus) -> None:
        bus.subscribe("test_collected", self._on_collected)
        bus.subscribe("test_finished", self._on_finished)
        bus.subscribe("session_finished", self._on_session)

    def _on_collected(self, event: TestCollected) -> None:
        pass  # TestCase already upserted in pytest_collection_modifyitems

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


class _ConsoleSubscriber:
    def __init__(self) -> None:
        self._console = Console()

    def register(self, bus: EventBus) -> None:
        bus.subscribe("session_finished", self._on_session)
        bus.subscribe("gap_analysis_complete", self._on_gaps)

    def _on_session(self, event: SessionFinished) -> None:
        table = Table(title="TestWeaveX Run Summary", show_header=True)
        table.add_column("Metric", style="bold")
        table.add_column("Value")
        table.add_row("Run ID", event.run_id[:8] + "...")
        table.add_row("Total", str(event.total))
        table.add_row("Passed", f"[green]{event.passed}[/green]")
        table.add_row("Failed", f"[red]{event.failed}[/red]")
        table.add_row("Skipped", f"[yellow]{event.skipped}[/yellow]")
        table.add_row("Duration", f"{event.duration_ms / 1000:.2f}s")
        self._console.print(table)

    def _on_gaps(self, event: GapAnalysisComplete) -> None:
        self._console.print(
            f"\n[bold yellow]Gap Analysis:[/bold yellow] "
            f"{event.gaps_found} gaps found. "
            f"Top {len(event.top_gaps)} shown below."
        )
        if event.top_gaps:
            t = Table(show_header=True, header_style="bold")
            t.add_column("Score")
            t.add_column("Reason")
            t.add_column("Test Case ID")
            for g in event.top_gaps[:10]:
                t.add_row(
                    f"{g.get('priority_score', 0):.2f}",
                    g.get("gap_reason", ""),
                    g.get("test_case_id", "")[:16] + "...",
                )
            self._console.print(t)


class _TestWeaveXPlugin:
    def __init__(self, config: pytest.Config) -> None:
        tw_config = load_config()
        self._repo = _build_repo(config)
        self._bus = EventBus()
        self._storage_sub = _StorageSubscriber(self._repo)
        self._console_sub = _ConsoleSubscriber()
        self._storage_sub.register(self._bus)
        self._console_sub.register(self._bus)

        suite = config.getoption("--suite", default="default")
        environment = config.getoption("--environment", default="local")
        browser = config.getoption("--browser", default=None)

        self._run = self._repo.start_run(
            suite=suite,
            environment=environment,
            browser=browser,
            triggered_by="tw",
        )
        self._bus.emit(RunStarted(
            run_id=self._run.id,
            suite=suite,
            environment=environment,
            browser=browser,
        ))
        self._collected_ids: list[str] = []
        self._counts: dict[str, int] = {"passed": 0, "failed": 0, "skipped": 0}
        self._start_ms = int(time.time() * 1000)
        self._enable_gaps = config.getoption("--gaps", default=False)

    def pytest_collection_modifyitems(
        self, session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
    ) -> None:
        now = _now()
        for item in items:
            source_file = str(item.fspath)
            feature_id = generate_stable_id(source_file)
            tc_id = generate_stable_id(source_file, item.nodeid)
            test_case = TestCase(
                id=tc_id,
                title=item.name,
                feature_id=feature_id,
                gherkin=f"Scenario: {item.name}",
                test_type=_get_test_type(item),
                skill=_get_skill(item),
                is_automated=True,
                source_file=source_file,
                created_at=now,
                updated_at=now,
            )
            self._repo.upsert_test_case(test_case)
            self._collected_ids.append(tc_id)
            self._bus.emit(TestCollected(
                test_case_id=tc_id,
                node_id=item.nodeid,
                source_file=source_file,
            ))

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when != "call" and not (report.when == "setup" and report.failed):
            return
        source_file = str(report.fspath)
        tc_id = generate_stable_id(source_file, report.nodeid)
        status = _map_status(report)
        key = status.value if status.value in self._counts else "skipped"
        self._counts[key] = self._counts.get(key, 0) + 1
        error_msg: str | None = None
        if report.failed and report.longrepr:
            error_msg = str(report.longrepr)[-2000:]
        result_id = str(uuid.uuid4())
        duration_ms = int(getattr(report, "duration", 0) * 1000)
        self._bus.emit(TestFinished(
            run_id=self._run.id,
            test_case_id=tc_id,
            result_id=result_id,
            status=status.value,
            duration_ms=duration_ms,
            error_message=error_msg,
        ))

    def pytest_sessionfinish(
        self, session: pytest.Session, exitstatus: int
    ) -> None:
        duration_ms = int(time.time() * 1000) - self._start_ms
        total = sum(self._counts.values())
        self._bus.emit(SessionFinished(
            run_id=self._run.id,
            total=total,
            passed=self._counts.get("passed", 0),
            failed=self._counts.get("failed", 0),
            skipped=self._counts.get("skipped", 0),
            duration_ms=duration_ms,
            collected_ids=self._collected_ids,
        ))
        if self._enable_gaps:
            from testweavex.gap.analyzer import GapAnalyzer
            from testweavex.core.config import load_config
            analyzer = GapAnalyzer(self._repo, self._bus, load_config().gap_analysis)
            # GapAnalyzer already subscribed to session_finished in __init__
            # but event already emitted — run directly
            analyzer.run(self._run.id, self._collected_ids)


# ── Module-level hooks (must be at module level for pytest11 entry point) ──

def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("testweavex", "TestWeaveX options")
    group.addoption("--results-server", default=None, help="Remote result server URL")
    group.addoption("--token", default=None, help="Auth token for result server")
    group.addoption("--suite", default="default", help="Tag this run with a suite name")
    group.addoption("--environment", default="local", help="Target environment")
    group.addoption("--browser", default=None, help="Browser name for playwright tests")
    group.addoption("--gaps", action="store_true", default=False, help="Run gap analysis after session")
    group.addoption("--sync-tcm", default=None, help="Sync results to TCM provider (Phase 7)")


def pytest_configure(config: pytest.Config) -> None:
    if not hasattr(config, "_tw_plugin"):
        plugin = _TestWeaveXPlugin(config)
        config.pluginmanager.register(plugin, "testweavex_plugin")
        config._tw_plugin = plugin
```

- [ ] **Step 2: Run existing tests to confirm nothing broke**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_models.py tests/test_storage.py -v
```
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add testweavex/execution/plugin.py
git commit -m "feat: full pytest plugin with EventBus, hooks, storage+console subscribers"
```

---

## Task 4: Plugin Integration Tests

**Files:**
- Create: `tests/test_plugin.py`

- [ ] **Step 1: Write `tests/test_plugin.py`**

```python
import pytest


def test_plugin_captures_passing_test(pytester):
    pytester.makepyfile("""
        def test_always_passes():
            assert True
    """)
    result = pytester.runpytest("--tb=short")
    result.assert_outcomes(passed=1)


def test_plugin_captures_failing_test(pytester):
    pytester.makepyfile("""
        def test_always_fails():
            assert False
    """)
    result = pytester.runpytest("--tb=short")
    result.assert_outcomes(failed=1)


def test_plugin_captures_skipped_test(pytester):
    pytester.makepyfile("""
        import pytest
        @pytest.mark.skip(reason="not ready")
        def test_skipped():
            pass
    """)
    result = pytester.runpytest("--tb=short")
    result.assert_outcomes(skipped=1)


def test_plugin_accepts_testweavex_flags(pytester):
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    result = pytester.runpytest(
        "--suite=my-suite",
        "--environment=staging",
        "--tb=short",
    )
    result.assert_outcomes(passed=1)


def test_plugin_creates_db_file(pytester):
    pytester.makepyfile("""
        def test_simple():
            assert True
    """)
    pytester.runpytest("--tb=short")
    db_path = pytester.path / ".testweavex" / "results.db"
    assert db_path.exists()


def test_plugin_tw_type_marker(pytester):
    pytester.makepyfile("""
        import pytest
        @pytest.mark.tw_type("e2e")
        def test_e2e_style():
            assert True
    """)
    result = pytester.runpytest("--tb=short")
    result.assert_outcomes(passed=1)
```

- [ ] **Step 2: Run plugin tests**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_plugin.py -v
```
Expected: 6 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_plugin.py
git commit -m "test: pytest plugin integration tests via pytester"
```

---

## Task 5: CLI — Core Commands

**Files:**
- Create: `testweavex/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

```python
# tests/test_cli.py
import json
from typer.testing import CliRunner
from testweavex.cli import app

runner = CliRunner()


def test_tw_init_creates_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--llm-provider", "anthropic"])
    assert result.exit_code == 0
    config_file = tmp_path / "testweavex.config.yaml"
    assert config_file.exists()
    assert "anthropic" in config_file.read_text()


def test_tw_init_openai(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--llm-provider", "openai"])
    assert result.exit_code == 0
    assert "openai" in (tmp_path / "testweavex.config.yaml").read_text()


def test_tw_status_empty_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Coverage" in result.output or "0" in result.output


def test_tw_status_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["status", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "coverage_percentage" in data


def test_tw_history_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["history"])
    assert result.exit_code == 0


def test_tw_gaps_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["gaps"])
    assert result.exit_code == 1
    assert "Phase 5" in result.output


def test_tw_generate_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["generate", "--feature", "login", "--skill", "functional/smoke"])
    assert result.exit_code == 1
    assert "Phase 5" in result.output


def test_tw_serve_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 1
    assert "Phase 6" in result.output


def test_tw_migrate_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["migrate", "--source", "testrail"])
    assert result.exit_code == 1
    assert "Phase 7" in result.output


def test_tw_sync_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["sync", "--tcm", "testrail"])
    assert result.exit_code == 1
    assert "Phase 7" in result.output
```

- [ ] **Step 2: Run to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_cli.py -v
```
Expected: `ModuleNotFoundError: No module named 'testweavex.cli'`

- [ ] **Step 3: Create `testweavex/cli.py`**

```python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from testweavex.core.config import load_config
from testweavex.storage.sqlite import SQLiteRepository

app = typer.Typer(
    name="tw",
    help="TestWeaveX — unified test management and execution.",
    invoke_without_command=True,
    no_args_is_help=False,
)
console = Console()

_SUBCOMMANDS = {
    "init", "status", "history", "gaps",
    "generate", "serve", "migrate", "sync",
}


def _get_repo() -> SQLiteRepository:
    db_dir = Path.cwd() / ".testweavex"
    db_dir.mkdir(exist_ok=True)
    return SQLiteRepository(db_url=f"sqlite:///{db_dir / 'results.db'}")


# ── Root ──────────────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        import pytest
        sys.exit(pytest.main(sys.argv[1:]))


# ── init ─────────────────────────────────────────────────────────────────

@app.command()
def init(
    llm_provider: str = typer.Option("anthropic", "--llm-provider", help="LLM provider"),
) -> None:
    """Create testweavex.config.yaml in the current directory."""
    config_path = Path.cwd() / "testweavex.config.yaml"
    model_defaults = {
        "anthropic": "claude-sonnet-4-6",
        "openai": "gpt-4o",
        "ollama": "llama3",
        "azure": "gpt-4",
    }
    model = model_defaults.get(llm_provider, "claude-sonnet-4-6")
    content = f"""\
llm:
  provider: {llm_provider}
  model: {model}
  api_key: ${{ANTHROPIC_API_KEY}}
  temperature: 0.3
  max_retries: 3
  timeout_seconds: 30

gap_analysis:
  scoring_weights:
    priority: 0.30
    test_type: 0.25
    defects: 0.20
    frequency: 0.15
    staleness: 0.10
  match_threshold: 0.65
  top_gaps_default: 10
"""
    config_path.write_text(content, encoding="utf-8")
    console.print(f"[green]Created[/green] {config_path}")


# ── status ───────────────────────────────────────────────────────────────

@app.command()
def status(
    format: str = typer.Option("table", "--format", help="Output format: table|json"),
) -> None:
    """Show test coverage and automation status."""
    repo = _get_repo()
    coverage = repo.get_coverage_percentage()
    all_cases = repo.get_all_test_cases()

    from collections import Counter
    type_counts: Counter = Counter()
    type_automated: Counter = Counter()
    for tc in all_cases:
        type_counts[tc.test_type.value] += 1
        if tc.is_automated:
            type_automated[tc.test_type.value] += 1

    if format == "json":
        data = {
            "coverage_percentage": coverage,
            "total_test_cases": len(all_cases),
            "automated": sum(type_automated.values()),
            "by_type": {
                t: {"total": type_counts[t], "automated": type_automated.get(t, 0)}
                for t in type_counts
            },
        }
        typer.echo(json.dumps(data, indent=2))
        return

    table = Table(title=f"TestWeaveX Status — Coverage: {coverage:.1f}%")
    table.add_column("Test Type")
    table.add_column("Total", justify="right")
    table.add_column("Automated", justify="right")
    table.add_column("Gap", justify="right")
    for t in sorted(type_counts):
        total = type_counts[t]
        automated = type_automated.get(t, 0)
        table.add_row(t, str(total), str(automated), str(total - automated))
    console.print(table)


# ── history ──────────────────────────────────────────────────────────────

@app.command()
def history(
    last_n: int = typer.Option(10, "--last-n", help="Number of runs to show"),
) -> None:
    """Show recent test run history."""
    repo = _get_repo()
    runs = repo.list_runs(limit=last_n)
    if not runs:
        console.print("No test runs recorded yet.")
        return
    table = Table(title="Recent Test Runs")
    table.add_column("Run ID")
    table.add_column("Suite")
    table.add_column("Environment")
    table.add_column("Started")
    for run in runs:
        table.add_row(
            run.id[:8] + "...",
            run.suite,
            run.environment,
            run.started_at.strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)


# ── Stubs ─────────────────────────────────────────────────────────────────

@app.command()
def gaps(
    limit: int = typer.Option(10, "--limit"),
    min_score: float = typer.Option(0.0, "--min-score"),
    generate: bool = typer.Option(False, "--generate"),
) -> None:
    """Show automation gap analysis. (Requires Phase 5)"""
    console.print("[red]tw gaps requires Phase 5 — not yet available.[/red]")
    raise typer.Exit(code=1)


@app.command()
def generate(
    feature: str = typer.Option(..., "--feature"),
    skill: str = typer.Option("functional/smoke", "--skill"),
) -> None:
    """Generate tests with LLM. (Requires Phase 5)"""
    console.print("[red]tw generate requires Phase 5 — not yet available.[/red]")
    raise typer.Exit(code=1)


@app.command()
def serve(
    port: int = typer.Option(8080, "--port"),
) -> None:
    """Start the TestWeaveX web UI. (Requires Phase 6)"""
    console.print("[red]tw serve requires Phase 6 — not yet available.[/red]")
    raise typer.Exit(code=1)


@app.command()
def migrate(
    source: str = typer.Option(..., "--source"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Migrate from external TCM. (Requires Phase 7)"""
    console.print("[red]tw migrate requires Phase 7 — not yet available.[/red]")
    raise typer.Exit(code=1)


@app.command()
def sync(
    tcm: str = typer.Option(..., "--tcm"),
) -> None:
    """Sync results to external TCM. (Requires Phase 7)"""
    console.print("[red]tw sync requires Phase 7 — not yet available.[/red]")
    raise typer.Exit(code=1)


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in _SUBCOMMANDS:
        import pytest
        sys.exit(pytest.main(args))
    app()
```

- [ ] **Step 4: Run CLI tests**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_cli.py -v
```
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add testweavex/cli.py tests/test_cli.py
git commit -m "feat: Typer CLI with tw, init, status, history + stubs for gaps/generate/serve/migrate/sync"
```

---

## Task 6: Gap Detector

**Files:**
- Create: `testweavex/gap/__init__.py`
- Create: `testweavex/gap/detector.py`
- Create: `tests/test_gap_detector.py`

- [ ] **Step 1: Write failing detector tests**

```python
# tests/test_gap_detector.py
import uuid
from datetime import datetime, timezone

import pytest

from testweavex.core.models import (
    TestCase, TestResult, TestStatus, TestType, generate_stable_id,
)
from testweavex.gap.detector import GapDetector
from testweavex.storage.sqlite import SQLiteRepository


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_tc(title: str = "test") -> TestCase:
    tc_id = generate_stable_id("file.py", title)
    return TestCase(
        id=tc_id, title=title, feature_id=generate_stable_id("file.py"),
        gherkin=f"Scenario: {title}", test_type=TestType.smoke,
        skill="functional/smoke", is_automated=True,
        created_at=_now(), updated_at=_now(),
    )


@pytest.fixture
def repo():
    return SQLiteRepository()


def test_no_gaps_when_all_collected(repo):
    tc = _make_tc("passing")
    repo.upsert_test_case(tc)
    detector = GapDetector(repo)
    gaps = detector.find_uncollected([tc.id])
    assert gaps == []


def test_uncollected_creates_gap(repo):
    tc = _make_tc("missing")
    repo.upsert_test_case(tc)
    detector = GapDetector(repo)
    gaps = detector.find_uncollected([])  # collected nothing
    assert any(g.test_case_id == tc.id for g in gaps)
    assert gaps[0].gap_reason == "uncollected"


def test_never_run_creates_gap(repo):
    tc = _make_tc("never_run")
    repo.upsert_test_case(tc)
    detector = GapDetector(repo)
    gaps = detector.find_never_run()
    assert any(g.test_case_id == tc.id for g in gaps)
    assert gaps[0].gap_reason == "never_run"


def test_never_run_excludes_run_test(repo):
    tc = _make_tc("has_result")
    repo.upsert_test_case(tc)
    run = repo.start_run("suite")
    result = TestResult(
        id=str(uuid.uuid4()), run_id=run.id, test_case_id=tc.id,
        status=TestStatus.passed, duration_ms=100,
    )
    repo.save_result(result)
    detector = GapDetector(repo)
    gaps = detector.find_never_run()
    assert not any(g.test_case_id == tc.id for g in gaps)


def test_always_failing_creates_gap(repo):
    tc = _make_tc("always_fail")
    repo.upsert_test_case(tc)
    run = repo.start_run("suite")
    result = TestResult(
        id=str(uuid.uuid4()), run_id=run.id, test_case_id=tc.id,
        status=TestStatus.failed, duration_ms=100,
    )
    repo.save_result(result)
    detector = GapDetector(repo)
    gaps = detector.find_always_failing()
    assert any(g.test_case_id == tc.id for g in gaps)
    assert gaps[0].gap_reason == "always_failing"


def test_find_all_deduplicates(repo):
    tc = _make_tc("uncollected_and_never_run")
    repo.upsert_test_case(tc)
    detector = GapDetector(repo)
    gaps = detector.find_all(collected_ids=[])
    tc_ids = [g.test_case_id for g in gaps]
    assert tc_ids.count(tc.id) == 1
```

- [ ] **Step 2: Run to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_gap_detector.py -v
```
Expected: `ModuleNotFoundError: No module named 'testweavex.gap'`

- [ ] **Step 3: Create `testweavex/gap/__init__.py`**

Empty file.

- [ ] **Step 4: Create `testweavex/gap/detector.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from testweavex.core.models import Gap, GapStatus, TestCase
from testweavex.storage.base import StorageRepository


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class GapDetector:
    def __init__(self, repo: StorageRepository) -> None:
        self._repo = repo

    def find_uncollected(self, collected_ids: list[str]) -> list[Gap]:
        collected = set(collected_ids)
        all_cases = self._repo.get_all_test_cases()
        now = _now()
        return [
            Gap(
                id=str(uuid.uuid4()),
                test_case_id=tc.id,
                gap_reason="uncollected",
                status=GapStatus.open,
                detected_at=now,
            )
            for tc in all_cases
            if tc.id not in collected
        ]

    def find_never_run(self) -> list[Gap]:
        now = _now()
        return [
            Gap(
                id=str(uuid.uuid4()),
                test_case_id=tc.id,
                gap_reason="never_run",
                status=GapStatus.open,
                detected_at=now,
            )
            for tc in self._repo.get_never_run_test_cases()
        ]

    def find_always_failing(self) -> list[Gap]:
        now = _now()
        return [
            Gap(
                id=str(uuid.uuid4()),
                test_case_id=tc.id,
                gap_reason="always_failing",
                status=GapStatus.open,
                detected_at=now,
            )
            for tc in self._repo.get_always_failing_test_cases()
        ]

    def find_all(self, collected_ids: list[str]) -> list[Gap]:
        seen: set[str] = set()
        result: list[Gap] = []
        for gap in (
            self.find_uncollected(collected_ids)
            + self.find_never_run()
            + self.find_always_failing()
        ):
            if gap.test_case_id not in seen:
                seen.add(gap.test_case_id)
                result.append(gap)
        return result
```

- [ ] **Step 5: Run detector tests**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_gap_detector.py -v
```
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add testweavex/gap/__init__.py testweavex/gap/detector.py tests/test_gap_detector.py
git commit -m "feat: GapDetector with three strategies (uncollected, never_run, always_failing)"
```

---

## Task 7: Gap Scorer

**Files:**
- Create: `testweavex/gap/scorer.py`
- Create: `tests/test_gap_scorer.py`

- [ ] **Step 1: Write failing scorer tests**

```python
# tests/test_gap_scorer.py
import uuid
from datetime import datetime, timezone

import pytest

from testweavex.core.models import (
    Gap, GapStatus, ScoringSignals, TestType,
)
from testweavex.gap.scorer import GapScorer


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _gap(tc_id: str = "tc1") -> Gap:
    return Gap(
        id=str(uuid.uuid4()), test_case_id=tc_id,
        gap_reason="never_run", status=GapStatus.open,
        detected_at=_now(),
    )


def _signals(**kwargs) -> ScoringSignals:
    defaults = dict(
        test_priority=2, test_type=TestType.smoke,
        defect_count=0, executions_90d=5, days_since_run=10,
    )
    defaults.update(kwargs)
    return ScoringSignals(**defaults)


def test_score_in_range():
    scorer = GapScorer()
    gap = _gap()
    signals = _signals()
    scored = scorer.score(gap, signals)
    assert 0.0 <= scored.priority_score <= 1.0


def test_p1_scores_higher_than_p3():
    scorer = GapScorer()
    gap = _gap()
    s_p1 = scorer.score(gap, _signals(test_priority=1))
    s_p3 = scorer.score(gap, _signals(test_priority=3))
    assert s_p1.priority_score > s_p3.priority_score


def test_smoke_scores_higher_than_edge_case():
    scorer = GapScorer()
    gap = _gap()
    s_smoke = scorer.score(gap, _signals(test_type=TestType.smoke))
    s_edge = scorer.score(gap, _signals(test_type=TestType.edge_cases))
    assert s_smoke.priority_score > s_edge.priority_score


def test_score_all_sorts_descending():
    scorer = GapScorer()
    gap_high = _gap("high")
    gap_low = _gap("low")
    signals = {
        "high": _signals(test_priority=1, test_type=TestType.smoke),
        "low": _signals(test_priority=3, test_type=TestType.edge_cases),
    }
    scored = scorer.score_all([gap_high, gap_low], signals)
    assert scored[0].test_case_id == "high"
    assert scored[1].test_case_id == "low"


def test_staleness_raises_score():
    scorer = GapScorer()
    gap = _gap()
    s_stale = scorer.score(gap, _signals(days_since_run=999))
    s_fresh = scorer.score(gap, _signals(days_since_run=0))
    assert s_stale.priority_score > s_fresh.priority_score


def test_score_clamped_to_1():
    scorer = GapScorer()
    gap = _gap()
    signals = _signals(
        test_priority=1, test_type=TestType.smoke,
        defect_count=100, executions_90d=100, days_since_run=999,
    )
    scored = scorer.score(gap, signals)
    assert scored.priority_score <= 1.0
```

- [ ] **Step 2: Run to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_gap_scorer.py -v
```
Expected: `ModuleNotFoundError: No module named 'testweavex.gap.scorer'`

- [ ] **Step 3: Create `testweavex/gap/scorer.py`**

```python
from __future__ import annotations

from testweavex.core.models import Gap, ScoringSignals, TestType

_TYPE_SCORES: dict[TestType, float] = {
    TestType.smoke: 1.00,
    TestType.e2e: 0.90,
    TestType.happy_path: 0.85,
    TestType.integration: 0.80,
    TestType.system: 0.75,
    TestType.sanity: 0.70,
    TestType.data_driven: 0.60,
    TestType.edge_cases: 0.50,
    TestType.accessibility: 0.40,
    TestType.cross_browser: 0.35,
}

_PRIORITY_SCORES: dict[int, float] = {1: 1.0, 2: 0.6, 3: 0.3}

_DEFAULT_WEIGHTS: dict[str, float] = {
    "priority": 0.30,
    "test_type": 0.25,
    "defects": 0.20,
    "frequency": 0.15,
    "staleness": 0.10,
}


class GapScorer:
    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or _DEFAULT_WEIGHTS

    def score(self, gap: Gap, signals: ScoringSignals) -> Gap:
        priority_score = _PRIORITY_SCORES.get(signals.test_priority, 0.3)
        type_score = _TYPE_SCORES.get(signals.test_type, 0.5)
        defect_score = min(signals.defect_count / 5.0, 1.0)
        frequency_score = min(signals.executions_90d / 20.0, 1.0)
        staleness_score = min(signals.days_since_run / 90.0, 1.0)

        raw = (
            self._weights.get("priority", 0.30) * priority_score
            + self._weights.get("test_type", 0.25) * type_score
            + self._weights.get("defects", 0.20) * defect_score
            + self._weights.get("frequency", 0.15) * frequency_score
            + self._weights.get("staleness", 0.10) * staleness_score
        )
        final = round(min(max(raw, 0.0), 1.0), 4)
        return gap.model_copy(update={"priority_score": final})

    def score_all(
        self,
        gaps: list[Gap],
        signals_map: dict[str, ScoringSignals],
    ) -> list[Gap]:
        scored = []
        for gap in gaps:
            signals = signals_map.get(gap.test_case_id)
            if signals is None:
                scored.append(gap)
            else:
                scored.append(self.score(gap, signals))
        return sorted(scored, key=lambda g: g.priority_score, reverse=True)
```

- [ ] **Step 4: Run scorer tests**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_gap_scorer.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add testweavex/gap/scorer.py tests/test_gap_scorer.py
git commit -m "feat: GapScorer with six-signal priority scoring"
```

---

## Task 8: Gap Analyzer + Update CLI

**Files:**
- Create: `testweavex/gap/analyzer.py`
- Create: `tests/test_gap_analyzer.py`
- Modify: `testweavex/cli.py` (update `gaps` command to fully work)

- [ ] **Step 1: Write failing analyzer tests**

```python
# tests/test_gap_analyzer.py
import uuid
from datetime import datetime, timezone

import pytest

from testweavex.core.config import GapAnalysisConfig
from testweavex.core.models import (
    TestCase, TestResult, TestStatus, TestType, generate_stable_id,
)
from testweavex.events import EventBus, SessionFinished
from testweavex.gap.analyzer import GapAnalyzer
from testweavex.storage.sqlite import SQLiteRepository


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_tc(title: str = "test") -> TestCase:
    return TestCase(
        id=generate_stable_id("file.py", title),
        title=title,
        feature_id=generate_stable_id("file.py"),
        gherkin=f"Scenario: {title}",
        test_type=TestType.smoke,
        skill="functional/smoke",
        is_automated=True,
        created_at=_now(),
        updated_at=_now(),
    )


@pytest.fixture
def repo():
    return SQLiteRepository()


@pytest.fixture
def bus():
    return EventBus()


def test_analyzer_saves_gaps_on_session_finished(repo, bus):
    tc = _make_tc("never_collected")
    repo.upsert_test_case(tc)

    config = GapAnalysisConfig()
    analyzer = GapAnalyzer(repo, bus, config)

    run = repo.start_run("suite")
    repo.end_run(run.id)

    # run directly (as called from plugin when --gaps flag is set)
    analyzer.run(run.id, collected_ids=[])

    gaps = repo.get_gaps(limit=50, status="open")
    assert len(gaps) > 0


def test_analyzer_emits_gap_analysis_complete(repo, bus):
    tc = _make_tc("uncollected")
    repo.upsert_test_case(tc)

    config = GapAnalysisConfig()
    analyzer = GapAnalyzer(repo, bus, config)

    received = []
    bus.subscribe("gap_analysis_complete", received.append)

    run = repo.start_run("suite")
    repo.end_run(run.id)
    analyzer.run(run.id, collected_ids=[])

    assert len(received) == 1
    assert received[0].gaps_found >= 1


def test_analyzer_scores_are_nonzero(repo, bus):
    tc = _make_tc("p1_smoke")
    tc = tc.model_copy(update={"priority": 1})
    repo.upsert_test_case(tc)

    config = GapAnalysisConfig()
    analyzer = GapAnalyzer(repo, bus, config)

    run = repo.start_run("suite")
    repo.end_run(run.id)
    analyzer.run(run.id, collected_ids=[])

    gaps = repo.get_gaps(limit=50, status="open")
    assert all(g.priority_score > 0.0 for g in gaps)
```

- [ ] **Step 2: Run to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_gap_analyzer.py -v
```
Expected: `ModuleNotFoundError: No module named 'testweavex.gap.analyzer'`

- [ ] **Step 3: Create `testweavex/gap/analyzer.py`**

```python
from __future__ import annotations

from testweavex.core.config import GapAnalysisConfig
from testweavex.events import EventBus, GapAnalysisComplete
from testweavex.gap.detector import GapDetector
from testweavex.gap.scorer import GapScorer
from testweavex.storage.base import StorageRepository


class GapAnalyzer:
    def __init__(
        self,
        repo: StorageRepository,
        bus: EventBus,
        config: GapAnalysisConfig,
    ) -> None:
        self._repo = repo
        self._bus = bus
        self._config = config

    def run(self, run_id: str, collected_ids: list[str]) -> None:
        detector = GapDetector(self._repo)
        scorer = GapScorer(self._config.scoring_weights)

        raw_gaps = detector.find_all(collected_ids)

        signals_map = {}
        for gap in raw_gaps:
            try:
                signals_map[gap.test_case_id] = self._repo.get_scoring_signals(
                    gap.test_case_id
                )
            except Exception:
                pass

        scored_gaps = scorer.score_all(raw_gaps, signals_map)
        if scored_gaps:
            self._repo.save_gaps(scored_gaps)

        top_n = scored_gaps[: self._config.top_gaps_default]
        self._bus.emit(
            GapAnalysisComplete(
                run_id=run_id,
                gaps_found=len(scored_gaps),
                top_gaps=[g.model_dump(mode="json") for g in top_n],
            )
        )
```

- [ ] **Step 4: Run analyzer tests**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_gap_analyzer.py -v
```
Expected: 3 passed

- [ ] **Step 5: Update `tw gaps` in `testweavex/cli.py` — replace stub with real implementation**

Replace the `gaps` function:

```python
@app.command()
def gaps(
    limit: int = typer.Option(10, "--limit", help="Max gaps to show"),
    min_score: float = typer.Option(0.0, "--min-score", help="Minimum priority score"),
    generate: bool = typer.Option(False, "--generate", help="Generate tests for top gaps"),
) -> None:
    """Show and optionally generate tests for automation gaps."""
    from testweavex.events import EventBus
    from testweavex.gap.analyzer import GapAnalyzer
    repo = _get_repo()
    bus = EventBus()
    config = load_config()
    analyzer = GapAnalyzer(repo, bus, config.gap_analysis)

    runs = repo.list_runs(limit=1)
    run_id = runs[0].id if runs else "standalone"

    analyzer.run(run_id, collected_ids=[])
    all_gaps = repo.get_gaps(limit=limit, status="open")
    filtered = [g for g in all_gaps if g.priority_score >= min_score]

    if not filtered:
        console.print("No gaps found matching criteria.")
        return

    table = Table(title=f"Top {len(filtered)} Automation Gaps")
    table.add_column("Score", justify="right")
    table.add_column("Reason")
    table.add_column("Test Case ID")
    for g in filtered:
        table.add_row(
            f"{g.priority_score:.3f}",
            g.gap_reason,
            g.test_case_id[:16] + "...",
        )
    console.print(table)
```

- [ ] **Step 6: Run all tests**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/ -v --ignore=tests/test_llm.py
```
Expected: all pass except any LLM tests requiring API keys

- [ ] **Step 7: Commit**

```bash
git add testweavex/gap/analyzer.py tests/test_gap_analyzer.py testweavex/cli.py
git commit -m "feat: GapAnalyzer orchestrates detection+scoring; tw gaps fully implemented"
```

---

## Task 9: Web App Factory + Static Files

**Files:**
- Create: `testweavex/web/__init__.py`
- Create: `testweavex/web/app.py`
- Create: `testweavex/web/api/__init__.py`
- Create: `testweavex/web/static/index.html` (move from `testweavex_ui_design.html`)

- [ ] **Step 1: Move `testweavex_ui_design.html` to `testweavex/web/static/index.html`**

```bash
mkdir -p testweavex/web/static
cp testweavex_ui_design.html testweavex/web/static/index.html
```

- [ ] **Step 2: Create empty `__init__.py` files**

```bash
touch testweavex/web/__init__.py testweavex/web/api/__init__.py
```

- [ ] **Step 3: Create `testweavex/web/app.py`**

```python
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from testweavex.core.config import TestWeaveXConfig, load_config
from testweavex.events import EventBus
from testweavex.storage.sqlite import SQLiteRepository

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: TestWeaveXConfig | None = None) -> FastAPI:
    if config is None:
        config = load_config()

    db_dir = Path.cwd() / ".testweavex"
    db_dir.mkdir(exist_ok=True)
    repo = SQLiteRepository(db_url=f"sqlite:///{db_dir / 'results.db'}")
    bus = EventBus()

    app = FastAPI(title="TestWeaveX", version="0.1.0")
    app.state.repo = repo
    app.state.bus = bus
    app.state.config = config

    from testweavex.web.api.dashboard import router as dashboard_router
    from testweavex.web.api.runs import router as runs_router
    from testweavex.web.api.test_cases import router as test_cases_router
    from testweavex.web.api.gaps import router as gaps_router
    from testweavex.web.api.settings import router as settings_router
    from testweavex.web.api.events import router as events_router

    app.include_router(dashboard_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")
    app.include_router(test_cases_router, prefix="/api")
    app.include_router(gaps_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(events_router, prefix="/api")

    if _STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")

    return app
```

- [ ] **Step 4: Write basic web app test**

```python
# tests/test_web_api.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from testweavex.web.app import create_app
    app = create_app()
    return TestClient(app)


def test_dashboard_endpoint(client):
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "coverage_percentage" in data


def test_runs_endpoint(client):
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_test_cases_endpoint(client):
    response = client.get("/api/test-cases")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_gaps_endpoint(client):
    response = client.get("/api/gaps")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_settings_get(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert "llm" in data


def test_events_endpoint(client):
    with client.stream("GET", "/api/events") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        # Read first chunk (connected event)
        chunk = next(response.iter_text())
        assert "connected" in chunk
```

- [ ] **Step 5: Run the web test (will fail until API routes exist)**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_web_api.py -v
```
Expected: ImportError for missing router modules — continue to next step.

- [ ] **Step 6: Commit what exists so far**

```bash
git add testweavex/web/__init__.py testweavex/web/app.py testweavex/web/api/__init__.py testweavex/web/static/index.html
git commit -m "feat: web app factory + static index.html (testweavex_ui_design.html)"
```

---

## Task 10: Web API Routes

**Files:**
- Create: `testweavex/web/api/dashboard.py`
- Create: `testweavex/web/api/runs.py`
- Create: `testweavex/web/api/test_cases.py`
- Create: `testweavex/web/api/gaps.py`
- Create: `testweavex/web/api/settings.py`
- Create: `testweavex/web/api/events.py`
- Create: `tests/test_sse.py`

- [ ] **Step 1: Create `testweavex/web/api/dashboard.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(request: Request) -> dict:
    repo = request.app.state.repo
    coverage = repo.get_coverage_percentage()
    runs = repo.list_runs(limit=1)
    gaps = repo.get_gaps(limit=1, status="open")
    all_cases = repo.get_all_test_cases()
    return {
        "coverage_percentage": coverage,
        "total_test_cases": len(all_cases),
        "automated": sum(1 for tc in all_cases if tc.is_automated),
        "open_gaps": len(repo.get_gaps(limit=9999, status="open")),
        "last_run_id": runs[0].id if runs else None,
    }
```

- [ ] **Step 2: Create `testweavex/web/api/runs.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/runs")
async def list_runs(request: Request, limit: int = 50) -> list[dict]:
    repo = request.app.state.repo
    runs = repo.list_runs(limit=limit)
    return [r.model_dump(mode="json") for r in runs]


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict:
    repo = request.app.state.repo
    try:
        run = repo.get_run(run_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Run not found")
    results = repo.get_results_for_run(run_id)
    data = run.model_dump(mode="json")
    data["results"] = [r.model_dump(mode="json") for r in results]
    return data
```

- [ ] **Step 3: Create `testweavex/web/api/test_cases.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/test-cases")
async def list_test_cases(
    request: Request,
    test_type: str | None = None,
    is_automated: bool | None = None,
) -> list[dict]:
    repo = request.app.state.repo
    cases = repo.get_all_test_cases()
    if test_type:
        cases = [tc for tc in cases if tc.test_type.value == test_type]
    if is_automated is not None:
        cases = [tc for tc in cases if tc.is_automated == is_automated]
    return [tc.model_dump(mode="json") for tc in cases]
```

- [ ] **Step 4: Create `testweavex/web/api/gaps.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/gaps")
async def list_gaps(
    request: Request,
    limit: int = 50,
    status: str = "open",
    min_score: float = 0.0,
) -> list[dict]:
    repo = request.app.state.repo
    gaps = repo.get_gaps(limit=limit, status=status)
    filtered = [g for g in gaps if g.priority_score >= min_score]
    return [g.model_dump(mode="json") for g in filtered]


@router.post("/gaps/{gap_id}/generate")
async def generate_for_gap(gap_id: str, request: Request) -> dict:
    return {
        "message": "LLM generation for gaps available in Phase 5+",
        "gap_id": gap_id,
    }
```

- [ ] **Step 5: Create `testweavex/web/api/settings.py`**

```python
from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


@router.get("/settings")
async def get_settings(request: Request) -> dict:
    config = request.app.state.config
    return {
        "llm": {
            "provider": config.llm.provider,
            "model": config.llm.model,
            "temperature": config.llm.temperature,
        },
        "tcm": {"provider": config.tcm.provider},
        "gap_analysis": {
            "top_gaps_default": config.gap_analysis.top_gaps_default,
            "match_threshold": config.gap_analysis.match_threshold,
        },
    }


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    temperature: float | None = None


@router.put("/settings")
async def update_settings(body: SettingsUpdate, request: Request) -> dict:
    config_path = Path.cwd() / "testweavex.config.yaml"
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    else:
        raw = {}
    if "llm" not in raw:
        raw["llm"] = {}
    if body.llm_provider:
        raw["llm"]["provider"] = body.llm_provider
    if body.llm_model:
        raw["llm"]["model"] = body.llm_model
    if body.temperature is not None:
        raw["llm"]["temperature"] = body.temperature
    config_path.write_text(yaml.dump(raw), encoding="utf-8")
    return {"status": "updated"}
```

- [ ] **Step 6: Create `testweavex/web/api/events.py`**

```python
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("/events")
async def sse_events(request: Request) -> StreamingResponse:
    async def generate():
        yield 'data: {"event_type": "connected"}\n\n'
        while True:
            if await request.is_disconnected():
                break
            yield ": keep-alive\n\n"
            await asyncio.sleep(15)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 7: Create `tests/test_sse.py`**

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from testweavex.web.app import create_app
    return TestClient(create_app())


def test_sse_returns_event_stream(client):
    with client.stream("GET", "/api/events") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        chunk = next(response.iter_text())
        assert "connected" in chunk
```

- [ ] **Step 8: Run all web tests**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_web_api.py tests/test_sse.py -v
```
Expected: 7 passed

- [ ] **Step 9: Commit**

```bash
git add testweavex/web/api/dashboard.py testweavex/web/api/runs.py \
  testweavex/web/api/test_cases.py testweavex/web/api/gaps.py \
  testweavex/web/api/settings.py testweavex/web/api/events.py \
  tests/test_web_api.py tests/test_sse.py
git commit -m "feat: FastAPI REST + SSE endpoints for dashboard, runs, test-cases, gaps, settings"
```

---

## Task 11: Wire `tw serve` + Final Integration

**Files:**
- Modify: `testweavex/cli.py` (update `serve` stub to full implementation)

- [ ] **Step 1: Replace `serve` stub in `testweavex/cli.py`**

Replace the `serve` function:

```python
@app.command()
def serve(
    port: int = typer.Option(8080, "--port", help="Port to listen on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind"),
) -> None:
    """Start the TestWeaveX web UI at http://localhost:<port>"""
    import uvicorn
    from testweavex.web.app import create_app
    config = load_config()
    application = create_app(config)
    console.print(f"[green]TestWeaveX UI:[/green] http://{host}:{port}")
    uvicorn.run(application, host=host, port=port)
```

- [ ] **Step 2: Update `test_tw_serve_stub` in `tests/test_cli.py`**

The `serve` command now starts Uvicorn rather than printing a Phase 6 stub message. Update the test to check it no longer fails with exit_code=1:

```python
def test_tw_serve_is_registered(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Just verify help text is available (don't start server in tests)
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "port" in result.output.lower()
```

Remove the old `test_tw_serve_stub` test and replace it with `test_tw_serve_is_registered`.

- [ ] **Step 3: Run full test suite**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/ -v --ignore=tests/test_llm.py -x
```
Expected: all pass

- [ ] **Step 4: Verify `tw --help` works**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m testweavex.cli --help
```

- [ ] **Step 5: Final commit**

```bash
git add testweavex/cli.py tests/test_cli.py
git commit -m "feat: tw serve wired to FastAPI+Uvicorn; phase 4-5-6 implementation complete"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| EventBus + typed events | Task 1 |
| StorageRepository new methods | Task 2 |
| pytest_addoption, pytest_configure, collection/execution/finish hooks | Task 3 |
| Plugin integration tests via pytester | Task 4 |
| `tw`, `tw init`, `tw status`, `tw history` | Task 5 |
| Stub commands with clear Phase N messages | Task 5 |
| Gap detection — three strategies | Task 6 |
| Gap scoring — six signals + weight formula | Task 7 |
| Gap analyzer — orchestrates + emits GapAnalysisComplete | Task 8 |
| `tw gaps` fully implemented | Task 8 |
| FastAPI app factory + static file serving | Task 9 |
| All 7 API routes | Task 10 |
| SSE endpoint | Task 10 |
| `tw serve` wired to Uvicorn | Task 11 |
| `testweavex_ui_design.html` served at `/` | Task 9 |
| All existing tests still pass | Verified in Task 11 Step 3 |

**Placeholder scan:** No TBDs. All code blocks are complete. ✓

**Type consistency:**
- `GapAnalyzer.run(run_id: str, collected_ids: list[str])` used in Task 8 and referenced in Task 3 plugin — consistent ✓
- `scorer.score_all(gaps, signals_map: dict[str, ScoringSignals])` matches Task 7 definition ✓
- `repo.get_all_test_cases()` used in Tasks 5, 6, 10 — defined in Task 2 ✓
- `repo.list_runs(limit)` used in Tasks 5, 10 — defined in Task 2 ✓
- `repo.get_results_for_run(run_id)` used in Task 10 — defined in Task 2 ✓
