# Missing V1 Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement five missing V1 modules — `reporters/`, `storage/server.py`, `llm/ollama.py`, `llm/azure.py`, `web/api/generate.py` — plus all wiring changes in plugin, LLM adapters, and web app.

**Architecture:** Each new module follows an existing ABC contract (`StorageRepository`, `LLMAdapter`, `BaseReporter`). The reporters layer formalises two inline subscribers already in `plugin.py`. `ServerRepository` is an httpx HTTP client over `StorageRepository`. The generate route is a synchronous FastAPI endpoint. All tests mock external I/O (httpx, openai SDK, anthropic SDK).

**Tech Stack:** Python 3.11, httpx, openai SDK (Ollama + Azure), FastAPI TestClient, pytest + unittest.mock

**Spec:** `docs/superpowers/specs/2026-04-26-missing-modules-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `testweavex/reporters/__init__.py` | Create | Package marker |
| `testweavex/reporters/base.py` | Create | `BaseReporter` ABC |
| `testweavex/reporters/console.py` | Create | `ConsoleReporter` — Rich terminal output |
| `testweavex/reporters/sqlite.py` | Create | `SQLiteReporter` — persist results via `StorageRepository` |
| `testweavex/reporters/server.py` | Create | `ServerReporter` — push events via HTTP (best-effort) |
| `testweavex/storage/server.py` | Create | `ServerRepository` — httpx client implementing `StorageRepository` |
| `testweavex/llm/ollama.py` | Create | `OllamaAdapter` — OpenAI-compat endpoint |
| `testweavex/llm/azure.py` | Create | `AzureOpenAIAdapter` — Azure OpenAI |
| `testweavex/llm/base.py` | Modify | `_build_gap_prompt`, add ollama/azure to `get_llm_adapter` |
| `testweavex/llm/openai.py` | Modify | Implement `suggest_gap_automation` |
| `testweavex/llm/anthropic.py` | Modify | Implement `suggest_gap_automation` |
| `testweavex/web/api/generate.py` | Create | `POST /api/generate` |
| `testweavex/web/api/gaps.py` | Modify | Wire `POST /api/gaps/{gap_id}/generate` |
| `testweavex/web/app.py` | Modify | Include generate router |
| `testweavex/execution/plugin.py` | Modify | Use reporters, fix `_build_repo` |
| `tests/test_reporters.py` | Create | Tests for all reporter classes |
| `tests/test_storage_server.py` | Create | Tests for `ServerRepository` |
| `tests/test_llm.py` | Modify | Add Ollama, Azure, factory, gap-automation tests |
| `tests/test_web_api.py` | Modify | Add generate and gap-generate endpoint tests |

---

### Task 1: BaseReporter ABC + reporters/ scaffold

**Files:**
- Create: `testweavex/reporters/__init__.py`
- Create: `testweavex/reporters/base.py`
- Create: `tests/test_reporters.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reporters.py
from __future__ import annotations

import pytest


def test_base_reporter_cannot_be_instantiated_directly():
    from testweavex.reporters.base import BaseReporter
    with pytest.raises(TypeError):
        BaseReporter()  # abstract


def test_concrete_reporter_must_implement_register():
    from testweavex.reporters.base import BaseReporter

    class NoRegister(BaseReporter):
        pass

    with pytest.raises(TypeError):
        NoRegister()


def test_concrete_reporter_is_instantiable_when_register_implemented():
    from testweavex.reporters.base import BaseReporter
    from testweavex.events import EventBus

    class OkReporter(BaseReporter):
        def register(self, bus: EventBus) -> None:
            pass

    r = OkReporter()
    assert r is not None
```

- [ ] **Step 2: Run test to verify it fails**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_reporters.py -v
```

Expected: `ModuleNotFoundError: No module named 'testweavex.reporters'`

- [ ] **Step 3: Create package files**

```python
# testweavex/reporters/__init__.py
```

```python
# testweavex/reporters/base.py
from __future__ import annotations

from abc import ABC, abstractmethod

from testweavex.events import EventBus


class BaseReporter(ABC):

    @abstractmethod
    def register(self, bus: EventBus) -> None: ...
```

- [ ] **Step 4: Run test to verify it passes**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_reporters.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add testweavex/reporters/__init__.py testweavex/reporters/base.py tests/test_reporters.py
git commit -m "feat: add BaseReporter ABC and reporters/ package"
```

---

### Task 2: ConsoleReporter

**Files:**
- Create: `testweavex/reporters/console.py`
- Modify: `tests/test_reporters.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_reporters.py`:

```python
def test_console_reporter_subscribes_to_session_finished():
    from testweavex.reporters.console import ConsoleReporter
    from testweavex.events import EventBus, SessionFinished

    reporter = ConsoleReporter()
    bus = EventBus()
    reporter.register(bus)

    # Should not raise — just verify handlers are wired
    event = SessionFinished(
        run_id="r1",
        total=3,
        passed=2,
        failed=1,
        skipped=0,
        duration_ms=1000,
        collected_ids=["a", "b", "c"],
    )
    bus.emit(event)  # fires handler — no assertion needed, just no crash


def test_console_reporter_subscribes_to_gap_analysis_complete():
    from testweavex.reporters.console import ConsoleReporter
    from testweavex.events import EventBus, GapAnalysisComplete

    reporter = ConsoleReporter()
    bus = EventBus()
    reporter.register(bus)

    event = GapAnalysisComplete(run_id="r1", gaps_found=2, top_gaps=[])
    bus.emit(event)  # no crash
```

- [ ] **Step 2: Run test to verify it fails**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_reporters.py::test_console_reporter_subscribes_to_session_finished -v
```

Expected: `ImportError: cannot import name 'ConsoleReporter'`

- [ ] **Step 3: Create ConsoleReporter**

This is a direct move of `_ConsoleSubscriber` from `plugin.py` — same logic, new name and base class.

```python
# testweavex/reporters/console.py
from __future__ import annotations

from rich.console import Console
from rich.table import Table

from testweavex.events import EventBus, GapAnalysisComplete, SessionFinished
from testweavex.reporters.base import BaseReporter


class ConsoleReporter(BaseReporter):

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
```

- [ ] **Step 4: Run tests to verify they pass**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_reporters.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add testweavex/reporters/console.py tests/test_reporters.py
git commit -m "feat: add ConsoleReporter"
```

---

### Task 3: SQLiteReporter

**Files:**
- Create: `testweavex/reporters/sqlite.py`
- Modify: `tests/test_reporters.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_reporters.py`:

```python
def test_sqlite_reporter_saves_result_on_test_finished():
    from unittest.mock import MagicMock
    from testweavex.reporters.sqlite import SQLiteReporter
    from testweavex.events import EventBus, TestFinished

    mock_repo = MagicMock()
    reporter = SQLiteReporter(mock_repo)
    bus = EventBus()
    reporter.register(bus)

    event = TestFinished(
        run_id="run-1",
        test_case_id="tc-1",
        result_id="res-1",
        status="passed",
        duration_ms=200,
        error_message=None,
    )
    bus.emit(event)

    mock_repo.save_result.assert_called_once()
    saved = mock_repo.save_result.call_args[0][0]
    assert saved.run_id == "run-1"
    assert saved.test_case_id == "tc-1"
    assert saved.status.value == "passed"
    assert saved.duration_ms == 200


