# TestWeaveX Phase 4+5+6 Design
# Execution Plugin · Gap Analysis · Web UI

**Date:** 2026-04-20
**Phases:** 4 (Execution + CLI), 5 (Gap Analysis), 6 (Web UI)
**Weeks:** 7–14 of 18-week build order
**Status:** Approved

---

## Context

Phases 1 (Foundation), 2 (LLM Adapters), and 3 (Generation) are complete. This spec covers the next three phases together to ensure a clean, long-term architecture. The central design decision is an **event bus** that decouples the pytest plugin, gap analysis, and web UI — enabling real-time SSE streaming to the browser without tight coupling between layers.

---

## Architecture Decision: Event Bus (Approach C)

All three phases share a single synchronous publish/subscribe event bus at `testweavex/events.py`.

### EventBus

```python
class EventBus:
    def emit(self, event: TWEvent) -> None: ...
    def subscribe(self, event_type: str, handler: Callable) -> None: ...
```

### Typed Events (Pydantic models)

| Event | Emitted by | Consumed by |
|-------|-----------|-------------|
| `RunStarted` | plugin `pytest_configure` | StorageSubscriber, ConsoleSubscriber, SSESubscriber |
| `TestCollected` | plugin `pytest_collection_modifyitems` | StorageSubscriber |
| `TestStarted` | plugin `pytest_runtest_logreport` | ConsoleSubscriber, SSESubscriber |
| `TestFinished` | plugin `pytest_runtest_logreport` | StorageSubscriber, ConsoleSubscriber, SSESubscriber |
| `SessionFinished` | plugin `pytest_sessionfinish` | GapAnalyzer, ConsoleSubscriber, SSESubscriber |
| `GapAnalysisComplete` | gap/analyzer.py | ConsoleSubscriber, SSESubscriber |

### Subscribers

| Subscriber | Responsibility |
|-----------|---------------|
| `StorageSubscriber` | Writes all events to `StorageRepository` |
| `ConsoleSubscriber` | Rich terminal output — inline in `execution/plugin.py` |
| `SSESubscriber` | Broadcasts events as JSON to connected web clients |

The plugin emits events and has no knowledge of storage, gap analysis, or web UI. Each subscriber is independently testable.

---

## Phase 4: Execution Plugin + CLI

### `execution/plugin.py`

Implements five pytest hooks:

**`pytest_addoption`**
Registers custom flags:
- `--results-server URL` — remote result server
- `--token TOKEN` — auth token for remote server
- `--suite NAME` — tag this run with a suite name
- `--environment NAME` — target environment (staging, prod, etc.)
- `--browser NAME` — browser for playwright tests
- `--gaps` — compute and display gap report after session
- `--sync-tcm PROVIDER` — sync results to external TCM (Phase 7)

**`pytest_configure`**
1. Load `testweavex.config.yaml` via existing config loader
2. Build `StorageRepository` via factory (flag → env var → config → SQLite default)
3. Create `EventBus`
4. Register `StorageSubscriber`, `ConsoleSubscriber`, optionally `SSESubscriber`
5. Create `TestRun` record, emit `RunStarted`

**`pytest_collection_modifyitems`**
For each collected item:
1. Generate stable ID: `generate_stable_id(str(item.fspath), item.nodeid)`
2. Upsert `TestCase` to storage with `is_automated=True`
3. Emit `TestCollected`

**`pytest_runtest_logreport`**
On `report.when == "call"`:
1. Map pytest outcome to `TestStatus` enum
2. Capture duration, error message, traceback
3. Emit `TestStarted` then `TestFinished`

**`pytest_sessionfinish`**
1. Call `StorageRepository.mark_uncollected_as_gaps(run_id)`
2. Emit `SessionFinished`
3. If `--gaps` flag: gap analyzer runs (via event subscription), then `ConsoleSubscriber` renders gap table

**ConsoleSubscriber (inline in plugin.py)**
Uses Rich to render:
- Live progress bar during run
- Final summary table: pass/fail/skip counts, coverage %, total duration
- Gap table (top 10 by priority score) when `--gaps` is active

