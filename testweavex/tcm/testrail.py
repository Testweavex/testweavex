from __future__ import annotations

from datetime import datetime, timezone

import httpx

from testweavex.core.exceptions import TCMConnectorError
from testweavex.core.models import TestCase, TestType, TestStatus, generate_stable_id
from testweavex.tcm.base import TCMConnector


def _unix_to_dt(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)


def _map_priority(priority_id: int) -> int:
    """TestRail priority_id: 1=Critical, 2=High, 3=Medium, 4=Low → TestWeaveX 1–3."""
    return min(priority_id, 3)


def _build_gherkin(case: dict) -> str:
    gherkin = case.get("custom_gherkin")
    if gherkin and gherkin.strip():
        return gherkin.strip()
    title = case["title"]
    return f'Scenario: {title}\n  Given the test "{title}" exists in the TCM'


def _map_case(case: dict, project_id: int) -> TestCase:
    suite_id = case.get("suite_id", 0)
    refs_raw = case.get("refs") or ""
    tags = [r.strip() for r in refs_raw.split(",") if r.strip()]
    created_at = _unix_to_dt(case.get("created_on") or 0)
    updated_at = _unix_to_dt(case.get("updated_on") or 0)
    is_automated = (case.get("custom_automation_type") or "None") != "None"

    return TestCase(
        id=generate_stable_id(str(project_id), str(case["id"])),
        title=case["title"],
        feature_id=generate_stable_id(str(project_id), str(suite_id)),
        gherkin=_build_gherkin(case),
        test_type=TestType.sanity,
        skill="builtin",
        status=TestStatus.pending,
        is_automated=is_automated,
        tcm_id=str(case["id"]),
        tags=tags,
        priority=_map_priority(case.get("priority_id", 3)),
        created_at=created_at,
        updated_at=updated_at,
    )


class TestRailConnector(TCMConnector):

    def __init__(self, config: dict, client: httpx.Client | None = None) -> None:
        self._project_id = int(config["project_id"])
        self._suite_id = int(config["suite_id"]) if config.get("suite_id") else None
        self._client = client or httpx.Client(
            base_url=config["url"].rstrip("/"),
            auth=httpx.BasicAuth(config["username"], config["api_key"]),
            timeout=30.0,
        )

    def health_check(self) -> bool:
        try:
            resp = self._client.get(f"/api/v2/get_project/{self._project_id}")
            return resp.status_code == 200
        except Exception:
            return False

    def fetch_all_test_cases(self) -> list[TestCase]:
        suite_ids = (
            [self._suite_id]
            if self._suite_id
            else self._get_all_suite_ids()
        )
        cases: list[TestCase] = []
        for suite_id in suite_ids:
            cases.extend(self._fetch_suite(suite_id))
        return cases

    def _get_all_suite_ids(self) -> list[int]:
        try:
            resp = self._client.get(f"/api/v2/get_suites/{self._project_id}")
            resp.raise_for_status()
            return [s["id"] for s in resp.json()]
        except Exception as exc:
            raise TCMConnectorError(f"TestRail get_suites failed: {exc}") from exc

    def _fetch_suite(self, suite_id: int) -> list[TestCase]:
        cases: list[TestCase] = []
        offset = 0
        limit = 250
        while True:
            try:
                resp = self._client.get(
                    f"/api/v2/get_cases/{self._project_id}",
                    params={"suite_id": suite_id, "offset": offset, "limit": limit},
                )
                resp.raise_for_status()
            except Exception as exc:
                raise TCMConnectorError(f"TestRail get_cases failed: {exc}") from exc
            data = resp.json()
            page = data.get("cases", [])
            if not page:
                break
            cases.extend(_map_case(c, self._project_id) for c in page)
            offset += limit
        return cases
