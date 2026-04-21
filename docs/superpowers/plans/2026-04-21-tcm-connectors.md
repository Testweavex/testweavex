# TCM Connectors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `testweavex/tcm/` — one-way pull connectors for TestRail and Xray (Jira), wired into `tw migrate` and `tw sync` CLI commands.

**Architecture:** Thin connector pattern — each connector only fetches `TestCase` objects via HTTP; all orchestration (upsert, file writing, progress output) lives in `cli.py`. A `get_connector(config)` factory in `__init__.py` selects the right implementation.

**Tech Stack:** Python 3.11+, httpx 0.24+, Pydantic v2, Typer, Rich, pytest + unittest.mock

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `testweavex/tcm/__init__.py` | `get_connector` factory |
| Create | `testweavex/tcm/base.py` | Abstract `TCMConnector` interface |
| Create | `testweavex/tcm/builtin.py` | `BuiltinTCMConnector` — delegates to `StorageRepository` |
| Create | `testweavex/tcm/testrail.py` | `TestRailConnector` — httpx + Basic auth |
| Create | `testweavex/tcm/xray.py` | `XrayConnector` — httpx + OAuth2 per-request |
| Create | `tests/test_tcm.py` | All TCM connector tests |
| Modify | `testweavex/cli.py` | Wire `migrate` and `sync` commands |
| Modify | `tests/test_cli.py` | Tests for `migrate` and `sync` CLI commands |

**Note:** `testweavex/core/exceptions.py` already has `TCMConnectorError` — no changes needed there.

---

## Task 1: Abstract Interface + Factory

**Files:**
- Create: `testweavex/tcm/base.py`
- Create: `testweavex/tcm/__init__.py`
- Create: `tests/test_tcm.py`

- [ ] **Step 1: Write failing tests for the factory**

```python
# tests/test_tcm.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from testweavex.core.config import TCMConfig
from testweavex.core.exceptions import ConfigError
from testweavex.tcm import get_connector
from testweavex.tcm.builtin import BuiltinTCMConnector


def test_get_connector_none_returns_builtin():
    cfg = TCMConfig(provider="none")
    repo = MagicMock()
    connector = get_connector(cfg, repo=repo)
    assert isinstance(connector, BuiltinTCMConnector)


def test_get_connector_builtin_returns_builtin():
    cfg = TCMConfig(provider="builtin")
    repo = MagicMock()
    connector = get_connector(cfg, repo=repo)
    assert isinstance(connector, BuiltinTCMConnector)


def test_get_connector_unknown_raises_config_error():
    cfg = TCMConfig(provider="jira-cloud")
    with pytest.raises(ConfigError, match="Unknown TCM provider"):
        get_connector(cfg)
```

- [ ] **Step 2: Run to verify failures**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_tcm.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `testweavex.tcm` does not exist yet.

- [ ] **Step 3: Create `testweavex/tcm/base.py`**

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from testweavex.core.models import TestCase


class TCMConnector(ABC):

    @abstractmethod
    def fetch_all_test_cases(self) -> list[TestCase]: ...

    @abstractmethod
    def health_check(self) -> bool: ...
```

- [ ] **Step 4: Create `testweavex/tcm/builtin.py`**

```python
from __future__ import annotations

from testweavex.storage.base import StorageRepository
from testweavex.tcm.base import TCMConnector
from testweavex.core.models import TestCase


class BuiltinTCMConnector(TCMConnector):

    def __init__(self, repo: StorageRepository) -> None:
        self._repo = repo

    def fetch_all_test_cases(self) -> list[TestCase]:
        return self._repo.get_all_test_cases()

    def health_check(self) -> bool:
        return True
```

- [ ] **Step 5: Create `testweavex/tcm/__init__.py`**

```python
from __future__ import annotations

from testweavex.core.config import TCMConfig
from testweavex.core.exceptions import ConfigError
from testweavex.storage.base import StorageRepository
from testweavex.tcm.base import TCMConnector


