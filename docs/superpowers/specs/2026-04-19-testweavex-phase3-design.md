# TestWeaveX Phase 3 — Generation Engine Design Spec

**Date:** 2026-04-19
**Status:** Approved
**Phase:** 3 of 8
**Builds on:** Phase 1 (core/models.py, storage/sqlite.py), Phase 2 (llm adapters, skill loader)

---

## Goal

Deliver the generation engine layer. After Phase 3, a user can run `tw generate --feature "User Login" --skill functional/smoke --category UI` and receive a reviewed, written `.feature` file plus stub step definitions — all without any LLM output reaching the filesystem without engineer approval. Phase 3 also implements the `generate_step_definitions` stub left in Phase 2.

---

## Key Decisions

1. **Single-session pipeline with `ReviewCallback` protocol.** `GenerationEngine.run()` is one synchronous call. The review gate is injected as a `ReviewCallback` — `RichReviewCallback` for the CLI, a stub for tests. No background threads, no separate process.
2. **`--dry-run` flag follows pytest's `--collect-only` principle.** `dry_run=True` prints everything to stdout and writes nothing. Safe to run in CI.
3. **Feature file path:** `{features_dir}/{category}/{skill_name}/{functionality_name}.feature`. Default `features_dir = Path.cwd() / "features"`. Fully configurable via `testweavex.config.yaml`.
4. **Append, never overwrite.** If a `.feature` file already exists, new approved scenarios are appended after deduplication by title. No existing scenarios are lost.
5. **Step reuse via regex/pattern matching.** `StepMatcher` scans `@given/@when/@then` decorator arguments in existing `.py` files. Steps that fuzzy-match existing patterns are counted as reused; only unmatched steps go to the LLM for implementation.
6. **`generate_step_definitions` implemented in both adapters.** The Phase 2 `NotImplementedError` stubs are replaced with real implementations in this phase.
7. **`GenerationError` for filesystem failures.** Already declared in `core/exceptions.py`. Raised on unwritable paths or unparseable step definition files.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `testweavex/generation/__init__.py` | Create | Package marker |
| `testweavex/generation/engine.py` | Create | `ReviewCallback` protocol + `RichReviewCallback` + `GenerationEngine` |
| `testweavex/generation/gherkin.py` | Create | `GherkinFormatter` + `FeatureFileWriter` |
| `testweavex/generation/codegen.py` | Create | `StepMatcher` + `StepDefinitionGenerator` |
| `testweavex/core/models.py` | Modify | Add `GenerationResult` model |
| `testweavex/core/config.py` | Modify | Add `features_dir` and `step_defs_dir` fields |
| `testweavex/llm/openai.py` | Modify | Implement `generate_step_definitions` |
| `testweavex/llm/anthropic.py` | Modify | Implement `generate_step_definitions` |
| `tests/test_generation.py` | Create | All generation tests (mocked LLM, temp filesystem) |

---

## Section 1 — Architecture & Component Boundaries

```
testweavex/generation/
├── __init__.py
├── engine.py      — GenerationEngine + ReviewCallback protocol + RichReviewCallback
├── gherkin.py     — GherkinFormatter + FeatureFileWriter
└── codegen.py     — StepMatcher (regex reuse) + StepDefinitionGenerator
```

### Data flow

```
CLI → GenerationEngine.run(request, category, dry_run)
    → adapter.generate_tests(request)                      # Phase 2 LLM call
    → callback.review_scenarios(scenarios, dry_run)        # Rich display or dry-run print
    → FeatureFileWriter.write(scenarios, category, request, dry_run)
    → StepMatcher.load_from_dirs(step_defs_dir)            # regex scan existing steps
    → StepDefinitionGenerator.analyze(scenarios, patterns) # match + find new steps
    → callback.review_new_modules(new_steps, dry_run)
    → adapter.generate_step_definitions(scenarios, existing_steps)
    → StepDefinitionGenerator.write_step_definitions(steps, dry_run)
→ GenerationResult
```

Each component has one clear responsibility and communicates through Pydantic models or plain Python types. No component imports from another generation submodule — all cross-component communication goes through `engine.py`.

---

## Section 2 — Component Design Details

### `engine.py`

```python
class ReviewCallback(Protocol):
    def review_scenarios(
        self,
        scenarios: list[Scenario],
        dry_run: bool,
    ) -> list[Scenario]: ...

    def review_new_modules(
        self,
        new_steps: list[StepDefinition],
        dry_run: bool,
    ) -> list[StepDefinition]: ...


class RichReviewCallback:
    """Rich terminal interactive review.

    Displays a table of scenarios with confidence scores. User selects
    which to keep: 'a' = all, 'n' = none, '1,3,5' = pick by number.
    In dry-run mode, prints to stdout and auto-approves all — no prompts.
    """

    def review_scenarios(self, scenarios: list[Scenario], dry_run: bool) -> list[Scenario]: ...
    def review_new_modules(self, new_steps: list[StepDefinition], dry_run: bool) -> list[StepDefinition]: ...


class GenerationEngine:
    def __init__(
        self,
        adapter: LLMAdapter,
        config: TestWeaveXConfig,
        callback: ReviewCallback | None = None,  # defaults to RichReviewCallback
    ) -> None: ...

    def run(
        self,
        request: GenerationRequest,
        category: str,       # e.g. "UI", "API", or user-defined
        dry_run: bool = False,
    ) -> GenerationResult: ...
```

