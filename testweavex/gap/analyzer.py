from __future__ import annotations

from testweavex.core.config import GapAnalysisConfig
from testweavex.events import EventBus, GapAnalysisComplete
from testweavex.gap.detector import GapDetector
from testweavex.gap.scorer import GapScorer
from testweavex.storage.base import StorageRepository


class GapAnalyzer:
    def __init__(
        self,
        repo: StorageRepository,
        bus: EventBus,
        config: GapAnalysisConfig,
    ) -> None:
        self._repo = repo
        self._bus = bus
        self._config = config

    def run(self, run_id: str, collected_ids: list[str]) -> None:
        detector = GapDetector(self._repo)
        scorer = GapScorer(self._config.scoring_weights)

        raw_gaps = detector.find_all(collected_ids)

        signals_map = {}
        for gap in raw_gaps:
            try:
                signals_map[gap.test_case_id] = self._repo.get_scoring_signals(
                    gap.test_case_id
                )
            except Exception:
                pass

        scored_gaps = scorer.score_all(raw_gaps, signals_map)
        if scored_gaps:
            self._repo.save_gaps(scored_gaps)

        top_n = scored_gaps[: self._config.top_gaps_default]
        self._bus.emit(
            GapAnalysisComplete(
                run_id=run_id,
                gaps_found=len(scored_gaps),
                top_gaps=[g.model_dump(mode="json") for g in top_n],
            )
        )
