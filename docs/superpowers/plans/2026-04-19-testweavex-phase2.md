# TestWeaveX Phase 2 — LLM Adapters & Skill Loader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the LLM adapter layer (OpenAI + Anthropic) and skill file framework so the system can load any skill YAML, call an LLM, and return a validated `GenerationResponse` — with multi-skill merge and retry-on-bad-output.

**Architecture:** New Pydantic generation models go into `core/models.py` (shared contract). `_deduplicate` and the abstract `LLMAdapter` live in `llm/base.py`. Concrete adapters (`openai.py`, `anthropic.py`) import from base. `SkillLoader` searches config path → project custom dir → built-ins. All adapter tests mock the provider SDK — no API keys needed.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML 6+, openai SDK, anthropic SDK, unittest.mock (tests only)

**Python executable:** `/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `testweavex/core/models.py` | Modify | Append 5 generation models |
| `testweavex/core/config.py` | Modify | Add `skills_dir` to `TestWeaveXConfig` |
| `testweavex/llm/__init__.py` | Create | Package marker |
| `testweavex/llm/base.py` | Create | `LLMAdapter` ABC + `_deduplicate` + `get_llm_adapter` factory |
| `testweavex/llm/openai.py` | Create | `OpenAIAdapter` — OpenAI chat completions |
| `testweavex/llm/anthropic.py` | Create | `AnthropicAdapter` — Anthropic messages API |
| `testweavex/skills/__init__.py` | Create | Package marker |
| `testweavex/skills/loader.py` | Create | `SkillFile` model + `SkillLoader` class |
| `testweavex/skills/builtin/__init__.py` | Create | Package marker |
| `testweavex/skills/builtin/functional/__init__.py` | Create | Package marker |
| `testweavex/skills/builtin/functional/smoke.yaml` | Create | Smoke test skill |
| `testweavex/skills/builtin/functional/sanity.yaml` | Create | Sanity test skill |
| `testweavex/skills/builtin/functional/happy_path.yaml` | Create | Happy path skill |
| `testweavex/skills/builtin/functional/edge_cases.yaml` | Create | Edge cases skill |
| `testweavex/skills/builtin/functional/data_driven.yaml` | Create | Data-driven skill |
| `testweavex/skills/builtin/functional/integration.yaml` | Create | Integration test skill |
| `testweavex/skills/builtin/functional/system.yaml` | Create | System test skill |
| `testweavex/skills/builtin/functional/e2e.yaml` | Create | End-to-end test skill |
| `testweavex/skills/builtin/nonfunctional/__init__.py` | Create | Package marker |
| `testweavex/skills/builtin/nonfunctional/accessibility.yaml` | Create | Accessibility skill |
| `testweavex/skills/builtin/nonfunctional/cross_browser.yaml` | Create | Cross-browser skill |
| `tests/test_models.py` | Modify | Append generation model tests |
| `tests/test_llm.py` | Create | Adapter + factory tests (all mocked) |
| `tests/test_skills.py` | Create | Skill loader tests |

---

## Task 1: Generation Models

**Files:**
- Modify: `testweavex/core/models.py` (append after `RunSummary`)
- Modify: `tests/test_models.py` (append new test class)

- [ ] **Step 1: Write failing tests for generation models**

Append to `tests/test_models.py`:

```python
class TestGenerationModels:
    def test_generation_request_requires_skill_names(self):
        from testweavex.core.models import GenerationRequest
        req = GenerationRequest(
            feature_description="User login",
            skill_names=["functional/smoke"],
        )
        assert req.skill_names == ["functional/smoke"]
        assert req.n_suggestions == 5
        assert req.acceptance_criteria == []

    def test_generation_request_multi_skill(self):
        from testweavex.core.models import GenerationRequest
        req = GenerationRequest(
            feature_description="User login",
            skill_names=["functional/smoke", "functional/e2e"],
            n_suggestions=3,
        )
        assert len(req.skill_names) == 2

    def test_scenario_confidence_validates_range(self):
        from testweavex.core.models import Scenario
        import pytest
        with pytest.raises(Exception):
            Scenario(
                title="Test",
                gherkin="Given something",
                confidence=1.5,
                rationale="reason",
                skill_used="functional/smoke",
            )

    def test_scenario_valid_construction(self):
        from testweavex.core.models import Scenario
        s = Scenario(
            title="User logs in",
            gherkin="Given I am on login page\nWhen I enter credentials\nThen I am logged in",
            confidence=0.9,
            rationale="Core auth flow",
            suggested_tags=["smoke", "auth"],
            skill_used="functional/smoke",
        )
        assert s.confidence == 0.9
        assert s.skill_used == "functional/smoke"

    def test_generation_response_construction(self):
        from testweavex.core.models import GenerationResponse, Scenario
        s = Scenario(
            title="Test",
            gherkin="Given x\nWhen y\nThen z",
            confidence=0.8,
            rationale="reason",
            skill_used="functional/smoke",
        )
        resp = GenerationResponse(
            scenarios=[s],
            skill_used="functional/smoke",
            llm_model="gpt-4o",
            tokens_used=100,
            generation_time_ms=500,
        )
        assert len(resp.scenarios) == 1
        assert resp.tokens_used == 100

    def test_step_definition_response_construction(self):
        from testweavex.core.models import StepDefinition, StepDefinitionResponse
        step = StepDefinition(
            step_text="I am on the login page",
            implementation="@given('I am on the login page')\ndef step(): pass",
        )
        resp = StepDefinitionResponse(
            new_steps=[step],
            reused_count=2,
            llm_model="gpt-4o",
            tokens_used=80,
        )
        assert resp.reused_count == 2
        assert step.requires_new_module is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_models.py::TestGenerationModels -v
```

Expected: FAIL — `ImportError: cannot import name 'GenerationRequest'`

- [ ] **Step 3: Append the 5 generation models to `testweavex/core/models.py`**

Add after the `RunSummary` class (end of file):

```python
class GenerationRequest(BaseModel):
    feature_description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    existing_scenarios: list[str] = Field(default_factory=list)
    skill_names: list[str]
    n_suggestions: int = 5


