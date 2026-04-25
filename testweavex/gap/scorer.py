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
