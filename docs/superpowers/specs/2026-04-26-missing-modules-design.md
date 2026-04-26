# TestWeaveX — Missing Modules Design

**Date:** 2026-04-26
**Status:** Approved
**Scope:** Five missing V1 modules: `storage/server.py`, `reporters/`, `llm/ollama.py`, `llm/azure.py`, `web/api/generate.py`

---

## 1. `storage/server.py` — ServerRepository

### Purpose
HTTP client implementation of `StorageRepository`. Used when `--results-server` is configured, replacing `SQLiteRepository` as the storage backend.

### Contract
- Implements every method of `StorageRepository` ABC
- Uses `httpx.Client` (synchronous) with `Authorization: Bearer <token>` header
- URL convention: each method maps to a REST endpoint (e.g. `POST /runs`, `POST /results`, `GET /gaps`)
- Raises `StorageError` on any non-2xx response
- No local caching — every call is a live HTTP round-trip
- Timeout from `httpx` defaults (connect=5s, read=30s)

### Endpoint mapping

| Method | HTTP |
|--------|------|
| `start_run(...)` | `POST /runs` |
| `end_run(run_id)` | `PATCH /runs/{run_id}` |
| `get_run(run_id)` | `GET /runs/{run_id}` |
| `list_runs(limit)` | `GET /runs?limit=N` |
| `save_result(r)` | `POST /results` |
| `get_results_for_run(run_id)` | `GET /runs/{run_id}/results` |
| `upsert_test_case(tc)` | `PUT /test-cases/{id}` |
| `get_test_case(id)` | `GET /test-cases/{id}` |
| `get_all_test_cases()` | `GET /test-cases` |
| `get_never_run_test_cases()` | `GET /test-cases?filter=never_run` |
| `get_always_failing_test_cases()` | `GET /test-cases?filter=always_failing` |
| `save_gaps(gaps)` | `POST /gaps/batch` |
| `get_gaps(limit, status)` | `GET /gaps?limit=N&status=S` |
| `mark_uncollected_as_gaps(ids)` | `POST /gaps/mark-uncollected` |
| `get_coverage_percentage()` | `GET /coverage` → `{"percentage": float}` |
| `get_coverage_trend(weeks)` | `GET /coverage/trend?weeks=N` |
| `get_flaky_tests(min_runs)` | `GET /test-cases?filter=flaky&min_runs=N` |
| `get_scoring_signals(tc_id)` | `GET /test-cases/{id}/signals` |

### Plugin wiring
`plugin.py` `_build_repo()` removes the `NotImplementedError`:
```python
if server_url:
    from testweavex.storage.server import ServerRepository
    token = config.getoption("--token", default=None)
    return ServerRepository(server_url, token)
```

---

## 2. `reporters/` — Reporter Layer

### Purpose
Formalises the inline `_StorageSubscriber` and `_ConsoleSubscriber` in `plugin.py` into a proper module. Adds `ServerReporter` for real-time event push.

### Components

**`reporters/base.py`**
```python
class BaseReporter(ABC):
    @abstractmethod
    def register(self, bus: EventBus) -> None: ...
```

**`reporters/console.py` — `ConsoleReporter(BaseReporter)`**
Moves `_ConsoleSubscriber` from `plugin.py` here unchanged. Subscribes to `session_finished` and `gap_analysis_complete`. Prints Rich tables to terminal.

**`reporters/sqlite.py` — `SQLiteReporter(BaseReporter)`**
Moves `_StorageSubscriber` from `plugin.py` here. Takes a `StorageRepository` at construction. Subscribes to `test_finished` and `session_finished`. Calls `repo.save_result()` and `repo.end_run()`.

**`reporters/server.py` — `ServerReporter(BaseReporter)`**
New. Takes `server_url: str` and `token: str | None`. Subscribes to `test_finished` and `session_finished`. On each event, fires a `POST /events` to the result server with the event payload as JSON. Uses `httpx`, best-effort — failures are logged to stderr, never crash the test run.

### Plugin wiring
`plugin.py` replaces inline classes with reporter imports:
```python
from testweavex.reporters.console import ConsoleReporter
from testweavex.reporters.sqlite import SQLiteReporter

reporters = [ConsoleReporter(), SQLiteReporter(repo)]
if server_url:
    from testweavex.reporters.server import ServerReporter
    reporters.append(ServerReporter(server_url, token))
for r in reporters:
    r.register(bus)
```
The `_StorageSubscriber` and `_ConsoleSubscriber` class definitions are deleted from `plugin.py`.

