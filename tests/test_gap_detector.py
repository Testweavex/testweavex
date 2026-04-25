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
