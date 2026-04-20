from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from testweavex.core.models import (
    Gap,
    GapStatus,
    ScoringSignals,
    TestCase,
    TestResult,
    TestRun,
    TestStatus,
    TestType,
    generate_stable_id,
)
from testweavex.storage.sqlite import SQLiteRepository


@pytest.fixture
def repo():
    """In-memory SQLite repo — isolated per test."""
    return SQLiteRepository(db_url="sqlite:///:memory:")


def _make_test_case(feature_path: str = "features/login.feature",
                    scenario: str = "User logs in") -> TestCase:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return TestCase(
        id=generate_stable_id(feature_path, scenario),
        title=scenario,
        feature_id=generate_stable_id(feature_path),
        gherkin="Given I am on the login page\nWhen I enter valid credentials\nThen I am logged in",
        test_type=TestType.smoke,
        skill="functional/smoke",
        created_at=now,
        updated_at=now,
    )


class TestUpsertAndGetTestCase:
    def test_upsert_creates_new_test_case(self, repo):
        tc = _make_test_case()
        repo.upsert_test_case(tc)
        retrieved = repo.get_test_case(tc.id)
        assert retrieved.id == tc.id
        assert retrieved.title == tc.title
        assert retrieved.test_type == TestType.smoke

    def test_upsert_updates_existing(self, repo):
        tc = _make_test_case()
        repo.upsert_test_case(tc)
        updated = tc.model_copy(update={"title": "Updated title", "is_automated": True})
        repo.upsert_test_case(updated)
        retrieved = repo.get_test_case(tc.id)
        assert retrieved.title == "Updated title"
        assert retrieved.is_automated is True

    def test_get_test_case_not_found(self, repo):
        from testweavex.core.exceptions import RecordNotFound
        with pytest.raises(RecordNotFound):
            repo.get_test_case("nonexistent-id")


class TestRunLifecycle:
    def test_start_and_end_run(self, repo):
        tc = _make_test_case()
        repo.upsert_test_case(tc)

        run = repo.start_run(suite="regression", environment="ci")
        assert run.id
        assert run.completed_at is None

        result = TestResult(
            id=str(uuid.uuid4()),
            run_id=run.id,
            test_case_id=tc.id,
            status=TestStatus.passed,
            duration_ms=1500,
        )
        repo.save_result(result)
        repo.end_run(run.id)

        retrieved = repo.get_run(run.id)
        assert retrieved.completed_at is not None
        assert retrieved.suite == "regression"
        assert retrieved.environment == "ci"

    def test_get_run_not_found(self, repo):
        from testweavex.core.exceptions import RecordNotFound
        with pytest.raises(RecordNotFound):
            repo.get_run("nonexistent-run-id")


class TestCoveragePercentage:
    def test_no_test_cases(self, repo):
        assert repo.get_coverage_percentage() == 0.0

    def test_all_automated(self, repo):
        tc = _make_test_case()
        automated = tc.model_copy(update={"is_automated": True})
        repo.upsert_test_case(automated)
        assert repo.get_coverage_percentage() == 100.0

    def test_mixed_automated(self, repo):
        for i in range(4):
            tc = _make_test_case(scenario=f"Scenario {i}")
            is_auto = i < 2
            repo.upsert_test_case(tc.model_copy(update={"is_automated": is_auto}))
        pct = repo.get_coverage_percentage()
        assert pct == 50.0


class TestMarkUncollectedAsGaps:
    def test_uncollected_test_cases_become_gaps(self, repo):
        tc1 = _make_test_case(scenario="Scenario A")
        tc2 = _make_test_case(scenario="Scenario B")
        tc3 = _make_test_case(scenario="Scenario C")
        for tc in [tc1, tc2, tc3]:
            repo.upsert_test_case(tc)

        repo.mark_uncollected_as_gaps(collected_ids=[tc1.id])

        gaps = repo.get_gaps(limit=10, status="open")
        gap_tc_ids = {g.test_case_id for g in gaps}
        assert tc2.id in gap_tc_ids
        assert tc3.id in gap_tc_ids
        assert tc1.id not in gap_tc_ids

    def test_does_not_create_duplicate_gaps(self, repo):
        tc = _make_test_case()
        repo.upsert_test_case(tc)

        repo.mark_uncollected_as_gaps(collected_ids=[])
        repo.mark_uncollected_as_gaps(collected_ids=[])

        gaps = repo.get_gaps(limit=10, status="open")
        tc_gap_ids = [g for g in gaps if g.test_case_id == tc.id]
        assert len(tc_gap_ids) == 1

    def test_empty_collected_ids_flags_all(self, repo):
        tc1 = _make_test_case(scenario="A")
        tc2 = _make_test_case(scenario="B")
        repo.upsert_test_case(tc1)
        repo.upsert_test_case(tc2)

        repo.mark_uncollected_as_gaps(collected_ids=[])

        gaps = repo.get_gaps(limit=10)
        assert len(gaps) == 2