def test_sqlite_reporter_ends_run_on_session_finished():
    from unittest.mock import MagicMock
    from testweavex.reporters.sqlite import SQLiteReporter
    from testweavex.events import EventBus, SessionFinished

    mock_repo = MagicMock()
    reporter = SQLiteReporter(mock_repo)
    bus = EventBus()
    reporter.register(bus)

    event = SessionFinished(
        run_id="run-2",
        total=1, passed=1, failed=0, skipped=0,
        duration_ms=500,
        collected_ids=["tc-1"],
    )
    bus.emit(event)

    mock_repo.end_run.assert_called_once_with("run-2")
    mock_repo.mark_uncollected_as_gaps.assert_called_once_with(["tc-1"])
```

- [ ] **Step 2: Run tests to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_reporters.py::test_sqlite_reporter_saves_result_on_test_finished -v
```

Expected: `ImportError: cannot import name 'SQLiteReporter'`

- [ ] **Step 3: Create SQLiteReporter**

This is a direct move of `_StorageSubscriber` from `plugin.py` — same logic, new name and base class.

```python
# testweavex/reporters/sqlite.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_reporters.py -v
```

Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add testweavex/reporters/sqlite.py tests/test_reporters.py
git commit -m "feat: add SQLiteReporter"
```

---

### Task 4: ServerReporter

**Files:**
- Create: `testweavex/reporters/server.py`
- Modify: `tests/test_reporters.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_reporters.py`:

```python
def test_server_reporter_posts_test_finished_to_events_endpoint():
    from unittest.mock import MagicMock, patch
    from testweavex.events import EventBus, TestFinished

    with patch("testweavex.reporters.server.httpx.Client") as mock_cls:
        mock_client = mock_cls.return_value
        from testweavex.reporters.server import ServerReporter

        reporter = ServerReporter("http://server:8000", "tok")
        bus = EventBus()
        reporter.register(bus)

        event = TestFinished(
            run_id="run-1",
            test_case_id="tc-1",
            result_id="r-1",
            status="passed",
            duration_ms=100,
            error_message=None,
        )
        bus.emit(event)

        mock_client.post.assert_called_once_with(
            "/events", json=event.model_dump(mode="json")
        )


def test_server_reporter_swallows_http_errors_silently():
    from unittest.mock import MagicMock, patch
    from testweavex.events import EventBus, TestFinished
    import httpx

    with patch("testweavex.reporters.server.httpx.Client") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.post.side_effect = httpx.ConnectError("refused")
        from testweavex.reporters.server import ServerReporter

        reporter = ServerReporter("http://server:8000", None)
        bus = EventBus()
        reporter.register(bus)

        event = TestFinished(
            run_id="run-1",
            test_case_id="tc-1",
            result_id="r-1",
            status="failed",
            duration_ms=50,
            error_message="AssertionError",
        )
        bus.emit(event)  # must NOT raise


def test_server_reporter_posts_session_finished():
    from unittest.mock import patch
    from testweavex.events import EventBus, SessionFinished

    with patch("testweavex.reporters.server.httpx.Client") as mock_cls:
        mock_client = mock_cls.return_value
        from testweavex.reporters.server import ServerReporter

        reporter = ServerReporter("http://server:8000", "tok")
        bus = EventBus()
        reporter.register(bus)

        event = SessionFinished(
            run_id="run-1",
            total=2, passed=2, failed=0, skipped=0,
            duration_ms=300,
            collected_ids=["tc-1", "tc-2"],
        )
        bus.emit(event)

        mock_client.post.assert_called_once_with(
            "/events", json=event.model_dump(mode="json")
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_reporters.py::test_server_reporter_posts_test_finished_to_events_endpoint -v
```

Expected: `ImportError: cannot import name 'ServerReporter'`

- [ ] **Step 3: Create ServerReporter**

```python
# testweavex/reporters/server.py
from __future__ import annotations

import sys

import httpx

from testweavex.events import EventBus, SessionFinished, TestFinished, TWEvent
from testweavex.reporters.base import BaseReporter


class ServerReporter(BaseReporter):

    def __init__(self, base_url: str, token: str | None) -> None:
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
        )

    def register(self, bus: EventBus) -> None:
        bus.subscribe("test_finished", self._push)
        bus.subscribe("session_finished", self._push)

    def _push(self, event: TWEvent) -> None:
        try:
            self._client.post("/events", json=event.model_dump(mode="json"))
        except Exception as exc:
            print(f"[testweavex] ServerReporter: failed to push event: {exc}", file=sys.stderr)
```

- [ ] **Step 4: Run tests to verify they pass**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_reporters.py -v
```

Expected: 10 PASSED

- [ ] **Step 5: Commit**

```bash
git add testweavex/reporters/server.py tests/test_reporters.py
git commit -m "feat: add ServerReporter with best-effort HTTP event push"
```

---

### Task 5: ServerRepository

