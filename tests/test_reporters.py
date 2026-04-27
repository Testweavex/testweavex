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