`run()` steps:
1. Call `adapter.generate_tests(request)` → `GenerationResponse`
2. Call `callback.review_scenarios(scenarios, dry_run)` → approved list
3. If approved list is empty → return `GenerationResult` with zeros, no further work
4. Call `FeatureFileWriter.write(approved_scenarios, category, request, dry_run)` → written paths
5. Call `StepMatcher.load_from_dirs(step_dirs)` → existing pattern set
6. Call `StepDefinitionGenerator.analyze(approved_scenarios, patterns)` → `(new_steps, reused_count)`
7. If `new_steps` non-empty: call `callback.review_new_modules(new_steps, dry_run)` → approved steps; then call `adapter.generate_step_definitions(approved_scenarios, list(patterns))` → `StepDefinitionResponse`; then call `StepDefinitionGenerator.write_step_definitions(approved_steps, dry_run)` → written paths
8. Return `GenerationResult`

---

### `gherkin.py`

```python
class GherkinFormatter:
    def format_feature_file(
        self,
        feature_name: str,
        scenarios: list[Scenario],
    ) -> str: ...
    # Returns a well-formatted .feature string.
    # Adds "Feature: {feature_name}" header.
    # Normalises each Scenario.gherkin: consistent 2-space indentation,
    # blank line between scenarios.


class FeatureFileWriter:
    def __init__(self, config: TestWeaveXConfig) -> None: ...

    def resolve_path(
        self,
        category: str,           # e.g. "UI"
        skill_name: str,         # e.g. "functional/smoke" → normalised to "smoke"
        functionality_name: str, # derived from feature_description slug
    ) -> Path: ...
    # Returns: {features_dir}/{category}/{skill_name}/{functionality_name}.feature
    # Default features_dir = Path.cwd() / "features"

    def write(
        self,
        scenarios: list[Scenario],
        category: str,
        request: GenerationRequest,
        dry_run: bool,
    ) -> list[Path]: ...
    # File exists → parse existing scenarios, deduplicate by title, append new ones only.
    # File absent → create parent directories, write fresh.
    # dry_run=True → print resolved path + content to stdout, write nothing, return [].
    # Returns list of paths written.
```

**`functionality_name` derivation:** slugify `request.feature_description` — lowercase, spaces → underscores, strip non-alphanumeric, truncate to 40 chars. Example: `"User Login with SSO!"` → `"user_login_with_sso"`.

**Skill name normalisation:** strip leading category prefix. `"functional/smoke"` → `"smoke"`.

**Append deduplication:** same `_deduplicate` logic as `llm/base.py` — compare by `title.lower().strip()`. Existing scenarios in the file are parsed from the `Scenario:` headings.

---

### `codegen.py`

```python
class StepMatcher:
    """Scans .py files for @given/@when/@then decorators, extracts patterns."""

    def load_from_dirs(self, step_dirs: list[Path]) -> set[str]: ...
    # Reads all .py files in step_dirs recursively.
    # Extracts string/regex arguments from @given/@when/@then decorator calls.
    # Returns set of pattern strings.


class StepDefinitionGenerator:
    def __init__(self, adapter: LLMAdapter, config: TestWeaveXConfig) -> None: ...

    def analyze(
        self,
        scenarios: list[Scenario],
        existing_patterns: set[str],
    ) -> tuple[list[StepDefinition], int]: ...
    # Extracts all step lines (Given/When/Then/And/But) from scenarios' Gherkin.
    # Normalised comparison against existing_patterns.
    # Returns: (new_steps_needing_implementation, reused_count)
    # Does NOT call the LLM — only classifies steps.

    def write_step_definitions(
        self,
        steps: list[StepDefinition],
        dry_run: bool,
    ) -> list[Path]: ...
    # Groups steps by requires_new_module / module_spec.
    # Appends to existing step def files or creates new ones.
    # dry_run=True → prints to stdout, writes nothing, returns [].
    # Default output dir: config.step_defs_dir or "tests/step_definitions/"
```

`StepDefinitionGenerator.analyze()` classifies steps — it does not call the LLM. The LLM call (`adapter.generate_step_definitions`) is made by `GenerationEngine.run()` after review approval, passing the unmatched steps for implementation.

---

## Section 3 — New Models & Config Changes

### `GenerationResult` (append to `core/models.py`)