class Scenario(BaseModel):
    title: str
    gherkin: str
    confidence: float
    rationale: str
    suggested_tags: list[str] = Field(default_factory=list)
    skill_used: str

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be 0.0–1.0, got {v}")
        return v


class GenerationResponse(BaseModel):
    scenarios: list[Scenario]
    skill_used: str
    llm_model: str
    tokens_used: int
    generation_time_ms: int


class StepDefinition(BaseModel):
    step_text: str
    implementation: str
    requires_new_module: bool = False
    module_spec: str | None = None


class StepDefinitionResponse(BaseModel):
    new_steps: list[StepDefinition]
    reused_count: int
    llm_model: str
    tokens_used: int
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_models.py -v
```

Expected: All tests pass (existing 16 + 6 new = 22 total)

- [ ] **Step 5: Commit**

```bash
git add testweavex/core/models.py tests/test_models.py
git commit -m "feat: generation models — GenerationRequest, Scenario, GenerationResponse, StepDefinition, StepDefinitionResponse"
```

---

## Task 2: Add `skills_dir` to Config

**Files:**
- Modify: `testweavex/core/config.py` (add `skills_dir` field to `TestWeaveXConfig`)

- [ ] **Step 1: Add `skills_dir` field to `TestWeaveXConfig` dataclass**

In `testweavex/core/config.py`, update the `TestWeaveXConfig` dataclass:

```python
@dataclass
class TestWeaveXConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    tcm: TCMConfig = field(default_factory=TCMConfig)
    gap_analysis: GapAnalysisConfig = field(default_factory=GapAnalysisConfig)
    results_server: Optional[str] = None
    skills_dir: Optional[str] = None
```

Also update `load_config` to read `skills_dir` from YAML (add after the `gap_analysis` block):

```python
    if sd := raw.get("skills_dir"):
        cfg.skills_dir = sd or None
```

- [ ] **Step 2: Run full test suite to confirm nothing broke**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/ -v
```

Expected: All 22 tests pass

- [ ] **Step 3: Commit**

```bash
git add testweavex/core/config.py
git commit -m "feat: add skills_dir to TestWeaveXConfig for custom skill search path"
```

---

## Task 3: Skill Loader

**Files:**
- Create: `testweavex/skills/__init__.py`
- Create: `testweavex/skills/loader.py`
- Create: `tests/test_skills.py`

- [ ] **Step 1: Create `tests/test_skills.py` with all skill loader tests**

```python
from __future__ import annotations

import pytest
from pathlib import Path

from testweavex.skills.loader import SkillFile, SkillLoader
from testweavex.core.exceptions import SkillNotFoundError, ConfigError


class TestSkillLoaderBuiltins:
    def test_load_builtin_smoke_returns_skill_file(self):
        loader = SkillLoader()
        skill = loader.load("functional/smoke")
        assert skill.name == "functional/smoke"
        assert skill.display_name != ""
        assert "{feature_description}" in skill.prompt_template

    def test_load_all_10_builtins_valid(self):
        loader = SkillLoader()
        skill_names = [
            "functional/smoke",
            "functional/sanity",
            "functional/happy_path",
            "functional/edge_cases",
            "functional/data_driven",
            "functional/integration",
            "functional/system",
            "functional/e2e",
            "nonfunctional/accessibility",
            "nonfunctional/cross_browser",
        ]
        for name in skill_names:
            skill = loader.load(name)
            assert skill.name == name, f"Expected name={name}, got {skill.name}"

    def test_skill_not_found_raises(self):
        loader = SkillLoader()
        with pytest.raises(SkillNotFoundError):
            loader.load("functional/nonexistent")

    def test_list_skills_returns_all_builtins(self):
        loader = SkillLoader()
        skills = loader.list_skills()
        names = {s.name for s in skills}
        assert "functional/smoke" in names
        assert "nonfunctional/accessibility" in names
        assert len(skills) >= 10


class TestSkillLoaderCustom:
    def test_custom_skill_overrides_builtin(self, tmp_path):
        custom_dir = tmp_path / "testweavex" / "skills" / "custom" / "functional"
        custom_dir.mkdir(parents=True)
        (custom_dir / "smoke.yaml").write_text(
            "name: functional/smoke\n"
            "display_name: Custom Smoke\n"
            "description: Custom override\n"
            "prompt_template: Custom {feature_description} {acceptance_criteria} "
            "{existing_scenarios} {n_suggestions}\n",
            encoding="utf-8",
        )
        loader = SkillLoader()
        # Patch CWD to tmp_path so custom dir is found
        import os
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            skill = loader.load("functional/smoke")
            assert skill.display_name == "Custom Smoke"
        finally:
            os.chdir(old_cwd)

    def test_list_skills_custom_overrides_builtin_in_list(self, tmp_path):
        custom_dir = tmp_path / "testweavex" / "skills" / "custom" / "functional"
        custom_dir.mkdir(parents=True)
        (custom_dir / "smoke.yaml").write_text(
            "name: functional/smoke\n"
            "display_name: Custom Smoke\n"
            "description: Custom\n"
            "prompt_template: {feature_description} {acceptance_criteria} "
            "{existing_scenarios} {n_suggestions}\n",
            encoding="utf-8",
        )
        import os
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            loader = SkillLoader()
            skills = loader.list_skills()
            smoke_skills = [s for s in skills if s.name == "functional/smoke"]
            assert len(smoke_skills) == 1
            assert smoke_skills[0].display_name == "Custom Smoke"
        finally:
            os.chdir(old_cwd)

    def test_config_path_takes_priority_over_custom(self, tmp_path):
        from testweavex.core.config import TestWeaveXConfig, LLMConfig
        config_skills_dir = tmp_path / "config-skills" / "functional"
        config_skills_dir.mkdir(parents=True)
        (config_skills_dir / "smoke.yaml").write_text(
            "name: functional/smoke\n"
            "display_name: Config Smoke\n"
            "description: From config path\n"
            "prompt_template: {feature_description} {acceptance_criteria} "
            "{existing_scenarios} {n_suggestions}\n",
            encoding="utf-8",
        )
        config = TestWeaveXConfig(skills_dir=str(tmp_path / "config-skills"))
        loader = SkillLoader(config=config)
        skill = loader.load("functional/smoke")
        assert skill.display_name == "Config Smoke"

    def test_invalid_yaml_raises_config_error(self, tmp_path):
        custom_dir = tmp_path / "testweavex" / "skills" / "custom" / "functional"
        custom_dir.mkdir(parents=True)
        (custom_dir / "bad.yaml").write_text(
            "name: functional/bad\n"
            "this_is_not_valid_yaml: [unclosed\n",
            encoding="utf-8",
        )
        import os
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            loader = SkillLoader()
            with pytest.raises(ConfigError):
                loader.load("functional/bad")
        finally:
            os.chdir(old_cwd)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_skills.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'testweavex.skills'`

