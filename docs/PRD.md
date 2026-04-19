# TestWeaveX — Product Requirements Document

**Version:** 1.0 — Draft
**Date:** April 2026
**Status:** For Review
**Author:** Pankaj S
**GitHub Org:** github.com/testweavex

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Product Vision & Positioning](#3-product-vision--positioning)
4. [Target Users](#4-target-users)
5. [Core Product Loop](#5-core-product-loop)
6. [Architecture Overview](#6-architecture-overview)
7. [V1 Scope](#7-v1-scope)
8. [Testing Skills Framework](#8-testing-skills-framework)
9. [SHAPE Framework Application](#9-shape-framework-application)
10. [CLI Reference (V1)](#10-cli-reference-v1)
11. [Open Source Strategy](#11-open-source-strategy)
12. [Success Metrics](#12-success-metrics)
13. [Risks & Mitigations](#13-risks--mitigations)
14. [Roadmap](#14-roadmap)
15. [Appendix: Key Decisions Log](#15-appendix-key-decisions-log)

---

## 1. Executive Summary

TestWeaveX is an open-source, unified test management and execution platform built for engineering teams who want to move faster without sacrificing test quality. It brings together test case management, test execution, and AI-assisted test generation into a single, Git-native platform — with any LLM acting as a coworker that suggests, but never decides.

> **Mission:** Eliminate the gap between manual test plans and automated test suites by making test generation, execution, and management a single continuous loop.

The platform is designed around three core beliefs:

- The engineer is always in control. The LLM suggests. The engineer approves.
- Test management and test execution should be the same system, not two systems bolted together.
- Coverage gaps — manual tests with no automation counterpart — should surface automatically and be closeable in minutes, not sprints.

---

## 2. Problem Statement

Modern engineering teams face a fragmented testing landscape that creates three chronic pain points.

### 2.1 Fragmented Toolchain

Teams rely on separate tools for test management (TestRail, Xray, Zephyr), test execution (Playwright, Selenium), and BDD frameworks (Cucumber, Behave). There is no single source of truth. Results rarely sync back to the TCM automatically. Coverage visibility is always stale.

### 2.2 Stale Manual Test Portfolios

Most teams have hundreds or thousands of manual test cases in their TCM with no automation counterpart. There is no systematic way to identify which ones matter most to automate, and writing automation from scratch is slow. The gap grows with every sprint.

### 2.3 Test Creation Bottleneck

When a new feature is built, writing test cases is time-consuming, repetitive, and often deferred. Acceptance criteria exist in tickets but rarely translate automatically into Gherkin scenarios or automation code. QA engineers spend hours on boilerplate that an LLM could draft in seconds.

> **Root Cause:** Test management was designed for a manual world. Execution frameworks were designed for a code world. Neither was designed for the AI-augmented, BDD-first, CI/CD-native world that engineering teams now operate in.

---

## 3. Product Vision & Positioning

> *"TestWeaveX is an open-source unified test management and execution platform for engineering teams. It uses any LLM as a coworker to generate, review, and close coverage gaps — without replacing the engineer's judgment."*

### 3.1 Core Differentiators

| Differentiator | What It Means |
|----------------|---------------|
| **Git-native TCM** | Test cases live as Gherkin feature files in the repo. The TCM is a view over those files, not a separate database. Test cases and code are always in sync. |
| **Execution-aware by default** | Every test case knows its last run status, flakiness rate, and average execution time automatically — no manual sync required. |
| **LLM as coworker** | Bring any LLM (OpenAI, Anthropic, Ollama, Azure OpenAI). The LLM suggests tests; the engineer approves. Human judgement is never bypassed. |
| **Automatic gap analysis** | The platform continuously compares the TCM against the automation suite and surfaces stale manual tests with no counterpart. |
| **Coverage-aware requirements** | Acceptance criteria link to test cases. Coverage maps update automatically when tests are added, removed, or changed. |
| **Zero-config start** | Works locally with SQLite by default. No server, no account, no friction. One CLI flag routes results to a self-hosted team server. |

---

## 4. Target Users

| User | Primary Need | Key Interaction |
|------|-------------|-----------------|
| **QA Engineer** | Generate, review, and manage test cases efficiently without writing boilerplate | Web UI — reviewing LLM suggestions, approving test cases, monitoring coverage maps |
| **Developer** | Know which tests to run before merging, and have new feature tests ready at PR time | CLI — running tests, checking coverage, getting PR-level test impact reports |
| **QA Lead / Manager** | Visibility into coverage health, flakiness trends, and gap closure over time | Web UI dashboards — coverage trends, gap reports, sprint-over-sprint progress |
| **DevOps / Platform Engineer** | Embed TestWeaveX into CI/CD pipelines with minimal configuration | CLI + YAML config — pipeline integration, result server setup, Docker deployment |

---

## 5. Core Product Loop

TestWeaveX is built around a single continuous feedback loop. Every feature exists to accelerate or strengthen one step in this loop:

```
Feature Description
  → LLM Suggests Tests
  → Engineer Reviews & Approves
  → Gherkin Generated
  → Code Modules Created/Reused
  → Tests Execute
  → Results Flow to TCM
  → Gaps Surface
  → Loop Repeats
```

### 5.1 New Feature Flow

1. Engineer adds feature description or acceptance criteria (plain English or structured)
2. LLM suggests N test scenarios (functional + integration + edge cases)
3. Engineer selects, discards, and optionally adds their own scenarios
4. Approved scenarios are written as Gherkin feature files in the repo
5. LLM generates or reuses step definition code; new modules confirmed by engineer before creation
6. Tests execute locally or in CI/CD; results flow back to TCM automatically

### 5.2 Gap Analysis Flow

1. TestWeaveX compares TCM test cases against automation suite
2. Unautomated tests are surfaced with priority ranking (frequency, criticality, defect history)
3. Engineer selects which gaps to close
4. LLM generates Gherkin + step definitions for selected gaps
5. Engineer reviews, approves, and merges; coverage map updates automatically

### 5.3 Execution & Result Sync Flow

1. Tests run via CLI (local) or CI/CD pipeline
2. Results stored in local SQLite by default
3. With `--results-server` flag, results push to self-hosted TCM server
4. TCM updates test case status, execution history, flakiness scores, and coverage maps
5. If result-update flag is set, external TCMs (TestRail, Xray) are also updated via API

---

## 6. Architecture Overview

### 6.1 High-Level Components

| Component | Responsibility | Interface | V1/V2 |
|-----------|---------------|-----------|-------|
| Test Generation Engine | LLM-powered Gherkin + step definition generation from feature descriptions and gap analysis | Python API + CLI | V1 |
| Test Execution Runtime | Playwright-based execution for UI and API tests | CLI + Python API | V1 |
| Built-in TCM | Git-native test case management, coverage mapping, execution history, gap analysis | Web UI + CLI | V1 |
| LLM Adapter Layer | Bring-your-own-LLM abstraction supporting OpenAI, Anthropic, Ollama, Azure OpenAI | Config file | V1 |
| Reporter & Result Sync | Captures execution results, syncs to local SQLite or remote server, updates external TCMs | CLI flag + config | V1 |
| Testing Skill Files | Domain-specific prompt strategies for each testing type (functional, etc.) | YAML skill files | V1 |
| Web UI | QA engineer interface for test review, coverage maps, gap analysis, dashboards | Browser (local) | V1 |
| External TCM Connectors | Bidirectional sync with TestRail, Xray, CSV | Config + CLI | V1 |
| Migration Tool | One-command import from existing TCMs | CLI | V1 |
| Load/Performance Testing | k6/Locust integration reusing existing Gherkin scenarios | CLI + config | V2 |
| Mobile Execution | Appium-based mobile test execution | CLI + config | V2 |
| Cloud Hosted TCM | Managed hosted option for teams without infrastructure | SaaS | V2 |

### 6.2 Storage Architecture

| Tier | Storage | Use Case |
|------|---------|----------|
| **Local (default)** | SQLite — stored in `.testweavex/` in project directory | Individual developers running tests locally. Zero config, works offline, instant setup. |
| **Team (self-hosted)** | SQLite behind a lightweight Docker container | Teams wanting shared history across CI/CD and local runs. One `docker-compose` command to start. |
| **Enterprise (V2)** | Cloud-hosted managed service | Teams without infrastructure who want zero-ops setup. Commercial tier. |

> **Default Behaviour:** When no server is configured, all results are stored locally. Adding `--results-server <url> --token <token>` to any CLI command routes results to the configured server.

### 6.3 LLM Adapter Layer

| Provider | Supported Models |
|----------|-----------------|
| OpenAI | GPT-4o, GPT-4-turbo, GPT-3.5-turbo |
| Anthropic | Claude Opus, Claude Sonnet, Claude Haiku |
| Ollama (self-hosted) | Llama 3, Mistral, Phi-3, any locally hosted model |
| Azure OpenAI | All Azure-deployed OpenAI models |
| Custom | Any OpenAI-compatible API endpoint |

The adapter handles prompt construction, context injection (existing Gherkin, Page Object models, feature descriptions), and structured output parsing. The prompting architecture — not the API call — is the core IP.

---

## 7. V1 Scope

### 7.1 What Ships in V1

V1 delivers the core loop end-to-end: from feature description to test execution to coverage visibility. Goal: get the first 50 teams using TestWeaveX and validate the gap analysis flow as the primary hook.

| Feature | Description | Priority | Notes |
|---------|-------------|----------|-------|
| LLM test suggestion | Given a feature description or acceptance criteria, LLM suggests N test scenarios in Gherkin | P0 | Supports all configured LLM providers |
| Engineer review flow | Web UI and CLI interface to accept, discard, and add test scenarios before generation | P0 | Human-in-loop at every step |
| Gherkin generation | Approved scenarios written as `.feature` files in configured repo directory | P0 | Follows BDD best practices |
| Step definition generation | LLM generates Python step definitions, reusing existing modules where possible | P0 | New modules require engineer approval |
| Playwright execution — UI | Execute UI test cases via Playwright (Chrome, Firefox, WebKit) | P0 | Cross-browser support |
| Playwright execution — API | Execute API test cases via Playwright network interception | P0 | REST API support in V1 |
| Playwright recording import | Import Playwright recordings to bootstrap test scenarios | P0 | Reduces blank-page problem |
| Built-in TCM — Web UI | Test case list, status, coverage map, gap report, execution history | P0 | Local-first, browser-based |
| Built-in TCM — CLI | `tw list`, `tw status`, `tw gaps`, `tw history` commands | P0 | Full CLI parity with Web UI |
| Local SQLite storage | Default result storage, zero config | P0 | Auto-created on first run |
| Result server sync | Push results to self-hosted server via `--results-server` flag | P0 | Docker container provided |
| Gap analysis report | Surface manual tests with no automation counterpart, ranked by priority | P0 | **Core USP** |
| Gap-to-automation | Generate automation for selected gaps via LLM from within gap report | P0 | Closes the loop |
| Testing skill files | YAML-based skill configs for each testing type | P0 | 10 skills in V1 |
| External TCM import — CSV | Import test cases from CSV export | P1 | Universal fallback |
| External TCM import — TestRail | Import via TestRail API | P1 | Most common enterprise TCM |
| External TCM import — Xray | Import via Xray API (Jira) | P1 | Common in enterprise |
| Result export — TestRail | Push execution results to TestRail | P1 | Required for enterprise adoption |
| Flakiness detection | Flag tests with inconsistent pass/fail pattern across runs | P1 | Requires 3+ run history |
| Coverage trend dashboard | Sprint-over-sprint coverage improvement tracking | P1 | Web UI only |
| Acceptance criteria import | Parse acceptance criteria from plain text or structured YAML | P1 | Enables new feature flow |
| Integration test suggestions | LLM suggests integration scenarios alongside functional tests | P1 | Prompt strategy in skill file |

### 7.2 Explicitly Out of V1

- Mobile test execution (Appium) — V2
- Load and stress testing (k6/Locust integration) — V2
- Security testing automation — V2
- Performance test case generation — V2
- Cloud-hosted TCM — V2
- External TCM connectors beyond TestRail and Xray — V2
- AI-powered test prioritisation and risk-based selection — V2
- Visual regression testing — V2

---

## 8. Testing Skills Framework

TestWeaveX uses a YAML-based skill file system to encode domain-specific testing knowledge. Each skill file contains LLM prompt strategies, assertion patterns, data setup guidance, and example scenarios for a specific testing type. Skills are composable — multiple skills can apply to a single test session.

### V1 Built-in Skills (10)

| Skill Path | Category | What It Generates |
|-----------|----------|-------------------|
| `functional/smoke` | Functional | Critical path scenarios covering must-work flows. Fast execution, high confidence. |
| `functional/sanity` | Functional | Narrow tests confirming recent changes haven't broken adjacent functionality. |
| `functional/happy_path` | Functional | End-to-end scenarios following the intended user journey without errors. |
| `functional/edge_cases` | Functional | Boundary value, upper/lower bound, and null/empty input scenarios. |
| `functional/data_driven` | Functional | Parameterised scenarios using data tables for multiple input/output combinations. |
| `functional/integration` | Functional | Cross-service and cross-module interaction scenarios. Suggests which services to mock vs. call live. |
| `functional/system` | Functional | Full system scenarios spanning multiple components and layers. |
| `functional/e2e` | Functional | Complete user journey scenarios from entry point to completion, including third-party integrations. |
| `nonfunctional/accessibility` | Non-Functional | WCAG 2.1 AA compliance scenarios using Playwright axe-core integration. |
| `nonfunctional/cross_browser` | Non-Functional | Scenarios tagged for execution across Chrome, Firefox, and WebKit. |

V2 skill additions: `security/owasp_top_10`, `nonfunctional/performance_baseline`, `nonfunctional/load_k6`, `nonfunctional/usability_exploratory`, `nonfunctional/compatibility`.

> **Skill File Format:** Each skill is a YAML file with: `name`, `description`, `prompt_template`, `assertion_patterns`, `data_setup_hints`, `example_scenarios`, and `tags`. Skills are stored in `testweavex/skills/` and are fully customisable by teams.

### Custom Skills

Teams add custom skills by creating YAML files in `testweavex/skills/custom/`. Custom skills override built-ins with the same name. No Python code changes required.

---

## 9. SHAPE Framework Application

| Principle | How TestWeaveX Applies It |
|-----------|--------------------------|
| **S — SOP Driven** | Testing skill files encode standardised operating procedures for each test type. Teams define and share SOPs as YAML — versioned, reviewable, and improvable over time. The LLM follows the SOP; it does not invent its own approach. |
| **H — Human in Loop** | Every LLM-generated test case, every new code module, and every gap closure requires explicit engineer approval before it is committed. The platform is designed so that no automated action is irreversible without a human decision point. |
| **A — Running in Arbitrage** | TestWeaveX captures the gap between what LLMs can generate (80% of test boilerplate in 2% of the time) and what engineers currently spend time on. This arbitrage is the product's economic value proposition — and the moat while it lasts. |
| **P — Product Is No Longer the Mode** | TestWeaveX's endgame is infrastructure, not a product. It embeds into CI/CD pipelines, lives in the repo, and runs invisibly. The goal is for teams to forget it is there — because it just works. |
| **E — Staying Employable** | TestWeaveX is explicitly positioned as a 10x lever for QA engineers, not a replacement. The tool amplifies QA expertise — engineers who use it produce more coverage, catch more gaps, and move faster. |

---

## 10. CLI Reference (V1)

The TestWeaveX CLI is the primary interface for developers and CI/CD pipelines. All commands follow the `tw <command> [options]` pattern. The `tw` command is 100% pytest-compatible — every pytest flag works unchanged.

| Command | Description | Key Options |
|---------|-------------|-------------|
| `tw init` | Initialise TestWeaveX in a project directory, create config file and skills folder | `--llm-provider`, `--tcm-url` |
| `tw generate` | Generate test cases from feature description or acceptance criteria file | `--feature`, `--skill`, `--llm`, `--output` |
| `tw run` | Execute test suite or specific feature file | `--suite`, `--tags`, `--browser`, `--results-server`, `--token` |
| `tw gaps` | Run gap analysis and display unautomated test cases ranked by priority | `--tcm`, `--output`, `--generate` |
| `tw import` | Import test cases from external TCM or CSV | `--source`, `--format`, `--map` |
| `tw status` | Show current coverage map and execution summary | `--format (table/json/html)` |
| `tw history` | Show execution history for a test case or suite | `--id`, `--last-n`, `--format` |
| `tw sync` | Push execution results to external TCM | `--tcm`, `--run-id`, `--update-status` |
| `tw serve` | Start local Web UI server | `--port (default: 8080)`, `--host` |
| `tw migrate` | Migrate from an external TCM to built-in TCM | `--source`, `--format`, `--dry-run` |

**Example CI/CD pipeline usage (GitHub Actions):**

```yaml
- name: Run tests
  run: |
    tw run --suite regression \
           --results-server ${{ secrets.TW_SERVER }} \
           --token ${{ secrets.TW_TOKEN }} \
           --sync-tcm testrail
```

---

## 11. Open Source Strategy

### 11.1 Repository Structure

- Core library: `testweavex` (PyPI) — MIT licence
- GitHub organisation: `github.com/testweavex`
- Repositories: `testweavex` (core), `testweavex-server` (Docker), `testweavex-skills` (community skills), `testweavex-docs` (Docusaurus site)

### 11.2 Contribution Model

- Skill files are the primary community contribution surface — low barrier, high value
- External TCM connectors as community-maintained plugins
- LLM adapter contributions for new providers
- Core execution runtime and TCM maintained by core team

### 11.3 Commercial Layer (V2)

- Hosted TestWeaveX Cloud — managed result server, no infrastructure
- Enterprise SSO, RBAC, audit logs, on-premise support
- Deep integrations with enterprise TCMs (qTest, Azure DevOps, PractiTest) as paid connectors
- Priority support and SLA packages

> **Moat:** The defensible asset is not the code — it is the community-built skill file library, the quality of the prompting architecture, and the ecosystem of TCM connectors. These compound over time in ways that a fork cannot replicate quickly.

---

## 12. Success Metrics

### 12.1 V1 Launch Targets (6 months post-release)

| Metric | Target |
|--------|--------|
| PyPI downloads | 5,000+ per month |
| GitHub stars | 500+ |
| Active teams using TestWeaveX | 50+ teams running in CI/CD |
| Community skill files contributed | 5+ beyond core 10 |
| External TCM integrations | TestRail + Xray functional |
| Gap analysis adoption | 70%+ of active teams running gap reports |

### 12.2 Product Health Metrics

| Metric | Definition |
|--------|-----------|
| Time to first gap report | Minutes from install to seeing first gap analysis result. Target: under 10 minutes. |
| Test generation acceptance rate | % of LLM-suggested tests accepted by engineers. Target: 60%+. Below 40% signals prompt quality issues. |
| Coverage gap closure rate | % of surfaced gaps that result in automated tests within 2 sprints. Target: 40%+. |
| Flakiness rate of generated tests | % of LLM-generated tests flagged as flaky after 5 runs. Target: under 15%. |
| CI/CD adoption rate | % of active teams using `--results-server` in pipelines. Target: 80%+ within 30 days. |

---

## 13. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| LLM-generated tests have high false-positive rate | Engineers lose trust, stop approving suggestions, adoption dies | Human-in-loop approval is mandatory. Track acceptance rate as a health metric. Invest in skill file quality and prompt iteration. |
| Dynamic code generation creates fragile shared modules | Auto-generated classes change and break hundreds of tests simultaneously | New modules require engineer approval before creation. Module versioning and change impact preview before any regeneration. |
| Scope creep — too many testing types before core loop is proven | V1 ships late, nothing works well, early adopters churn | Hard V1 cutoff: 10 skills, 2 TCM connectors, Playwright only. Everything else is roadmapped and dated. |
| Enterprise teams won't trust LLM with internal test code | Blocks enterprise adoption | Self-hosted Ollama support in V1. All LLM calls are local-network-routable. No data leaves the customer's environment unless explicitly configured. |
| Built-in TCM seen as immature vs TestRail | Teams plug in TestRail and ignore built-in TCM | Lean into Git-native differentiation — TestRail can't do this. Ensure built-in TCM is the best experience for greenfield teams. |

---

## 14. Roadmap

| Phase | Timeline | Theme | Key Deliverables |
|-------|----------|-------|-----------------|
| **V1 — Foundation** | Months 1–4 | Core loop, end-to-end | Test generation, Playwright execution, built-in TCM, gap analysis, 10 skill files, CLI + Web UI, TestRail/Xray import, local SQLite + result server |
| **V1.1 — Stability** | Months 5–6 | Polish & adoption | Flakiness detection, coverage trends, Zephyr connector, performance baseline skill, improved LLM acceptance rate, community skill contributions |
| **V2 — Expand** | Months 7–12 | Broaden test types | Mobile (Appium), load testing (k6), security skill (OWASP), visual regression, Azure DevOps connector, cloud-hosted TCM beta |
| **V3 — Platform** | Year 2 | Ecosystem & intelligence | AI test prioritisation, risk-based selection, marketplace for skill files, enterprise SSO/RBAC, managed cloud GA, plugin architecture |

---

## 15. Appendix: Key Decisions Log

These decisions were made during product definition and should not be revisited without strong evidence.

| Decision | Rationale |
|----------|-----------|
| **Built-in TCM is first-class, not a fallback** | The unified platform story only works if the TCM is excellent. A fallback TCM creates a two-tier experience and weakens the core positioning. |
| **LLM is a coworker, not an autopilot** | Trust is the product. Engineers who feel replaced disengage. Engineers who feel empowered advocate. The human-in-loop model is non-negotiable. |
| **Git-native feature files (not database-stored)** | Test cases and code drift apart in every database-first TCM. Git-native eliminates this class of problem entirely. |
| **Local SQLite default, server opt-in** | Zero-config start is the primary adoption lever. Forcing a server setup in V1 kills weekend experiments that become team standards. |
| **Open source core, commercial cloud/enterprise** | The moat is community and ecosystem, not the codebase. Closed source would slow adoption and kill the skill file contribution model. |
| **Playwright only in V1 (no Selenium, no Appium)** | Playwright is the modern standard and supports UI + API. Adding Selenium adds maintenance without adding users. Appium (mobile) is V2. |
| **Bring your own LLM (no bundled model)** | Enterprise security requirements make a bundled cloud LLM a blocker. Self-hosted Ollama support in V1 removes the biggest enterprise objection. |

---

*See also: [`CLAUDE.md`](../CLAUDE.md) for quick reference | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) for technical spec*
