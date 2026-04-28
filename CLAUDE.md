# TestWeaveX — Claude CLI Context

> **One-stop reference for AI-assisted development of TestWeaveX.**
> Claude Code: read this file first. Full specs are in `docs/PRD.md` and `docs/ARCHITECTURE.md`.

---

## What Is TestWeaveX?

TestWeaveX is an **open-source, unified test management and execution platform** built as a pytest plugin. It brings together:

- **Built-in TCM** (Git-native test case management, coverage maps, gap analysis)
- **LLM-powered test generation** (bring your own model — OpenAI, Anthropic, Ollama, Azure)
- **pytest-native execution** (extends pytest, never replaces it — `tw` = `pytest` + TestWeaveX flags)
- **Web UI** (FastAPI + React, bundled into the Python package, started with `tw serve`)

**GitHub org:** `github.com/testweavex`
**PyPI package:** `testweavex`
**CLI entry point:** `tw` (maps to `testweavex.cli:main`)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Test runner | pytest 7+, pytest-bdd 7+, pytest-playwright 0.4+ |
| Parallelism | pytest-xdist 3+ |
| Data models | Pydantic v2 |
| CLI | Typer 0.9+ |
| Storage | SQLAlchemy 2+ / SQLite (default) |
| HTTP client | httpx 0.24+ |
| Web backend | FastAPI + Uvicorn |
| Web frontend | React 18 + Vite (bundled as static files in package) |
| Streaming | Server-Sent Events (SSE) |
| Config | PyYAML 6+ |
| LLM SDKs | openai, anthropic, ollama (optional, provider-agnostic) |
| Containers | Docker + docker-compose (result server only) |

---

## Project Structure

```
testweavex/
├── core/
│   ├── models.py          # Pydantic data models — shared contract
│   ├── config.py          # testweavex.config.yaml loader
│   └── exceptions.py      # Custom exception hierarchy
├── llm/
│   ├── base.py            # Abstract LLMAdapter interface
│   ├── openai.py          # OpenAI implementation
│   ├── anthropic.py       # Anthropic implementation
│   ├── ollama.py          # Ollama (self-hosted)
│   └── azure.py           # Azure OpenAI
├── skills/
│   ├── loader.py          # YAML skill file loader + validator
│   └── builtin/           # 10 built-in skill YAML files
│       ├── functional/    # smoke, sanity, happy_path, edge_cases,
│       │                  # data_driven, integration, system, e2e
│       └── nonfunctional/ # accessibility, cross_browser
├── generation/
│   ├── engine.py          # Orchestrates skill + LLM + review gate
│   ├── gherkin.py         # Gherkin formatter + .feature file writer
│   └── codegen.py         # Step definition generator + reuse logic
├── execution/
│   └── plugin.py          # pytest plugin — all hook implementations
├── storage/
│   ├── base.py            # Abstract StorageRepository interface
│   ├── sqlite.py          # Local SQLite (default, zero-config)
│   ├── server.py          # HTTP client to remote result server
│   └── models.py          # SQLAlchemy ORM models
├── reporters/
│   ├── base.py            # Abstract BaseReporter interface
│   ├── console.py         # Rich terminal output
│   ├── sqlite.py          # Persists results via StorageRepository
│   └── server.py          # Real-time push to result server
├── gap/
│   ├── detector.py        # Three-strategy gap detection
│   ├── scorer.py          # Six-signal priority scoring algorithm
│   └── analyzer.py        # Orchestrates detection + scoring + generation
├── tcm/
│   ├── base.py            # Abstract TCMConnector interface
│   ├── builtin.py         # Built-in TCM (reads from StorageRepository)
│   ├── testrail.py        # TestRail connector
│   └── xray.py            # Xray (Jira) connector
├── cli.py                 # Typer CLI — tw command
└── web/
    ├── app.py             # FastAPI app factory
    ├── api/               # Route handlers (dashboard, test_cases,
    │                      # runs, gaps, generate, settings, events)
    └── static/            # Built React app (bundled into package)
```

---

## Key Commands

```bash
# Install (not yet on PyPI — install from GitHub)
pip install git+https://github.com/testweavex/testweavex.git

# Run tests (all pytest flags work)
tw                                    # Run all tests
tw tests/auth/login.feature           # Run specific feature
tw -k smoke                           # Filter by tag/keyword
tw -v -x                              # Verbose, stop on first fail
tw -n 4                               # Parallel (pytest-xdist)

# With TestWeaveX extras
tw --results-server https://tcm.company.com --token $TOKEN
tw --gaps --sync-tcm testrail
tw --generate --skill functional/smoke

# Generate tests
tw generate --feature "User login with SSO" --skill functional/smoke

# Gap analysis
tw gaps --limit 20 --min-score 0.6

# Web UI
tw serve                              # http://localhost:8080

# Project setup
tw init --llm-provider anthropic
tw migrate --source testrail --dry-run
```

---

## Configuration

```yaml
# testweavex.config.yaml  (project root)
llm:
  provider: anthropic          # openai | anthropic | ollama | azure
  model: claude-sonnet-4-6
  api_key: ${ANTHROPIC_API_KEY}
  temperature: 0.3
  max_retries: 3
  timeout_seconds: 30

results_server: ${TESTWEAVEX_SERVER}   # Optional — enables team mode

tcm:
  provider: none               # testrail | xray | none

gap_analysis:
  scoring_weights:
    priority:  0.30
    test_type: 0.25
    defects:   0.20
    frequency: 0.15
    staleness: 0.10
  match_threshold: 0.65
  top_gaps_default: 10
```

