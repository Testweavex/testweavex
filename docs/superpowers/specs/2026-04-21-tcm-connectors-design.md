# TCM Connectors — Design Spec

**Date:** 2026-04-21
**Phase:** 7 — TCM Connectors
**Status:** Approved

---

## Summary

Build `testweavex/tcm/` — a package of one-way-pull connectors for external Test Case Management systems. V1 ships TestRail and Xray (Jira) connectors. Sync is **pull-only**: test cases flow from the external TCM into TestWeaveX's built-in storage. Results and test updates never go back to the external TCM.

---

## Decisions Made

| Question | Decision |
|---|---|
| Architecture pattern | Option A — thin connector, fat CLI |
| `migrate` writes | Files + DB (`.feature` files on disk + SQLite upsert) |
| `sync` writes | DB only (no file writing) |
| Sync direction | One-way pull only — no push back to external TCM |
| TestRail suites | Fetch all suites if `suite_id` omitted, single suite if specified |
| Xray auth | Re-authenticate per request (stateless, no token caching) |

---

## 1. Package Structure

```
testweavex/tcm/
├── __init__.py       # get_connector(config) factory
├── base.py           # Abstract TCMConnector interface
├── builtin.py        # BuiltinTCM — reads from StorageRepository
├── testrail.py       # TestRailConnector — httpx + Basic auth
└── xray.py           # XrayConnector — httpx + OAuth2 per-request
```

### Factory

`get_connector(config: TCMConfig) -> TCMConnector` in `__init__.py`:
- `"testrail"` → `TestRailConnector`
- `"xray"` → `XrayConnector`
- `"none"` or `"builtin"` → `BuiltinTCMConnector`
- anything else → raise `ConfigError`

---

## 2. Abstract Interface

```python
class TCMConnector(ABC):
    @abstractmethod
    def fetch_all_test_cases(self) -> list[TestCase]: ...

    @abstractmethod
    def health_check(self) -> bool: ...
```

Simplified from the architecture doc — `push_result` and `push_test_case` are excluded since sync is one-way.

### Field Mapping

| TestCase field | TestRail source | Xray source |
|---|---|---|
| `id` | `generate_stable_id(project_id, case_id)` | `generate_stable_id(project_key, issue_key)` |
| `title` | `case["title"]` | `issue["summary"]` |
| `tcm_id` | `str(case["id"])` | `issue["key"]` (e.g. `QA-42`) |
| `priority` | `case["priority_id"]` (1–4) | Jira priority mapped to 1–3 |
| `gherkin` | `case["custom_gherkin"]` or generated from title | BDD customfield if present, else generated from summary |
| `is_automated` | `case["custom_automation_type"] != "None"` | label `automated` present |
| `tags` | `case["refs"]` split | Jira labels |
| `feature_id` | `generate_stable_id(project_id, suite_id)` | `generate_stable_id(project_key)` |
| `test_type` | default `TestType.sanity` | default `TestType.sanity` |
| `skill` | `"builtin"` | `"builtin"` |

**Minimal Gherkin fallback** (when no Gherkin source exists):
```gherkin
Scenario: {title}
  Given the test "{title}" exists in the TCM
```

---

## 3. TestRail Connector

**Auth:** `httpx.BasicAuth(username, api_key)` — standard HTTP Basic.

### `fetch_all_test_cases()` flow

1. If `suite_id` configured: fetch that suite only
2. Else: `GET /api/v2/get_suites/{project_id}` → all suite IDs
3. For each suite: `GET /api/v2/get_cases/{project_id}?suite_id={id}&offset={n}&limit=250` — paginate until empty
4. Map each case dict → `TestCase` using field mapping above
5. Return flat list

### `health_check()`

`GET /api/v2/get_project/{project_id}` → `True` if HTTP 200, `False` otherwise.

### Error handling

- Non-2xx → raise `TCMConnectionError(f"TestRail {status}: {body}")`
- Missing `custom_gherkin` → use minimal Gherkin fallback
- Network timeout → raise `TCMConnectionError`

---

## 4. Xray Connector

**Auth:** OAuth2 client credentials, re-authenticated per-request (stateless).

### Auth flow

```
POST https://xray.cloud.getxray.app/api/v2/authenticate
Body: {"client_id": ..., "client_secret": ...}
Response: raw JWT string (not JSON-wrapped)
Use as: Authorization: Bearer {token}
```

### `fetch_all_test_cases()` flow

1. Authenticate → get token
2. `GET {jira_url}/rest/api/2/search?jql=project={project_key}+AND+issuetype=Test&maxResults=100&startAt=0`
3. Paginate via `startAt` until `issues` is empty
4. Map each issue → `TestCase`
5. Return flat list

### `health_check()`

Authenticate → `GET {jira_url}/rest/api/2/project/{project_key}` → `True` if 200.

### Error handling

- Auth failure → raise `TCMConnectionError("Xray authentication failed: {status}")`
- Non-2xx on search → raise `TCMConnectionError`

---

## 5. Builtin TCM Connector

Reads from `StorageRepository` — serves as the "TCM" when no external system is configured.

```python
class BuiltinTCMConnector(TCMConnector):
    def __init__(self, repo: StorageRepository): ...
    def fetch_all_test_cases(self) -> list[TestCase]:
        return self.repo.get_all_test_cases()
    def health_check(self) -> bool:
        return True
```

---

## 6. CLI Integration

### `tw migrate --source testrail [--dry-run]`

1. Load config → validate `source` matches `config.tcm.provider` (error if mismatch)
2. `connector.health_check()` → abort with clear message if fails
3. `connector.fetch_all_test_cases()`
4. **Dry-run:** print Rich table (id, title, tcm_id, is_automated), exit 0
5. **Non-dry-run:**
   - `repo.upsert_test_case(tc)` for each
   - Write `.feature` file: `{features_dir or "features"}/{sanitised_title}.feature`
   - Feature file contains `tc.gherkin`
   - Print Rich progress + final summary (N imported, M already existed, K errors)
   - Errors are collected and reported at end — partial success is allowed

### `tw sync --tcm testrail`

1. Load config → validate `--tcm` matches `config.tcm.provider`
2. `connector.health_check()` → abort if fails
3. `connector.fetch_all_test_cases()`
4. `repo.upsert_test_case(tc)` for each (no file writing)
5. Print summary: new cases added, existing updated

### Feature file naming

```python
def _safe_filename(title: str) -> str:
    return re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_").lower()[:80]
```

Path: `{config.features_dir or "features"}/{_safe_filename(tc.title)}.feature`

---

## 7. Exceptions

Add to `testweavex/core/exceptions.py`:

```python
class TCMConnectionError(TestWeaveXError):
    """Raised when a TCM connector cannot reach or authenticate with the external TCM."""
```

---

## 8. Config YAML (reference)

```yaml
tcm:
  provider: testrail   # testrail | xray | none

  testrail:
    url: https://company.testrail.io
    username: ${TESTRAIL_USER}
    api_key: ${TESTRAIL_KEY}
    project_id: 12
    suite_id: 45        # optional — omit to fetch all suites

  xray:
    jira_url: https://company.atlassian.net
    client_id: ${XRAY_CLIENT_ID}
    client_secret: ${XRAY_SECRET}
    project_key: QA
```

---

## 9. Out of Scope (V1)

- Pushing results back to TestRail/Xray
- Webhook-based real-time sync
- CSV import (`tw import`)
- Token caching for Xray
- TestRail attachment/screenshot sync