**Stable ID algorithm — frozen, never change:**
```python
generate_stable_id(feature_path, scenario_name)
# → hashlib.sha256("|".join(parts).encode()).hexdigest()  # full 64 chars
```

---

### `testweavex/cli.py`

Typer app. Root command `tw` with no subcommand delegates directly to `pytest.main()`, passing all arguments through unchanged. This preserves "tw is pytest" — every pytest flag works.

**Fully implemented commands:**

| Command | Behaviour |
|---------|-----------|
| `tw [paths] [pytest-flags]` | `pytest.main(sys.argv[1:])` — plugin auto-loads via `pytest11` entry point |
| `tw init --llm-provider {anthropic\|openai\|ollama\|azure}` | Writes `testweavex.config.yaml` to project root with provider defaults |
| `tw status [--format table\|json\|html]` | Queries storage, prints coverage % by feature and test type |
| `tw history [--last-n 10]` | Lists last N runs with pass/fail/skip/duration |

**Stubbed commands (exit 1 with clear message):**

| Command | Waiting on |
|---------|-----------|
| `tw gaps [--limit N] [--min-score F] [--generate]` | Phase 5 — unblocked by this spec |
| `tw generate --feature "..." --skill SKILL` | Phase 5 — unblocked by this spec |
| `tw serve [--port 8080]` | Phase 6 — unblocked by this spec |
| `tw migrate --source {testrail\|xray} [--dry-run]` | Phase 7 TCM connectors |
| `tw sync --tcm {testrail\|xray}` | Phase 7 TCM connectors |

Stub message: `"tw {command} requires Phase N — not yet available."`

---

## Phase 5: Gap Analysis

### `gap/detector.py`

Three detection strategies, all reading from `StorageRepository`:

1. **Uncollected** — `TestCase` records with `is_automated=False` or never seen in any run
2. **Never run** — test cases with no `TestResult` records in the last N sessions
3. **Always failing** — test cases that have never recorded a `PASS` status

Returns `list[Gap]` with `gap_reason` set to the detection strategy name.

### `gap/scorer.py`

Applies six-signal scoring using `ScoringSignals` from storage:

```python
WEIGHTS = {
    'priority':  0.30,
    'test_type': 0.25,
    'defects':   0.20,
    'frequency': 0.15,
    'staleness': 0.10,
}
```

Test type scores:
`smoke=1.00, e2e=0.90, happy_path=0.85, integration=0.80, system=0.75,
sanity=0.70, data_driven=0.60, edge_case=0.50, accessibility=0.40`

Returns gaps sorted by `priority_score` descending. Score is clamped to `[0.0, 1.0]`.

### `gap/analyzer.py`

Orchestrates detection + scoring:
1. Subscribes to `SessionFinished` on the `EventBus`
2. Calls `detector.find_gaps()` → `scorer.score_gaps()`
3. Saves ranked gaps via `StorageRepository.save_gaps()`
4. Emits `GapAnalysisComplete` with top N gaps

`tw gaps` and `tw generate` become fully implemented once this module exists — they call the analyzer directly (outside of a pytest session) against the stored data.

---

## Phase 6: Web UI

### `web/app.py`

FastAPI app factory:

```python
def create_app(config) -> FastAPI: ...
```

Mounts `web/static/` for static files. Serves `index.html` (the `testweavex_ui_design.html` design system) at `/`.

### API Routes (`web/api/`)

| Route | Method | Description |
|-------|--------|-------------|
| `/api/dashboard` | GET | Coverage %, run summary, gap count |
| `/api/runs` | GET | Paginated test run history |
| `/api/runs/{run_id}` | GET | Single run + all results |
| `/api/test-cases` | GET | All test cases, filterable by type/status/tag |
| `/api/gaps` | GET | Ranked gaps list |
| `/api/gaps/{gap_id}/generate` | POST | Trigger LLM generation for a gap |
| `/api/settings` | GET | Read current config |
| `/api/settings` | PUT | Write updated config to `testweavex.config.yaml` |
| `/api/events` | GET | SSE stream — all EventBus events as JSON |