**Priority chain for result server URL:**
1. `--results-server` CLI flag
2. `TESTWEAVEX_SERVER` env var
3. `results_server` in `testweavex.config.yaml`

---

## Core Data Models (Pydantic v2)

| Model | Key Fields |
|-------|-----------|
| `TestCase` | `id` (stable hash), `title`, `gherkin`, `test_type`, `status`, `is_automated`, `tags`, `priority` |
| `Feature` | `id`, `name`, `acceptance_criteria`, `test_case_ids`, `source_file` |
| `TestRun` | `id` (UUID), `suite`, `environment`, `browser`, `started_at`, `result_ids` |
| `TestResult` | `id`, `run_id`, `test_case_id`, `status`, `duration_ms`, `error_message` |
| `Gap` | `id`, `test_case_id`, `priority_score` (0–1), `gap_reason`, `suggested_gherkin`, `status` |

**Stable ID generation — never change this algorithm:**
```python
import hashlib

def generate_stable_id(*parts: str) -> str:
    key = '|'.join(parts).encode('utf-8')
    return hashlib.sha256(key).hexdigest()  # full 64 chars — never truncate

# test_case_id = generate_stable_id(feature_path, scenario_name)
# feature_id   = generate_stable_id(feature_path)
```

---

## LLM Adapter Contract

All LLM calls go through `LLMAdapter`. Never import provider SDKs outside of `testweavex/llm/`.

```python
class LLMAdapter(ABC):
    def generate_tests(self, request: GenerationRequest) -> GenerationResponse: ...
    def generate_step_definitions(self, scenarios, existing_steps) -> StepDefinitionResponse: ...
    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse: ...
    def health_check(self) -> bool: ...
```

**Every adapter must:**
- Return validated Pydantic objects (never raw LLM text)
- Retry up to `max_retries` on JSON validation failures
- Raise `LLMOutputError` after exhausting retries

---

## Pytest Plugin Entry Point

```toml
# pyproject.toml
[project.entry-points.'pytest11']
testweavex = 'testweavex.execution.plugin'

[project.scripts]
tw = 'testweavex.cli:main'
```

**Plugin hooks implemented:** `pytest_addoption`, `pytest_configure`, `pytest_collection_modifyitems`, `pytest_runtest_logreport`, `pytest_sessionfinish`

---

## Storage Factory Pattern

```python
def get_repository(config) -> StorageRepository:
    server_url = (
        config.getoption('--results-server', default=None)
        or os.getenv('TESTWEAVEX_SERVER')
        or load_config().get('results_server')
    )
    if server_url:
        token = config.getoption('--token') or os.getenv('TESTWEAVEX_TOKEN')
        return ServerRepository(server_url, token)
    return SQLiteRepository()   # Default — zero config
```

SQLite database location: `.testweavex/results.db` in project root. Add `.testweavex/` to `.gitignore`.

---

## Gap Scoring Weights

```python
WEIGHTS = {
    'priority':  0.30,   # P1 tests must be automated first
    'test_type': 0.25,   # Smoke/E2E gaps hurt most
    'defects':   0.20,   # Tests linked to bugs are high value
    'frequency': 0.15,   # Frequently-run tests benefit most
    'staleness': 0.10,   # Stale = higher regression risk
}
```

Test type priority scores (for `test_type` signal):
`smoke=1.00`, `e2e=0.90`, `happy_path=0.85`, `integration=0.80`,
`system=0.75`, `sanity=0.70`, `data_driven=0.60`, `edge_case=0.50`, `accessibility=0.40`

---

## Non-Negotiable Design Rules

1. **No LLM output reaches the filesystem without engineer approval.** The generation engine always presents suggestions for review before writing any file.
2. **Stable IDs are immutable.** `generate_stable_id(feature_path, scenario_name)` — never change the algorithm. Changing it breaks sync for all existing data.
3. **StorageRepository is the only persistence interface.** Components must never query SQLite or make HTTP calls directly.
4. **LLMAdapter is the only LLM interface.** Never call `openai`, `anthropic`, or `ollama` outside `testweavex/llm/`.
5. **tw is pytest.** Every `pytest` flag works with `tw`. Unknown flags pass through to pytest unchanged.
6. **Built-in TCM is first-class.** It is not a fallback. Do not treat it as secondary to external TCM connectors.

---

## Development Build Order

| Phase | Weeks | Deliverable |
|-------|-------|-------------|
| 1 — Foundation | 1–2 | `core/models.py` + `storage/sqlite.py` |
| 2 — LLM | 3–4 | `llm/base.py` + `llm/openai.py` + `skills/loader.py` |
| 3 — Generation | 5–6 | `generation/engine.py` + `generation/gherkin.py` |
| 4 — Execution | 7–8 | `execution/plugin.py` + `cli.py` |
| 5 — Gap Analysis | 9–10 | `gap/detector.py` + `gap/scorer.py` |
| 6 — Web UI | 11–14 | `web/app.py` + React frontend |
| 7 — TCM Connectors | 15–16 | `tcm/testrail.py` + `tcm/xray.py` |
| 8 — Polish & OSS | 17–18 | Docs, README, contribution guide |

---

## Further Reading

- [`docs/PRD.md`](docs/PRD.md) — Full Product Requirements Document (15 sections)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — Full Technical Architecture Specification (16 sections)
- [`docs/UI_DESIGN.md`](docs/UI_DESIGN.md) — Web UI design system and screen specifications