class TestFlakyTests:
    def test_returns_empty_with_no_runs(self, repo):
        tc = _make_test_case()
        repo.upsert_test_case(tc)
        assert repo.get_flaky_tests(min_runs=1) == []

    def test_consistent_pass_not_flaky(self, repo):
        tc = _make_test_case()
        repo.upsert_test_case(tc)
        run = repo.start_run(suite="s")
        for i in range(5):
            repo.save_result(TestResult(
                id=str(uuid.uuid4()),
                run_id=run.id,
                test_case_id=tc.id,
                status=TestStatus.passed,
                duration_ms=100,
            ))
        assert repo.get_flaky_tests(min_runs=5) == []

    def test_mixed_results_is_flaky(self, repo):
        tc = _make_test_case()
        repo.upsert_test_case(tc)
        run = repo.start_run(suite="s")
        statuses = [TestStatus.passed, TestStatus.failed, TestStatus.passed,
                    TestStatus.failed, TestStatus.passed]
        for status in statuses:
            repo.save_result(TestResult(
                id=str(uuid.uuid4()),
                run_id=run.id,
                test_case_id=tc.id,
                status=status,
                duration_ms=100,
            ))
        flaky = repo.get_flaky_tests(min_runs=5)
        assert len(flaky) == 1
        assert flaky[0].id == tc.id

    def test_below_min_runs_not_returned(self, repo):
        tc = _make_test_case()
        repo.upsert_test_case(tc)
        run = repo.start_run(suite="s")
        for status in [TestStatus.passed, TestStatus.failed]:
            repo.save_result(TestResult(
                id=str(uuid.uuid4()),
                run_id=run.id,
                test_case_id=tc.id,
                status=status,
                duration_ms=100,
            ))
        assert repo.get_flaky_tests(min_runs=5) == []


class TestScoringSignals:
    def test_returns_signals_for_known_test(self, repo):
        tc = _make_test_case()
        repo.upsert_test_case(tc)
        signals = repo.get_scoring_signals(tc.id)
        assert signals.test_priority == 2
        assert signals.test_type == TestType.smoke
        assert signals.defect_count == 0
        assert signals.executions_90d == 0

    def test_raises_for_unknown_test(self, repo):
        from testweavex.core.exceptions import RecordNotFound
        with pytest.raises(RecordNotFound):
            repo.get_scoring_signals("nonexistent-id")


def test_get_all_test_cases_empty(repo):
    assert repo.get_all_test_cases() == []


def test_get_all_test_cases_returns_all(repo):
    tc = _make_test_case()
    repo.upsert_test_case(tc)
    results = repo.get_all_test_cases()
    assert len(results) == 1
    assert results[0].id == tc.id


def test_get_never_run_test_cases(repo):
    tc = _make_test_case()
    repo.upsert_test_case(tc)
    never_run = repo.get_never_run_test_cases()
    assert any(tc_item.id == tc.id for tc_item in never_run)


def test_get_never_run_excludes_run_test(repo):
    tc = _make_test_case()
    repo.upsert_test_case(tc)
    run = repo.start_run("suite")
    result = TestResult(
        id=str(uuid.uuid4()),
        run_id=run.id,
        test_case_id=tc.id,
        status=TestStatus.passed,
        duration_ms=100,
    )
    repo.save_result(result)
    never_run = repo.get_never_run_test_cases()
    assert not any(tc_item.id == tc.id for tc_item in never_run)


def test_get_always_failing_test_cases(repo):
    tc = _make_test_case()
    repo.upsert_test_case(tc)
    run = repo.start_run("suite")
    result = TestResult(
        id=str(uuid.uuid4()),
        run_id=run.id,
        test_case_id=tc.id,
        status=TestStatus.failed,
        duration_ms=100,
    )
    repo.save_result(result)
    always_failing = repo.get_always_failing_test_cases()
    assert any(tc_item.id == tc.id for tc_item in always_failing)


def test_list_runs_empty(repo):
    assert repo.list_runs() == []


def test_list_runs_returns_most_recent_first(repo):
    import time
    run_a = repo.start_run("suite-a")
    time.sleep(0.01)  # Ensure different timestamp
    run_b = repo.start_run("suite-b")
    runs = repo.list_runs()
    assert len(runs) == 2
    # Verify by ID since suite-b was started more recently
    assert runs[0].id == run_b.id


def test_get_results_for_run(repo):
    tc = _make_test_case()
    repo.upsert_test_case(tc)
    run = repo.start_run("suite")
    r = TestResult(
        id=str(uuid.uuid4()),
        run_id=run.id,
        test_case_id=tc.id,
        status=TestStatus.passed,
        duration_ms=150,
    )
    repo.save_result(r)
    results = repo.get_results_for_run(run.id)
    assert len(results) == 1
    assert results[0].run_id == run.id
