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
        # ServerRepository will be implemented in a future phase
        raise NotImplementedError("Remote result server not yet supported")
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
        self._repo = _build_repo(config)
        self._bus = EventBus()
        self._storage_sub = _StorageSubscriber(self._repo)
        self._console_sub = _ConsoleSubscriber()
        self._storage_sub.register(self._bus)
        self._console_sub.register(self._bus)

        suite = config.getoption("--suite", default="default")
        environment = config.getoption("--environment", default="local")
        browser = config.getoption("browser", default=None)

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
            analyzer = GapAnalyzer(self._repo, self._bus, load_config().gap_analysis)
            analyzer.run(self._run.id, self._collected_ids)


# ── Module-level hooks (must be at module level for pytest11 entry point) ──

def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("testweavex", "TestWeaveX options")
    group.addoption("--results-server", default=None, help="Remote result server URL")
    group.addoption("--token", default=None, help="Auth token for result server")
    group.addoption("--suite", default="default", help="Tag this run with a suite name")
    group.addoption("--environment", default="local", help="Target environment")
    group.addoption("--tw-browser", default=None, dest="browser", help="Browser name for playwright tests (tw alias)")
    group.addoption("--gaps", action="store_true", default=False, help="Run gap analysis after session")
    group.addoption("--sync-tcm", default=None, help="Sync results to TCM provider (Phase 7)")


def pytest_configure(config: pytest.Config) -> None:
    if not hasattr(config, "_tw_plugin"):
        plugin = _TestWeaveXPlugin(config)
        config.pluginmanager.register(plugin, "testweavex_plugin")
        config._tw_plugin = plugin