---

## 3. `llm/ollama.py` — OllamaAdapter

### Purpose
`LLMAdapter` implementation for Ollama (self-hosted). Follows the same structure as `AnthropicAdapter`.

### Design
- Uses the `openai` SDK with `base_url` set to Ollama's OpenAI-compatible endpoint
- Default base URL: `http://localhost:11434/v1`
- `LLMConfig.base_url` overrides the default
- API key: sends `"ollama"` as a placeholder (Ollama ignores it)
- Model: `LLMConfig.model` (e.g. `llama3`, `mistral`, `phi-3`)
- Retry loop, JSON parsing, `LLMOutputError` — identical pattern to `OpenAIAdapter`
- `health_check()`: sends a minimal completion request; returns `False` on any exception

### `get_llm_adapter` update (`llm/base.py`)
```python
if provider == "ollama":
    from testweavex.llm.ollama import OllamaAdapter
    return OllamaAdapter(config.llm)
```

---

## 4. `llm/azure.py` — AzureOpenAIAdapter

### Purpose
`LLMAdapter` implementation for Azure OpenAI. Follows the same structure as `OpenAIAdapter`.

### Design
- Uses `openai.AzureOpenAI` client
- Requires three fields from `LLMConfig`: `azure_endpoint`, `api_version`, `deployment_name`
- Raises `ConfigError` at construction if any of the three are missing or empty
- `deployment_name` is used as the `model` parameter in API calls (Azure convention)
- Retry loop, JSON parsing, `LLMOutputError` — identical pattern to `OpenAIAdapter`
- `health_check()`: minimal completion; returns `False` on any exception

### `get_llm_adapter` update (`llm/base.py`)
```python
if provider == "azure":
    from testweavex.llm.azure import AzureOpenAIAdapter
    return AzureOpenAIAdapter(config.llm)
```

Error message for unknown provider updated to include all four:
```
"Unsupported LLM provider: '...'. Choose: openai, anthropic, ollama, azure"
```

---

## 5. `web/api/generate.py` — Generate Route

### Purpose
Synchronous LLM test generation endpoint for the Web UI.

### API

**`POST /api/generate`**

Request body:
```json
{
  "feature_description": "User login with SSO",
  "skill": "functional/smoke",
  "n_suggestions": 5
}
```

Response (`200 OK`): `GenerationResponse` serialised as JSON
```json
{
  "scenarios": [...],
  "skill_used": "functional/smoke",
  "llm_model": "claude-sonnet-4-6",
  "tokens_used": 1234,
  "generation_time_ms": 4200
}
```

Error responses:
- `503` — LLM not configured or `health_check()` fails
- `422` — `LLMOutputError` after exhausted retries (includes error message)

### Implementation
- Instantiates `get_llm_adapter(config)` per-request (stateless)
- Builds a `GenerationRequest` from the request body
- Calls `adapter.generate_tests(request)`
- Returns `response.model_dump(mode="json")`

### Gap route wiring
`gaps.py` `POST /api/gaps/{gap_id}/generate` stub is updated to call the same generation path:
1. Load the gap from repo
2. Load the associated test case
3. Call `adapter.suggest_gap_automation(test_case)`
4. Return the `GenerationResponse`

### `web/app.py` update
```python
from testweavex.web.api.generate import router as generate_router
app.include_router(generate_router, prefix="/api")
```

---

## Files Changed Summary

| File | Change |
|------|--------|
| `testweavex/storage/server.py` | New — `ServerRepository` |
| `testweavex/reporters/__init__.py` | New |
| `testweavex/reporters/base.py` | New — `BaseReporter` ABC |
| `testweavex/reporters/console.py` | New — `ConsoleReporter` (moved from plugin) |
| `testweavex/reporters/sqlite.py` | New — `SQLiteReporter` (moved from plugin) |
| `testweavex/reporters/server.py` | New — `ServerReporter` |
| `testweavex/llm/ollama.py` | New — `OllamaAdapter` |
| `testweavex/llm/azure.py` | New — `AzureOpenAIAdapter` |
| `testweavex/llm/base.py` | Update — add ollama/azure cases, update error message |
| `testweavex/web/api/generate.py` | New — `POST /api/generate` |
| `testweavex/web/api/gaps.py` | Update — wire gap generate stub |
| `testweavex/web/app.py` | Update — include generate router |
| `testweavex/execution/plugin.py` | Update — use reporters, remove inline classes, fix `_build_repo` |