- [ ] **Step 3: Create `testweavex/skills/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Create `testweavex/skills/loader.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from testweavex.core.exceptions import ConfigError, SkillNotFoundError


class SkillFile(BaseModel):
    name: str
    display_name: str
    description: str
    prompt_template: str
    assertion_hints: list[str] = Field(default_factory=list)
    data_setup: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    estimated_duration_seconds: int = 60
    priority: int = 3


class SkillLoader:

    def __init__(self, config=None) -> None:
        self._config = config
        self._builtin_dir = Path(__file__).parent / "builtin"

    def load(self, skill_name: str) -> SkillFile:
        for search_dir in self._search_dirs():
            candidate = search_dir / f"{skill_name}.yaml"
            if candidate.exists():
                return self._parse(candidate)
        raise SkillNotFoundError(f"Skill not found: '{skill_name}'")

    def list_skills(self) -> list[SkillFile]:
        seen: dict[str, SkillFile] = {}
        for path in sorted(self._builtin_dir.rglob("*.yaml")):
            skill = self._parse(path)
            seen[skill.name] = skill
        for search_dir in self._search_dirs()[:-1]:
            if search_dir.exists():
                for path in sorted(search_dir.rglob("*.yaml")):
                    try:
                        skill = self._parse(path)
                        seen[skill.name] = skill
                    except ConfigError:
                        pass
        return list(seen.values())

    def _search_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        if self._config and getattr(self._config, "skills_dir", None):
            dirs.append(Path(self._config.skills_dir))
        dirs.append(Path.cwd() / "testweavex" / "skills" / "custom")
        dirs.append(self._builtin_dir)
        return dirs

    def _parse(self, path: Path) -> SkillFile:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            return SkillFile(**raw)
        except Exception as exc:
            raise ConfigError(f"Invalid skill file {path}: {exc}") from exc
```

- [ ] **Step 5: Run skill tests — expect most to fail (skill YAML files missing)**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_skills.py::TestSkillLoaderBuiltins -v
```

Expected: FAIL — `SkillNotFoundError` because YAML files don't exist yet. `TestSkillLoaderCustom` tests that don't need built-ins may pass.

- [ ] **Step 6: Commit the loader (skills YAML files come next task)**

```bash
git add testweavex/skills/__init__.py testweavex/skills/loader.py tests/test_skills.py
git commit -m "feat: SkillFile model and SkillLoader with 3-level search (config, custom, builtin)"
```

---

## Task 4: Built-in Skill YAML Files

**Files:**
- Create: `testweavex/skills/builtin/__init__.py`
- Create: `testweavex/skills/builtin/functional/__init__.py`
- Create: `testweavex/skills/builtin/nonfunctional/__init__.py`
- Create: all 10 YAML files

- [ ] **Step 1: Create package markers**

Create three empty `__init__.py` files:
- `testweavex/skills/builtin/__init__.py` (empty)
- `testweavex/skills/builtin/functional/__init__.py` (empty)
- `testweavex/skills/builtin/nonfunctional/__init__.py` (empty)

- [ ] **Step 2: Create `testweavex/skills/builtin/functional/smoke.yaml`**

```yaml
name: functional/smoke
display_name: Smoke Testing
description: >
  Critical path scenarios covering must-work flows.
  Fast, high confidence. Run on every deployment.

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

  Return a JSON object:
  {{"scenarios": [{{"title": "...", "gherkin": "...", "confidence": 0.0-1.0, "rationale": "...", "suggested_tags": [...]}}]}}

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

- [ ] **Step 3: Create `testweavex/skills/builtin/functional/sanity.yaml`**

```yaml
name: functional/sanity
display_name: Sanity Testing
description: >
  Post-change regression scenarios covering adjacent functionality.
  Verifies that recent changes have not broken existing features.

prompt_template: |
  You are a senior QA engineer generating sanity test scenarios.

  Feature: {feature_description}
  Acceptance Criteria: {acceptance_criteria}
  Existing scenarios (avoid duplicates): {existing_scenarios}

  Generate {n_suggestions} sanity test scenarios that:
  - Verify adjacent functionality was not broken by recent changes
  - Focus on integration points between components
  - Are quick to run (under 60 seconds each)
  - Follow strict Given/When/Then Gherkin format

  Return a JSON object:
  {{"scenarios": [{{"title": "...", "gherkin": "...", "confidence": 0.0-1.0, "rationale": "...", "suggested_tags": [...]}}]}}

assertion_hints:
  - Verify related features still work after change
  - Check side effects on adjacent modules

data_setup:
  - Use existing test fixtures where possible

tags: [sanity, regression, fast]
estimated_duration_seconds: 60
priority: 2
```

- [ ] **Step 4: Create `testweavex/skills/builtin/functional/happy_path.yaml`**

```yaml
name: functional/happy_path
display_name: Happy Path Testing
description: >
  Scenarios covering the intended user journey without errors.
  Tests the system behaves correctly when used as designed.

prompt_template: |
  You are a senior QA engineer generating happy path test scenarios.

  Feature: {feature_description}
  Acceptance Criteria: {acceptance_criteria}
  Existing scenarios (avoid duplicates): {existing_scenarios}

  Generate {n_suggestions} happy path scenarios that:
  - Cover the primary intended user journey
  - Use valid inputs and expected user behaviour
  - Verify the complete flow from start to finish
  - Follow strict Given/When/Then Gherkin format

  Return a JSON object:
  {{"scenarios": [{{"title": "...", "gherkin": "...", "confidence": 0.0-1.0, "rationale": "...", "suggested_tags": [...]}}]}}

