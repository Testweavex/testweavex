from __future__ import annotations

from datetime import datetime, timezone

import httpx

from testweavex.core.exceptions import TCMConnectorError
from testweavex.core.models import TestCase, TestType, TestStatus, generate_stable_id
from testweavex.tcm.base import TCMConnector

_XRAY_AUTH_URL = "https://xray.cloud.getxray.app/api/v2/authenticate"

_PRIORITY_MAP = {
    "blocker": 1, "critical": 1, "highest": 1,
    "high": 1, "major": 1,
    "medium": 2, "normal": 2,
    "low": 3, "minor": 3, "lowest": 3,
}


def _iso_to_dt(s: str | None) -> datetime:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not s:
        return now
    try:
        normalized = s.replace("+0000", "+00:00").replace(".000+00:00", "+00:00")
        return datetime.fromisoformat(normalized).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return now


def _map_priority(priority_name: str) -> int:
    return _PRIORITY_MAP.get(priority_name.lower(), 2)


def _build_gherkin(issue: dict) -> str:
    description = (issue["fields"].get("description") or "").strip()
    if description and "Scenario" in description:
        return description
    title = issue["fields"]["summary"]
    return f'Scenario: {title}\n  Given the test "{title}" exists in the TCM'


def _map_issue(issue: dict, project_key: str) -> TestCase:
    fields = issue["fields"]
    labels: list[str] = fields.get("labels") or []
    is_automated = "automated" in [lbl.lower() for lbl in labels]
    priority_name = (fields.get("priority") or {}).get("name", "Medium")

    return TestCase(
        id=generate_stable_id(project_key, issue["key"]),
        title=fields["summary"],
        feature_id=generate_stable_id(project_key),
        gherkin=_build_gherkin(issue),
        test_type=TestType.sanity,
        skill="builtin",
        status=TestStatus.pending,
        is_automated=is_automated,
        tcm_id=issue["key"],
        tags=labels,
        priority=_map_priority(priority_name),
        created_at=_iso_to_dt(fields.get("created")),
        updated_at=_iso_to_dt(fields.get("updated")),
    )


class XrayConnector(TCMConnector):

    def __init__(self, config: dict, client: httpx.Client | None = None) -> None:
        self._jira_url = config["jira_url"].rstrip("/")
        self._client_id = config["client_id"]
        self._client_secret = config["client_secret"]
        self._project_key = config["project_key"]
        self._client = client or httpx.Client(timeout=30.0)

    def _authenticate(self) -> str:
        try:
            resp = self._client.post(
                _XRAY_AUTH_URL,
                json={"client_id": self._client_id, "client_secret": self._client_secret},
            )
            resp.raise_for_status()
        except Exception as exc:
            raise TCMConnectorError(f"Xray authentication failed: {exc}") from exc
        raw = resp.text.strip().strip('"')
        return raw

    def health_check(self) -> bool:
        try:
            token = self._authenticate()
            resp = self._client.get(
                f"{self._jira_url}/rest/api/2/project/{self._project_key}",
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.status_code == 200
        except Exception:
            return False

    def fetch_all_test_cases(self) -> list[TestCase]:
        token = self._authenticate()
        headers = {"Authorization": f"Bearer {token}"}
        jql = f"project={self._project_key}+AND+issuetype=Test"
        issues: list[TestCase] = []
        start_at = 0
        max_results = 100

        while True:
            try:
                resp = self._client.get(
                    f"{self._jira_url}/rest/api/2/search",
                    params={"jql": jql, "maxResults": max_results, "startAt": start_at},
                    headers=headers,
                )
                resp.raise_for_status()
            except TCMConnectorError:
                raise
            except Exception as exc:
                raise TCMConnectorError(f"Xray search failed: {exc}") from exc

            data = resp.json()
            page = data.get("issues", [])
            if not page:
                break
            issues.extend(_map_issue(i, self._project_key) for i in page)
            start_at += len(page)

        return issues
