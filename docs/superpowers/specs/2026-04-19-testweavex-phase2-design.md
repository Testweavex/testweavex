# TestWeaveX Phase 2 — LLM Adapters & Skill Loader Design Spec

**Date:** 2026-04-19
**Status:** Approved
**Phase:** 2 of 8
**Builds on:** Phase 1 (core/models.py, storage/sqlite.py)

---

## Goal

Deliver the LLM adapter layer and skill file framework. After Phase 2, the system can load any built-in or custom skill YAML, construct a prompt, call OpenAI or Anthropic, and return a validated `GenerationResponse`. No LLM output escapes the adapter as raw text. Multiple skills can be combined in a single generation request.

---

## Key Decisions

1. **Providers in scope:** OpenAI and Anthropic only. Ollama and Azure follow in a later phase.
2. **Testing strategy:** Mock provider SDKs — no real API calls, no keys required in CI.
3. **Skill search order:** config-defined path → project root `testweavex/skills/custom/` → built-ins. First match wins; custom overrides built-in with the same name.
4. **Multi-skill support:** `GenerationRequest` accepts a list of skill names. Each skill runs as a separate LLM call; results are merged and deduplicated before returning.
5. **New models in `core/models.py`:** generation-specific models live alongside storage models since they are the shared contract consumed by Phase 3 (generation engine), Phase 5 (gap analyzer), and Phase 6 (web API).
6. **Retry contract:** adapters retry up to `config.max_retries` on JSON parse or Pydantic `ValidationError`, then raise `LLMOutputError`.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `testweavex/core/models.py` | Modify | Add 5 new generation models |
| `testweavex/llm/__init__.py` | Create | Package marker |
| `testweavex/llm/base.py` | Create | Abstract `LLMAdapter` + `get_llm_adapter()` factory |
| `testweavex/llm/openai.py` | Create | OpenAI adapter implementation |
| `testweavex/llm/anthropic.py` | Create | Anthropic adapter implementation |
| `testweavex/skills/__init__.py` | Create | Package marker |
| `testweavex/skills/loader.py` | Create | `SkillFile` model + `SkillLoader` class |
| `testweavex/skills/builtin/functional/smoke.yaml` | Create | Smoke test skill |
| `testweavex/skills/builtin/functional/sanity.yaml` | Create | Sanity test skill |
| `testweavex/skills/builtin/functional/happy_path.yaml` | Create | Happy path skill |
| `testweavex/skills/builtin/functional/edge_cases.yaml` | Create | Edge cases skill |
| `testweavex/skills/builtin/functional/data_driven.yaml` | Create | Data-driven skill |
| `testweavex/skills/builtin/functional/integration.yaml` | Create | Integration test skill |
| `testweavex/skills/builtin/functional/system.yaml` | Create | System test skill |
| `testweavex/skills/builtin/functional/e2e.yaml` | Create | End-to-end test skill |
| `testweavex/skills/builtin/nonfunctional/accessibility.yaml` | Create | Accessibility skill |
| `testweavex/skills/builtin/nonfunctional/cross_browser.yaml` | Create | Cross-browser skill |
| `tests/test_llm.py` | Create | LLM adapter tests (mocked SDKs) |
| `tests/test_skills.py` | Create | Skill loader tests |

---

## Section 1 — New Pydantic Models (`core/models.py`)

Append these 5 models to the existing `core/models.py`. They extend the shared contract for the generation pipeline.

```python
class GenerationRequest(BaseModel):
    feature_description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    existing_scenarios: list[str] = Field(default_factory=list)
    skill_names: list[str]          # supports 1 or more skills
    n_suggestions: int = 5


class Scenario(BaseModel):
    title: str
    gherkin: str
    confidence: float               # 0.0–1.0, same validator as Gap.priority_score
    rationale: str
    suggested_tags: list[str] = Field(default_factory=list)
    skill_used: str                 # which skill produced this scenario


class GenerationResponse(BaseModel):
    scenarios: list[Scenario]
    skill_used: str                 # comma-joined when multi-skill
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

`Scenario.confidence` validator:
```python
@field_validator("confidence")
@classmethod
def confidence_in_range(cls, v: float) -> float:
    if not 0.0 <= v <= 1.0:
        raise ValueError(f"confidence must be 0.0–1.0, got {v}")
    return v
```

---

## Section 2 — Abstract LLM Adapter (`llm/base.py`)

```python
from abc import ABC, abstractmethod
from testweavex.core.models import (
    GenerationRequest, GenerationResponse,
    Scenario, StepDefinitionResponse, TestCase,
)
from testweavex.core.config import LLMConfig, TestWeaveXConfig
from testweavex.core.exceptions import ConfigError


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


def get_llm_adapter(config: TestWeaveXConfig) -> LLMAdapter:
    from testweavex.llm.openai import OpenAIAdapter
    from testweavex.llm.anthropic import AnthropicAdapter

    provider = config.llm.provider
    if provider == "openai":
        return OpenAIAdapter(config.llm)
    if provider == "anthropic":
        return AnthropicAdapter(config.llm)
    raise ConfigError(f"Unsupported LLM provider: '{provider}'. Choose: openai, anthropic")
```

Imports of concrete adapters are deferred inside the function to avoid circular imports and to ensure that optional SDK dependencies (openai, anthropic) are only imported when actually needed.

---

## Section 3 — OpenAI Adapter (`llm/openai.py`)

```python
import json
import time
from pydantic import ValidationError
import openai

