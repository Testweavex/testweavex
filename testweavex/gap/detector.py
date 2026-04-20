from __future__ import annotations

import uuid
from datetime import datetime, timezone

from testweavex.core.models import Gap, GapStatus
from testweavex.storage.base import StorageRepository


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class GapDetector:
    def __init__(self, repo: StorageRepository) -> None:
        self._repo = repo

    def find_uncollected(self, collected_ids: list[str]) -> list[Gap]:
        collected = set(collected_ids)
        all_cases = self._repo.get_all_test_cases()
        now = _now()
        return [
            Gap(
                id=str(uuid.uuid4()),
                test_case_id=tc.id,
                gap_reason="uncollected",
                status=GapStatus.open,
                detected_at=now,
            )
            for tc in all_cases
            if tc.id not in collected
        ]

    def find_never_run(self) -> list[Gap]:
        now = _now()
        return [
            Gap(
                id=str(uuid.uuid4()),
                test_case_id=tc.id,
                gap_reason="never_run",
                status=GapStatus.open,
                detected_at=now,
            )
            for tc in self._repo.get_never_run_test_cases()
        ]

    def find_always_failing(self) -> list[Gap]:
        now = _now()
        return [
            Gap(
                id=str(uuid.uuid4()),
                test_case_id=tc.id,
                gap_reason="always_failing",
                status=GapStatus.open,
                detected_at=now,
            )
            for tc in self._repo.get_always_failing_test_cases()
        ]

    def find_all(self, collected_ids: list[str]) -> list[Gap]:
        seen: set[str] = set()
        result: list[Gap] = []
        for gap in (
            self.find_uncollected(collected_ids)
            + self.find_never_run()
            + self.find_always_failing()
        ):
            if gap.test_case_id not in seen:
                seen.add(gap.test_case_id)
                result.append(gap)
        return result
