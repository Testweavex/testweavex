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