assertion_hints:
  - Verify the complete expected outcome
  - Confirm system state after each major action
  - Validate data persistence where applicable

data_setup:
  - Use realistic but minimal test data
  - Ensure preconditions reflect normal user state

tags: [happy-path, functional]
estimated_duration_seconds: 90
priority: 2
```

- [ ] **Step 5: Create `testweavex/skills/builtin/functional/edge_cases.yaml`**

```yaml
name: functional/edge_cases
display_name: Edge Case Testing
description: >
  Boundary values, null inputs, upper/lower bounds, and unexpected inputs.
  Tests system robustness at the limits of expected behaviour.

prompt_template: |
  You are a senior QA engineer generating edge case test scenarios.

  Feature: {feature_description}
  Acceptance Criteria: {acceptance_criteria}
  Existing scenarios (avoid duplicates): {existing_scenarios}

  Generate {n_suggestions} edge case scenarios that:
  - Test boundary values (min, max, empty, null)
  - Cover unexpected or malformed inputs
  - Test system behaviour at capacity or resource limits
  - Follow strict Given/When/Then Gherkin format

  Return a JSON object:
  {{"scenarios": [{{"title": "...", "gherkin": "...", "confidence": 0.0-1.0, "rationale": "...", "suggested_tags": [...]}}]}}

assertion_hints:
  - Verify appropriate error messages for invalid inputs
  - Check system does not crash on boundary values
  - Confirm graceful degradation under unexpected conditions

data_setup:
  - Use boundary values explicitly (0, -1, max_int, empty string, null)
  - Test with malformed data formats

tags: [edge-cases, boundary, robustness]
estimated_duration_seconds: 60
priority: 3
```

- [ ] **Step 6: Create `testweavex/skills/builtin/functional/data_driven.yaml`**

```yaml
name: functional/data_driven
display_name: Data-Driven Testing
description: >
  Parameterised scenarios using Gherkin Examples tables.
  Tests the same behaviour across multiple data sets efficiently.

prompt_template: |
  You are a senior QA engineer generating data-driven test scenarios.

  Feature: {feature_description}
  Acceptance Criteria: {acceptance_criteria}
  Existing scenarios (avoid duplicates): {existing_scenarios}

  Generate {n_suggestions} data-driven scenarios that:
  - Use Gherkin Scenario Outline with Examples tables
  - Cover at least 3 data combinations per scenario
  - Include valid, invalid, and boundary data rows
  - Follow strict Given/When/Then Gherkin format with <placeholders>

  Return a JSON object:
  {{"scenarios": [{{"title": "...", "gherkin": "...", "confidence": 0.0-1.0, "rationale": "...", "suggested_tags": [...]}}]}}

assertion_hints:
  - Each Examples row should test a distinct behaviour
  - Include at least one row that triggers an error path
  - Validate output format varies correctly with input

data_setup:
  - Define Examples table headers that match step placeholders
  - Include edge values in the data table

tags: [data-driven, parameterised, outline]
estimated_duration_seconds: 120
priority: 3
```

- [ ] **Step 7: Create `testweavex/skills/builtin/functional/integration.yaml`**

```yaml
name: functional/integration
display_name: Integration Testing
description: >
  Cross-service interactions and interface contracts between components.
  Tests that separately developed units work together correctly.

prompt_template: |
  You are a senior QA engineer generating integration test scenarios.

  Feature: {feature_description}
  Acceptance Criteria: {acceptance_criteria}
  Existing scenarios (avoid duplicates): {existing_scenarios}

  Generate {n_suggestions} integration test scenarios that:
  - Test interactions between two or more components or services
  - Verify data flows correctly across boundaries
  - Cover both successful integration and failure propagation
  - Follow strict Given/When/Then Gherkin format

  Return a JSON object:
  {{"scenarios": [{{"title": "...", "gherkin": "...", "confidence": 0.0-1.0, "rationale": "...", "suggested_tags": [...]}}]}}

assertion_hints:
  - Verify data format and schema at integration points
  - Test error propagation between services
  - Confirm retry and timeout behaviour

data_setup:
  - Specify whether to use real or mocked downstream services
  - Define required service states before each scenario

tags: [integration, cross-service]
estimated_duration_seconds: 180
priority: 2
```

- [ ] **Step 8: Create `testweavex/skills/builtin/functional/system.yaml`**

```yaml
name: functional/system
display_name: System Testing
description: >
  Full system test spanning multiple components end-to-end.
  Tests the integrated system against functional requirements.

prompt_template: |
  You are a senior QA engineer generating system test scenarios.

  Feature: {feature_description}
  Acceptance Criteria: {acceptance_criteria}
  Existing scenarios (avoid duplicates): {existing_scenarios}

  Generate {n_suggestions} system test scenarios that:
  - Span the full system stack from UI or API to database
  - Verify functional requirements are met end-to-end
  - Cover main user journeys across multiple components
  - Follow strict Given/When/Then Gherkin format

  Return a JSON object:
  {{"scenarios": [{{"title": "...", "gherkin": "...", "confidence": 0.0-1.0, "rationale": "...", "suggested_tags": [...]}}]}}

assertion_hints:
  - Verify system state is consistent across all components
  - Confirm audit trails and logs reflect operations
  - Validate data integrity end-to-end

data_setup:
  - Use a full system test environment (not mocks)
  - Define required system state and seed data

tags: [system, full-stack]
estimated_duration_seconds: 300
priority: 2
```

- [ ] **Step 9: Create `testweavex/skills/builtin/functional/e2e.yaml`**

```yaml
name: functional/e2e
display_name: End-to-End Testing
description: >
  Complete user journey including third-party integrations.
  Tests the system from a real user's perspective.

prompt_template: |
  You are a senior QA engineer generating end-to-end test scenarios.

  Feature: {feature_description}
  Acceptance Criteria: {acceptance_criteria}
  Existing scenarios (avoid duplicates): {existing_scenarios}

  Generate {n_suggestions} end-to-end scenarios that:
  - Simulate a complete real user journey
  - Include third-party service interactions where applicable
  - Test the UI, API, and backend in a single flow
  - Follow strict Given/When/Then Gherkin format

  Return a JSON object:
  {{"scenarios": [{{"title": "...", "gherkin": "...", "confidence": 0.0-1.0, "rationale": "...", "suggested_tags": [...]}}]}}