```python
class GenerationResult(BaseModel):
    written_files: list[str]       # relative paths of .feature files written
    step_files_written: list[str]  # relative paths of step def files written
    reused_steps: int              # steps matched to existing patterns
    new_steps: int                 # new step definitions generated
    dry_run: bool
    scenarios_approved: int
    scenarios_total: int
```

### Config additions (`core/config.py`)

```python
features_dir: str | None = None     # default: "features/" relative to cwd
step_defs_dir: str | None = None    # default: "tests/step_definitions/"
```

YAML example:
```yaml
# testweavex.config.yaml
features_dir: ./features
step_defs_dir: ./tests/step_definitions
```

---

## Section 4 — `generate_step_definitions` Implementation

Both adapters replace the `NotImplementedError` stub with a real implementation.

```python
def generate_step_definitions(
    self,
    scenarios: list[Scenario],
    existing_steps: list[str],
) -> StepDefinitionResponse:
    prompt = _build_step_prompt(scenarios, existing_steps)
    # same retry loop as generate_tests
    # parse JSON → list[StepDefinition]
    # return StepDefinitionResponse(
    #     new_steps=...,
    #     reused_count=len(existing_steps),
    #     llm_model=self._config.model,
    #     tokens_used=...,
    # )
```

`_build_step_prompt()` is a module-level helper in each adapter file (not shared — prompt style differs per provider). It receives the Gherkin text from each scenario and the already-matched step patterns, asking the LLM only to generate implementations for unmatched steps.

**OpenAI prompt style:** `response_format={"type": "json_object"}`, user message only.

**Anthropic prompt style:** `SYSTEM_PROMPT` instructs JSON-only output; unmatched steps listed in user message.

Expected JSON shape from LLM:
```json
{
  "new_steps": [
    {
      "step_text": "the user {name} is logged in",
      "implementation": "@given('the user {name} is logged in')\ndef step_user_logged_in(name):\n    ...",
      "requires_new_module": false,
      "module_spec": null
    }
  ]
}
```

---

## Section 5 — Edge Cases & Error Handling

### `FeatureFileWriter` append behaviour
- File exists → parse existing `Scenario:` headings, deduplicate by title, append only new scenarios
- File absent → create parent directories, write fresh file
- `dry_run=True` → show what would be appended, touch nothing

### Error table

| Situation | Behaviour |
|-----------|-----------|
| LLM returns 0 scenarios | `run()` returns early, `scenarios_total=0`, no files touched |
| User rejects all scenarios in review | Early return, `scenarios_approved=0`, no step generation |
| Feature file directory not writable | Raise `GenerationError` with path in message |
| Step def file not parseable (bad Python) | Log warning, skip append, raise `GenerationError` |
| `generate_step_definitions` exhausts retries | `LLMOutputError` propagates from adapter |
| All steps match existing patterns | `adapter.generate_step_definitions` never called |

### `--dry-run` guarantee
No filesystem writes anywhere in the pipeline. All output goes to stdout via `RichReviewCallback`. Safe to run in CI to preview what would be generated.

---

## Section 6 — Tests (`tests/test_generation.py`)

All tests use mocked LLM adapters and `tmp_path` for filesystem operations. No real API calls.

### `engine.py` tests

```python
test_run_dry_run_returns_result_with_no_files_written
test_run_writes_feature_files_when_not_dry_run
test_run_empty_review_returns_early
test_run_partial_approval_filters_scenarios
test_run_propagates_generation_response_metadata
```

### `gherkin.py` tests

```python
test_format_feature_file_produces_valid_gherkin
test_feature_file_writer_resolve_path_default
test_feature_file_writer_resolve_path_custom_features_dir
test_feature_file_writer_dry_run_writes_nothing
test_feature_file_writer_write_creates_file
test_functionality_name_slugifies_description
test_feature_file_writer_appends_new_scenarios_to_existing_file
test_feature_file_writer_deduplicates_on_append
```

### `codegen.py` tests

```python
test_step_matcher_extracts_patterns_from_py_files
test_step_matcher_empty_dirs_returns_empty_set
test_analyze_returns_new_steps_and_reused_count
test_analyze_all_steps_matched_skips_llm_call
test_write_step_definitions_dry_run_writes_nothing
test_write_step_definitions_creates_file
test_write_step_definitions_appends_to_existing_module
```

### Adapter additions (`tests/test_llm.py`)

```python
test_openai_generate_step_definitions_returns_valid_response
test_openai_generate_step_definitions_retries_on_invalid_json
test_anthropic_generate_step_definitions_returns_valid_response
```

---

## Non-Goals for Phase 3

- `tw generate` CLI command (Phase 4)
- `suggest_gap_automation` implementation (Phase 5)
- Ollama and Azure adapters (later phase)
- Web UI for generation (Phase 6)
- Parallel multi-skill generation (later optimisation)