from testweavex.core.config import LLMConfig
from testweavex.core.exceptions import LLMOutputError
from testweavex.core.models import (
    GenerationRequest, GenerationResponse, Scenario,
    StepDefinitionResponse, TestCase,
)
from testweavex.llm.base import LLMAdapter
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
        # Multi-skill: run each skill, merge results
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
        for attempt in range(self._config.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self._config.model,
                    temperature=self._config.temperature,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.choices[0].message.content
                data = json.loads(raw)
                scenarios = [
                    Scenario(**s, skill_used=skill_name)
                    for s in data.get("scenarios", data if isinstance(data, list) else [])
                ]
                tokens = resp.usage.total_tokens if resp.usage else 0
                return scenarios, tokens
            except (json.JSONDecodeError, ValidationError, KeyError) as exc:
                last_exc = exc
        raise LLMOutputError(
            f"OpenAI returned invalid output after {self._config.max_retries} attempts"
        ) from last_exc

    def generate_step_definitions(self, scenarios, existing_steps) -> StepDefinitionResponse:
        # Stub — implemented in Phase 3
        raise NotImplementedError

    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse:
        # Stub — implemented in Phase 5
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


def _deduplicate(scenarios: list[Scenario]) -> list[Scenario]:
    seen: set[str] = set()
    result: list[Scenario] = []
    for s in scenarios:
        key = s.title.lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result
```

---

## Section 4 — Anthropic Adapter (`llm/anthropic.py`)

Same contract as OpenAI. Differences:
- Uses `anthropic.Anthropic(api_key=...)` client
- Calls `client.messages.create(model=..., max_tokens=4096, system=SYSTEM_PROMPT, messages=[...])`
- System prompt instructs JSON-only output
- Parses `response.content[0].text` instead of `choices[0].message.content`
- Token count from `response.usage.input_tokens + response.usage.output_tokens`
- Retry contract identical: up to `max_retries`, then `LLMOutputError`

```python
SYSTEM_PROMPT = (
    "You are a senior QA engineer. Respond ONLY with valid JSON. "
    "No markdown, no explanation, no code fences — just the JSON object."
)
```

`_deduplicate` is shared — import from `testweavex.llm.openai` to avoid duplication.

---

## Section 5 — Skill Loader (`skills/loader.py`)

### `SkillFile` model

```python
class SkillFile(BaseModel):
    name: str                                   # e.g. "functional/smoke"
    display_name: str
    description: str
    prompt_template: str
    assertion_hints: list[str] = Field(default_factory=list)
    data_setup: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    estimated_duration_seconds: int = 60
    priority: int = 3
```

### `SkillLoader` class

```python
class SkillLoader:

    def __init__(self, config: TestWeaveXConfig | None = None) -> None:
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
        # built-ins first (lowest priority)
        for path in sorted(self._builtin_dir.rglob("*.yaml")):
            skill = self._parse(path)
            seen[skill.name] = skill
        # then custom dirs (higher priority — override built-ins)
        for search_dir in self._search_dirs()[:-1]:  # exclude builtin
            for path in sorted(search_dir.rglob("*.yaml")):
                skill = self._parse(path)
                seen[skill.name] = skill
        return list(seen.values())

    def _search_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        if self._config and self._config.skills_dir:
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

---

## Section 6 — Built-in Skill YAML Schema

All 10 skill files follow this schema exactly. Example (`functional/smoke.yaml`):

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

  Return a JSON object: {"scenarios": [{"title": "...", "gherkin": "...",
  "confidence": 0.0-1.0, "rationale": "...", "suggested_tags": [...]}]}

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

The remaining 9 skill files follow the same schema with test-type-appropriate prompt instructions, assertion hints, and tags.

---

## Section 7 — Tests

### `tests/test_llm.py` (all mocked — no API keys needed)

```python
# OpenAI adapter
test_generate_tests_single_skill_returns_valid_response
test_generate_tests_multi_skill_merges_and_deduplicates
test_retries_on_invalid_json_then_raises_llm_output_error   # 3 bad → LLMOutputError
test_retries_then_succeeds                                   # 1 bad, 2nd good → returns
test_health_check_returns_true
test_health_check_returns_false_on_exception

# Anthropic adapter
test_anthropic_generate_tests_returns_valid_response
test_anthropic_retries_on_invalid_json_then_raises

# Factory
test_get_llm_adapter_openai_returns_openai_adapter
test_get_llm_adapter_anthropic_returns_anthropic_adapter
test_get_llm_adapter_unknown_provider_raises_config_error
```

### `tests/test_skills.py` (no LLM needed)

```python
test_load_builtin_smoke_returns_skill_file
test_load_all_10_builtins_valid                  # all 10 load without error
test_custom_skill_overrides_builtin              # custom smoke.yaml wins
test_skill_not_found_raises_skill_not_found_error
test_list_skills_returns_all_builtins
test_list_skills_custom_overrides_builtin_in_list
test_config_path_takes_priority_over_custom      # config dir searched first
test_invalid_yaml_raises_config_error
```

---

## Error Handling

| Situation | Exception |
|-----------|-----------|
| Unknown LLM provider in config | `ConfigError` |
| LLM returns malformed JSON after all retries | `LLMOutputError` |
| Skill file not found in any search location | `SkillNotFoundError` |
| Skill YAML exists but fails Pydantic validation | `ConfigError` |
| LLM API network error | Propagated as `LLMOutputError` wrapping the original |

---

## Config Changes (`core/config.py`)

Add `skills_dir: str | None = None` to `TestWeaveXConfig` to support config-defined skill search path:

```yaml
# testweavex.config.yaml
skills_dir: ./my-team-skills/    # optional — searched before built-ins
```

---

## Non-Goals for Phase 2

- Ollama and Azure adapters (Phase 3 or later)
- Generation engine orchestration (Phase 3)
- Step definition generation (Phase 3)
- `suggest_gap_automation` implementation (Phase 5)
- `tw generate` CLI command (Phase 4)