assertion_hints:
  - Verify the complete user-visible outcome
  - Confirm emails, notifications, or external side effects
  - Validate third-party integrations respond correctly

data_setup:
  - Use production-like data and environments
  - Configure real or sandbox third-party services

tags: [e2e, user-journey, browser]
estimated_duration_seconds: 600
priority: 1
```

- [ ] **Step 10: Create `testweavex/skills/builtin/nonfunctional/accessibility.yaml`**

```yaml
name: nonfunctional/accessibility
display_name: Accessibility Testing
description: >
  WCAG 2.1 AA compliance scenarios using axe-core.
  Tests that the application is usable by people with disabilities.

prompt_template: |
  You are a senior QA engineer generating accessibility test scenarios.

  Feature: {feature_description}
  Acceptance Criteria: {acceptance_criteria}
  Existing scenarios (avoid duplicates): {existing_scenarios}

  Generate {n_suggestions} accessibility test scenarios that:
  - Cover WCAG 2.1 AA compliance requirements
  - Test keyboard navigation and focus management
  - Verify screen reader compatibility (ARIA labels, roles, landmarks)
  - Test colour contrast and visual presentation
  - Follow strict Given/When/Then Gherkin format

  Return a JSON object:
  {{"scenarios": [{{"title": "...", "gherkin": "...", "confidence": 0.0-1.0, "rationale": "...", "suggested_tags": [...]}}]}}

assertion_hints:
  - Run axe-core and assert zero violations
  - Verify all interactive elements are keyboard-reachable
  - Confirm ARIA attributes are correct and complete

data_setup:
  - Use a real browser (Playwright recommended)
  - Test with a screen reader simulator where possible

tags: [accessibility, a11y, wcag]
estimated_duration_seconds: 120
priority: 2
```

- [ ] **Step 11: Create `testweavex/skills/builtin/nonfunctional/cross_browser.yaml`**

```yaml
name: nonfunctional/cross_browser
display_name: Cross-Browser Testing
description: >
  Chromium, Firefox, and WebKit compatibility scenarios.
  Tests that the application behaves consistently across browsers.

prompt_template: |
  You are a senior QA engineer generating cross-browser test scenarios.

  Feature: {feature_description}
  Acceptance Criteria: {acceptance_criteria}
  Existing scenarios (avoid duplicates): {existing_scenarios}

  Generate {n_suggestions} cross-browser test scenarios that:
  - Are tagged for execution on Chromium, Firefox, and WebKit
  - Focus on rendering, layout, and behaviour differences between browsers
  - Cover CSS, JavaScript API compatibility, and form handling
  - Follow strict Given/When/Then Gherkin format

  Return a JSON object:
  {{"scenarios": [{{"title": "...", "gherkin": "...", "confidence": 0.0-1.0, "rationale": "...", "suggested_tags": [...]}}]}}

assertion_hints:
  - Verify visual layout is consistent across browsers
  - Test JavaScript behaviour with browser-specific APIs
  - Confirm form submission and file upload work in all browsers

data_setup:
  - Use pytest-playwright with --browser chromium --browser firefox --browser webkit
  - Tag scenarios with @chromium @firefox @webkit

tags: [cross-browser, chromium, firefox, webkit]
estimated_duration_seconds: 300
priority: 2
```

- [ ] **Step 12: Run skill loader tests — all should pass now**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_skills.py -v
```

Expected: All 8 tests pass

- [ ] **Step 13: Commit**

```bash
git add testweavex/skills/builtin/ tests/test_skills.py
git commit -m "feat: 10 built-in skill YAML files (8 functional + 2 nonfunctional)"
```

---

## Task 5: LLM Package + Abstract Base + Factory

**Files:**
- Create: `testweavex/llm/__init__.py`
- Create: `testweavex/llm/base.py`
- Create: `tests/test_llm.py` (factory tests only for now)

- [ ] **Step 1: Write failing factory tests in `tests/test_llm.py`**

```python
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from testweavex.core.config import LLMConfig, TestWeaveXConfig
from testweavex.core.exceptions import ConfigError, LLMOutputError
from testweavex.core.models import (
    GenerationRequest,
    GenerationResponse,
    Scenario,
    StepDefinitionResponse,
)
from testweavex.skills.loader import SkillFile


# ── Helpers ──────────────────────────────────────────────────────────────────

def _config(provider: str = "openai") -> TestWeaveXConfig:
    cfg = TestWeaveXConfig()
    cfg.llm = LLMConfig(
        provider=provider,
        model="gpt-4o" if provider in ("openai", "azure") else "claude-sonnet-4-6",
        api_key="test-key",
        temperature=0.3,
        max_retries=3,
        timeout_seconds=30,
    )
    return cfg


def _fake_skill(name: str = "functional/smoke") -> SkillFile:
    return SkillFile(
        name=name,
        display_name="Smoke Testing",
        description="Critical path",
        prompt_template=(
            "Feature: {feature_description}\n"
            "AC: {acceptance_criteria}\n"
            "Existing: {existing_scenarios}\n"
            "Count: {n_suggestions}"
        ),
    )


def _openai_response(scenarios: list[dict], total_tokens: int = 100) -> MagicMock:
    mock = MagicMock()
    mock.choices[0].message.content = json.dumps({"scenarios": scenarios})
    mock.usage.total_tokens = total_tokens
    return mock


def _anthropic_response(scenarios: list[dict], input_tokens: int = 80, output_tokens: int = 40) -> MagicMock:
    mock = MagicMock()
    mock.content[0].text = json.dumps({"scenarios": scenarios})
    mock.usage.input_tokens = input_tokens
    mock.usage.output_tokens = output_tokens
    return mock


SCENARIO_DATA = {
    "title": "User logs in with valid credentials",
    "gherkin": "Given I am on the login page\nWhen I enter valid credentials\nThen I am logged in",
    "confidence": 0.9,
    "rationale": "Core auth flow",
    "suggested_tags": ["smoke", "auth"],
}


# ── Factory tests ─────────────────────────────────────────────────────────────

class TestGetLLMAdapter:
    @patch("testweavex.llm.openai.openai.OpenAI")
    def test_get_llm_adapter_openai_returns_openai_adapter(self, _mock):
        from testweavex.llm.base import get_llm_adapter
        from testweavex.llm.openai import OpenAIAdapter
        adapter = get_llm_adapter(_config("openai"))
        assert isinstance(adapter, OpenAIAdapter)

    @patch("testweavex.llm.anthropic.anthropic.Anthropic")
    def test_get_llm_adapter_anthropic_returns_anthropic_adapter(self, _mock):
        from testweavex.llm.base import get_llm_adapter
        from testweavex.llm.anthropic import AnthropicAdapter
        adapter = get_llm_adapter(_config("anthropic"))
        assert isinstance(adapter, AnthropicAdapter)

    def test_get_llm_adapter_unknown_provider_raises_config_error(self):
        from testweavex.llm.base import get_llm_adapter
        with pytest.raises(ConfigError):
            get_llm_adapter(_config("unknown-provider"))
```

