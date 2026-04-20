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