### SSE Stream

`SSESubscriber` holds a queue of connected clients. On each `EventBus.emit()`, it serialises the event to JSON and pushes it to all connected SSE clients. The HTML frontend connects to `/api/events` on load and applies live updates — no polling.

### Static Frontend

`testweavex_ui_design.html` moves to `web/static/index.html`. No Node toolchain, no build step. Vanilla JS in the file consumes `/api/events` and `/api/*` endpoints. Future React migration only requires swapping this file — the API contract is unchanged.

`tw serve [--port 8080]` starts Uvicorn with `create_app(config)` on the specified port (default 8080).

---

## File Deliverables

```
testweavex/
├── events.py                    # EventBus + all TWEvent types (NEW)
├── execution/
│   └── plugin.py                # Full pytest hook implementations (REPLACE STUB)
├── cli.py                       # Typer CLI — tw command (NEW)
├── gap/
│   ├── __init__.py              # (NEW)
│   ├── detector.py              # Three-strategy gap detection (NEW)
│   ├── scorer.py                # Six-signal priority scoring (NEW)
│   └── analyzer.py              # Orchestrates detection + scoring (NEW)
└── web/
    ├── __init__.py              # (NEW)
    ├── app.py                   # FastAPI app factory (NEW)
    ├── api/
    │   ├── __init__.py          # (NEW)
    │   ├── dashboard.py         # /api/dashboard (NEW)
    │   ├── runs.py              # /api/runs (NEW)
    │   ├── test_cases.py        # /api/test-cases (NEW)
    │   ├── gaps.py              # /api/gaps (NEW)
    │   ├── settings.py          # /api/settings (NEW)
    │   └── events.py            # /api/events SSE (NEW)
    └── static/
        └── index.html           # testweavex_ui_design.html (MOVED)

tests/
├── test_plugin.py               # pytester fixture — full session simulation (NEW)
├── test_cli.py                  # CliRunner — all commands + stubs (NEW)
├── test_events.py               # EventBus pub/sub isolation (NEW)
├── test_gap_detector.py         # Three detection strategies (NEW)
├── test_gap_scorer.py           # Six-signal scoring math (NEW)
├── test_gap_analyzer.py         # End-to-end: SessionFinished → gaps saved (NEW)
├── test_web_api.py              # FastAPI TestClient — all routes (NEW)
└── test_sse.py                  # SSE stream receives events (NEW)
```

---

## Non-Negotiable Constraints (inherited from CLAUDE.md)

1. **`tw` is pytest.** Every pytest flag passes through unchanged.
2. **No LLM output reaches the filesystem without engineer approval.** Generation engine always presents review gate first.
3. **`StorageRepository` is the only persistence interface.** No direct SQLite or HTTP calls outside `storage/`.
4. **`LLMAdapter` is the only LLM interface.** Gap generation calls `generation/engine.py`, never provider SDKs directly.
5. **Stable ID algorithm is frozen.** `hashlib.sha256("|".join(parts).encode()).hexdigest()` — 64 chars, never truncate.
6. **All 40 existing tests must continue passing.** Phase 4+5+6 adds no breaking changes to Phase 1 contracts.

---

## Success Criteria

- `tw` runs all pytest tests with no flag conflicts
- `tw init` produces a valid `testweavex.config.yaml`
- `tw status` and `tw history` display accurate data from SQLite
- Plugin captures pass/fail/skip/duration for every test item
- Gap detector finds uncollected, never-run, and always-failing tests
- Gap scorer produces scores in `[0.0, 1.0]`, sorted descending
- `tw serve` starts the web UI; browser connects and receives live SSE updates
- `testweavex_ui_design.html` renders correctly when served at `/`
- All 8 new test files pass; all 40 existing tests continue to pass