- [ ] **Step 2: Run factory tests to confirm they fail**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py::TestGetLLMAdapter -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'testweavex.llm'`

- [ ] **Step 3: Create `testweavex/llm/__init__.py`**

Empty file.

- [ ] **Step 4: Create `testweavex/llm/base.py`**

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from testweavex.core.config import TestWeaveXConfig
from testweavex.core.exceptions import ConfigError
from testweavex.core.models import (
    GenerationRequest,
    GenerationResponse,
    Scenario,
    StepDefinitionResponse,
    TestCase,
)


class LLMAdapter(ABC):

    @abstractmethod
    def generate_tests(self, request: GenerationRequest) -> GenerationResponse: ...

    @abstractmethod
    def generate_step_definitions(
        self,
        scenarios: list[Scenario],
        existing_steps: list[str],
    ) -> StepDefinitionResponse: ...

    @abstractmethod
    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse: ...

    @abstractmethod
    def health_check(self) -> bool: ...


def _deduplicate(scenarios: list[Scenario]) -> list[Scenario]:
    seen: set[str] = set()
    result: list[Scenario] = []
    for s in scenarios:
        key = s.title.lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def get_llm_adapter(config: TestWeaveXConfig) -> LLMAdapter:
    from testweavex.llm.anthropic import AnthropicAdapter
    from testweavex.llm.openai import OpenAIAdapter

    provider = config.llm.provider
    if provider == "openai":
        return OpenAIAdapter(config.llm)
    if provider == "anthropic":
        return AnthropicAdapter(config.llm)
    raise ConfigError(
        f"Unsupported LLM provider: '{provider}'. Choose: openai, anthropic"
    )
```

- [ ] **Step 5: Run factory tests — they'll still fail because openai.py / anthropic.py don't exist yet**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py::TestGetLLMAdapter -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'testweavex.llm.openai'`

- [ ] **Step 6: Commit base (adapters come in next tasks)**

```bash
git add testweavex/llm/__init__.py testweavex/llm/base.py tests/test_llm.py
git commit -m "feat: LLMAdapter abstract base, _deduplicate, get_llm_adapter factory"
```

---

## Task 6: OpenAI Adapter

**Files:**
- Create: `testweavex/llm/openai.py`
- Modify: `tests/test_llm.py` (append OpenAI test class)

- [ ] **Step 1: Append OpenAI tests to `tests/test_llm.py`**

```python
# ── OpenAI adapter tests ───────────────────────────────────────────────────────

class TestOpenAIAdapter:

    @patch("testweavex.llm.openai.SkillLoader")
    @patch("testweavex.llm.openai.openai.OpenAI")
    def test_generate_tests_single_skill_returns_valid_response(
        self, mock_openai_class, mock_loader_class
    ):
        from testweavex.llm.openai import OpenAIAdapter

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _openai_response([SCENARIO_DATA])

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load.return_value = _fake_skill("functional/smoke")

        adapter = OpenAIAdapter(_config("openai").llm)
        request = GenerationRequest(
            feature_description="User authentication",
            skill_names=["functional/smoke"],
        )
        response = adapter.generate_tests(request)

        assert len(response.scenarios) == 1
        assert response.scenarios[0].title == "User logs in with valid credentials"
        assert response.scenarios[0].skill_used == "functional/smoke"
        assert response.skill_used == "functional/smoke"
        assert response.llm_model == "gpt-4o"
        assert response.tokens_used == 100

    @patch("testweavex.llm.openai.SkillLoader")
    @patch("testweavex.llm.openai.openai.OpenAI")
    def test_generate_tests_multi_skill_merges_and_deduplicates(
        self, mock_openai_class, mock_loader_class
    ):
        from testweavex.llm.openai import OpenAIAdapter

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        duplicate = SCENARIO_DATA.copy()
        e2e_unique = {**SCENARIO_DATA, "title": "Complete checkout flow"}
        mock_client.chat.completions.create.side_effect = [
            _openai_response([SCENARIO_DATA]),
            _openai_response([duplicate, e2e_unique]),
        ]

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load.side_effect = [
            _fake_skill("functional/smoke"),
            _fake_skill("functional/e2e"),
        ]

        adapter = OpenAIAdapter(_config("openai").llm)
        request = GenerationRequest(
            feature_description="Checkout",
            skill_names=["functional/smoke", "functional/e2e"],
        )
        response = adapter.generate_tests(request)

        assert len(response.scenarios) == 2
        titles = [s.title for s in response.scenarios]
        assert "User logs in with valid credentials" in titles
        assert "Complete checkout flow" in titles
        assert response.skill_used == "functional/smoke, functional/e2e"

    @patch("testweavex.llm.openai.SkillLoader")
    @patch("testweavex.llm.openai.openai.OpenAI")
    def test_retries_on_invalid_json_then_raises_llm_output_error(
        self, mock_openai_class, mock_loader_class
    ):
        from testweavex.llm.openai import OpenAIAdapter

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        bad = MagicMock()
        bad.choices[0].message.content = "not valid json {{{"
        bad.usage.total_tokens = 10
        mock_client.chat.completions.create.return_value = bad

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load.return_value = _fake_skill()

        adapter = OpenAIAdapter(_config("openai").llm)
        request = GenerationRequest(
            feature_description="Login",
            skill_names=["functional/smoke"],
        )
        with pytest.raises(LLMOutputError):
            adapter.generate_tests(request)

        assert mock_client.chat.completions.create.call_count == 3  # max_retries=3

    @patch("testweavex.llm.openai.SkillLoader")
    @patch("testweavex.llm.openai.openai.OpenAI")
    def test_retries_then_succeeds(self, mock_openai_class, mock_loader_class):
        from testweavex.llm.openai import OpenAIAdapter

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        bad = MagicMock()
        bad.choices[0].message.content = "bad json"
        bad.usage.total_tokens = 0

        mock_client.chat.completions.create.side_effect = [
            bad,
            _openai_response([SCENARIO_DATA]),
        ]

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load.return_value = _fake_skill()

        adapter = OpenAIAdapter(_config("openai").llm)
        request = GenerationRequest(
            feature_description="Login",
            skill_names=["functional/smoke"],
        )
        response = adapter.generate_tests(request)
        assert len(response.scenarios) == 1
        assert mock_client.chat.completions.create.call_count == 2

    @patch("testweavex.llm.openai.openai.OpenAI")
    def test_health_check_returns_true(self, mock_openai_class):
        from testweavex.llm.openai import OpenAIAdapter
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock()
        adapter = OpenAIAdapter(_config("openai").llm)
        assert adapter.health_check() is True

    @patch("testweavex.llm.openai.openai.OpenAI")
    def test_health_check_returns_false_on_exception(self, mock_openai_class):
        from testweavex.llm.openai import OpenAIAdapter
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("connection error")
        adapter = OpenAIAdapter(_config("openai").llm)
        assert adapter.health_check() is False