def get_connector(
    config: TCMConfig,
    repo: StorageRepository | None = None,
) -> TCMConnector:
    provider = config.provider.lower()

    if provider in ("none", "builtin"):
        from testweavex.tcm.builtin import BuiltinTCMConnector
        if repo is None:
            raise ConfigError("BuiltinTCMConnector requires a StorageRepository")
        return BuiltinTCMConnector(repo)

    if provider == "testrail":
        from testweavex.tcm.testrail import TestRailConnector
        return TestRailConnector(config.testrail)

    if provider == "xray":
        from testweavex.tcm.xray import XrayConnector
        return XrayConnector(config.xray)

    raise ConfigError(f"Unknown TCM provider: {config.provider!r}")
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_tcm.py -v
```

Expected: 3 tests pass.

- [ ] **Step 7: Commit**

```bash
git add testweavex/tcm/ tests/test_tcm.py
git commit -m "feat: tcm base interface, builtin connector, and get_connector factory"
```

---

## Task 2: BuiltinTCMConnector Tests

**Files:**
- Modify: `tests/test_tcm.py`

- [ ] **Step 1: Add BuiltinTCMConnector tests**

Append to `tests/test_tcm.py`:

```python
from testweavex.tcm.builtin import BuiltinTCMConnector
from testweavex.core.models import TestCase, TestType, TestStatus, generate_stable_id
from datetime import datetime, timezone


def _make_tc(title: str = "Login test") -> TestCase:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return TestCase(
        id=generate_stable_id("features/login.feature", title),
        title=title,
        feature_id=generate_stable_id("features/login.feature"),
        gherkin="Scenario: Login\n  Given I am on login page",
        test_type=TestType.smoke,
        skill="builtin",
        created_at=now,
        updated_at=now,
    )


class TestBuiltinTCMConnector:
    def test_fetch_all_delegates_to_repo(self):
        repo = MagicMock()
        tc = _make_tc()
        repo.get_all_test_cases.return_value = [tc]
        connector = BuiltinTCMConnector(repo)
        result = connector.fetch_all_test_cases()
        assert result == [tc]
        repo.get_all_test_cases.assert_called_once()

    def test_health_check_always_true(self):
        connector = BuiltinTCMConnector(MagicMock())
        assert connector.health_check() is True
```

- [ ] **Step 2: Run tests**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_tcm.py -v
```

Expected: 5 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_tcm.py
git commit -m "test: BuiltinTCMConnector unit tests"
```

---

## Task 3: TestRail Connector

**Files:**
- Create: `testweavex/tcm/testrail.py`
- Modify: `tests/test_tcm.py`

- [ ] **Step 1: Write failing tests for TestRailConnector**

Append to `tests/test_tcm.py`:

```python
from unittest.mock import patch, MagicMock
from testweavex.tcm.testrail import TestRailConnector


def _make_tr_config(suite_id: int | None = None) -> dict:
    return {
        "url": "https://company.testrail.io",
        "username": "user@test.com",
        "api_key": "secret",
        "project_id": 12,
        "suite_id": suite_id,
    }