**Files:**
- Create: `testweavex/storage/server.py`
- Create: `tests/test_storage_server.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_storage_server.py
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


def _run_json(run_id: str = "run-123") -> dict:
    return {
        "id": run_id,
        "suite": "smoke",
        "environment": "local",
        "browser": None,
        "triggered_by": "tw",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "result_ids": [],
    }


def _tc_json(tc_id: str = "tc-abc") -> dict:
    from testweavex.core.models import generate_stable_id
    return {
        "id": tc_id,
        "title": "Login test",
        "feature_id": generate_stable_id("features/login.feature"),
        "gherkin": "Scenario: Login\n  Given I am on login page",
        "test_type": "smoke",
        "skill": "functional/smoke",
        "status": "pending",
        "is_automated": False,
        "tcm_id": None,
        "tags": [],
        "priority": 2,
        "source_file": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _mock_response(data, status_code: int = 200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


def _mock_error_response(status_code: int = 500):
    import httpx
    mock = MagicMock()
    mock.status_code = status_code
    mock.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error", request=MagicMock(), response=MagicMock()
    )
    return mock


class TestServerRepository:

    @patch("testweavex.storage.server.httpx.Client")
    def test_start_run_posts_and_returns_test_run(self, mock_cls):
        mock_client = mock_cls.return_value
        mock_client.post.return_value = _mock_response(_run_json(), 201)

        from testweavex.storage.server import ServerRepository
        from testweavex.core.models import TestRun

        repo = ServerRepository("http://server:8000", "token")
        run = repo.start_run("smoke")

        assert isinstance(run, TestRun)
        assert run.id == "run-123"
        assert run.suite == "smoke"
        mock_client.post.assert_called_once_with("/runs", json={
            "suite": "smoke",
            "environment": "local",
            "browser": None,
            "triggered_by": "tw",
        })

    @patch("testweavex.storage.server.httpx.Client")
    def test_end_run_patches_run(self, mock_cls):
        mock_client = mock_cls.return_value
        mock_client.patch.return_value = _mock_response({}, 200)

        from testweavex.storage.server import ServerRepository

        repo = ServerRepository("http://server:8000")
        repo.end_run("run-123")

        mock_client.patch.assert_called_once_with("/runs/run-123")

    @patch("testweavex.storage.server.httpx.Client")
    def test_upsert_test_case_puts_test_case(self, mock_cls):
        mock_client = mock_cls.return_value
        mock_client.put.return_value = _mock_response(_tc_json(), 200)

        from testweavex.storage.server import ServerRepository
        from testweavex.core.models import TestCase, TestType, TestStatus, generate_stable_id

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        tc = TestCase(
            id="tc-abc",
            title="Login test",
            feature_id=generate_stable_id("features/login.feature"),
            gherkin="Scenario: Login\n  Given I am on login page",
            test_type=TestType.smoke,
            skill="functional/smoke",
            status=TestStatus.pending,
            is_automated=False,
            created_at=now,
            updated_at=now,
        )

        repo = ServerRepository("http://server:8000")
        repo.upsert_test_case(tc)

        mock_client.put.assert_called_once_with(
            "/test-cases/tc-abc", json=tc.model_dump(mode="json")
        )

    @patch("testweavex.storage.server.httpx.Client")
    def test_get_gaps_returns_gap_list(self, mock_cls):
        mock_client = mock_cls.return_value
        gap_data = [{
            "id": "gap-1",
            "test_case_id": "tc-abc",
            "priority_score": 0.75,
            "gap_reason": "never run",
            "suggested_gherkin": None,
            "status": "open",
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "closed_at": None,
        }]
        mock_client.get.return_value = _mock_response(gap_data)

        from testweavex.storage.server import ServerRepository
        from testweavex.core.models import Gap

        repo = ServerRepository("http://server:8000")
        gaps = repo.get_gaps(limit=10, status="open")

        assert len(gaps) == 1
        assert isinstance(gaps[0], Gap)
        assert gaps[0].priority_score == 0.75
        mock_client.get.assert_called_once_with("/gaps?limit=10&status=open")

    @patch("testweavex.storage.server.httpx.Client")
    def test_get_coverage_percentage_returns_float(self, mock_cls):
        mock_client = mock_cls.return_value
        mock_client.get.return_value = _mock_response({"percentage": 62.5})

        from testweavex.storage.server import ServerRepository

        repo = ServerRepository("http://server:8000")
        pct = repo.get_coverage_percentage()

        assert pct == 62.5
        mock_client.get.assert_called_once_with("/coverage")

    @patch("testweavex.storage.server.httpx.Client")
    def test_non_2xx_response_raises_storage_error(self, mock_cls):
        import httpx
        from testweavex.core.exceptions import StorageError

        mock_client = mock_cls.return_value
        mock_client.post.return_value = _mock_error_response(500)

        from testweavex.storage.server import ServerRepository

        repo = ServerRepository("http://server:8000")
        with pytest.raises(StorageError):
            repo.start_run("smoke")

    @patch("testweavex.storage.server.httpx.Client")
    def test_constructor_sets_auth_header_when_token_given(self, mock_cls):
        from testweavex.storage.server import ServerRepository

        ServerRepository("http://server:8000", "my-token")

        _, kwargs = mock_cls.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer my-token"

    @patch("testweavex.storage.server.httpx.Client")
    def test_constructor_omits_auth_header_when_no_token(self, mock_cls):
        from testweavex.storage.server import ServerRepository

        ServerRepository("http://server:8000", None)

        _, kwargs = mock_cls.call_args
        assert "Authorization" not in kwargs["headers"]


import pytest
```

- [ ] **Step 2: Run tests to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_storage_server.py -v
```

Expected: `ModuleNotFoundError: No module named 'testweavex.storage.server'`

- [ ] **Step 3: Create ServerRepository**

```python
# testweavex/storage/server.py
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from testweavex.core.exceptions import StorageError
from testweavex.core.models import (
    Gap,
    ScoringSignals,
    TestCase,
    TestResult,
    TestRun,
)
from testweavex.storage.base import StorageRepository


class ServerRepository(StorageRepository):

    def __init__(self, base_url: str, token: str | None = None) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
        )

    # ── internal helpers ──────────────────────────────────────────────────────

    def _get(self, path: str) -> httpx.Response:
        try:
            resp = self._client.get(path)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            raise StorageError(f"Server error on GET {path}: {exc}") from exc

    def _post(self, path: str, data: object) -> httpx.Response:
        try:
            resp = self._client.post(path, json=data)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            raise StorageError(f"Server error on POST {path}: {exc}") from exc

    def _put(self, path: str, data: object) -> httpx.Response:
        try:
            resp = self._client.put(path, json=data)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            raise StorageError(f"Server error on PUT {path}: {exc}") from exc

    def _patch(self, path: str) -> httpx.Response:
        try:
            resp = self._client.patch(path)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            raise StorageError(f"Server error on PATCH {path}: {exc}") from exc

    # ── StorageRepository interface ───────────────────────────────────────────

    def start_run(
        self,
        suite: str,
        environment: str = "local",
        browser: str | None = None,
        triggered_by: str = "tw",
    ) -> TestRun:
        resp = self._post("/runs", {
            "suite": suite,
            "environment": environment,
            "browser": browser,
            "triggered_by": triggered_by,
        })
        return TestRun(**resp.json())

    def end_run(self, run_id: str) -> None:
        self._patch(f"/runs/{run_id}")

    def get_run(self, run_id: str) -> TestRun:
        resp = self._get(f"/runs/{run_id}")
        return TestRun(**resp.json())

    def list_runs(self, limit: int = 50) -> list[TestRun]:
        resp = self._get(f"/runs?limit={limit}")
        return [TestRun(**r) for r in resp.json()]

    def save_result(self, r: TestResult) -> None:
        self._post("/results", r.model_dump(mode="json"))

    def get_results_for_run(self, run_id: str) -> list[TestResult]:
        resp = self._get(f"/runs/{run_id}/results")
        return [TestResult(**r) for r in resp.json()]

    def upsert_test_case(self, tc: TestCase) -> None:
        self._put(f"/test-cases/{tc.id}", tc.model_dump(mode="json"))

    def get_test_case(self, id: str) -> TestCase:
        resp = self._get(f"/test-cases/{id}")
        return TestCase(**resp.json())

    def get_all_test_cases(self) -> list[TestCase]:
        resp = self._get("/test-cases")
        return [TestCase(**tc) for tc in resp.json()]

    def get_never_run_test_cases(self) -> list[TestCase]:
        resp = self._get("/test-cases?filter=never_run")
        return [TestCase(**tc) for tc in resp.json()]

    def get_always_failing_test_cases(self) -> list[TestCase]:
        resp = self._get("/test-cases?filter=always_failing")
        return [TestCase(**tc) for tc in resp.json()]

    def save_gaps(self, gaps: list[Gap]) -> None:
        self._post("/gaps/batch", [g.model_dump(mode="json") for g in gaps])

    def get_gaps(self, limit: int = 50, status: str = "open") -> list[Gap]:
        resp = self._get(f"/gaps?limit={limit}&status={status}")
        return [Gap(**g) for g in resp.json()]

    def mark_uncollected_as_gaps(self, collected_ids: list[str]) -> None:
        self._post("/gaps/mark-uncollected", {"collected_ids": collected_ids})

    def get_coverage_percentage(self) -> float:
        resp = self._get("/coverage")
        return float(resp.json()["percentage"])

    def get_coverage_trend(self, weeks: int) -> list[dict]:
        resp = self._get(f"/coverage/trend?weeks={weeks}")
        return resp.json()

    def get_flaky_tests(self, min_runs: int = 5) -> list[TestCase]:
        resp = self._get(f"/test-cases?filter=flaky&min_runs={min_runs}")
        return [TestCase(**tc) for tc in resp.json()]

    def get_scoring_signals(self, tc_id: str) -> ScoringSignals:
        resp = self._get(f"/test-cases/{tc_id}/signals")
        return ScoringSignals(**resp.json())