```

- [ ] **Step 2: Run OpenAI tests to confirm they fail**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py::TestOpenAIAdapter -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'testweavex.llm.openai'`

- [ ] **Step 3: Create `testweavex/llm/openai.py`**

```python
from __future__ import annotations

import json
import time

import openai
from pydantic import ValidationError

from testweavex.core.config import LLMConfig
from testweavex.core.exceptions import LLMOutputError
from testweavex.core.models import (
    GenerationRequest,
    GenerationResponse,
    Scenario,
    StepDefinitionResponse,
    TestCase,
)
from testweavex.llm.base import LLMAdapter, _deduplicate
from testweavex.skills.loader import SkillLoader


class OpenAIAdapter(LLMAdapter):

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client = openai.OpenAI(
            api_key=config.api_key,
            timeout=config.timeout_seconds,
        )
        self._loader = SkillLoader()

    def generate_tests(self, request: GenerationRequest) -> GenerationResponse:
        all_scenarios: list[Scenario] = []
        total_tokens = 0
        start = time.monotonic()

        for skill_name in request.skill_names:
            skill = self._loader.load(skill_name)
            prompt = skill.prompt_template.format(
                feature_description=request.feature_description,
                acceptance_criteria="\n".join(request.acceptance_criteria),
                existing_scenarios="\n".join(request.existing_scenarios),
                n_suggestions=request.n_suggestions,
            )
            scenarios, tokens = self._call_with_retry(prompt, skill_name)
            all_scenarios.extend(scenarios)
            total_tokens += tokens

        deduped = _deduplicate(all_scenarios)
        elapsed = int((time.monotonic() - start) * 1000)

        return GenerationResponse(
            scenarios=deduped,
            skill_used=", ".join(request.skill_names),
            llm_model=self._config.model,
            tokens_used=total_tokens,
            generation_time_ms=elapsed,
        )

    def _call_with_retry(
        self, prompt: str, skill_name: str
    ) -> tuple[list[Scenario], int]:
        last_exc: Exception | None = None
        for _ in range(self._config.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self._config.model,
                    temperature=self._config.temperature,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.choices[0].message.content
                data = json.loads(raw)
                raw_list = data.get("scenarios", data if isinstance(data, list) else [])
                scenarios = [Scenario(**s, skill_used=skill_name) for s in raw_list]
                tokens = resp.usage.total_tokens if resp.usage else 0
                return scenarios, tokens
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_exc = exc
        raise LLMOutputError(
            f"OpenAI returned invalid output after {self._config.max_retries} attempts"
        ) from last_exc

    def generate_step_definitions(
        self, scenarios: list[Scenario], existing_steps: list[str]
    ) -> StepDefinitionResponse:
        raise NotImplementedError

    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse:
        raise NotImplementedError

    def health_check(self) -> bool:
        try:
            self._client.chat.completions.create(
                model=self._config.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
```

- [ ] **Step 4: Run OpenAI tests + factory tests**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py::TestOpenAIAdapter tests/test_llm.py::TestGetLLMAdapter -v
```

Expected: All 9 tests pass (6 OpenAI + 3 factory — Anthropic factory test still fails)

- [ ] **Step 5: Commit**

```bash
git add testweavex/llm/openai.py tests/test_llm.py
git commit -m "feat: OpenAIAdapter — generate_tests with multi-skill merge and retry"
```

---

## Task 7: Anthropic Adapter

**Files:**
- Create: `testweavex/llm/anthropic.py`
- Modify: `tests/test_llm.py` (append Anthropic test class)

- [ ] **Step 1: Append Anthropic tests to `tests/test_llm.py`**

```python
# ── Anthropic adapter tests ───────────────────────────────────────────────────

