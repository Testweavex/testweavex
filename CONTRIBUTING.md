# Contributing to TestWeaveX

Thank you for your interest in contributing to TestWeaveX!

## Ways to Contribute

The lowest-barrier entry points are:

- **New skill YAML file** — add a testing pattern (e.g., `functional/performance.yaml`)
- **New LLM adapter** — add support for another provider (Cohere, Mistral, etc.)
- **New TCM connector** — add support for another test management tool
- **Bug fixes** — see [open issues](https://github.com/Testweavex/testweavex/issues)
- **Documentation** — improve README, add examples, fix typos

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend work)
- Git

### Backend

```bash
git clone https://github.com/Testweavex/testweavex
cd testweavex
pip install -e ".[dev]"
pytest tests/ -v
```

### Frontend

```bash
cd frontend
npm install
npm test           # Vitest unit tests
npm run dev        # Dev server on :5173, proxies /api → FastAPI on :8080
npm run build      # Writes production bundle to testweavex/web/static/
```

---

## Branch Naming

```
feat/<description>        # new feature
fix/<description>         # bug fix
docs/<description>        # documentation only
refactor/<description>    # code cleanup, no behaviour change
test/<description>        # test-only change
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Cohere LLM adapter
fix: guard coverage_percentage null in dashboard
docs: add Xray connector setup guide
refactor: extract scoring weights to constants
test: add edge case for gap scoring with zero executions
```

---

## Making a Pull Request

1. Fork the repo and create your branch from `main`
2. Write tests for any new behaviour (`pytest tests/ -v` must pass)
3. Fill in the PR template (GitHub loads it automatically from `.github/pull_request_template.md`) — especially the Design Rules checklist
4. Open a PR against `main`

### PR Design Rules Checklist

These are enforced on every PR regardless of size:

- [ ] No LLM output written to disk without the review gate
- [ ] `generate_stable_id` algorithm is **unchanged** (changing it breaks all existing data)
- [ ] All persistence goes through `StorageRepository` — no direct SQLite or HTTP calls
- [ ] All LLM calls go through `LLMAdapter` — no direct provider SDK imports outside `testweavex/llm/`
- [ ] `tw` still behaves identically to `pytest` for all standard flags

---

## Adding a Skill YAML

Skills live in `testweavex/skills/builtin/`. Create a new file under `functional/` or `nonfunctional/`:

```yaml
# testweavex/skills/builtin/functional/performance.yaml
name: functional/performance
display_name: Performance Tests
description: Generates performance and load test scenarios

prompt_template: |
  You are a senior QA engineer specialising in performance testing.
  Feature: {feature_description}
  Generate {n_suggestions} performance test scenarios.
  Include response time assertions, load conditions, and expected thresholds.
  Return JSON: title, gherkin, confidence, rationale, suggested_tags

assertion_hints:
  - Verify response time is under threshold
  - Verify the system handles the expected number of concurrent users
tags: [performance, nonfunctional]
priority: 4
```

Run `pytest tests/test_skills.py -v` to verify your skill loads and validates correctly.

---

## Adding an LLM Adapter

1. Create `testweavex/llm/yourprovider.py` implementing `LLMAdapter` (see `testweavex/llm/base.py`)
2. Register it in the `get_llm_adapter` factory in `testweavex/llm/base.py`
3. Add an optional dependency to `pyproject.toml` under `[project.optional-dependencies]`
4. Write tests in `tests/test_llm.py`

The adapter **must**:

- Return validated Pydantic objects — never raw LLM text
- Retry up to `max_retries` on JSON validation failures
- Raise `LLMOutputError` after exhausting retries
- Implement `health_check() -> bool`

---

## Adding a TCM Connector

1. Create `testweavex/tcm/yourtool.py` implementing `TCMConnector` (see `testweavex/tcm/base.py`)
2. Register it in `testweavex/tcm/__init__.py` factory function `get_connector`
3. Write tests with mocked HTTP responses in `tests/test_tcm.py`

---

## Design Rules (non-negotiable)

1. **No LLM output reaches the filesystem without engineer approval.** The generation engine always presents suggestions for review before writing any file.
2. **Stable IDs are immutable.** Never change `generate_stable_id` — doing so breaks sync for all existing data.
3. **`StorageRepository` is the only persistence interface.** Components never query SQLite or make HTTP calls directly.
4. **`LLMAdapter` is the only LLM interface.** Never import provider SDKs outside `testweavex/llm/`.
5. **`tw` is pytest.** Every pytest flag works with `tw`. Unknown flags pass through unchanged.
6. **Built-in TCM is first-class.** It is not a fallback to external connectors — it is the primary TCM.

---

## Questions?

Open an [issue](https://github.com/Testweavex/testweavex/issues) or start a [GitHub Discussion](https://github.com/Testweavex/testweavex/discussions).
