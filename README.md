# TestWeaveX

> **Unified test management and execution — powered by any LLM. The AI suggests. You decide.**

[![PyPI](https://img.shields.io/pypi/v/testweavex)](https://pypi.org/project/testweavex)
[![Python](https://img.shields.io/pypi/pyversions/testweavex)](https://pypi.org/project/testweavex)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://github.com/testwavex/testweavex/actions/workflows/ci.yml/badge.svg)](https://github.com/testwavex/testweavex/actions)

---

## Mission

Most teams have their test cases in one tool, their automation in another, and their results in a third. Gap analysis is a manual spreadsheet exercise done once a quarter — if at all.

**TestWeaveX closes that loop.** It is a Git-native pytest plugin that brings test case management (TCM), LLM-powered test generation, execution tracking, and automated gap analysis into a single cohesive platform. Every test run automatically maps what is automated against what should be, surfaces the highest-priority gaps, and — with your approval — generates the missing automation.

No lock-in. Bring your own LLM (OpenAI, Anthropic, Ollama, Azure). Keep using pytest exactly as you do today.

---

## Why TestWeaveX?

| Problem | TestWeaveX Solution |
|---------|-------------------|
| Test cases scattered across TestRail, Jira, spreadsheets | Built-in Git-native TCM — your repo is the source of truth |
| No visibility into automation gaps | Automated gap detection on every `tw` run |
| LLM tools that write code directly to disk | Review-gated generation — LLM suggests, engineer approves |
| Switching test runners breaks workflows | `tw` is `pytest` — every flag, plugin, and fixture works unchanged |
| Results siloed per-developer | Optional team result server (`docker-compose up`) |

---

## Features

- **pytest-native** — `tw` is a thin wrapper; all pytest flags, plugins, and fixtures work unchanged
- **Built-in TCM** — Git-native test case management with stable deterministic IDs
- **LLM test generation** — 10 built-in skill files (smoke, E2E, accessibility, and more); write your own in YAML
- **Gap analysis** — six-signal priority scoring surfaces the highest-value automation gaps first
- **Review-gated** — no LLM output reaches your repo without engineer approval
- **Provider-agnostic** — OpenAI, Anthropic, Ollama (local), Azure OpenAI
- **Team mode** — optional self-hosted result server for shared dashboards and history
- **Web UI** — FastAPI + React dashboard, started with `tw serve`
- **TCM connectors** — TestRail and Xray (Jira) sync (Phase 7)

---

## Getting Started

### Install

```bash
pip install git+https://github.com/testweavex/testweavex.git
```

### Initialise

```bash
tw init --llm-provider anthropic
```

Creates `testweavex.config.yaml` in your project root and populates `testweavex/skills/` with the 10 built-in skill files.

### Run your tests

```bash
tw                              # same as pytest — all flags work
tw tests/login.feature          # run a specific feature
tw -k smoke -n 4                # filter by tag, run in parallel
tw -v -x                        # verbose, stop on first failure
```

Results are stored automatically in `.testweavex/results.db`. No configuration needed.

### View gap report

```bash
tw gaps --limit 20
```

Compares your TCM against your automation suite. Shows unautomated tests ranked by priority score. Add `--generate` to produce automation candidates for review.

### Generate tests

```bash
tw generate --feature "User login with SSO" --skill functional/smoke
```

### Start the Web UI

```bash
tw serve                        # http://localhost:8080
```

---

## Configuration

```yaml
# testweavex.config.yaml
llm:
  provider: anthropic            # openai | anthropic | ollama | azure
  model: claude-sonnet-4-6
  api_key: ${ANTHROPIC_API_KEY}  # ${ENV_VAR} interpolation supported
  temperature: 0.3
  max_retries: 3
  timeout_seconds: 30

results_server: ${TESTWEAVEX_SERVER}   # optional — enables team mode

tcm:
  provider: none                 # testrail | xray | none

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

**Result server URL priority chain:** `--results-server` flag → `TESTWEAVEX_SERVER` env var → `results_server` in config file.

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `tw [paths]` | Run tests (wraps pytest — all pytest flags work) |
| `tw init` | Initialise TestWeaveX in a project |
| `tw generate` | Generate tests from a feature description |
| `tw gaps` | Run gap analysis, show prioritised report |
| `tw import` | Import test cases from TestRail, Xray, or CSV |
| `tw status` | Show coverage map and summary |
| `tw history` | Show execution history |
| `tw serve` | Start local Web UI (port 8080) |
| `tw migrate` | Migrate from external TCM |
| `tw sync` | Push results to external TCM |

---

## Architecture

TestWeaveX is a **pytest plugin** with a thin Typer CLI. All functionality flows through three pipelines:

```
Generation:   Feature description + skill file  →  Approved Gherkin + step definitions
Execution:    Feature files + pytest config      →  Test results in storage + TCM updated
Gap Analysis: TCM test cases + automation suite  →  Ranked gap list + optional generation
```

### Component Map

| Module | Responsibility | Phase |
|--------|---------------|-------|
| `core/models.py` | Pydantic v2 data models — shared contract across all components | 1 |
| `core/config.py` | YAML config loader with `${ENV_VAR}` interpolation | 1 |
| `core/exceptions.py` | Exception hierarchy | 1 |
| `storage/sqlite.py` | Local SQLite persistence — zero config default | 1 |
| `storage/server.py` | HTTP client to remote result server | 1 |
| `llm/` | Provider-agnostic LLM adapter layer | 2 |
| `skills/` | YAML skill files — one per test type | 2 |
| `generation/engine.py` | Orchestrates skill + LLM + review gate | 3 |
| `generation/gherkin.py` | Gherkin formatter + `.feature` file writer | 3 |
| `execution/plugin.py` | pytest plugin hooks | 4 |
| `cli.py` | Typer CLI — `tw` entry point | 4 |
| `gap/detector.py` | Three-strategy gap detection | 5 |
| `gap/scorer.py` | Six-signal priority scoring algorithm | 5 |
| `web/app.py` | FastAPI + React dashboard | 6 |
| `tcm/testrail.py` | TestRail connector | 7 |
| `tcm/xray.py` | Xray (Jira) connector | 7 |

### Storage Factory

```python
def get_repository(config) -> StorageRepository:
    server_url = (
        config.getoption('--results-server')
        or os.getenv('TESTWEAVEX_SERVER')
        or load_config().get('results_server')
    )
    if server_url:
        return ServerRepository(server_url, token)
    return SQLiteRepository()   # default — zero config
```

### Stable ID Algorithm

Test case IDs are deterministic SHA-256 hashes — stable across machines, CI runs, and environments. **This algorithm is frozen and must never change after first deployment.**

```python
import hashlib

def generate_stable_id(*parts: str) -> str:
    key = "|".join(parts).encode("utf-8")
    return hashlib.sha256(key).hexdigest()  # full 64 chars

# test_case_id = generate_stable_id(feature_path, scenario_name)
# feature_id   = generate_stable_id(feature_path)
```

### Gap Priority Scoring

Gaps are ranked 0.0–1.0. Higher = automate first.

| Signal | Weight | Rationale |
|--------|--------|-----------|
| Priority | 30% | P1 tests must be automated before P4 |
| Test Type | 25% | Smoke/E2E gaps hurt most (smoke=1.0, e2e=0.9) |
| Defect History | 20% | Tests linked to past bugs are high value |
| Execution Frequency | 15% | Frequently-run manual tests benefit most |
| Staleness | 10% | Not run recently = higher regression risk |

### Data Models

| Model | Key Fields |
|-------|-----------|
| `TestCase` | `id` (stable hash), `title`, `gherkin`, `test_type`, `status`, `is_automated`, `tags`, `priority` |
| `Feature` | `id`, `name`, `acceptance_criteria`, `test_case_ids`, `source_file` |
| `TestRun` | `id` (UUID), `suite`, `environment`, `browser`, `started_at`, `result_ids` |
| `TestResult` | `id`, `run_id`, `test_case_id`, `status`, `duration_ms`, `error_message` |
| `Gap` | `id`, `test_case_id`, `priority_score` (0–1), `gap_reason`, `suggested_gherkin`, `status` |

### LLM Adapter Contract

All LLM calls go through `LLMAdapter`. Provider SDKs are never imported outside `testweavex/llm/`.

```python
class LLMAdapter(ABC):
    def generate_tests(self, request: GenerationRequest) -> GenerationResponse: ...
    def generate_step_definitions(self, scenarios, existing_steps) -> StepDefinitionResponse: ...
    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse: ...
    def health_check(self) -> bool: ...
```

---

## Project Structure

```
testweavex/
├── core/
│   ├── models.py          # Pydantic data models
│   ├── config.py          # YAML config loader
│   └── exceptions.py      # Exception hierarchy
├── llm/
│   ├── base.py            # Abstract LLMAdapter
│   ├── openai.py          # OpenAI
│   ├── anthropic.py       # Anthropic
│   ├── ollama.py          # Ollama (self-hosted)
│   └── azure.py           # Azure OpenAI
├── skills/
│   ├── loader.py          # YAML skill loader + validator
│   └── builtin/
│       ├── functional/    # smoke, sanity, happy_path, edge_cases,
│       │                  # data_driven, integration, system, e2e
│       └── nonfunctional/ # accessibility, cross_browser
├── generation/
│   ├── engine.py          # Orchestrates skill + LLM + review gate
│   ├── gherkin.py         # Gherkin formatter + .feature writer
│   └── codegen.py         # Step definition generator
├── execution/
│   └── plugin.py          # pytest plugin hooks
├── storage/
│   ├── base.py            # Abstract StorageRepository (13 methods)
│   ├── sqlite.py          # Local SQLite (default, zero-config)
│   ├── server.py          # HTTP client to remote result server
│   └── models.py          # SQLAlchemy ORM (5 tables)
├── reporters/
│   ├── console.py         # Rich terminal output
│   ├── sqlite.py          # Persists results via StorageRepository
│   └── server.py          # Real-time push to result server
├── gap/
│   ├── detector.py        # Three-strategy gap detection
│   ├── scorer.py          # Six-signal priority scoring
│   └── analyzer.py        # Orchestrates detection + scoring + generation
├── tcm/
│   ├── builtin.py         # Built-in TCM (reads from StorageRepository)
│   ├── testrail.py        # TestRail connector
│   └── xray.py            # Xray (Jira) connector
├── cli.py                 # Typer CLI — tw command
└── web/
    ├── app.py             # FastAPI app factory
    ├── api/               # Route handlers
    └── static/            # Built React app
```

---

## Build Roadmap

| Phase | Weeks | Deliverable |
|-------|-------|-------------|
| 1 — Foundation | 1–2 | `core/models.py` + `storage/sqlite.py` ✅ |
| 2 — LLM | 3–4 | `llm/base.py` + `llm/openai.py` + `skills/loader.py` |
| 3 — Generation | 5–6 | `generation/engine.py` + `generation/gherkin.py` |
| 4 — Execution | 7–8 | `execution/plugin.py` + `cli.py` |
| 5 — Gap Analysis | 9–10 | `gap/detector.py` + `gap/scorer.py` |
| 6 — Web UI | 11–14 | `web/app.py` + React frontend |
| 7 — TCM Connectors | 15–16 | `tcm/testrail.py` + `tcm/xray.py` |
| 8 — Polish & OSS | 17–18 | Docs, README, contribution guide |

---

## Development Setup

```bash
git clone https://github.com/testwavex/testweavex
cd testweavex
pip install -e ".[dev]"
pytest tests/ -v
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Test runner | pytest 7+, pytest-bdd 7+, pytest-playwright 0.4+ |
| Parallelism | pytest-xdist 3+ |
| Data models | Pydantic v2 |
| CLI | Typer 0.9+ |
| Storage | SQLAlchemy 2+ / SQLite |
| HTTP client | httpx 0.24+ |
| Web backend | FastAPI + Uvicorn |
| Web frontend | React 18 + Vite |
| Streaming | Server-Sent Events (SSE) |
| Config | PyYAML 6+ |
| LLM SDKs | openai, anthropic, ollama (optional extras) |

### Non-Negotiable Design Rules

1. **No LLM output reaches the filesystem without engineer approval.** Generation always presents suggestions for review first.
2. **Stable IDs are immutable.** Never change `generate_stable_id` — doing so breaks sync for all existing data.
3. **`StorageRepository` is the only persistence interface.** Components never query SQLite or make HTTP calls directly.
4. **`LLMAdapter` is the only LLM interface.** Never import provider SDKs outside `testweavex/llm/`.
5. **`tw` is pytest.** Every pytest flag works. Unknown flags pass through unchanged.
6. **Built-in TCM is first-class.** It is not a fallback to external connectors — it is the primary TCM.

---

## CI/CD Example

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    tw --suite regression \
       --results-server ${{ secrets.TW_SERVER }} \
       --token ${{ secrets.TW_TOKEN }} \
       --sync-tcm testrail
```

---

## Contributing

Contributions welcome. The lowest-barrier entry point is a new **skill YAML file**:

```yaml
# testweavex/skills/custom/your-skill.yaml
name: custom/your-skill
display_name: Your Skill Name
description: What this skill generates

prompt_template: |
  You are a senior QA engineer.
  Feature: {feature_description}
  Generate {n_suggestions} test scenarios that...
  Return JSON: title, gherkin, confidence, rationale, suggested_tags

assertion_hints:
  - Verify primary outcome
tags: [custom]
priority: 3
```

Other contribution areas: LLM adapter implementations, TCM connectors, bug fixes, documentation.

See [CONTRIBUTING.md](CONTRIBUTING.md) (coming in Phase 8).

---

## Documentation

Full documentation site: **https://testwavex.github.io/testweavex/**

- [PRD](docs/PRD.md) — Full Product Requirements Document
- [Architecture](docs/ARCHITECTURE.md) — Full Technical Architecture Specification

---

## License

MIT — see [LICENSE](LICENSE).