class TestAnthropicAdapter:

    @patch("testweavex.llm.anthropic.SkillLoader")
    @patch("testweavex.llm.anthropic.anthropic.Anthropic")
    def test_anthropic_generate_tests_returns_valid_response(
        self, mock_anthropic_class, mock_loader_class
    ):
        from testweavex.llm.anthropic import AnthropicAdapter

        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.create.return_value = _anthropic_response([SCENARIO_DATA])

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load.return_value = _fake_skill("functional/smoke")

        adapter = AnthropicAdapter(_config("anthropic").llm)
        request = GenerationRequest(
            feature_description="User authentication",
            skill_names=["functional/smoke"],
        )
        response = adapter.generate_tests(request)

        assert len(response.scenarios) == 1
        assert response.scenarios[0].title == "User logs in with valid credentials"
        assert response.scenarios[0].skill_used == "functional/smoke"
        assert response.tokens_used == 120  # 80 + 40

    @patch("testweavex.llm.anthropic.SkillLoader")
    @patch("testweavex.llm.anthropic.anthropic.Anthropic")
    def test_anthropic_retries_on_invalid_json_then_raises(
        self, mock_anthropic_class, mock_loader_class
    ):
        from testweavex.llm.anthropic import AnthropicAdapter

        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        bad = MagicMock()
        bad.content[0].text = "not json {{{"
        bad.usage.input_tokens = 10
        bad.usage.output_tokens = 5
        mock_client.messages.create.return_value = bad

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load.return_value = _fake_skill()

        adapter = AnthropicAdapter(_config("anthropic").llm)
        request = GenerationRequest(
            feature_description="Login",
            skill_names=["functional/smoke"],
        )
        with pytest.raises(LLMOutputError):
            adapter.generate_tests(request)

        assert mock_client.messages.create.call_count == 3
```

- [ ] **Step 2: Run Anthropic tests to confirm they fail**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py::TestAnthropicAdapter -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'testweavex.llm.anthropic'`

- [ ] **Step 3: Create `testweavex/llm/anthropic.py`**

```python
from __future__ import annotations

import json
import time

import anthropic
from pydantic import ValidationError

from testweavex.core.config import LLMConfig
from testweavex.core.exceptions import LLMOutputError
from testweavex.core.models import (
    GenerationRequest,
    GenerationResponse,
    Scenario,
    StepDefinitionResponse,
    TestCase,
)
from testweavex.llm.base import LLMAdapter, _deduplicate
from testweavex.skills.loader import SkillLoader

_SYSTEM_PROMPT = (
    "You are a senior QA engineer. Respond ONLY with valid JSON. "
    "No markdown, no explanation, no code fences — just the JSON object."
)


class AnthropicAdapter(LLMAdapter):

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client = anthropic.Anthropic(api_key=config.api_key)
        self._loader = SkillLoader()

    def generate_tests(self, request: GenerationRequest) -> GenerationResponse:
        all_scenarios: list[Scenario] = []
        total_tokens = 0
        start = time.monotonic()

        for skill_name in request.skill_names:
            skill = self._loader.load(skill_name)
            prompt = skill.prompt_template.format(
                feature_description=request.feature_description,
                acceptance_criteria="\n".join(request.acceptance_criteria),
                existing_scenarios="\n".join(request.existing_scenarios),
                n_suggestions=request.n_suggestions,
            )
            scenarios, tokens = self._call_with_retry(prompt, skill_name)
            all_scenarios.extend(scenarios)
            total_tokens += tokens

        deduped = _deduplicate(all_scenarios)
        elapsed = int((time.monotonic() - start) * 1000)

        return GenerationResponse(
            scenarios=deduped,
            skill_used=", ".join(request.skill_names),
            llm_model=self._config.model,
            tokens_used=total_tokens,
            generation_time_ms=elapsed,
        )

    def _call_with_retry(
        self, prompt: str, skill_name: str
    ) -> tuple[list[Scenario], int]:
        last_exc: Exception | None = None
        for _ in range(self._config.max_retries):
            try:
                resp = self._client.messages.create(
                    model=self._config.model,
                    max_tokens=4096,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.content[0].text
                data = json.loads(raw)
                raw_list = data.get("scenarios", data if isinstance(data, list) else [])
                scenarios = [Scenario(**s, skill_used=skill_name) for s in raw_list]
                tokens = resp.usage.input_tokens + resp.usage.output_tokens
                return scenarios, tokens
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_exc = exc
        raise LLMOutputError(
            f"Anthropic returned invalid output after {self._config.max_retries} attempts"
        ) from last_exc

    def generate_step_definitions(
        self, scenarios: list[Scenario], existing_steps: list[str]
    ) -> StepDefinitionResponse:
        raise NotImplementedError

    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse:
        raise NotImplementedError

    def health_check(self) -> bool:
        try:
            self._client.messages.create(
                model=self._config.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False
```

- [ ] **Step 4: Run all LLM tests**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py -v
```

Expected: All 11 tests pass (3 factory + 6 OpenAI + 2 Anthropic)

- [ ] **Step 5: Commit**

```bash
git add testweavex/llm/anthropic.py tests/test_llm.py
git commit -m "feat: AnthropicAdapter — generate_tests with multi-skill merge and retry"
```

---

## Task 8: Final Verification

**Files:** No new files — run full suite and check imports

- [ ] **Step 1: Run the complete test suite**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/ -v
```

Expected: All tests pass (33 existing + 22 new models + 11 LLM + 8 skills = 74 total)

- [ ] **Step 2: Import smoke check**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -c "
from testweavex.core.models import GenerationRequest, Scenario, GenerationResponse, StepDefinition, StepDefinitionResponse
from testweavex.llm.base import LLMAdapter, get_llm_adapter, _deduplicate
from testweavex.skills.loader import SkillFile, SkillLoader
print('Phase 2 import smoke check: OK')
"
```

Expected: `Phase 2 import smoke check: OK`

- [ ] **Step 3: Verify all 10 built-in skills load cleanly**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -c "
from testweavex.skills.loader import SkillLoader
loader = SkillLoader()
skills = loader.list_skills()
print(f'Loaded {len(skills)} built-in skills:')
for s in sorted(skills, key=lambda x: x.name):
    print(f'  {s.name} — {s.display_name}')
"
```

Expected output (10 lines):
```
Loaded 10 built-in skills:
  functional/data_driven — Data-Driven Testing
  functional/e2e — End-to-End Testing
  functional/edge_cases — Edge Case Testing
  functional/happy_path — Happy Path Testing
  functional/integration — Integration Testing
  functional/sanity — Sanity Testing
  functional/smoke — Smoke Testing
  functional/system — System Testing
  nonfunctional/accessibility — Accessibility Testing
  nonfunctional/cross_browser — Cross-Browser Testing
```

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: Phase 2 complete — LLM adapters (OpenAI + Anthropic) and skill loader with 10 built-in skills"
```
