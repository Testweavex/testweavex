# TestWeaveX — Technical Architecture Specification

**Version:** 1.0 — Draft
**Date:** April 2026
**Status:** For Engineering Review
**Author:** Pankaj S
**GitHub Org:** github.com/testweavex

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Core Data Models](#2-core-data-models)
3. [LLM Adapter Layer](#3-llm-adapter-layer)
4. [Skill Files Framework](#4-skill-files-framework)
5. [Generation Engine](#5-generation-engine)
6. [pytest Plugin Architecture](#6-pytest-plugin-architecture)
7. [CLI — The tw Command](#7-cli--the-tw-command)
8. [Storage Layer](#8-storage-layer)
9. [Reporter Pattern](#9-reporter-pattern)
10. [Gap Analyzer](#10-gap-analyzer)
11. [Web UI](#11-web-ui)
12. [External TCM Connectors](#12-external-tcm-connectors)
13. [Self-Hosted Result Server](#13-self-hosted-result-server)
14. [Dependency Map](#14-dependency-map)
15. [Build & Release Pipeline](#15-build--release-pipeline)
16. [Development Build Order](#16-development-build-order)

---

## 1. Architecture Overview

TestWeaveX is built as a pytest plugin with a thin CLI wrapper, a Git-native test case management system, an LLM generation engine, and a FastAPI-powered Web UI. All components share a common storage interface and communicate through well-defined Python APIs.

### 1.1 Architecture Philosophy

- **pytest-native:** TestWeaveX extends pytest, not replaces it. Existing pytest and pytest-bdd users adopt TestWeaveX with a single `pip install`.
- **Plugin-first:** Every integration point — LLM providers, TCM connectors, storage backends, reporters — is an abstract interface with swappable concrete implementations.
- **Human in loop:** No LLM output reaches the filesystem without explicit engineer approval. Every generation step has a mandatory review gate.
- **Zero-config start:** Local SQLite storage requires no setup. A single CLI flag routes results to a team server. Complexity is opt-in, not default.
- **Git-native TCM:** Test cases live as Gherkin feature files in the repository. The TCM is a view over those files, never a separate source of truth.

### 1.2 Tech Stack

| Layer | Technology / Library |
|-------|---------------------|
| Core language | Python 3.11+ |
| Test execution | pytest 7+, pytest-bdd 7+, pytest-playwright 0.4+ |
| Parallel execution | pytest-xdist 3+ |
| Data models | Pydantic v2 |
| CLI | Typer 0.9+ |
| Local storage | SQLAlchemy 2+ with SQLite |
| Remote storage client | httpx 0.24+ |
| Web UI backend | FastAPI + Uvicorn |
| Web UI frontend | React 18 + Vite (bundled into package) |
| Real-time streaming | Server-Sent Events (SSE) |
| Config files | PyYAML 6+ |
| LLM integrations | openai, anthropic, ollama, azure-openai SDKs |
| Package manager | uv (recommended) / pip |
| Container (server) | Docker + docker-compose |
| CI/CD | GitHub Actions |

### 1.3 Three Core Pipelines

All product functionality flows through one of three pipelines. Every component belongs to exactly one pipeline.

| Pipeline | Input | Output |
|----------|-------|--------|
| **Generation** | Feature description + skill file | Approved Gherkin + step definitions in repo |
| **Execution** | Feature files + pytest config | Test results in storage + TCM updated |
| **Gap Analysis** | TCM test cases + automation suite | Ranked gap list + optional generated automation |

### 1.4 Complete Component Map

```
testweavex/
├── core/
│   ├── models.py          # Pydantic data models — shared across all components
│   ├── config.py          # testweavex.config.yaml loader + validation
│   └── exceptions.py      # Custom exception hierarchy
│
├── llm/
│   ├── base.py            # Abstract LLMAdapter interface
│   ├── openai.py          # OpenAI implementation
│   ├── anthropic.py       # Anthropic implementation
│   ├── ollama.py          # Ollama (self-hosted) implementation
│   └── azure.py           # Azure OpenAI implementation
│
├── skills/
│   ├── loader.py          # YAML skill file loader + validator
│   └── builtin/           # 10 built-in skill YAML files
│       ├── functional/
│       │   ├── smoke.yaml
│       │   ├── sanity.yaml
│       │   ├── happy_path.yaml
│       │   ├── edge_cases.yaml
│       │   ├── data_driven.yaml
│       │   ├── integration.yaml
│       │   ├── system.yaml
│       │   └── e2e.yaml
│       └── nonfunctional/
│           ├── accessibility.yaml
│           └── cross_browser.yaml
│
├── generation/
│   ├── engine.py          # Orchestrates skill + LLM + validation + review
│   ├── gherkin.py         # Gherkin formatter and .feature file writer
│   └── codegen.py         # Step definition generator + module reuse logic
│
├── execution/
│   └── plugin.py          # pytest plugin — all hook implementations
│
├── storage/
│   ├── base.py            # Abstract StorageRepository interface
│   ├── sqlite.py          # Local SQLite implementation (default)
│   ├── server.py          # HTTP client to remote result server
│   └── models.py          # SQLAlchemy ORM models
│
├── reporters/
│   ├── base.py            # Abstract BaseReporter interface
│   ├── console.py         # Rich terminal output
│   ├── sqlite.py          # Persists to StorageRepository
│   └── server.py          # Real-time push to result server
│
├── gap/
│   ├── detector.py        # Three-strategy gap detection
│   ├── scorer.py          # Six-signal priority scoring
│   └── analyzer.py        # Orchestrates detection + scoring + generation
│
├── tcm/
│   ├── base.py            # Abstract TCMConnector interface
│   ├── builtin.py         # Built-in TCM (reads from StorageRepository)
│   ├── testrail.py        # TestRail connector
│   └── xray.py            # Xray (Jira) connector
│
├── cli.py                 # Typer CLI — thin wrapper over pytest + tw commands
│
└── web/
    ├── app.py             # FastAPI app factory
    ├── api/               # API route handlers
    │   ├── dashboard.py
    │   ├── test_cases.py
    │   ├── runs.py
    │   ├── gaps.py
    │   ├── generate.py
    │   ├── settings.py
    │   └── events.py      # SSE streaming endpoint
    └── static/            # Built React app (bundled into package)
        ├── index.html
        └── assets/
```

---

## 2. Core Data Models

All data models are Pydantic v2 `BaseModel` subclasses. They serve as the shared contract between all components — storage, generation, execution, gap analysis, and the web API all speak the same model language.

### 2.1 TestCase

```python
class TestCase(BaseModel):
    id: str                      # Stable ID: hash(feature_path + scenario_name)
    title: str                   # Scenario name from Gherkin
    feature_id: str              # Parent feature ID
    gherkin: str                 # Full Gherkin scenario text
    test_type: TestType          # Enum: smoke, e2e, integration, etc.
    skill: str                   # Skill file that generated this test
    status: TestStatus           # pending | passed | failed | skipped | flaky
    is_automated: bool = False   # True if .feature file exists in repo
    tcm_id: Optional[str]        # ID in external TCM if synced
    tags: list[str] = []         # Gherkin tags (@smoke, @critical, etc.)
    priority: int = 2            # 1=critical 2=high 3=medium 4=low
    source_file: Optional[str]   # Path to .feature file
    created_at: datetime
    updated_at: datetime
```

### 2.2 Feature

```python
class Feature(BaseModel):
    id: str                           # hash(feature_file_path)
    name: str                         # Feature name from .feature file
    description: str                  # Feature description block
    acceptance_criteria: list[str]    # Parsed from structured comments
    test_case_ids: list[str]          # IDs of child TestCases
    source_file: Optional[str]        # Relative path to .feature file
```

### 2.3 TestRun & TestResult

```python
class TestRun(BaseModel):
    id: str                           # UUID generated at run start
    suite: str                        # Test suite name or path
    environment: str                  # local | ci | staging | prod
    browser: Optional[str]            # chromium | firefox | webkit
    triggered_by: str                 # 'tw' | 'pytest' | 'api'
    started_at: datetime
    completed_at: Optional[datetime]
    result_ids: list[str]             # IDs of TestResult records

class TestResult(BaseModel):
    id: str
    run_id: str
    test_case_id: str
    status: TestStatus
    duration_ms: int
    error_message: Optional[str]
    screenshot_path: Optional[str]
    retry_count: int = 0
```

### 2.4 Gap

```python
class Gap(BaseModel):
    id: str
    test_case_id: str           # Manual TestCase with no automation
    priority_score: float       # 0.0 – 1.0, higher = automate first
    gap_reason: str             # Human-readable explanation
    suggested_gherkin: Optional[str]  # LLM-generated suggestion
    status: str = 'open'        # open | pending_review | closed | dismissed
    detected_at: datetime
    closed_at: Optional[datetime]
```

### 2.5 Stable ID Generation

Stable IDs are the foundation of TestWeaveX's sync reliability. The same test always gets the same ID across machines, environments, and CI runs. Renaming a scenario generates a new ID — the old one surfaces as a gap candidate.

```python
import hashlib

def generate_stable_id(*parts: str) -> str:
    """Deterministic ID from path + name. Collision-resistant, short."""
    key = '|'.join(parts).encode('utf-8')
    return hashlib.sha256(key).hexdigest()[:16]

# Usage:
# test_case_id = generate_stable_id(feature_path, scenario_name)
# feature_id   = generate_stable_id(feature_path)
```

> ⚠️ **Never change this algorithm.** Changing it invalidates all existing stable IDs in every deployed instance.

---

## 3. LLM Adapter Layer

All LLM interactions are abstracted behind a single interface. The rest of the system never imports a provider-specific SDK directly. Every adapter returns validated Pydantic objects — raw LLM text never flows through the system.

### 3.1 Abstract Interface

```python
from abc import ABC, abstractmethod

class LLMAdapter(ABC):

    @abstractmethod
    def generate_tests(self,
        request: GenerationRequest
    ) -> GenerationResponse: ...

    @abstractmethod
    def generate_step_definitions(self,
        scenarios: list[Scenario],
        existing_steps: list[StepDefinition]
    ) -> StepDefinitionResponse: ...

    @abstractmethod
    def suggest_gap_automation(self,
        manual_test: TestCase
    ) -> GenerationResponse: ...

    @abstractmethod
    def health_check(self) -> bool: ...
```

### 3.2 Structured Output Contract

Every adapter must return a `GenerationResponse` — a Pydantic model containing a list of validated `Scenario` objects. If the LLM returns malformed JSON or fails validation, the adapter retries up to 3 times before raising `LLMOutputError`. The engineer never sees raw LLM output.

```python
class Scenario(BaseModel):
    title: str
    gherkin: str
    confidence: float          # 0.0 – 1.0
    rationale: str             # Why this test is valuable
    suggested_tags: list[str]

class GenerationResponse(BaseModel):
    scenarios: list[Scenario]
    skill_used: str
    llm_model: str
    tokens_used: int
    generation_time_ms: int
```

### 3.3 Provider Configuration

```yaml
# testweavex.config.yaml
llm:
  provider: anthropic          # openai | anthropic | ollama | azure
  model: claude-sonnet-4-6
  api_key: ${ANTHROPIC_API_KEY} # env var interpolation supported
  temperature: 0.3             # lower = more deterministic output
  max_retries: 3
  timeout_seconds: 30

  # Ollama self-hosted example:
  # provider: ollama
  # base_url: http://localhost:11434
  # model: llama3

  # Azure OpenAI example:
  # provider: azure
  # azure_endpoint: https://company.openai.azure.com
  # api_version: 2024-02-01
  # deployment_name: gpt-4o
```

### 3.4 Confidence Score Indicators

| Score Range | Display | Meaning |
|-------------|---------|---------|
| 0.85 – 1.00 | ✓ Green | High confidence — likely approve |
| 0.65 – 0.84 | ? Amber | Review carefully before approving |
| Below 0.65 | ⚠ Red | Low confidence — consider discarding |

---

## 4. Skill Files Framework

Skill files are the SOP layer of TestWeaveX. Each YAML file encodes domain-specific testing knowledge — prompt strategies, assertion patterns, data setup guidance — for a specific test type. Skills are loaded at runtime and injected into the generation engine.

### 4.1 Skill File Schema

```yaml
# testweavex/skills/builtin/functional/smoke.yaml

name: functional/smoke
display_name: Smoke Testing
description: >
  Critical path scenarios covering must-work flows.
  Fast, high confidence. Should run on every deployment.

prompt_template: |
  You are a senior QA engineer generating smoke test scenarios.

  Feature: {feature_description}
  Acceptance Criteria: {acceptance_criteria}
  Existing scenarios (avoid duplicates): {existing_scenarios}

  Generate {n_suggestions} smoke test scenarios that:
  - Cover the critical path only
  - Execute in under 30 seconds each
  - Have a single clear pass/fail outcome
  - Follow strict Given/When/Then Gherkin format

  Return a JSON array with fields:
  title, gherkin, confidence (0-1), rationale, suggested_tags

assertion_hints:
  - Verify primary user-facing outcome
  - Check HTTP status codes for API tests
  - Confirm page load and key element visibility for UI tests

data_setup:
  - Use minimal test data
  - Prefer idempotent setup steps

tags: [smoke, fast, critical-path]
estimated_duration_seconds: 30
priority: 1
```

### 4.2 Built-in Skills (V1)

| Skill Path | Testing Focus |
|-----------|--------------|
| `functional/smoke` | Critical path, fast execution, every deployment |
| `functional/sanity` | Post-change regression on adjacent functionality |
| `functional/happy_path` | Intended user journey without errors |
| `functional/edge_cases` | Boundary values, null inputs, upper/lower bounds |
| `functional/data_driven` | Parameterised scenarios with data tables |
| `functional/integration` | Cross-service interactions, mock vs. live decisions |
| `functional/system` | Full system spans across multiple components |
| `functional/e2e` | Complete user journey including third-party integrations |
| `nonfunctional/accessibility` | WCAG 2.1 AA compliance via axe-core |
| `nonfunctional/cross_browser` | Chromium, Firefox, WebKit tagged scenarios |

> **Extensibility:** Teams add custom skills by creating YAML files in `testweavex/skills/custom/`. Custom skills override built-ins with the same name. No Python code changes required.

---

## 5. Generation Engine

The generation engine orchestrates the full path from feature description to approved, committed test cases. It is the only component that calls the LLM adapter and the only component that writes to the filesystem — and only after explicit engineer approval.

### 5.1 Generation Pipeline (10 Steps)

| Step | Action | Human Gate? |
|------|--------|-------------|
| 1. Load skill | Load YAML for requested test type | No |
| 2. Build context | Gather feature desc, existing scenarios, step defs | No |
| 3. Construct prompt | Inject context into skill `prompt_template` | No |
| 4. Call LLM | Get structured `GenerationResponse` | No |
| 5. Validate & deduplicate | Check Gherkin syntax, flag duplicates | No |
| 6. Present suggestions | Show scenarios with confidence scores | **YES — engineer approves/discards** |
| 7. Write feature files | Write approved Gherkin to `.feature` files | No (post-approval) |
| 8. Generate step defs | Check existing steps, generate new ones | No |
| 9. New module needed? | If new class/module required for steps | **YES — engineer approves** |
| 10. Write step defs | Write approved step definitions to file | No (post-approval) |

### 5.2 Step Definition Reuse

Before generating new step definitions, the engine scans existing step files for reusable implementations using regex pattern matching on step text. Reuse rate is tracked as a metric — high reuse means the Page Object model is maturing correctly.

```python
class StepDefinitionGenerator:

    def generate(self, scenarios, existing_steps):
        new_steps = []
        reused = []
        new_modules = []

        for step in self._extract_steps(scenarios):
            match = self._find_reusable(step, existing_steps)
            if match:
                reused.append(match)
            else:
                generated = self.llm.generate_step(step, existing_steps)
                if generated.requires_new_module:
                    new_modules.append(generated.module_spec)
                new_steps.append(generated)

        return new_steps, reused, new_modules
        # new_modules triggers human approval before writing
```

---

## 6. pytest Plugin Architecture

TestWeaveX is registered as a pytest plugin via the `pytest11` entry point in `pyproject.toml`. This means it activates automatically for any project that has `pip install testweavex` — no configuration changes required.

### 6.1 Entry Point Registration

```toml
# pyproject.toml

[project.entry-points.'pytest11']
testweavex = 'testweavex.execution.plugin'

[project.scripts]
tw = 'testweavex.cli:main'
```

### 6.2 Plugin Hook Implementations

```python
# testweavex/execution/plugin.py

def pytest_addoption(parser):
    group = parser.getgroup('testweavex')
    group.addoption('--results-server', help='TestWeaveX result server URL')
    group.addoption('--token',          help='Result server auth token')
    group.addoption('--sync-tcm',       help='Sync to external TCM (testrail/xray)')
    group.addoption('--generate',       action='store_true')
    group.addoption('--gaps',           action='store_true')
    group.addoption('--skill',          help='Testing skill for generation')

def pytest_configure(config):
    repo = get_repository(config)          # SQLite or Server
    config.testweavex_repo = repo
    config.testweavex_reporters = build_reporters(config, repo)
    config.testweavex_run = repo.start_run()

def pytest_collection_modifyitems(session, config, items):
    repo = config.testweavex_repo
    for item in items:
        if hasattr(item, 'scenario'):      # pytest-bdd item
            tc = build_test_case(item)     # Map scenario -> TestCase
            repo.upsert_test_case(tc)      # Sync to TCM
    repo.mark_uncollected_as_gaps(         # Anything not collected = gap
        collected_ids=[...]
    )

def pytest_runtest_logreport(report):
    if report.when == 'call':
        result = build_result(report)
        for r in report.config.testweavex_reporters:
            r.on_test_result(result)

def pytest_sessionfinish(session, exitstatus):
    config = session.config
    summary = build_summary(session)
    for r in config.testweavex_reporters:
        r.on_session_end(summary)
    if config.getoption('--sync-tcm'):
        get_connector(config).sync_results(config.testweavex_run)
    if config.getoption('--gaps'):
        GapAnalyzer(config).run_and_print()
```

### 6.3 pytest-bdd Integration

pytest-bdd collects each Gherkin Scenario as a pytest item. TestWeaveX intercepts the collection phase to sync scenarios with the TCM and detect gaps. The mapping between a pytest-bdd item and a TestWeaveX `TestCase` is deterministic via stable IDs.

```python
def build_test_case(item) -> TestCase:
    scenario = item.scenario
    feature  = scenario.feature
    return TestCase(
        id           = generate_stable_id(feature.filename, scenario.name),
        title        = scenario.name,
        feature_id   = generate_stable_id(feature.filename),
        gherkin      = format_gherkin(scenario),
        test_type    = infer_type_from_tags(scenario.tags),
        skill        = infer_skill_from_tags(scenario.tags),
        is_automated = True,
        tags         = list(scenario.tags),
        source_file  = feature.filename,
    )
```

---

## 7. CLI — The tw Command

The `tw` CLI is a thin Typer wrapper that builds pytest arguments and hands off to `pytest.main()`. TestWeaveX-specific flags are added alongside full pytest passthrough. Every pytest flag works with `tw` transparently.

### 7.1 Command Reference

| Command | Description | Key Options |
|---------|-------------|-------------|
| `tw [paths]` | Run tests (wraps pytest) | `--results-server`, `--token`, `--sync-tcm`, `--gaps`, `--generate` |
| `tw generate` | Generate test cases from feature description | `--feature`, `--skill`, `--llm`, `--output` |
| `tw gaps` | Run gap analysis and show ranked report | `--limit`, `--min-score`, `--generate`, `--export` |
| `tw import` | Import test cases from external TCM or CSV | `--source (testrail/xray/csv)`, `--map` |
| `tw status` | Show coverage map and execution summary | `--format (table/json/html)` |
| `tw history` | Show execution history for test or suite | `--id`, `--last-n`, `--format` |
| `tw serve` | Start Web UI server | `--host`, `--port`, `--open` |
| `tw migrate` | Migrate from external TCM to built-in | `--source`, `--dry-run` |
| `tw init` | Initialise TestWeaveX in a project | `--llm-provider`, `--tcm` |

### 7.2 pytest Compatibility

```bash
tw                          # Run all tests (same as pytest)
tw tests/login.feature      # Run specific feature file
tw -k 'smoke'               # Filter by tag/keyword
tw -v                       # Verbose output
tw -x                       # Stop on first failure
tw -n 4                     # Parallel (pytest-xdist)
tw --co                     # Collect only — show what would run
tw --tb short               # Short traceback format

# TestWeaveX additions:
tw --results-server https://tcm.company.com --token $TOKEN
tw --gaps --sync-tcm testrail
tw --generate --skill functional/smoke
```

---

## 8. Storage Layer

All persistence goes through a single abstract `StorageRepository` interface. Two concrete implementations exist: `SQLiteRepository` (local default) and `ServerRepository` (team mode). The factory function returns the correct implementation based on configuration — callers are completely unaware of which backend is active.

### 8.1 Abstract Interface

```python
class StorageRepository(ABC):
    @abstractmethod
    def upsert_test_case(self, tc: TestCase): ...
    @abstractmethod
    def save_result(self, r: TestResult): ...
    @abstractmethod
    def start_run(self) -> TestRun: ...
    @abstractmethod
    def end_run(self, run_id: str): ...
    @abstractmethod
    def get_gaps(self, limit=50, status='open') -> list[Gap]: ...
    @abstractmethod
    def save_gaps(self, gaps: list[Gap]): ...
    @abstractmethod
    def get_coverage_percentage(self) -> float: ...
    @abstractmethod
    def get_coverage_trend(self, weeks: int) -> list[dict]: ...
    @abstractmethod
    def get_flaky_tests(self, min_runs=5) -> list[TestCase]: ...
    @abstractmethod
    def get_scoring_signals(self, tc_id: str) -> ScoringSignals: ...
    @abstractmethod
    def mark_uncollected_as_gaps(self, collected_ids: list[str]): ...
```

### 8.2 SQLite — Storage Location

```python
def _find_or_create_db_path(self) -> str:
    """
    Walk up from cwd to find project root.
    Project root = directory containing pyproject.toml or pytest.ini.
    Creates .testweavex/ directory if not present.
    """
    root = self._find_project_root()   # Walks up checking for markers
    db_dir = os.path.join(root, '.testweavex')
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, 'results.db')

# Result: .testweavex/results.db in project root
# Add to .gitignore: .testweavex/
```

### 8.3 Factory — Config-Driven Backend Switch

```python
def get_repository(config) -> StorageRepository:
    """
    Priority order for server URL:
    1. --results-server CLI flag
    2. TESTWEAVEX_SERVER environment variable
    3. results_server key in testweavex.config.yaml
    """
    server_url = (
        config.getoption('--results-server', default=None)
        or os.getenv('TESTWEAVEX_SERVER')
        or load_config().get('results_server')
    )
    if server_url:
        token = config.getoption('--token') or os.getenv('TESTWEAVEX_TOKEN')
        return ServerRepository(server_url, token)
    return SQLiteRepository()   # Default — zero config required
```

### 8.4 Flakiness Detection Query

```python
def get_flaky_tests(self, min_runs=5) -> list[TestCase]:
    """
    Flaky = test has both PASSED and FAILED results
    in last N runs with no code changes between them.
    Ranked by failure rate descending.
    """
    return session.execute('''
        SELECT test_case_id,
               COUNT(*) total_runs,
               SUM(status='passed') passes,
               SUM(status='failed') failures,
               CAST(SUM(status='failed') AS FLOAT)/COUNT(*) failure_rate
        FROM test_results
        GROUP BY test_case_id
        HAVING total_runs >= :min_runs AND passes > 0 AND failures > 0
        ORDER BY failure_rate DESC
    ''', {'min_runs': min_runs}).fetchall()
```

---

## 9. Reporter Pattern

Reporters are observers that react to test execution events. Multiple reporters run simultaneously — the console reporter shows terminal output while the SQLite reporter persists and the server reporter streams results in real time. Adding a new reporter requires no changes to the execution plugin.

### 9.1 Abstract Interface

```python
class BaseReporter(ABC):
    @abstractmethod
    def on_test_start(self, item): ...
    @abstractmethod
    def on_test_result(self, result: TestResult): ...
    @abstractmethod
    def on_session_end(self, summary: RunSummary): ...
```

### 9.2 Reporter Activation Logic

```python
def build_reporters(config, repo) -> list[BaseReporter]:
    reporters = [
        ConsoleReporter(),       # Always active — terminal output
        SQLiteReporter(repo),    # Always active — local persistence
    ]
    if config.getoption('--results-server'):
        reporters.append(ServerReporter(config))
    return reporters
```

### 9.3 Full Execution Data Flow

```
tw --results-server https://tcm.co --token $TOKEN
│
├── CLI builds pytest args → pytest.main(args)
│
├── pytest_configure
│   └── ServerRepository + 3 reporters initialised
│
├── pytest_collection_modifyitems
│   ├── Scenarios synced to TCM
│   └── Uncollected TCM tests marked as gap candidates
│
├── [Tests execute via pytest-playwright + pytest-bdd]
│   └── pytest_runtest_logreport (per test)
│       ├── ConsoleReporter  → ✓/✗ terminal output
│       ├── SQLiteReporter   → .testweavex/results.db
│       └── ServerReporter   → POST /api/results (real-time)
│
└── pytest_sessionfinish
    ├── Flakiness scores recalculated
    ├── Coverage map updated
    ├── TestRail synced (if --sync-tcm testrail)
    └── Gap report printed (if --gaps)
```

---

## 10. Gap Analyzer

The Gap Analyzer is the core USP engine. It compares all TCM test cases against the automation suite, identifies unautomated tests, scores them by automation priority, and optionally triggers LLM generation for selected gaps.

### 10.1 Detection — Three Matching Strategies

```python
def detect(self, tcm_tests, automated_tests) -> list[Gap]:
    index = self._build_index(automated_tests)
    gaps  = []

    for test in tcm_tests:
        if test.is_automated: continue

        match = (
            # Strategy 1: Exact stable ID match
            self._match_by_stable_id(test, index)
            # Strategy 2: External TCM ID match (imported tests)
            or self._match_by_tcm_id(test, index)
            # Strategy 3: Semantic similarity (fuzzy, offline)
            or self._match_by_semantic_similarity(test, index)
        )

        if not match:
            gaps.append(Gap(test_case_id=test.id, ...))

    return gaps

def _match_by_semantic_similarity(self, test, index):
    """
    Jaccard similarity on title tokens (70%) +
    tag overlap score (30%).
    Threshold: 0.65. Fast, offline, no LLM call.
    ~85% accuracy on well-written test titles.
    """
```

### 10.2 Scoring — Six-Signal Priority Algorithm

```python
WEIGHTS = {
    'priority':  0.30,  # P1 tests must be automated first
    'test_type': 0.25,  # Smoke/E2E gaps hurt most
    'defects':   0.20,  # Tests linked to bugs are high value
    'frequency': 0.15,  # Frequently-run tests benefit most
    'staleness': 0.10,  # Stale = higher risk of undiscovered regressions
}

def score(self, gap, signals) -> float:
    priority_score  = (5 - signals.test_priority) / 4
    type_score      = TEST_TYPE_SCORES[signals.test_type]
    defect_score    = min(1.0, log1p(signals.defect_count) / log1p(10))
    frequency_score = min(1.0, signals.executions_90d / 30)
    staleness_score = min(1.0, signals.days_since_run / 30)

    return sum([
        WEIGHTS['priority']  * priority_score,
        WEIGHTS['test_type'] * type_score,
        WEIGHTS['defects']   * defect_score,
        WEIGHTS['frequency'] * frequency_score,
        WEIGHTS['staleness'] * staleness_score,
    ])
```

### 10.3 Test Type Priority Scores

| Test Type | Priority Score |
|-----------|---------------|
| smoke | 1.00 |
| e2e | 0.90 |
| happy_path | 0.85 |
| integration | 0.80 |
| system | 0.75 |
| sanity | 0.70 |
| data_driven | 0.60 |
| edge_case | 0.50 |
| accessibility | 0.40 |

### 10.4 Configurable Weights

```yaml
# testweavex.config.yaml
gap_analysis:
  scoring_weights:
    priority:  0.30
    test_type: 0.25
    defects:   0.20
    frequency: 0.15
    staleness: 0.10
  match_threshold: 0.65
  top_gaps_default: 10
  min_runs_for_flaky: 5
```

---

## 11. Web UI

The Web UI is a React single-page application bundled inside the Python package. `tw serve` starts a FastAPI server that serves both the REST API and the static React build from a single process on `localhost:8080` by default.

### 11.1 FastAPI App Structure

```python
def create_app() -> FastAPI:
    app = FastAPI(title='TestWeaveX', docs_url='/api/docs')

    app.include_router(dashboard.router,  prefix='/api/dashboard')
    app.include_router(test_cases.router, prefix='/api/test-cases')
    app.include_router(runs.router,       prefix='/api/runs')
    app.include_router(gaps.router,       prefix='/api/gaps')
    app.include_router(generate.router,   prefix='/api/generate')
    app.include_router(settings.router,   prefix='/api/settings')
    app.include_router(events.router,     prefix='/api/events')

    # Serve bundled React app
    static_dir = Path(__file__).parent / 'static'
    app.mount('/assets', StaticFiles(directory=static_dir/'assets'))

    @app.get('/{full_path:path}')
    async def serve_frontend(full_path: str):
        return FileResponse(static_dir / 'index.html')

    return app
```

### 11.2 Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard` | KPI summary, coverage trend, top gaps, recent failures |
| GET | `/api/test-cases` | Paginated list with filters (type/status/feature/tags) |
| GET | `/api/test-cases/{id}` | Single test case with execution history |
| GET | `/api/runs` | Execution run history |
| GET | `/api/runs/{id}` | Run detail with per-test results |
| GET | `/api/gaps` | Scored gap list with filters |
| POST | `/api/gaps/{id}/generate` | Trigger LLM generation for a gap (async, streams via SSE) |
| POST | `/api/generate/{sid}/approve` | Approve/discard/add scenarios, write to repo |
| GET | `/api/events/{session_id}` | SSE stream for live run or generation events |
| GET | `/api/settings` | Current config (LLM, TCM, storage) |
| PUT | `/api/settings` | Update config |

### 11.3 Server-Sent Events (SSE) Streaming

SSE provides real-time updates to the Web UI during test runs and LLM generation. The server pushes events; the browser listens. No WebSocket complexity required.

```python
# Backend — events.py
@router.get('/{session_id}')
async def stream_events(session_id: str):
    async def generator():
        queue = event_bus.subscribe(session_id)
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                yield f'data: {json.dumps(event)}\n\n'
                if event.get('type') == 'session_end': break
        finally:
            event_bus.unsubscribe(session_id, queue)

    return StreamingResponse(generator(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
```

```javascript
// Frontend — React hook
useEffect(() => {
    const src = new EventSource(`/api/events/${sessionId}`);
    src.onmessage = e => {
        const evt = JSON.parse(e.data);
        if (evt.type === 'test_result') updateResults(evt.result);
        if (evt.type === 'session_end') { setSummary(evt.summary); src.close(); }
    };
    return () => src.close();
}, [sessionId]);
```

### 11.4 Six Key Screens

| Screen | Primary Purpose |
|--------|----------------|
| **Dashboard** | KPI overview: coverage %, gap count, flaky tests, last run summary, 12-week trend chart |
| **Test Cases** | Filterable list of all tests (manual + automated). Side panel shows Gherkin + history. |
| **Gap Report** | Ranked unautomated tests with priority score bar, one-click Generate per gap |
| **Generation Review** | LLM suggestions with confidence scores, accept/discard/edit, custom scenario input |
| **Live Run View** | Real-time test results streaming via SSE as tests execute |
| **Settings** | LLM provider config, TCM connector setup, scoring weight tuning |

### 11.5 Frontend Packaging

The React app is built with Vite during the release pipeline and the output is committed to `testweavex/web/static/`. End users receive the bundled frontend as part of `pip install testweavex` — no Node.js required at runtime.

```toml
# pyproject.toml — include static files in wheel
[tool.setuptools.package-data]
'testweavex.web' = ['static/**/*']
```

```bash
# CI/CD release step:
cd testweavex/web/frontend && npm run build
cp -r dist/* ../static/
git add web/static && git commit -m 'chore: update frontend build'
```

---

## 12. External TCM Connectors

TCM connectors enable bidirectional sync between TestWeaveX and external test case management systems. All connectors implement a single abstract interface. V1 ships TestRail and Xray (Jira) connectors.

### 12.1 Abstract Interface

```python
class TCMConnector(ABC):

    @abstractmethod
    def fetch_all_test_cases(self) -> list[TestCase]:
        """Pull all test cases from the external TCM for gap analysis."""

    @abstractmethod
    def push_result(self, result: TestResult, run_id: str):
        """Update test case status in external TCM after a run."""

    @abstractmethod
    def push_test_case(self, tc: TestCase):
        """Create or update a test case in the external TCM."""

    @abstractmethod
    def health_check(self) -> bool: ...
```

### 12.2 Configuration

```yaml
# testweavex.config.yaml
tcm:
  provider: testrail          # testrail | xray | none

  testrail:
    url: https://company.testrail.io
    username: ${TESTRAIL_USER}
    api_key: ${TESTRAIL_KEY}
    project_id: 12
    suite_id: 45

  xray:
    jira_url: https://company.atlassian.net
    client_id: ${XRAY_CLIENT_ID}
    client_secret: ${XRAY_SECRET}
    project_key: QA
```

### 12.3 Import & Migration

```bash
# One-command migration from TestRail:
tw migrate --source testrail --dry-run

# Output:
# Found 847 test cases in TestRail project 12
# 142 already have automation counterparts (matched by title)
# 705 will be imported as manual tests (gap candidates)
# Run without --dry-run to proceed.

tw migrate --source testrail
# Imports all 847 test cases, assigns stable IDs,
# stores tcm_id for bidirectional sync.
# First gap report now available immediately.
```

---

## 13. Self-Hosted Result Server

The result server is a lightweight Docker container that accepts result pushes from multiple clients (local machines, CI/CD pipelines) and serves the shared Web UI for the team. It is the team-mode upgrade from local SQLite storage.

### 13.1 Docker Setup

```yaml
# docker-compose.yml
version: '3.8'
services:
  testweavex-server:
    image: ghcr.io/testweavex/server:latest
    ports:
      - '8080:8080'
    volumes:
      - testweavex_data:/data
    environment:
      - DATABASE_URL=sqlite:////data/results.db
      - SECRET_KEY=${TESTWEAVEX_SECRET_KEY}
      - ALLOWED_ORIGINS=https://your-domain.com
    restart: unless-stopped

volumes:
  testweavex_data:
```

### 13.2 CI/CD Integration

```yaml
# GitHub Actions — push results to team server
- name: Run tests
  run: |
    tw run --suite regression \
           --results-server ${{ secrets.TW_SERVER }} \
           --token ${{ secrets.TW_TOKEN }} \
           --sync-tcm testrail
```

---

## 14. Dependency Map

All production dependencies are well-established, actively maintained libraries. No dependency introduces a vendor lock-in.

| Package | Version | Purpose | Category |
|---------|---------|---------|----------|
| pytest | >=7.0 | Core test runner | Required |
| pytest-bdd | >=7.0 | Gherkin feature file support | Required |
| pytest-playwright | >=0.4 | Playwright browser automation fixtures | Required |
| pytest-xdist | >=3.0 | Parallel test execution | Required |
| pydantic | >=2.0 | Data models and validation | Required |
| typer | >=0.9 | CLI framework | Required |
| sqlalchemy | >=2.0 | ORM for SQLite storage | Required |
| httpx | >=0.24 | Async HTTP client for server repo | Required |
| fastapi | >=0.110 | Web UI backend | Required |
| uvicorn | >=0.27 | ASGI server for FastAPI | Required |
| pyyaml | >=6.0 | Skill file and config loading | Required |
| rich | >=13.0 | Terminal output formatting | Required |
| openai | >=1.0 | OpenAI LLM adapter | Optional |
| anthropic | >=0.20 | Anthropic LLM adapter | Optional |
| ollama | >=0.1 | Ollama self-hosted adapter | Optional |
| testrail-api | latest | TestRail TCM connector | Optional |

---

## 15. Build & Release Pipeline

### 15.1 Repository Structure

```
github.com/testweavex/
├── testweavex/          # Core Python library (this spec)
├── testweavex-server/   # Self-hosted result server (Docker)
├── testweavex-skills/   # Community skill file contributions
└── testweavex-docs/     # Docusaurus documentation site
```

### 15.2 CI/CD Pipeline (GitHub Actions)

```yaml
on: [push, pull_request]

jobs:
  test:
    steps:
      - run: pip install -e '.[dev]'
      - run: pytest tests/ -v              # Test the framework itself
      - run: tw tests/integration/ --gaps  # Dog-food: use tw to test tw

  build-frontend:
    steps:
      - run: cd testweavex/web/frontend && npm ci && npm run build
      - run: cp -r dist/* ../static/

  publish:                                 # On tag push only
    needs: [test, build-frontend]
    steps:
      - run: pip install build && python -m build
      - run: twine upload dist/*
```

### 15.3 Versioning Strategy

- **MAJOR:** breaking changes to public API or CLI flags
- **MINOR:** new features, new skill files, new TCM connectors
- **PATCH:** bug fixes, dependency updates, prompt improvements
- Skill file updates ship as PATCH — no breaking change

---

## 16. Development Build Order

The recommended build sequence ensures a working end-to-end demo exists at every stage. Never build infrastructure that has nothing to demonstrate.

| Phase | Milestone | Deliverable | Validates |
|-------|-----------|-------------|-----------|
| **1 — Foundation** | Week 1–2 | `core/models.py` + `storage/sqlite.py` | Data layer works |
| **2 — LLM** | Week 3–4 | `llm/base.py` + `llm/openai.py` + `skills/loader.py` | LLM returns structured scenarios |
| **3 — Generation** | Week 5–6 | `generation/engine.py` + `generation/gherkin.py` | Feature → Gherkin file on disk |
| **4 — Execution** | Week 7–8 | `execution/plugin.py` + `cli.py` | `tw` runs pytest, results in SQLite |
| **5 — Gap Analysis** | Week 9–10 | `gap/detector.py` + `gap/scorer.py` | `tw --gaps` shows ranked report |
| **6 — Web UI** | Week 11–14 | `web/app.py` + React frontend | Dashboard + gap report in browser |
| **7 — TCM Connectors** | Week 15–16 | `tcm/testrail.py` + `tcm/xray.py` | Import + sync with TestRail |
| **8 — Polish & OSS** | Week 17–18 | Docs, README, contribution guide | Public GitHub release |

---

*See also: [`CLAUDE.md`](../CLAUDE.md) for quick reference | [`docs/PRD.md`](PRD.md) for product requirements*