def _mock_response(json_data: object, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    resp.raise_for_status = MagicMock()
    return resp


class TestTestRailConnector:
    def test_health_check_returns_true_on_200(self):
        mock_client = MagicMock()
        mock_client.get.return_value = _mock_response({"id": 12, "name": "MyProject"})
        connector = TestRailConnector(_make_tr_config(), client=mock_client)
        assert connector.health_check() is True
        mock_client.get.assert_called_once_with("/api/v2/get_project/12")

    def test_health_check_returns_false_on_error(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Connection refused")
        connector = TestRailConnector(_make_tr_config(), client=mock_client)
        assert connector.health_check() is False

    def test_fetch_uses_configured_suite_id(self):
        mock_client = MagicMock()
        cases_page1 = {
            "cases": [
                {
                    "id": 101,
                    "title": "User can log in",
                    "suite_id": 45,
                    "priority_id": 2,
                    "refs": "REF-1,REF-2",
                    "custom_gherkin": "Scenario: Login\n  Given I am on login page",
                    "custom_automation_type": "None",
                    "created_on": 1700000000,
                    "updated_on": 1700001000,
                }
            ],
            "offset": 0,
            "limit": 250,
            "size": 1,
        }
        cases_page2 = {"cases": [], "offset": 250, "limit": 250, "size": 0}
        mock_client.get.side_effect = [
            _mock_response(cases_page1),
            _mock_response(cases_page2),
        ]
        connector = TestRailConnector(_make_tr_config(suite_id=45), client=mock_client)
        result = connector.fetch_all_test_cases()
        assert len(result) == 1
        tc = result[0]
        assert tc.title == "User can log in"
        assert tc.tcm_id == "101"
        assert tc.gherkin == "Scenario: Login\n  Given I am on login page"
        assert tc.is_automated is False
        assert "REF-1" in tc.tags

    def test_fetch_all_suites_when_no_suite_id(self):
        mock_client = MagicMock()
        suites_resp = _mock_response([{"id": 10}, {"id": 11}])
        cases_s10_p1 = _mock_response({
            "cases": [{"id": 1, "title": "T1", "suite_id": 10, "priority_id": 1,
                        "refs": "", "custom_gherkin": None,
                        "custom_automation_type": "Automated",
                        "created_on": 1700000000, "updated_on": 1700001000}],
            "offset": 0, "limit": 250, "size": 1,
        })
        cases_s10_p2 = _mock_response({"cases": [], "offset": 250, "limit": 250, "size": 0})
        cases_s11_p1 = _mock_response({
            "cases": [{"id": 2, "title": "T2", "suite_id": 11, "priority_id": 3,
                        "refs": "", "custom_gherkin": None,
                        "custom_automation_type": "None",
                        "created_on": 1700000000, "updated_on": 1700001000}],
            "offset": 0, "limit": 250, "size": 1,
        })
        cases_s11_p2 = _mock_response({"cases": [], "offset": 250, "limit": 250, "size": 0})
        mock_client.get.side_effect = [
            suites_resp,
            cases_s10_p1, cases_s10_p2,
            cases_s11_p1, cases_s11_p2,
        ]
        connector = TestRailConnector(_make_tr_config(), client=mock_client)
        result = connector.fetch_all_test_cases()
        assert len(result) == 2
        assert result[0].is_automated is True   # custom_automation_type != "None"
        assert result[1].is_automated is False

    def test_missing_gherkin_uses_fallback(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = [
            _mock_response({
                "cases": [{"id": 5, "title": "Edge case test", "suite_id": 45,
                            "priority_id": 3, "refs": "",
                            "custom_gherkin": None,
                            "custom_automation_type": "None",
                            "created_on": 1700000000, "updated_on": 1700001000}],
                "offset": 0, "limit": 250, "size": 1,
            }),
            _mock_response({"cases": [], "offset": 250, "limit": 250, "size": 0}),
        ]
        connector = TestRailConnector(_make_tr_config(suite_id=45), client=mock_client)
        result = connector.fetch_all_test_cases()
        assert 'Scenario: Edge case test' in result[0].gherkin

    def test_non_2xx_raises_tcm_connector_error(self):
        from testweavex.core.exceptions import TCMConnectorError
        mock_client = MagicMock()
        err_resp = _mock_response({"error": "Not found"}, status_code=404)
        err_resp.raise_for_status.side_effect = Exception("404")
        mock_client.get.return_value = err_resp
        connector = TestRailConnector(_make_tr_config(suite_id=45), client=mock_client)
        with pytest.raises(TCMConnectorError):
            connector.fetch_all_test_cases()
```

- [ ] **Step 2: Run to verify failures**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_tcm.py::TestTestRailConnector -v
```

Expected: `ImportError` — `testweavex.tcm.testrail` does not exist yet.

- [ ] **Step 3: Create `testweavex/tcm/testrail.py`**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_tcm.py::TestTestRailConnector -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add testweavex/tcm/testrail.py tests/test_tcm.py
git commit -m "feat: TestRailConnector with pagination and field mapping"
```

---

## Task 4: Xray Connector

**Files:**
- Create: `testweavex/tcm/xray.py`
- Modify: `tests/test_tcm.py`

- [ ] **Step 1: Write failing tests for XrayConnector**

Append to `tests/test_tcm.py`:

```python
from testweavex.tcm.xray import XrayConnector


def _make_xray_config() -> dict:
    return {
        "jira_url": "https://company.atlassian.net",
        "client_id": "CLIENT_ID",
        "client_secret": "CLIENT_SECRET",
        "project_key": "QA",
    }


def _xray_issue(key: str = "QA-1", summary: str = "Login test",
                priority: str = "High", labels: list | None = None,
                description: str | None = None) -> dict:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "priority": {"name": priority},
            "labels": labels or [],
            "created": "2023-01-15T10:30:00.000+0000",
            "updated": "2023-06-20T12:00:00.000+0000",
            "description": description,
        },
    }


class TestXrayConnector:
    def test_health_check_returns_true_on_200(self):
        mock_client = MagicMock()
        mock_client.post.return_value = _mock_response("jwt-token-string")
        mock_client.post.return_value.text = "jwt-token-string"
        mock_client.get.return_value = _mock_response({"key": "QA"})
        connector = XrayConnector(_make_xray_config(), client=mock_client)
        assert connector.health_check() is True

    def test_health_check_returns_false_on_auth_failure(self):
        mock_client = MagicMock()
        mock_client.post.side_effect = Exception("Auth failed")
        connector = XrayConnector(_make_xray_config(), client=mock_client)
        assert connector.health_check() is False

    def test_fetch_maps_issue_to_test_case(self):
        mock_client = MagicMock()
        auth_resp = MagicMock()
        auth_resp.text = '"jwt-token-string"'
        auth_resp.json.return_value = "jwt-token-string"
        auth_resp.raise_for_status = MagicMock()
        search_page1 = _mock_response({
            "total": 1,
            "startAt": 0,
            "maxResults": 100,
            "issues": [_xray_issue("QA-1", "Login test", "High", ["automated"],
                                    "Scenario: Login\n  Given I open login page")],
        })
        search_page2 = _mock_response({
            "total": 1, "startAt": 100, "maxResults": 100, "issues": [],
        })
        mock_client.post.return_value = auth_resp
        mock_client.get.side_effect = [search_page1, search_page2]
        connector = XrayConnector(_make_xray_config(), client=mock_client)
        result = connector.fetch_all_test_cases()
        assert len(result) == 1
        tc = result[0]
        assert tc.title == "Login test"
        assert tc.tcm_id == "QA-1"
        assert tc.is_automated is True
        assert tc.priority == 1
        assert "Scenario: Login" in tc.gherkin

    def test_fetch_uses_gherkin_fallback_when_no_description(self):
        mock_client = MagicMock()
        auth_resp = MagicMock()
        auth_resp.text = '"jwt-token-string"'
        auth_resp.json.return_value = "jwt-token-string"
        auth_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = auth_resp
        mock_client.get.side_effect = [
            _mock_response({
                "total": 1, "startAt": 0, "maxResults": 100,
                "issues": [_xray_issue("QA-2", "Edge case", description=None)],
            }),
            _mock_response({"total": 1, "startAt": 100, "maxResults": 100, "issues": []}),
        ]
        connector = XrayConnector(_make_xray_config(), client=mock_client)
        result = connector.fetch_all_test_cases()
        assert 'Scenario: Edge case' in result[0].gherkin

    def test_fetch_paginates_correctly(self):
        mock_client = MagicMock()
        auth_resp = MagicMock()
        auth_resp.text = '"jwt-token-string"'
        auth_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = auth_resp
        mock_client.get.side_effect = [
            _mock_response({
                "total": 2, "startAt": 0, "maxResults": 1,
                "issues": [_xray_issue("QA-1")],
            }),
            _mock_response({
                "total": 2, "startAt": 1, "maxResults": 1,
                "issues": [_xray_issue("QA-2")],
            }),
            _mock_response({
                "total": 2, "startAt": 2, "maxResults": 1, "issues": [],
            }),
        ]
        connector = XrayConnector(_make_xray_config(), client=mock_client)
        result = connector.fetch_all_test_cases()
        assert len(result) == 2

    def test_auth_failure_raises_tcm_connector_error(self):
        from testweavex.core.exceptions import TCMConnectorError
        mock_client = MagicMock()
        bad_resp = _mock_response({"error": "Unauthorized"}, status_code=401)
        bad_resp.raise_for_status.side_effect = Exception("401 Unauthorized")
        mock_client.post.return_value = bad_resp
        connector = XrayConnector(_make_xray_config(), client=mock_client)
        with pytest.raises(TCMConnectorError, match="Xray authentication failed"):
            connector.fetch_all_test_cases()
```

- [ ] **Step 2: Run to verify failures**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_tcm.py::TestXrayConnector -v
```

Expected: `ImportError` — `testweavex.tcm.xray` does not exist yet.

- [ ] **Step 3: Create `testweavex/tcm/xray.py`**

```python
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
            start_at += max_results

        return issues
```

- [ ] **Step 4: Run tests**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_tcm.py::TestXrayConnector -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_tcm.py -v
```

Expected: all TCM tests pass.

- [ ] **Step 6: Commit**

```bash
git add testweavex/tcm/xray.py tests/test_tcm.py
git commit -m "feat: XrayConnector with OAuth2 per-request auth and pagination"
```

---

## Task 5: Wire `migrate` Command

**Files:**
- Modify: `testweavex/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for `migrate`**

Append to `tests/test_cli.py`:

```python
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from testweavex.core.models import TestCase, TestType, TestStatus, generate_stable_id


def _cli_test_case(title: str = "Login test") -> TestCase:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return TestCase(
        id=generate_stable_id("12", "101"),
        title=title,
        feature_id=generate_stable_id("12", "45"),
        gherkin="Scenario: Login\n  Given I am on login page",
        test_type=TestType.sanity,
        skill="builtin",
        status=TestStatus.pending,
        is_automated=False,
        tcm_id="101",
        tags=[],
        priority=2,
        created_at=now,
        updated_at=now,
    )


def test_migrate_dry_run_prints_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: testrail\n  testrail:\n    url: https://t.io\n    username: u\n    api_key: k\n    project_id: 12\n")

    mock_connector = MagicMock()
    mock_connector.health_check.return_value = True
    mock_connector.fetch_all_test_cases.return_value = [_cli_test_case()]

    with patch("testweavex.cli.get_connector", return_value=mock_connector):
        result = runner.invoke(app, ["migrate", "--source", "testrail", "--dry-run"])

    assert result.exit_code == 0
    assert "Login test" in result.output or "1" in result.output
    assert not (tmp_path / "features").exists()


def test_migrate_imports_and_writes_feature_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: testrail\n  testrail:\n    url: https://t.io\n    username: u\n    api_key: k\n    project_id: 12\n")

    mock_connector = MagicMock()
    mock_connector.health_check.return_value = True
    mock_connector.fetch_all_test_cases.return_value = [_cli_test_case("Login test")]

    with patch("testweavex.cli.get_connector", return_value=mock_connector):
        result = runner.invoke(app, ["migrate", "--source", "testrail"])

    assert result.exit_code == 0
    feature_files = list((tmp_path / "features").glob("*.feature"))
    assert len(feature_files) == 1
    content = feature_files[0].read_text()
    assert "Login test" in content


def test_migrate_source_mismatch_exits_with_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: xray\n  xray:\n    jira_url: https://j.io\n    client_id: c\n    client_secret: s\n    project_key: QA\n")

    result = runner.invoke(app, ["migrate", "--source", "testrail"])
    assert result.exit_code != 0
    assert "testrail" in result.output.lower() or "mismatch" in result.output.lower() or "xray" in result.output.lower()


def test_migrate_health_check_failure_aborts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: testrail\n  testrail:\n    url: https://t.io\n    username: u\n    api_key: k\n    project_id: 12\n")

    mock_connector = MagicMock()
    mock_connector.health_check.return_value = False

    with patch("testweavex.cli.get_connector", return_value=mock_connector):
        result = runner.invoke(app, ["migrate", "--source", "testrail"])

    assert result.exit_code != 0
    assert "connect" in result.output.lower() or "health" in result.output.lower() or "failed" in result.output.lower()
```

- [ ] **Step 2: Run to verify failures**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_cli.py::test_migrate_dry_run_prints_summary tests/test_cli.py::test_migrate_imports_and_writes_feature_files tests/test_cli.py::test_migrate_source_mismatch_exits_with_error tests/test_cli.py::test_migrate_health_check_failure_aborts -v
```

Expected: all 4 fail — `migrate` still raises `Exit(1)` with "not yet available".

- [ ] **Step 3: Replace the `migrate` command in `testweavex/cli.py`**

Remove the old stub and replace with:

```python
@app.command()
def migrate(
    source: str = typer.Option(..., "--source", help="TCM source: testrail or xray"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
) -> None:
    """Import test cases from an external TCM into TestWeaveX."""
    import re
    from testweavex.tcm import get_connector

    config = load_config()
    if config.tcm.provider.lower() != source.lower():
        console.print(
            f"[red]Source mismatch:[/red] config has provider=[bold]{config.tcm.provider}[/bold]"
            f" but --source={source}"
        )
        raise typer.Exit(code=1)

    connector = get_connector(config.tcm)
    if not connector.health_check():
        console.print(f"[red]Cannot connect to {source}. Check your config credentials.[/red]")
        raise typer.Exit(code=1)

    console.print(f"Fetching test cases from {source}…")
    test_cases = connector.fetch_all_test_cases()

    if dry_run:
        table = Table(title=f"Dry Run — {len(test_cases)} test case(s) from {source}")
        table.add_column("TCM ID")
        table.add_column("Title")
        table.add_column("Automated")
        for tc in test_cases:
            table.add_row(tc.tcm_id or "", tc.title, "yes" if tc.is_automated else "no")
        console.print(table)
        return

    repo = _get_repo()
    features_dir = Path(config.features_dir or "features")
    features_dir.mkdir(parents=True, exist_ok=True)

    def _safe_filename(title: str) -> str:
        return re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_").lower()[:80]

    errors: list[str] = []
    for tc in test_cases:
        try:
            repo.upsert_test_case(tc)
            feature_path = features_dir / f"{_safe_filename(tc.title)}.feature"
            feature_path.write_text(
                f"Feature: {tc.title}\n\n{tc.gherkin}\n",
                encoding="utf-8",
            )
        except Exception as exc:
            errors.append(f"{tc.tcm_id}: {exc}")

    console.print(f"[green]Imported {len(test_cases) - len(errors)} test case(s)[/green]"
                  f" → {features_dir}")
    if errors:
        console.print(f"[yellow]{len(errors)} error(s):[/yellow]")
        for e in errors:
            console.print(f"  {e}")
```

Also add `get_connector` to the imports at the top of `cli.py` — but it's imported inside the function to keep the lazy import pattern. No top-level import change needed.

- [ ] **Step 4: Run tests**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_cli.py::test_migrate_dry_run_prints_summary tests/test_cli.py::test_migrate_imports_and_writes_feature_files tests/test_cli.py::test_migrate_source_mismatch_exits_with_error tests/test_cli.py::test_migrate_health_check_failure_aborts -v
```

Expected: all 4 pass.

- [ ] **Step 5: Commit**

```bash
git add testweavex/cli.py tests/test_cli.py
git commit -m "feat: tw migrate — import test cases from external TCM with dry-run support"
```

---

## Task 6: Wire `sync` Command

**Files:**
- Modify: `testweavex/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for `sync`**

Append to `tests/test_cli.py`:

```python
def test_sync_upserts_test_cases_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: testrail\n  testrail:\n    url: https://t.io\n    username: u\n    api_key: k\n    project_id: 12\n")

    mock_connector = MagicMock()
    mock_connector.health_check.return_value = True
    mock_connector.fetch_all_test_cases.return_value = [_cli_test_case()]

    with patch("testweavex.cli.get_connector", return_value=mock_connector):
        result = runner.invoke(app, ["sync", "--tcm", "testrail"])

    assert result.exit_code == 0
    assert not (tmp_path / "features").exists()
    assert "1" in result.output or "synced" in result.output.lower() or "imported" in result.output.lower()


def test_sync_tcm_mismatch_exits_with_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: xray\n  xray:\n    jira_url: https://j.io\n    client_id: c\n    client_secret: s\n    project_key: QA\n")

    result = runner.invoke(app, ["sync", "--tcm", "testrail"])
    assert result.exit_code != 0


def test_sync_health_check_failure_aborts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: testrail\n  testrail:\n    url: https://t.io\n    username: u\n    api_key: k\n    project_id: 12\n")

    mock_connector = MagicMock()
    mock_connector.health_check.return_value = False

    with patch("testweavex.cli.get_connector", return_value=mock_connector):
        result = runner.invoke(app, ["sync", "--tcm", "testrail"])

    assert result.exit_code != 0
```

- [ ] **Step 2: Run to verify failures**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_cli.py::test_sync_upserts_test_cases_no_files tests/test_cli.py::test_sync_tcm_mismatch_exits_with_error tests/test_cli.py::test_sync_health_check_failure_aborts -v
```

Expected: all 3 fail.

- [ ] **Step 3: Replace the `sync` command in `testweavex/cli.py`**

Remove the old stub and replace with:

```python
@app.command()
def sync(
    tcm: str = typer.Option(..., "--tcm", help="TCM provider: testrail or xray"),
) -> None:
    """Pull test cases from external TCM into TestWeaveX (one-way sync)."""
    from testweavex.tcm import get_connector

    config = load_config()
    if config.tcm.provider.lower() != tcm.lower():
        console.print(
            f"[red]Provider mismatch:[/red] config has provider=[bold]{config.tcm.provider}[/bold]"
            f" but --tcm={tcm}"
        )
        raise typer.Exit(code=1)

    connector = get_connector(config.tcm)
    if not connector.health_check():
        console.print(f"[red]Cannot connect to {tcm}. Check your config credentials.[/red]")
        raise typer.Exit(code=1)

    console.print(f"Syncing test cases from {tcm}…")
    test_cases = connector.fetch_all_test_cases()

    repo = _get_repo()
    errors: list[str] = []
    for tc in test_cases:
        try:
            repo.upsert_test_case(tc)
        except Exception as exc:
            errors.append(f"{tc.tcm_id}: {exc}")

    console.print(
        f"[green]Synced {len(test_cases) - len(errors)} test case(s)[/green] from {tcm}"
    )
    if errors:
        console.print(f"[yellow]{len(errors)} error(s):[/yellow]")
        for e in errors:
            console.print(f"  {e}")
```

- [ ] **Step 4: Run tests**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_cli.py::test_sync_upserts_test_cases_no_files tests/test_cli.py::test_sync_tcm_mismatch_exits_with_error tests/test_cli.py::test_sync_health_check_failure_aborts -v
```

Expected: all 3 pass.

- [ ] **Step 5: Run the full test suite**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/ -v --tb=short
```

Expected: all tests pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add testweavex/cli.py tests/test_cli.py
git commit -m "feat: tw sync — one-way pull from external TCM into TestWeaveX storage"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by task |
|---|---|
| `tcm/base.py` abstract interface | Task 1 |
| `tcm/builtin.py` reads from StorageRepository | Tasks 1–2 |
| `tcm/__init__.py` `get_connector` factory | Task 1 |
| TestRail connector: Basic auth, pagination, field mapping | Task 3 |
| TestRail: all suites when suite_id omitted | Task 3 |
| TestRail: single suite when suite_id specified | Task 3 |
| Xray connector: OAuth2 per-request, pagination | Task 4 |
| Xray: Gherkin fallback when no description | Task 4 |
| `TCMConnectorError` on non-2xx | Tasks 3–4 |
| `tw migrate --dry-run` prints table | Task 5 |
| `tw migrate` writes `.feature` files + upserts DB | Task 5 |
| `tw migrate` validates source vs config.tcm.provider | Task 5 |
| `tw sync` upserts to DB, no files written | Task 6 |
| `tw sync` validates --tcm vs config.tcm.provider | Task 6 |
| health_check abort on both commands | Tasks 5–6 |

**Placeholder scan:** None found — all steps contain complete code.

**Type consistency check:**
- `TCMConnector.fetch_all_test_cases() -> list[TestCase]` — consistent across base, builtin, testrail, xray
- `TCMConnector.health_check() -> bool` — consistent
- `get_connector(config: TCMConfig, repo: StorageRepository | None = None)` — consistent with CLI usage (CLI passes no `repo` for external connectors, passes `repo` only for builtin)
- `_mock_response` helper defined once in Task 3, reused in Task 4 — tests append to same file so it's in scope

**Note on `TCMConnectorError`:** `exceptions.py` already has this class. No modification needed.
