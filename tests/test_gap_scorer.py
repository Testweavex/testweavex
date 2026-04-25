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