```

- [ ] **Step 4: Run tests to verify they pass**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_storage_server.py -v
```

Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add testweavex/storage/server.py tests/test_storage_server.py
git commit -m "feat: add ServerRepository — httpx client for StorageRepository"
```

---

### Task 6: Refactor plugin.py — use reporters, fix _build_repo

**Files:**
- Modify: `testweavex/execution/plugin.py`

- [ ] **Step 1: Run existing plugin tests (baseline)**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_plugin.py -v
```

Expected: all pass. Note the count.

- [ ] **Step 2: Replace inline subscribers and fix _build_repo**

In `testweavex/execution/plugin.py`, make these changes:

**Remove** the `_StorageSubscriber` and `_ConsoleSubscriber` class definitions entirely (lines ~78–139).

**Replace** `_build_repo` with:

```python
def _build_repo(config: pytest.Config) -> "StorageRepository":
    server_url = config.getoption("--results-server", default=None) or None
    if server_url:
        token = config.getoption("--token", default=None)
        from testweavex.storage.server import ServerRepository
        return ServerRepository(server_url, token)
    db_dir = Path(str(config.rootpath)) / ".testweavex"
    db_dir.mkdir(exist_ok=True)
    return SQLiteRepository(db_url=f"sqlite:///{db_dir / 'results.db'}")
```

**Replace** the subscriber setup in `_TestWeaveXPlugin.__init__` (the four lines that were):
```python
self._storage_sub = _StorageSubscriber(self._repo)
self._console_sub = _ConsoleSubscriber()
self._storage_sub.register(self._bus)
self._console_sub.register(self._bus)
```
with:
```python
from testweavex.reporters.console import ConsoleReporter
from testweavex.reporters.sqlite import SQLiteReporter

server_url = config.getoption("--results-server", default=None) or None
reporters = [ConsoleReporter(), SQLiteReporter(self._repo)]
if server_url:
    from testweavex.reporters.server import ServerReporter
    token = config.getoption("--token", default=None)
    reporters.append(ServerReporter(server_url, token))
for r in reporters:
    r.register(self._bus)
```

**Remove** the now-unused `TYPE_CHECKING` import block if `StorageRepository` is no longer referenced via `TYPE_CHECKING`. Keep the import if it's still used in `_build_repo`'s return type annotation.

- [ ] **Step 3: Run existing plugin tests to verify nothing broke**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_plugin.py -v
```

Expected: same count as baseline, all PASSED.

- [ ] **Step 4: Run full test suite**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest --tb=short -q
```

Expected: no new failures.

- [ ] **Step 5: Commit**

```bash
git add testweavex/execution/plugin.py
git commit -m "refactor: use reporters in plugin, fix _build_repo for ServerRepository"
```

---

### Task 7: OllamaAdapter

**Files:**
- Create: `testweavex/llm/ollama.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_llm.py`:

```python
# ── Ollama adapter tests ───────────────────────────────────────────────────────

class TestOllamaAdapter:

    @patch("testweavex.llm.ollama.SkillLoader")
    @patch("testweavex.llm.ollama.openai.OpenAI")
    def test_ollama_generate_tests_uses_openai_compat_client(
        self, mock_openai_class, mock_loader_class
    ):
        from testweavex.llm.ollama import OllamaAdapter

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _openai_response([SCENARIO_DATA])

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load.return_value = _fake_skill("functional/smoke")

        cfg = _config("openai")
        cfg.llm.provider = "ollama"
        cfg.llm.model = "llama3"

        adapter = OllamaAdapter(cfg.llm)
        request = GenerationRequest(
            feature_description="Login",
            skill_names=["functional/smoke"],
        )
        response = adapter.generate_tests(request)

        assert len(response.scenarios) == 1
        assert response.llm_model == "llama3"

    @patch("testweavex.llm.ollama.openai.OpenAI")
    def test_ollama_uses_default_base_url_when_not_configured(self, mock_openai_class):
        from testweavex.llm.ollama import OllamaAdapter

        cfg = _config("openai")
        cfg.llm.provider = "ollama"
        cfg.llm.model = "llama3"
        cfg.llm.base_url = None

        OllamaAdapter(cfg.llm)

        _, kwargs = mock_openai_class.call_args
        assert kwargs["base_url"] == "http://localhost:11434/v1"

    @patch("testweavex.llm.ollama.openai.OpenAI")
    def test_ollama_uses_custom_base_url_when_configured(self, mock_openai_class):
        from testweavex.llm.ollama import OllamaAdapter

        cfg = _config("openai")
        cfg.llm.provider = "ollama"
        cfg.llm.base_url = "http://my-ollama:11434/v1"

        OllamaAdapter(cfg.llm)

        _, kwargs = mock_openai_class.call_args
        assert kwargs["base_url"] == "http://my-ollama:11434/v1"

    @patch("testweavex.llm.ollama.openai.OpenAI")
    def test_ollama_health_check_returns_false_on_exception(self, mock_openai_class):
        from testweavex.llm.ollama import OllamaAdapter

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("connection refused")

        cfg = _config("openai")
        cfg.llm.provider = "ollama"
        adapter = OllamaAdapter(cfg.llm)

        assert adapter.health_check() is False

    @patch("testweavex.llm.ollama.openai.OpenAI")
    def test_ollama_suggest_gap_automation_returns_generation_response(self, mock_openai_class):
        from testweavex.llm.ollama import OllamaAdapter
        from testweavex.core.models import TestCase, TestType, TestStatus, generate_stable_id
        from datetime import datetime, timezone

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _openai_response([SCENARIO_DATA])

        cfg = _config("openai")
        cfg.llm.provider = "ollama"
        cfg.llm.model = "llama3"
        adapter = OllamaAdapter(cfg.llm)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        tc = TestCase(
            id="tc-1",
            title="Login with valid creds",
            feature_id=generate_stable_id("features/login.feature"),
            gherkin="Scenario: Login\n  Given I am on login page",
            test_type=TestType.smoke,
            skill="functional/smoke",
            is_automated=False,
            created_at=now,
            updated_at=now,
        )
        response = adapter.suggest_gap_automation(tc)

        assert len(response.scenarios) == 1
        assert response.skill_used == "gap_automation"
```

