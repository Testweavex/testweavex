# Changelog

All notable changes to TestWeaveX are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.1.0] — unreleased

First public release. TestWeaveX is a pytest plugin that unifies test case
management, LLM-assisted test generation, execution, and gap analysis.

### Added

**Core & storage**
- Pydantic v2 data models — `TestCase`, `Feature`, `TestRun`, `TestResult`, `Gap`.
- `generate_stable_id()` — deterministic full-length SHA-256 IDs so test cases
  survive renames and stay stable across sync boundaries.
- `testweavex.config.yaml` loader with `${ENV_VAR}` interpolation.
- `StorageRepository` abstraction with two backends: `SQLiteRepository`
  (default, zero-config, writes to `.testweavex/results.db`) and
  `ServerRepository` (team mode, HTTP).

**LLM generation**
- Provider-agnostic `LLMAdapter` interface with OpenAI, Anthropic, Ollama, and
  Azure OpenAI implementations. Provider SDKs are optional extras.
- 10 built-in skill files covering functional (smoke, sanity, happy path, edge
  cases, data-driven, integration, system, e2e) and non-functional
  (accessibility, cross-browser) test types; custom skills load from YAML.
- `GenerationEngine` with a mandatory review gate — no LLM output reaches the
  filesystem without explicit approval.
- Gherkin formatter, `.feature` file writer with dedup, and a step-definition
  generator that reuses existing `@given`/`@when`/`@then` patterns.

**Execution**
- pytest plugin (`tw`) implementing `pytest_addoption`, `pytest_configure`,
  `pytest_collection_modifyitems`, `pytest_runtest_logreport`, and
  `pytest_sessionfinish`. Every pytest flag continues to work.
- Event bus with console and storage subscribers; Rich terminal run summary.
- Manual test execution recording.

**Gap analysis**
- Three-strategy gap detection and a six-signal priority scorer weighted by
  priority, test type, linked defects, run frequency, and staleness.

**Web UI**
- FastAPI backend with SSE streaming, bundled into the Python package.
- React 18 + Vite frontend: dashboard, test-case CRUD, test runs, gap report
  with inline generation, and settings.
- `tw serve` starts API and UI from a single process.

**TCM connectors**
- TestRail and Xray (Jira) connectors for one-way import into the built-in TCM.

**CLI**
- `tw init`, `tw generate`, `tw gaps`, `tw status`, `tw history`, `tw serve`,
  `tw migrate`, `tw sync`.

**Project**
- Docker and Podman deployment, docker-compose with optional PostgreSQL.
- GitHub Pages documentation site, tutorial, PRD, and architecture spec.
- CI running pytest on Python 3.11/3.12 plus frontend Vitest.

### Known limitations

- The `--sync-tcm` pytest flag is accepted but not yet wired up; it currently
  has no effect. Use `tw sync --tcm <provider>` instead.
- TCM sync is one-way (external TCM → TestWeaveX).

[Unreleased]: https://github.com/Testweavex/testweavex/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Testweavex/testweavex/releases/tag/v0.1.0
