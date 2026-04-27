# testweavex/storage/server.py
from __future__ import annotations

import httpx

from testweavex.core.exceptions import StorageError
from testweavex.core.models import (
    Gap,
    ScoringSignals,
    TestCase,
    TestResult,
    TestRun,
)
from testweavex.storage.base import StorageRepository


class ServerRepository(StorageRepository):

    def __init__(self, base_url: str, token: str | None = None) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
        )

    # ── internal helpers ──────────────────────────────────────────────────────

    def _get(self, path: str) -> httpx.Response:
        try:
            resp = self._client.get(path)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise StorageError(f"Server error on GET {path}: {exc}") from exc

    def _post(self, path: str, data: object) -> httpx.Response:
        try:
            resp = self._client.post(path, json=data)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise StorageError(f"Server error on POST {path}: {exc}") from exc

    def _put(self, path: str, data: object) -> httpx.Response:
        try:
            resp = self._client.put(path, json=data)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise StorageError(f"Server error on PUT {path}: {exc}") from exc

    def _patch(self, path: str, data: object | None = None) -> httpx.Response:
        try:
            resp = self._client.patch(path, json=data)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise StorageError(f"Server error on PATCH {path}: {exc}") from exc

    # ── StorageRepository interface ───────────────────────────────────────────

    def start_run(
        self,
        suite: str,
        environment: str = "local",
        browser: str | None = None,
        triggered_by: str = "tw",
    ) -> TestRun:
        resp = self._post("/runs", {
            "suite": suite,
            "environment": environment,
            "browser": browser,
            "triggered_by": triggered_by,
        })
        return TestRun(**resp.json())

    def end_run(self, run_id: str) -> None:
        self._patch(f"/runs/{run_id}")

    def get_run(self, run_id: str) -> TestRun:
        resp = self._get(f"/runs/{run_id}")
        return TestRun(**resp.json())

    def list_runs(self, limit: int = 50) -> list[TestRun]:
        resp = self._get(f"/runs?limit={limit}")
        return [TestRun(**r) for r in resp.json()]

    def save_result(self, r: TestResult) -> None:
        self._post("/results", r.model_dump(mode="json"))

    def get_results_for_run(self, run_id: str) -> list[TestResult]:
        resp = self._get(f"/runs/{run_id}/results")
        return [TestResult(**r) for r in resp.json()]

    def upsert_test_case(self, tc: TestCase) -> None:
        self._put(f"/test-cases/{tc.id}", tc.model_dump(mode="json"))

    def get_test_case(self, id: str) -> TestCase:
        resp = self._get(f"/test-cases/{id}")
        return TestCase(**resp.json())

    def get_all_test_cases(self) -> list[TestCase]:
        resp = self._get("/test-cases")
        return [TestCase(**tc) for tc in resp.json()]

    def get_never_run_test_cases(self) -> list[TestCase]:
        resp = self._get("/test-cases?filter=never_run")
        return [TestCase(**tc) for tc in resp.json()]

    def get_always_failing_test_cases(self) -> list[TestCase]:
        resp = self._get("/test-cases?filter=always_failing")
        return [TestCase(**tc) for tc in resp.json()]

    def save_gaps(self, gaps: list[Gap]) -> None:
        self._post("/gaps/batch", [g.model_dump(mode="json") for g in gaps])

    def get_gaps(self, limit: int = 50, status: str = "open") -> list[Gap]:
        resp = self._get(f"/gaps?limit={limit}&status={status}")
        return [Gap(**g) for g in resp.json()]

    def mark_uncollected_as_gaps(self, collected_ids: list[str]) -> None:
        self._post("/gaps/mark-uncollected", {"collected_ids": collected_ids})

    def get_coverage_percentage(self) -> float:
        resp = self._get("/coverage")
        return float(resp.json()["percentage"])

    def get_coverage_trend(self, weeks: int) -> list[dict]:
        resp = self._get(f"/coverage/trend?weeks={weeks}")
        return resp.json()

    def get_flaky_tests(self, min_runs: int = 5) -> list[TestCase]:
        resp = self._get(f"/test-cases?filter=flaky&min_runs={min_runs}")
        return [TestCase(**tc) for tc in resp.json()]

    def get_scoring_signals(self, tc_id: str) -> ScoringSignals:
        resp = self._get(f"/test-cases/{tc_id}/signals")
        return ScoringSignals(**resp.json())
