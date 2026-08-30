from __future__ import annotations

from datetime import datetime, timezone

from testweavex.core.config import GapAnalysisConfig
from testweavex.core.models import GapStatus
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
        resolved = self._resolved_gaps({g.test_case_id for g in scored_gaps})
        if scored_gaps or resolved:
            self._repo.save_gaps(scored_gaps + resolved)

        top_n = scored_gaps[: self._config.top_gaps_default]
        self._bus.emit(
            GapAnalysisComplete(
                run_id=run_id,
                gaps_found=len(scored_gaps),
                top_gaps=[g.model_dump(mode="json") for g in top_n],
            )
        )

    def _resolved_gaps(self, current_tc_ids: set[str]) -> list:
        """Close open gaps that this analysis no longer detects.

        Without this a gap stays open forever once recorded, even after the
        test case behind it is automated or starts running.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            open_gaps = self._repo.get_gaps(limit=10_000, status="open")
        except Exception:
            return []
        resolved = []
        for gap in open_gaps:
            if gap.test_case_id not in current_tc_ids:
                gap.status = GapStatus.closed
                gap.closed_at = now
                resolved.append(gap)
        return resolved
