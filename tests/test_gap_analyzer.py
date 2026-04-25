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


def test_analyzer_saves_gaps_on_run(repo, bus):
    tc = _make_tc("never_collected")
    repo.upsert_test_case(tc)

    config = GapAnalysisConfig()
    analyzer = GapAnalyzer(repo, bus, config)

    run = repo.start_run("suite")
    repo.end_run(run.id)

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