- [ ] **Step 2: Run tests to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py::TestOllamaAdapter -v
```

Expected: `ImportError: cannot import name 'OllamaAdapter'`

- [ ] **Step 3: Create OllamaAdapter**

```python
# testweavex/llm/ollama.py
from __future__ import annotations

import json
import time

import openai
from pydantic import ValidationError

from testweavex.core.config import LLMConfig
from testweavex.core.exceptions import LLMOutputError
from testweavex.core.models import (
    GenerationRequest,
    GenerationResponse,
    Scenario,
    StepDefinition,
    StepDefinitionResponse,
    TestCase,
)
from testweavex.llm.base import LLMAdapter, _build_gap_prompt, _deduplicate
from testweavex.skills.loader import SkillLoader

_SYSTEM_PROMPT = (
    "You are a senior QA engineer. Respond ONLY with valid JSON. "
    "No markdown, no explanation, no code fences — just the JSON object."
)


class OllamaAdapter(LLMAdapter):

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        base_url = config.base_url or "http://localhost:11434/v1"
        self._client = openai.OpenAI(
            api_key="ollama",
            base_url=base_url,
            timeout=config.timeout_seconds,
        )
        self._loader = SkillLoader()

    def generate_tests(self, request: GenerationRequest) -> GenerationResponse:
        all_scenarios: list[Scenario] = []
        total_tokens = 0
        start = time.monotonic()

        for skill_name in request.skill_names:
            skill = self._loader.load(skill_name)
            prompt = skill.prompt_template.format(
                feature_description=request.feature_description,
                acceptance_criteria="\n".join(request.acceptance_criteria),
                existing_scenarios="\n".join(request.existing_scenarios),
                n_suggestions=request.n_suggestions,
            )
            scenarios, tokens = self._call_with_retry(prompt, skill_name)
            all_scenarios.extend(scenarios)
            total_tokens += tokens

        deduped = _deduplicate(all_scenarios)
        elapsed = int((time.monotonic() - start) * 1000)

        return GenerationResponse(
            scenarios=deduped,
            skill_used=", ".join(request.skill_names),
            llm_model=self._config.model,
            tokens_used=total_tokens,
            generation_time_ms=elapsed,
        )

    def _call_with_retry(
        self, prompt: str, skill_name: str
    ) -> tuple[list[Scenario], int]:
        last_exc: Exception | None = None
        for _ in range(self._config.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self._config.model,
                    temperature=self._config.temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.choices[0].message.content
                data = json.loads(raw)
                raw_list = data.get("scenarios", data if isinstance(data, list) else [])
                scenarios = [Scenario(**s, skill_used=skill_name) for s in raw_list]
                tokens = resp.usage.total_tokens if resp.usage else 0
                return scenarios, tokens
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_exc = exc
        raise LLMOutputError(
            f"Ollama returned invalid output after {self._config.max_retries} attempts"
        ) from last_exc

    def generate_step_definitions(
        self, scenarios: list[Scenario], existing_steps: list[str]
    ) -> StepDefinitionResponse:
        from testweavex.llm.openai import _build_step_prompt
        prompt = _build_step_prompt(scenarios, existing_steps)
        last_exc: Exception | None = None
        for _ in range(self._config.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self._config.model,
                    temperature=self._config.temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.choices[0].message.content
                data = json.loads(raw)
                steps = [StepDefinition(**s) for s in data.get("new_steps", [])]
                tokens = resp.usage.total_tokens if resp.usage else 0
                return StepDefinitionResponse(
                    new_steps=steps,
                    reused_count=0,
                    llm_model=self._config.model,
                    tokens_used=tokens,
                )
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_exc = exc
        raise LLMOutputError(
            f"Ollama returned invalid step definitions after {self._config.max_retries} attempts"
        ) from last_exc

    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse:
        prompt = _build_gap_prompt(manual_test)
        scenarios, tokens = self._call_with_retry(prompt, "gap_automation")
        return GenerationResponse(
            scenarios=scenarios,
            skill_used="gap_automation",
            llm_model=self._config.model,
            tokens_used=tokens,
            generation_time_ms=0,
        )

    def health_check(self) -> bool:
        try:
            self._client.chat.completions.create(
                model=self._config.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
```

Note: `_build_gap_prompt` will be added to `llm/base.py` in Task 9. Add this stub to `llm/base.py` now so OllamaAdapter can import it:

```python
# Add to testweavex/llm/base.py after _deduplicate:

def _build_gap_prompt(test_case: TestCase) -> str:
    return (
        f"Manual test case to automate:\n"
        f"Title: {test_case.title}\n"
        f"Type: {test_case.test_type.value}\n"
        f"Gherkin:\n{test_case.gherkin}\n\n"
        "Generate exactly 1 Gherkin scenario that automates this test case.\n"
        'Return JSON: {"scenarios": [{"title": "...", "gherkin": "...", '
        '"confidence": 0.9, "rationale": "Automates the manual test case.", '
        '"suggested_tags": []}]}'
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py::TestOllamaAdapter -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add testweavex/llm/ollama.py testweavex/llm/base.py tests/test_llm.py
git commit -m "feat: add OllamaAdapter and _build_gap_prompt helper"
```

---

### Task 8: AzureOpenAIAdapter

**Files:**
- Create: `testweavex/llm/azure.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_llm.py`:

```python
# ── Azure adapter tests ───────────────────────────────────────────────────────

def _azure_config() -> "LLMConfig":
    cfg = LLMConfig(
        provider="azure",
        model="gpt-4",
        api_key="azure-key",
        temperature=0.3,
        max_retries=3,
        timeout_seconds=30,
        azure_endpoint="https://myorg.openai.azure.com/",
        api_version="2024-02-01",
        deployment_name="gpt-4-prod",
    )
    return cfg


class TestAzureOpenAIAdapter:

    @patch("testweavex.llm.azure.openai.AzureOpenAI")
    def test_azure_raises_config_error_when_endpoint_missing(self, _mock):
        from testweavex.llm.azure import AzureOpenAIAdapter
        from testweavex.core.exceptions import ConfigError

        cfg = _azure_config()
        cfg.azure_endpoint = None
        with pytest.raises(ConfigError, match="azure_endpoint"):
            AzureOpenAIAdapter(cfg)

    @patch("testweavex.llm.azure.openai.AzureOpenAI")
    def test_azure_raises_config_error_when_api_version_missing(self, _mock):
        from testweavex.llm.azure import AzureOpenAIAdapter
        from testweavex.core.exceptions import ConfigError

        cfg = _azure_config()
        cfg.api_version = None
        with pytest.raises(ConfigError, match="api_version"):
            AzureOpenAIAdapter(cfg)

    @patch("testweavex.llm.azure.openai.AzureOpenAI")
    def test_azure_raises_config_error_when_deployment_name_missing(self, _mock):
        from testweavex.llm.azure import AzureOpenAIAdapter
        from testweavex.core.exceptions import ConfigError

        cfg = _azure_config()
        cfg.deployment_name = None
        with pytest.raises(ConfigError, match="deployment_name"):
            AzureOpenAIAdapter(cfg)

    @patch("testweavex.llm.azure.SkillLoader")
    @patch("testweavex.llm.azure.openai.AzureOpenAI")
    def test_azure_generate_tests_uses_deployment_as_model(
        self, mock_azure_class, mock_loader_class
    ):
        from testweavex.llm.azure import AzureOpenAIAdapter

        mock_client = MagicMock()
        mock_azure_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _openai_response([SCENARIO_DATA])

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load.return_value = _fake_skill("functional/smoke")

        adapter = AzureOpenAIAdapter(_azure_config())
        request = GenerationRequest(
            feature_description="Login",
            skill_names=["functional/smoke"],
        )
        response = adapter.generate_tests(request)

        assert len(response.scenarios) == 1
        # llm_model should be the deployment name
        assert response.llm_model == "gpt-4-prod"
        # API call uses deployment name as model
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4-prod"

    @patch("testweavex.llm.azure.openai.AzureOpenAI")
    def test_azure_health_check_returns_false_on_exception(self, mock_azure_class):
        from testweavex.llm.azure import AzureOpenAIAdapter

        mock_client = MagicMock()
        mock_azure_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("auth error")

        adapter = AzureOpenAIAdapter(_azure_config())
        assert adapter.health_check() is False
```

- [ ] **Step 2: Run tests to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py::TestAzureOpenAIAdapter -v
```

Expected: `ImportError: cannot import name 'AzureOpenAIAdapter'`

- [ ] **Step 3: Create AzureOpenAIAdapter**

```python
# testweavex/llm/azure.py
from __future__ import annotations

import json
import time

import openai
from pydantic import ValidationError

from testweavex.core.config import LLMConfig
from testweavex.core.exceptions import ConfigError, LLMOutputError
from testweavex.core.models import (
    GenerationRequest,
    GenerationResponse,
    Scenario,
    StepDefinition,
    StepDefinitionResponse,
    TestCase,
)
from testweavex.llm.base import LLMAdapter, _build_gap_prompt, _deduplicate
from testweavex.skills.loader import SkillLoader

_SYSTEM_PROMPT = (
    "You are a senior QA engineer. Respond ONLY with valid JSON. "
    "No markdown, no explanation, no code fences — just the JSON object."
)


class AzureOpenAIAdapter(LLMAdapter):

    def __init__(self, config: LLMConfig) -> None:
        if not config.azure_endpoint:
            raise ConfigError("LLMConfig.azure_endpoint is required for provider 'azure'")
        if not config.api_version:
            raise ConfigError("LLMConfig.api_version is required for provider 'azure'")
        if not config.deployment_name:
            raise ConfigError("LLMConfig.deployment_name is required for provider 'azure'")
        self._config = config
        self._deployment = config.deployment_name
        self._client = openai.AzureOpenAI(
            api_key=config.api_key,
            azure_endpoint=config.azure_endpoint,
            api_version=config.api_version,
            timeout=config.timeout_seconds,
        )
        self._loader = SkillLoader()

    def generate_tests(self, request: GenerationRequest) -> GenerationResponse:
        all_scenarios: list[Scenario] = []
        total_tokens = 0
        start = time.monotonic()

        for skill_name in request.skill_names:
            skill = self._loader.load(skill_name)
            prompt = skill.prompt_template.format(
                feature_description=request.feature_description,
                acceptance_criteria="\n".join(request.acceptance_criteria),
                existing_scenarios="\n".join(request.existing_scenarios),
                n_suggestions=request.n_suggestions,
            )
            scenarios, tokens = self._call_with_retry(prompt, skill_name)
            all_scenarios.extend(scenarios)
            total_tokens += tokens

        deduped = _deduplicate(all_scenarios)
        elapsed = int((time.monotonic() - start) * 1000)

        return GenerationResponse(
            scenarios=deduped,
            skill_used=", ".join(request.skill_names),
            llm_model=self._deployment,
            tokens_used=total_tokens,
            generation_time_ms=elapsed,
        )

    def _call_with_retry(
        self, prompt: str, skill_name: str
    ) -> tuple[list[Scenario], int]:
        last_exc: Exception | None = None
        for _ in range(self._config.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self._deployment,
                    temperature=self._config.temperature,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.choices[0].message.content
                data = json.loads(raw)
                raw_list = data.get("scenarios", data if isinstance(data, list) else [])
                scenarios = [Scenario(**s, skill_used=skill_name) for s in raw_list]
                tokens = resp.usage.total_tokens if resp.usage else 0
                return scenarios, tokens
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_exc = exc
        raise LLMOutputError(
            f"Azure OpenAI returned invalid output after {self._config.max_retries} attempts"
        ) from last_exc

    def generate_step_definitions(
        self, scenarios: list[Scenario], existing_steps: list[str]
    ) -> StepDefinitionResponse:
        from testweavex.llm.openai import _build_step_prompt
        prompt = _build_step_prompt(scenarios, existing_steps)
        last_exc: Exception | None = None
        for _ in range(self._config.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self._deployment,
                    temperature=self._config.temperature,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.choices[0].message.content
                data = json.loads(raw)
                steps = [StepDefinition(**s) for s in data.get("new_steps", [])]
                tokens = resp.usage.total_tokens if resp.usage else 0
                return StepDefinitionResponse(
                    new_steps=steps,
                    reused_count=0,
                    llm_model=self._deployment,
                    tokens_used=tokens,
                )
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_exc = exc
        raise LLMOutputError(
            f"Azure OpenAI returned invalid step definitions after {self._config.max_retries} attempts"
        ) from last_exc

    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse:
        prompt = _build_gap_prompt(manual_test)
        scenarios, tokens = self._call_with_retry(prompt, "gap_automation")
        return GenerationResponse(
            scenarios=scenarios,
            skill_used="gap_automation",
            llm_model=self._deployment,
            tokens_used=tokens,
            generation_time_ms=0,
        )

    def health_check(self) -> bool:
        try:
            self._client.chat.completions.create(
                model=self._deployment,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py::TestAzureOpenAIAdapter -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add testweavex/llm/azure.py tests/test_llm.py
git commit -m "feat: add AzureOpenAIAdapter"
```

---

### Task 9: Update get_llm_adapter factory

**Files:**
- Modify: `testweavex/llm/base.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_llm.py` inside `TestGetLLMAdapter`:

```python
    @patch("testweavex.llm.ollama.openai.OpenAI")
    def test_get_llm_adapter_ollama_returns_ollama_adapter(self, _mock):
        from testweavex.llm.base import get_llm_adapter
        from testweavex.llm.ollama import OllamaAdapter

        cfg = _config("openai")
        cfg.llm.provider = "ollama"
        adapter = get_llm_adapter(cfg)
        assert isinstance(adapter, OllamaAdapter)

    @patch("testweavex.llm.azure.openai.AzureOpenAI")
    def test_get_llm_adapter_azure_returns_azure_adapter(self, _mock):
        from testweavex.llm.base import get_llm_adapter
        from testweavex.llm.azure import AzureOpenAIAdapter
        from testweavex.core.config import LLMConfig

        cfg = _config("openai")
        cfg.llm = LLMConfig(
            provider="azure",
            model="gpt-4",
            api_key="key",
            azure_endpoint="https://x.openai.azure.com/",
            api_version="2024-02-01",
            deployment_name="gpt-4-prod",
        )
        adapter = get_llm_adapter(cfg)
        assert isinstance(adapter, AzureOpenAIAdapter)

    def test_get_llm_adapter_unknown_provider_error_message_lists_all_four(self):
        from testweavex.llm.base import get_llm_adapter
        from testweavex.core.exceptions import ConfigError

        cfg = _config("openai")
        cfg.llm.provider = "unknown"
        with pytest.raises(ConfigError) as exc_info:
            get_llm_adapter(cfg)
        msg = str(exc_info.value)
        assert "ollama" in msg
        assert "azure" in msg
```

- [ ] **Step 2: Run tests to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py::TestGetLLMAdapter -v
```

Expected: the new ollama/azure/error-message tests FAIL.

- [ ] **Step 3: Update get_llm_adapter in llm/base.py**

Replace the `get_llm_adapter` function body (the `if provider == ...` block and the final `raise`) with:

```python
def get_llm_adapter(config: TestWeaveXConfig) -> LLMAdapter:
    provider = config.llm.provider
    if provider == "openai":
        from testweavex.llm.openai import OpenAIAdapter
        return OpenAIAdapter(config.llm)
    if provider == "anthropic":
        from testweavex.llm.anthropic import AnthropicAdapter
        return AnthropicAdapter(config.llm)
    if provider == "ollama":
        from testweavex.llm.ollama import OllamaAdapter
        return OllamaAdapter(config.llm)
    if provider == "azure":
        from testweavex.llm.azure import AzureOpenAIAdapter
        return AzureOpenAIAdapter(config.llm)
    raise ConfigError(
        f"Unsupported LLM provider: '{provider}'. Choose: openai, anthropic, ollama, azure"
    )
```

- [ ] **Step 4: Run all LLM tests to verify they pass**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py -v
```

Expected: all PASSED (including pre-existing tests).

- [ ] **Step 5: Commit**

```bash
git add testweavex/llm/base.py tests/test_llm.py
git commit -m "feat: add ollama and azure to get_llm_adapter factory"
```

---

### Task 10: Implement suggest_gap_automation in OpenAI and Anthropic adapters

**Files:**
- Modify: `testweavex/llm/openai.py`
- Modify: `testweavex/llm/anthropic.py`
- Modify: `tests/test_llm.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_llm.py`:

```python
def _make_test_case() -> "TestCase":
    from testweavex.core.models import TestCase, TestType, TestStatus, generate_stable_id
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return TestCase(
        id="tc-gap",
        title="Login with valid credentials",
        feature_id=generate_stable_id("features/login.feature"),
        gherkin="Scenario: Login\n  Given I am on login page\n  When I enter valid creds\n  Then I am logged in",
        test_type=TestType.smoke,
        skill="functional/smoke",
        is_automated=False,
        created_at=now,
        updated_at=now,
    )


@patch("testweavex.llm.openai.SkillLoader")
@patch("testweavex.llm.openai.openai.OpenAI")
def test_openai_suggest_gap_automation_returns_generation_response(
    mock_openai_class, mock_loader_class
):
    from testweavex.llm.openai import OpenAIAdapter

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.return_value = _openai_response([SCENARIO_DATA])
    mock_loader_class.return_value = MagicMock()

    adapter = OpenAIAdapter(_config("openai").llm)
    response = adapter.suggest_gap_automation(_make_test_case())

    assert len(response.scenarios) == 1
    assert response.skill_used == "gap_automation"


@patch("testweavex.llm.anthropic.SkillLoader")
@patch("testweavex.llm.anthropic.anthropic.Anthropic")
def test_anthropic_suggest_gap_automation_returns_generation_response(
    mock_anthropic_class, mock_loader_class
):
    from testweavex.llm.anthropic import AnthropicAdapter

    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = _anthropic_response([SCENARIO_DATA])
    mock_loader_class.return_value = MagicMock()

    adapter = AnthropicAdapter(_config("anthropic").llm)
    response = adapter.suggest_gap_automation(_make_test_case())

    assert len(response.scenarios) == 1
    assert response.skill_used == "gap_automation"
```

- [ ] **Step 2: Run tests to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py::test_openai_suggest_gap_automation_returns_generation_response tests/test_llm.py::test_anthropic_suggest_gap_automation_returns_generation_response -v
```

Expected: both FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement suggest_gap_automation in OpenAIAdapter**

In `testweavex/llm/openai.py`, replace:

```python
    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse:
        raise NotImplementedError
```

with:

```python
    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse:
        from testweavex.llm.base import _build_gap_prompt
        prompt = _build_gap_prompt(manual_test)
        scenarios, tokens = self._call_with_retry(prompt, "gap_automation")
        return GenerationResponse(
            scenarios=scenarios,
            skill_used="gap_automation",
            llm_model=self._config.model,
            tokens_used=tokens,
            generation_time_ms=0,
        )
```

- [ ] **Step 4: Implement suggest_gap_automation in AnthropicAdapter**

In `testweavex/llm/anthropic.py`, replace:

```python
    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse:
        raise NotImplementedError
```

with:

```python
    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse:
        from testweavex.llm.base import _build_gap_prompt
        prompt = _build_gap_prompt(manual_test)
        scenarios, tokens = self._call_with_retry(prompt, "gap_automation")
        return GenerationResponse(
            scenarios=scenarios,
            skill_used="gap_automation",
            llm_model=self._config.model,
            tokens_used=tokens,
            generation_time_ms=0,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py -v
```

Expected: all PASSED.

- [ ] **Step 6: Commit**

```bash
git add testweavex/llm/openai.py testweavex/llm/anthropic.py tests/test_llm.py
git commit -m "feat: implement suggest_gap_automation in OpenAI and Anthropic adapters"
```

---

### Task 11: POST /api/generate route

**Files:**
- Create: `testweavex/web/api/generate.py`
- Modify: `testweavex/web/app.py`
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_api.py`:

```python
from unittest.mock import MagicMock, patch
from testweavex.core.models import GenerationResponse


def _mock_generation_response() -> GenerationResponse:
    return GenerationResponse(
        scenarios=[],
        skill_used="functional/smoke",
        llm_model="test-model",
        tokens_used=100,
        generation_time_ms=500,
    )


def test_generate_endpoint_returns_200_with_response(client):
    with patch("testweavex.web.api.generate.get_llm_adapter") as mock_factory:
        mock_adapter = MagicMock()
        mock_adapter.health_check.return_value = True
        mock_adapter.generate_tests.return_value = _mock_generation_response()
        mock_factory.return_value = mock_adapter

        response = client.post("/api/generate", json={
            "feature_description": "User login",
            "skill": "functional/smoke",
            "n_suggestions": 3,
        })

    assert response.status_code == 200
    data = response.json()
    assert "scenarios" in data
    assert data["skill_used"] == "functional/smoke"
    assert data["llm_model"] == "test-model"


def test_generate_endpoint_returns_503_when_health_check_fails(client):
    with patch("testweavex.web.api.generate.get_llm_adapter") as mock_factory:
        mock_adapter = MagicMock()
        mock_adapter.health_check.return_value = False
        mock_factory.return_value = mock_adapter

        response = client.post("/api/generate", json={
            "feature_description": "Login",
            "skill": "functional/smoke",
            "n_suggestions": 3,
        })

    assert response.status_code == 503


def test_generate_endpoint_returns_422_on_llm_output_error(client):
    from testweavex.core.exceptions import LLMOutputError
    with patch("testweavex.web.api.generate.get_llm_adapter") as mock_factory:
        mock_adapter = MagicMock()
        mock_adapter.health_check.return_value = True
        mock_adapter.generate_tests.side_effect = LLMOutputError("bad output")
        mock_factory.return_value = mock_adapter

        response = client.post("/api/generate", json={
            "feature_description": "Login",
            "skill": "functional/smoke",
            "n_suggestions": 3,
        })

    assert response.status_code == 422


def test_generate_endpoint_returns_503_on_config_error(client):
    from testweavex.core.exceptions import ConfigError
    with patch("testweavex.web.api.generate.get_llm_adapter") as mock_factory:
        mock_factory.side_effect = ConfigError("no provider")

        response = client.post("/api/generate", json={
            "feature_description": "Login",
            "skill": "functional/smoke",
            "n_suggestions": 3,
        })

    assert response.status_code == 503
```

- [ ] **Step 2: Run tests to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_web_api.py::test_generate_endpoint_returns_200_with_response -v
```

Expected: `404 Not Found` (route doesn't exist yet).

- [ ] **Step 3: Create generate route**

```python
# testweavex/web/api/generate.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from testweavex.core.exceptions import ConfigError, LLMOutputError
from testweavex.core.models import GenerationRequest
from testweavex.llm.base import get_llm_adapter

router = APIRouter()


class GenerateRequest(BaseModel):
    feature_description: str
    skill: str = "functional/smoke"
    n_suggestions: int = 5


@router.post("/generate")
async def generate_tests(body: GenerateRequest, request: Request) -> dict:
    config = request.app.state.config

    try:
        adapter = get_llm_adapter(config)
    except ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not adapter.health_check():
        raise HTTPException(status_code=503, detail="LLM provider is not available")

    gen_request = GenerationRequest(
        feature_description=body.feature_description,
        skill_names=[body.skill],
        n_suggestions=body.n_suggestions,
    )

    try:
        response = adapter.generate_tests(gen_request)
    except LLMOutputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return response.model_dump(mode="json")
```

- [ ] **Step 4: Register the router in app.py**

In `testweavex/web/app.py`, add after the other router imports:

```python
    from testweavex.web.api.generate import router as generate_router
    app.include_router(generate_router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_web_api.py -v
```

Expected: all PASSED (including pre-existing tests).

- [ ] **Step 6: Commit**

```bash
git add testweavex/web/api/generate.py testweavex/web/app.py tests/test_web_api.py
git commit -m "feat: add POST /api/generate synchronous LLM generation endpoint"
```

---

### Task 12: Wire POST /api/gaps/{gap_id}/generate

**Files:**
- Modify: `testweavex/web/api/gaps.py`
- Modify: `tests/test_web_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_api.py`:

```python
def test_gap_generate_returns_404_when_gap_not_found(client):
    response = client.post("/api/gaps/nonexistent-gap-id/generate")
    assert response.status_code == 404


def test_gap_generate_returns_200_with_generation_response(client):
    from datetime import datetime, timezone
    from testweavex.core.models import (
        Gap, GapStatus, TestCase, TestType, TestStatus, generate_stable_id,
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    tc_id = generate_stable_id("features/login.feature", "Login test")
    gap = Gap(
        id="gap-1",
        test_case_id=tc_id,
        priority_score=0.8,
        gap_reason="never automated",
        status=GapStatus.open,
        detected_at=now,
    )
    tc = TestCase(
        id=tc_id,
        title="Login test",
        feature_id=generate_stable_id("features/login.feature"),
        gherkin="Scenario: Login\n  Given I am on login page",
        test_type=TestType.smoke,
        skill="functional/smoke",
        is_automated=False,
        created_at=now,
        updated_at=now,
    )

    with patch("testweavex.web.api.gaps.get_llm_adapter") as mock_factory:
        mock_adapter = MagicMock()
        mock_adapter.health_check.return_value = True
        mock_adapter.suggest_gap_automation.return_value = _mock_generation_response()
        mock_factory.return_value = mock_adapter

        repo = client.app.state.repo
        repo.upsert_test_case(tc)
        repo.save_gaps([gap])

        response = client.post("/api/gaps/gap-1/generate")

    assert response.status_code == 200
    data = response.json()
    assert "scenarios" in data
```

- [ ] **Step 2: Run tests to verify they fail**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_web_api.py::test_gap_generate_returns_404_when_gap_not_found -v
```

Expected: FAIL — current stub returns 200 with a message for all IDs.

- [ ] **Step 3: Update gaps.py**

Replace the stub `generate_for_gap` in `testweavex/web/api/gaps.py` with:

```python
from testweavex.core.exceptions import ConfigError, LLMOutputError, RecordNotFound
from testweavex.llm.base import get_llm_adapter


@router.post("/gaps/{gap_id}/generate")
async def generate_for_gap(gap_id: str, request: Request) -> dict:
    repo = request.app.state.repo
    config = request.app.state.config

    all_gaps = repo.get_gaps(limit=10000, status="open")
    gap = next((g for g in all_gaps if g.id == gap_id), None)
    if gap is None:
        raise HTTPException(status_code=404, detail=f"Gap '{gap_id}' not found")

    try:
        tc = repo.get_test_case(gap.test_case_id)
    except RecordNotFound:
        raise HTTPException(status_code=404, detail="Test case for gap not found")

    try:
        adapter = get_llm_adapter(config)
    except ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not adapter.health_check():
        raise HTTPException(status_code=503, detail="LLM provider is not available")

    try:
        response = adapter.suggest_gap_automation(tc)
    except LLMOutputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return response.model_dump(mode="json")
```

Also add `from fastapi import HTTPException` at the top of `gaps.py` if not already present.

- [ ] **Step 4: Run tests to verify they pass**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_web_api.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Run full test suite**

```
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest --tb=short -q
```

Expected: all PASSED (or at minimum no regressions from pre-plan baseline).

- [ ] **Step 6: Commit**

```bash
git add testweavex/web/api/gaps.py tests/test_web_api.py
git commit -m "feat: wire POST /api/gaps/{gap_id}/generate to LLM adapter"
```
