# TestWeaveX Phase 3 — Generation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the generation engine layer — `GenerationEngine`, `GherkinFormatter`, `FeatureFileWriter`, `StepMatcher`, and `StepDefinitionGenerator` — so `tw generate` can produce reviewed `.feature` files and stub step definitions end-to-end.

**Architecture:** `GenerationEngine.run()` is a single synchronous pipeline: it calls the LLM adapter, presents results via a `ReviewCallback` protocol (Rich terminal or dry-run), writes approved scenarios to `.feature` files, scans existing step patterns, and generates stub implementations for new steps. All filesystem writes are skipped when `dry_run=True`.

**Tech Stack:** Python 3.11+, Pydantic v2, Rich 13+, pytest-bdd (step decorator scanning via regex), pytest + tmp_path for tests.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `testweavex/core/models.py` | Modify | Append `GenerationResult` model |
| `testweavex/core/config.py` | Modify | Add `features_dir`, `step_defs_dir` to `TestWeaveXConfig` + `load_config()` |
| `testweavex/generation/__init__.py` | Create | Package marker |
| `testweavex/generation/gherkin.py` | Create | `GherkinFormatter` + `FeatureFileWriter` (append + dedup) |
| `testweavex/generation/codegen.py` | Create | `StepMatcher` (regex scan) + `StepDefinitionGenerator` (classify + write) |
| `testweavex/generation/engine.py` | Create | `ReviewCallback` protocol + `RichReviewCallback` + `GenerationEngine` |
| `testweavex/llm/openai.py` | Modify | Implement `generate_step_definitions` (replace `NotImplementedError`) |
| `testweavex/llm/anthropic.py` | Modify | Implement `generate_step_definitions` (replace `NotImplementedError`) |
| `tests/test_generation.py` | Create | All generation tests (mocked adapter, `tmp_path` filesystem) |

---

## Task 1: GenerationResult model + config fields

**Files:**
- Modify: `testweavex/core/models.py` (append after line 175)
- Modify: `testweavex/core/config.py` (add fields to dataclass + loader)
- Modify: `tests/test_models.py` (append 3 new tests)

- [ ] **Step 1: Write the failing tests**

Open `tests/test_models.py` and append at the end:

```python
def test_generation_result_valid():
    from testweavex.core.models import GenerationResult
    result = GenerationResult(
        written_files=["features/UI/smoke/login.feature"],
        step_files_written=["tests/step_definitions/login_steps.py"],
        reused_steps=3,
        new_steps=2,
        dry_run=False,
        scenarios_approved=2,
        scenarios_total=5,
    )
    assert result.scenarios_approved == 2
    assert result.dry_run is False
    assert result.reused_steps == 3


def test_testweavex_config_has_features_dir():
    from testweavex.core.config import TestWeaveXConfig
    cfg = TestWeaveXConfig()
    assert cfg.features_dir is None


def test_testweavex_config_has_step_defs_dir():
    from testweavex.core.config import TestWeaveXConfig
    cfg = TestWeaveXConfig()
    assert cfg.step_defs_dir is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_models.py::test_generation_result_valid tests/test_models.py::test_testweavex_config_has_features_dir tests/test_models.py::test_testweavex_config_has_step_defs_dir -v
```

Expected: FAIL — `ImportError: cannot import name 'GenerationResult'` and `AttributeError: 'TestWeaveXConfig' object has no attribute 'features_dir'`

- [ ] **Step 3: Append GenerationResult to models.py**

Open `testweavex/core/models.py` and append after the last line:

```python


class GenerationResult(BaseModel):
    written_files: list[str]
    step_files_written: list[str]
    reused_steps: int
    new_steps: int
    dry_run: bool
    scenarios_approved: int
    scenarios_total: int
```

- [ ] **Step 4: Add fields to TestWeaveXConfig**

In `testweavex/core/config.py`, replace the `TestWeaveXConfig` dataclass (lines 64–70):

```python
@dataclass
class TestWeaveXConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    tcm: TCMConfig = field(default_factory=TCMConfig)
    gap_analysis: GapAnalysisConfig = field(default_factory=GapAnalysisConfig)
    results_server: Optional[str] = None
    skills_dir: Optional[str] = None
    features_dir: Optional[str] = None
    step_defs_dir: Optional[str] = None
```

Then in `load_config()`, after the `skills_dir` block (after line 109), add:

```python
    if fd := raw.get("features_dir"):
        cfg.features_dir = fd or None

    if sdd := raw.get("step_defs_dir"):
        cfg.step_defs_dir = sdd or None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_models.py::test_generation_result_valid tests/test_models.py::test_testweavex_config_has_features_dir tests/test_models.py::test_testweavex_config_has_step_defs_dir -v
```

Expected: 3 PASSED

- [ ] **Step 6: Run full test suite to check no regressions**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest -v
```

Expected: all existing tests still PASS

- [ ] **Step 7: Commit**

```bash
git add testweavex/core/models.py testweavex/core/config.py tests/test_models.py
git commit -m "feat: add GenerationResult model and features_dir/step_defs_dir config fields"
```

---

## Task 2: GherkinFormatter + FeatureFileWriter

**Files:**
- Create: `testweavex/generation/__init__.py`
- Create: `testweavex/generation/gherkin.py`
- Create: `tests/test_generation.py`

- [ ] **Step 1: Create the generation package marker**

Create `testweavex/generation/__init__.py` as an empty file.

- [ ] **Step 2: Write failing tests**

Create `tests/test_generation.py`:

```python
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from testweavex.core.config import TestWeaveXConfig
from testweavex.core.models import (
    GenerationRequest,
    GenerationResult,
    GenerationResponse,
    Scenario,
    StepDefinition,
    StepDefinitionResponse,
)


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _make_scenario(
    title: str = "Login succeeds",
    gherkin: str = "",
    skill: str = "functional/smoke",
) -> Scenario:
    return Scenario(
        title=title,
        gherkin=gherkin or (
            "Given I am on the login page\n"
            "When I submit valid credentials\n"
            "Then I am logged in"
        ),
        confidence=0.9,
        rationale="Core happy path",
        skill_used=skill,
    )


def _make_request(description: str = "User Login") -> GenerationRequest:
    return GenerationRequest(
        feature_description=description,
        skill_names=["functional/smoke"],
    )


def _make_mock_adapter(
    scenarios: list[Scenario] | None = None,
    step_resp: StepDefinitionResponse | None = None,
) -> MagicMock:
    adapter = MagicMock()
    if scenarios is None:
        scenarios = [_make_scenario()]
    adapter.generate_tests.return_value = GenerationResponse(
        scenarios=scenarios,
        skill_used="functional/smoke",
        llm_model="gpt-4o",
        tokens_used=100,
        generation_time_ms=500,
    )
    if step_resp is None:
        step_resp = StepDefinitionResponse(
            new_steps=[],
            reused_count=0,
            llm_model="gpt-4o",
            tokens_used=50,
        )
    adapter.generate_step_definitions.return_value = step_resp
    return adapter


class AutoApproveCallback:
    def review_scenarios(self, scenarios, dry_run):
        return scenarios

    def review_new_modules(self, steps, dry_run):
        return steps


class RejectAllCallback:
    def review_scenarios(self, scenarios, dry_run):
        return []

    def review_new_modules(self, steps, dry_run):
        return []


# ─── GherkinFormatter ─────────────────────────────────────────────────────────

def test_format_feature_file_contains_feature_header():
    from testweavex.generation.gherkin import GherkinFormatter
    fmt = GherkinFormatter()
    result = fmt.format_feature_file("User Login", [_make_scenario()])
    assert result.startswith("Feature: User Login")


def test_format_feature_file_contains_scenario_heading():
    from testweavex.generation.gherkin import GherkinFormatter
    fmt = GherkinFormatter()
    result = fmt.format_feature_file("User Login", [_make_scenario("SSO login")])
    assert "  Scenario: SSO login" in result


def test_format_feature_file_indents_steps_with_4_spaces():
    from testweavex.generation.gherkin import GherkinFormatter
    fmt = GherkinFormatter()
    result = fmt.format_feature_file("Login", [_make_scenario()])
    assert "    Given I am on the login page" in result


def test_format_feature_file_multiple_scenarios_blank_line_between():
    from testweavex.generation.gherkin import GherkinFormatter
    fmt = GherkinFormatter()
    result = fmt.format_feature_file("Login", [_make_scenario("A"), _make_scenario("B")])
    assert "\n\n" in result


# ─── FeatureFileWriter ────────────────────────────────────────────────────────

def test_resolve_path_default_features_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from testweavex.generation.gherkin import FeatureFileWriter
    cfg = TestWeaveXConfig()
    writer = FeatureFileWriter(cfg)
    p = writer.resolve_path("UI", "functional/smoke", "user_login")
    assert p == tmp_path / "features" / "UI" / "smoke" / "user_login.feature"


def test_resolve_path_custom_features_dir(tmp_path):
    from testweavex.generation.gherkin import FeatureFileWriter
    cfg = TestWeaveXConfig()
    cfg.features_dir = str(tmp_path / "my-features")
    writer = FeatureFileWriter(cfg)
    p = writer.resolve_path("API", "functional/smoke", "login")
    assert p == tmp_path / "my-features" / "API" / "smoke" / "login.feature"


def test_resolve_path_strips_functional_prefix(tmp_path):
    from testweavex.generation.gherkin import FeatureFileWriter
    cfg = TestWeaveXConfig()
    cfg.features_dir = str(tmp_path)
    writer = FeatureFileWriter(cfg)
    p = writer.resolve_path("UI", "functional/happy_path", "checkout")
    assert "happy_path" in str(p)
    assert "functional" not in str(p)


def test_write_creates_feature_file(tmp_path):
    from testweavex.generation.gherkin import FeatureFileWriter
    cfg = TestWeaveXConfig()
    cfg.features_dir = str(tmp_path / "features")
    writer = FeatureFileWriter(cfg)
    paths = writer.write([_make_scenario()], "UI", _make_request(), dry_run=False)
    assert len(paths) == 1
    assert paths[0].exists()
    assert "Feature: User Login" in paths[0].read_text()


def test_write_dry_run_writes_nothing(tmp_path, capsys):
    from testweavex.generation.gherkin import FeatureFileWriter
    cfg = TestWeaveXConfig()
    cfg.features_dir = str(tmp_path / "features")
    writer = FeatureFileWriter(cfg)
    paths = writer.write([_make_scenario()], "UI", _make_request(), dry_run=True)
    assert paths == []
    assert not (tmp_path / "features").exists()
    assert "[dry-run]" in capsys.readouterr().out


def test_write_appends_new_scenarios_to_existing_file(tmp_path):
    from testweavex.generation.gherkin import FeatureFileWriter
    cfg = TestWeaveXConfig()
    cfg.features_dir = str(tmp_path / "features")
    writer = FeatureFileWriter(cfg)
    req = _make_request()
    writer.write([_make_scenario("SSO login")], "UI", req, dry_run=False)
    writer.write([_make_scenario("Password login")], "UI", req, dry_run=False)
    feature_file = (
        tmp_path / "features" / "UI" / "smoke" / "user_login.feature"
    )
    content = feature_file.read_text()
    assert "SSO login" in content
    assert "Password login" in content


def test_write_deduplicates_on_append(tmp_path):
    from testweavex.generation.gherkin import FeatureFileWriter
    cfg = TestWeaveXConfig()
    cfg.features_dir = str(tmp_path / "features")
    writer = FeatureFileWriter(cfg)
    req = _make_request()
    writer.write([_make_scenario("SSO login")], "UI", req, dry_run=False)
    writer.write([_make_scenario("SSO login")], "UI", req, dry_run=False)
    content = (
        tmp_path / "features" / "UI" / "smoke" / "user_login.feature"
    ).read_text()
    assert content.count("Scenario: SSO login") == 1


def test_slugify_converts_spaces_to_underscores():
    from testweavex.generation.gherkin import _slugify
    assert _slugify("User Login") == "user_login"


def test_slugify_removes_special_characters():
    from testweavex.generation.gherkin import _slugify
    assert _slugify("User Login with SSO!") == "user_login_with_sso"


def test_slugify_truncates_to_40_chars():
    from testweavex.generation.gherkin import _slugify
    assert len(_slugify("a" * 50)) <= 40
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_generation.py -v -k "Gherkin or slugify or resolve_path or write_creates or dry_run or appends or deduplicates"
```

Expected: FAIL — `ModuleNotFoundError: No module named 'testweavex.generation'`

- [ ] **Step 4: Implement gherkin.py**

Create `testweavex/generation/gherkin.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from testweavex.core.config import TestWeaveXConfig
from testweavex.core.exceptions import GenerationError
from testweavex.core.models import GenerationRequest, Scenario

_SCENARIO_HEADING_RE = re.compile(r"^\s*Scenario:\s*(.+)$", re.MULTILINE)
_NON_ALNUM_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = _NON_ALNUM_RE.sub("", text)
    text = _WHITESPACE_RE.sub("_", text)
    return text[:40]


class GherkinFormatter:

    def format_feature_file(self, feature_name: str, scenarios: list[Scenario]) -> str:
        lines = [f"Feature: {feature_name}", ""]
        for i, scenario in enumerate(scenarios):
            lines.append(f"  Scenario: {scenario.title}")
            for line in scenario.gherkin.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.lower().startswith("scenario:"):
                    continue
                lines.append(f"    {stripped}")
            if i < len(scenarios) - 1:
                lines.append("")
        return "\n".join(lines) + "\n"


class FeatureFileWriter:

    def __init__(self, config: TestWeaveXConfig) -> None:
        self._config = config

    def _features_root(self) -> Path:
        if self._config.features_dir:
            return Path(self._config.features_dir)
        return Path.cwd() / "features"

    def resolve_path(
        self, category: str, skill_name: str, functionality_name: str
    ) -> Path:
        short_skill = skill_name.split("/")[-1] if "/" in skill_name else skill_name
        return self._features_root() / category / short_skill / f"{functionality_name}.feature"

    def write(
        self,
        scenarios: list[Scenario],
        category: str,
        request: GenerationRequest,
        dry_run: bool,
    ) -> list[Path]:
        if not scenarios:
            return []

        functionality_name = _slugify(request.feature_description)
        skill_name = request.skill_names[0]
        target = self.resolve_path(category, skill_name, functionality_name)
        formatter = GherkinFormatter()

        if target.exists():
            existing_content = target.read_text(encoding="utf-8")
            existing_titles = {
                m.group(1).lower().strip()
                for m in _SCENARIO_HEADING_RE.finditer(existing_content)
            }
            scenarios = [
                s for s in scenarios
                if s.title.lower().strip() not in existing_titles
            ]

        if not scenarios:
            return []

        new_content = formatter.format_feature_file(request.feature_description, scenarios)

        if dry_run:
            print(f"[dry-run] Would write to: {target}")
            print(new_content)
            return []

        try:
            if target.exists():
                existing = target.read_text(encoding="utf-8").rstrip("\n")
                scenario_block = _scenarios_only(new_content)
                target.write_text(
                    existing + "\n\n" + scenario_block + "\n",
                    encoding="utf-8",
                )
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(new_content, encoding="utf-8")
        except OSError as exc:
            raise GenerationError(f"Cannot write feature file {target}: {exc}") from exc

        return [target]


def _scenarios_only(content: str) -> str:
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("Scenario:"):
            return "\n".join(lines[i:])
    return content
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_generation.py -v -k "Gherkin or slugify or resolve_path or write_creates or dry_run or appends or deduplicates"
```

Expected: all targeted tests PASS

- [ ] **Step 6: Commit**

```bash
git add testweavex/generation/__init__.py testweavex/generation/gherkin.py tests/test_generation.py
git commit -m "feat: add GherkinFormatter and FeatureFileWriter with append/dedup support"
```

---

## Task 3: StepMatcher

**Files:**
- Create: `testweavex/generation/codegen.py`
- Modify: `tests/test_generation.py` (append StepMatcher tests)

- [ ] **Step 1: Append failing StepMatcher tests**

Append to `tests/test_generation.py`:

```python
# ─── StepMatcher ──────────────────────────────────────────────────────────────

def test_step_matcher_extracts_given_when_then_patterns(tmp_path):
    from testweavex.generation.codegen import StepMatcher
    step_file = tmp_path / "steps.py"
    step_file.write_text(
        '@given("the user is logged in")\ndef step_a(): pass\n'
        '@when("they click submit")\ndef step_b(): pass\n'
        '@then("the form is submitted")\ndef step_c(): pass\n'
    )
    matcher = StepMatcher()
    patterns = matcher.load_from_dirs([tmp_path])
    assert "the user is logged in" in patterns
    assert "they click submit" in patterns
    assert "the form is submitted" in patterns


def test_step_matcher_empty_directory_returns_empty_set(tmp_path):
    from testweavex.generation.codegen import StepMatcher
    matcher = StepMatcher()
    assert matcher.load_from_dirs([tmp_path]) == set()


def test_step_matcher_nonexistent_dir_is_skipped():
    from testweavex.generation.codegen import StepMatcher
    matcher = StepMatcher()
    result = matcher.load_from_dirs([Path("/nonexistent/path/xyz")])
    assert result == set()


def test_step_matcher_scans_subdirectories(tmp_path):
    from testweavex.generation.codegen import StepMatcher
    sub = tmp_path / "auth"
    sub.mkdir()
    (sub / "login_steps.py").write_text('@given("I am on the login page")\ndef s(): pass\n')
    matcher = StepMatcher()
    patterns = matcher.load_from_dirs([tmp_path])
    assert "I am on the login page" in patterns
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_generation.py -v -k "step_matcher"
```

Expected: FAIL — `ModuleNotFoundError: No module named 'testweavex.generation.codegen'`

- [ ] **Step 3: Implement StepMatcher in codegen.py**

Create `testweavex/generation/codegen.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from testweavex.core.config import TestWeaveXConfig
from testweavex.core.exceptions import GenerationError
from testweavex.core.models import Scenario, StepDefinition, StepDefinitionResponse
from testweavex.llm.base import LLMAdapter

_STEP_DECORATOR_RE = re.compile(
    r'@(?:given|when|then)\s*\(\s*["\'](.+?)["\']\s*\)',
    re.IGNORECASE,
)
_STEP_LINE_RE = re.compile(r"^\s*(given|when|then|and|but)\s+(.+)", re.IGNORECASE)
_PARAM_RE = re.compile(r'(?:"[^"]*"|\{[^}]+\}|\d+)')
_KEYWORD_RE = re.compile(r"^\s*(?:given|when|then|and|but)\s+", re.IGNORECASE)


def _normalize_step(text: str) -> str:
    text = _KEYWORD_RE.sub("", text).lower().strip()
    text = _PARAM_RE.sub("<arg>", text)
    return text


class StepMatcher:

    def load_from_dirs(self, step_dirs: list[Path]) -> set[str]:
        patterns: set[str] = set()
        for d in step_dirs:
            if not d.is_dir():
                continue
            for py_file in sorted(d.rglob("*.py")):
                try:
                    content = py_file.read_text(encoding="utf-8")
                except OSError:
                    continue
                for match in _STEP_DECORATOR_RE.finditer(content):
                    patterns.add(match.group(1))
        return patterns


class StepDefinitionGenerator:
    pass  # implemented in Task 4
```

- [ ] **Step 4: Run StepMatcher tests to verify they pass**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_generation.py -v -k "step_matcher"
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add testweavex/generation/codegen.py tests/test_generation.py
git commit -m "feat: add StepMatcher — scans @given/@when/@then decorators for pattern reuse"
```

---

## Task 4: StepDefinitionGenerator

**Files:**
- Modify: `testweavex/generation/codegen.py` (implement `StepDefinitionGenerator`)
- Modify: `tests/test_generation.py` (append tests)

- [ ] **Step 1: Append failing StepDefinitionGenerator tests**

Append to `tests/test_generation.py`:

```python
# ─── StepDefinitionGenerator ─────────────────────────────────────────────────

def test_analyze_classifies_new_and_reused_steps():
    from testweavex.generation.codegen import StepDefinitionGenerator
    cfg = TestWeaveXConfig()
    gen = StepDefinitionGenerator(MagicMock(), cfg)
    scenario = _make_scenario(
        gherkin=(
            "Given I am on the login page\n"
            "When I submit valid credentials\n"
            "Then I am logged in"
        )
    )
    # "I am on the login page" normalises to match this pattern
    existing = {"I am on the login page"}
    new_steps, reused = gen.analyze([scenario], existing)
    assert reused == 1
    assert len(new_steps) == 2
    assert all(isinstance(s, StepDefinition) for s in new_steps)


def test_analyze_all_matched_returns_no_new_steps():
    from testweavex.generation.codegen import StepDefinitionGenerator
    cfg = TestWeaveXConfig()
    gen = StepDefinitionGenerator(MagicMock(), cfg)
    scenario = _make_scenario(
        gherkin=(
            "Given I am on the login page\n"
            "When I submit valid credentials\n"
            "Then I am logged in"
        )
    )
    existing = {
        "I am on the login page",
        "I submit valid credentials",
        "I am logged in",
    }
    new_steps, reused = gen.analyze([scenario], existing)
    assert new_steps == []
    assert reused == 3


def test_analyze_deduplicates_same_step_across_scenarios():
    from testweavex.generation.codegen import StepDefinitionGenerator
    cfg = TestWeaveXConfig()
    gen = StepDefinitionGenerator(MagicMock(), cfg)
    # Two scenarios with the same "Given" line
    s1 = _make_scenario("A", gherkin="Given I am on the login page\nWhen I do X\nThen Y")
    s2 = _make_scenario("B", gherkin="Given I am on the login page\nWhen I do Z\nThen W")
    new_steps, _ = gen.analyze([s1, s2], set())
    step_texts = [s.step_text for s in new_steps]
    # "Given I am on the login page" should appear only once
    assert sum(1 for t in step_texts if "login page" in t.lower()) == 1


def test_write_step_definitions_dry_run_writes_nothing(tmp_path, capsys):
    from testweavex.generation.codegen import StepDefinitionGenerator
    cfg = TestWeaveXConfig()
    cfg.step_defs_dir = str(tmp_path / "steps")
    gen = StepDefinitionGenerator(MagicMock(), cfg)
    step = StepDefinition(
        step_text="Given I am logged in",
        implementation="@given('I am logged in')\ndef step_logged_in(): pass",
    )
    paths = gen.write_step_definitions([step], dry_run=True)
    assert paths == []
    assert not (tmp_path / "steps").exists()
    assert "[dry-run]" in capsys.readouterr().out


def test_write_step_definitions_creates_new_file(tmp_path):
    from testweavex.generation.codegen import StepDefinitionGenerator
    cfg = TestWeaveXConfig()
    cfg.step_defs_dir = str(tmp_path / "steps")
    gen = StepDefinitionGenerator(MagicMock(), cfg)
    step = StepDefinition(
        step_text="Given I am logged in",
        implementation="@given('I am logged in')\ndef step_logged_in(): pass",
    )
    paths = gen.write_step_definitions([step], dry_run=False)
    assert len(paths) == 1
    assert paths[0].exists()
    content = paths[0].read_text()
    assert "from pytest_bdd import given, when, then" in content
    assert "step_logged_in" in content


def test_write_step_definitions_appends_to_existing_file(tmp_path):
    from testweavex.generation.codegen import StepDefinitionGenerator
    cfg = TestWeaveXConfig()
    cfg.step_defs_dir = str(tmp_path / "steps")
    gen = StepDefinitionGenerator(MagicMock(), cfg)
    step1 = StepDefinition(
        step_text="Given I am logged in",
        implementation="@given('I am logged in')\ndef step1(): pass",
    )
    step2 = StepDefinition(
        step_text="When I click submit",
        implementation="@when('I click submit')\ndef step2(): pass",
    )
    gen.write_step_definitions([step1], dry_run=False)
    gen.write_step_definitions([step2], dry_run=False)
    content = (tmp_path / "steps" / "generated_steps.py").read_text()
    assert "step1" in content
    assert "step2" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_generation.py -v -k "analyze or write_step_def"
```

Expected: FAIL — `AttributeError: 'StepDefinitionGenerator' object has no attribute 'analyze'`

- [ ] **Step 3: Implement StepDefinitionGenerator in codegen.py**

Replace the `class StepDefinitionGenerator: pass` stub in `testweavex/generation/codegen.py` with:

```python
class StepDefinitionGenerator:

    def __init__(self, adapter: LLMAdapter, config: TestWeaveXConfig) -> None:
        self._adapter = adapter
        self._config = config

    def _step_defs_root(self) -> Path:
        if self._config.step_defs_dir:
            return Path(self._config.step_defs_dir)
        return Path.cwd() / "tests" / "step_definitions"

    def analyze(
        self,
        scenarios: list[Scenario],
        existing_patterns: set[str],
    ) -> tuple[list[StepDefinition], int]:
        normalized_existing = {_normalize_step(p) for p in existing_patterns}
        seen: set[str] = set()
        new_steps: list[StepDefinition] = []
        reused_count = 0

        for scenario in scenarios:
            for line in scenario.gherkin.splitlines():
                if not _STEP_LINE_RE.match(line):
                    continue
                step_text = line.strip()
                norm = _normalize_step(step_text)
                if norm in seen:
                    continue
                seen.add(norm)
                if norm in normalized_existing:
                    reused_count += 1
                else:
                    new_steps.append(StepDefinition(step_text=step_text, implementation=""))
        return new_steps, reused_count

    def write_step_definitions(
        self,
        steps: list[StepDefinition],
        dry_run: bool,
    ) -> list[Path]:
        if not steps:
            return []

        default_file = self._step_defs_root() / "generated_steps.py"
        groups: dict[Path, list[StepDefinition]] = {}
        for step in steps:
            if step.requires_new_module and step.module_spec:
                target = self._step_defs_root() / step.module_spec
            else:
                target = default_file
            groups.setdefault(target, []).append(step)

        written: list[Path] = []
        for target, group_steps in groups.items():
            content = _render_steps(group_steps)
            if dry_run:
                print(f"[dry-run] Would write step definitions to: {target}")
                print(content)
                continue
            try:
                if target.exists():
                    existing = target.read_text(encoding="utf-8").rstrip("\n")
                    target.write_text(existing + "\n\n" + content + "\n", encoding="utf-8")
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    header = "from pytest_bdd import given, when, then\n\n"
                    target.write_text(header + content + "\n", encoding="utf-8")
                written.append(target)
            except OSError as exc:
                raise GenerationError(
                    f"Cannot write step definitions to {target}: {exc}"
                ) from exc

        return written


def _render_steps(steps: list[StepDefinition]) -> str:
    lines = []
    for step in steps:
        if step.implementation:
            lines.append(step.implementation)
        else:
            lines.append(f"# Step: {step.step_text}\npass")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_generation.py -v -k "analyze or write_step_def"
```

Expected: all targeted tests PASS

- [ ] **Step 5: Run full generation tests so far**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_generation.py -v
```

Expected: all passing so far PASS

- [ ] **Step 6: Commit**

```bash
git add testweavex/generation/codegen.py tests/test_generation.py
git commit -m "feat: add StepDefinitionGenerator — classifies new/reused steps and writes step def files"
```

---

## Task 5: Implement generate_step_definitions in OpenAI and Anthropic adapters

**Files:**
- Modify: `testweavex/llm/openai.py`
- Modify: `testweavex/llm/anthropic.py`
- Modify: `tests/test_llm.py` (append 3 tests)

- [ ] **Step 1: Append failing adapter tests**

Open `tests/test_llm.py` and append at the end:

```python
# ─── generate_step_definitions ───────────────────────────────────────────────

def _make_scenario_obj(title="Login succeeds"):
    from testweavex.core.models import Scenario
    return Scenario(
        title=title,
        gherkin="Given I am on the login page\nWhen I submit credentials\nThen I am logged in",
        confidence=0.9,
        rationale="test",
        skill_used="functional/smoke",
    )


def test_openai_generate_step_definitions_returns_valid_response(mock_openai_client):
    from testweavex.llm.openai import OpenAIAdapter
    from testweavex.core.models import StepDefinitionResponse
    resp_json = json.dumps({
        "new_steps": [
            {
                "step_text": "Given I am on the login page",
                "implementation": "@given('I am on the login page')\ndef step(): pass",
                "requires_new_module": False,
                "module_spec": None,
            }
        ]
    })
    mock_openai_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=resp_json))],
        usage=MagicMock(total_tokens=80),
    )
    adapter = OpenAIAdapter(_make_llm_config())
    adapter._client = mock_openai_client
    result = adapter.generate_step_definitions([_make_scenario_obj()], ["existing step"])
    assert isinstance(result, StepDefinitionResponse)
    assert len(result.new_steps) == 1
    assert result.reused_count == 1


def test_openai_generate_step_definitions_retries_then_raises(mock_openai_client):
    from testweavex.llm.openai import OpenAIAdapter
    from testweavex.core.exceptions import LLMOutputError
    mock_openai_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="not json"))],
        usage=MagicMock(total_tokens=10),
    )
    adapter = OpenAIAdapter(_make_llm_config())
    adapter._client = mock_openai_client
    with pytest.raises(LLMOutputError):
        adapter.generate_step_definitions([_make_scenario_obj()], [])


def test_anthropic_generate_step_definitions_returns_valid_response(mock_anthropic_client):
    from testweavex.llm.anthropic import AnthropicAdapter
    from testweavex.core.models import StepDefinitionResponse
    resp_json = json.dumps({
        "new_steps": [
            {
                "step_text": "When I submit credentials",
                "implementation": "@when('I submit credentials')\ndef step(): pass",
                "requires_new_module": False,
                "module_spec": None,
            }
        ]
    })
    mock_anthropic_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=resp_json)],
        usage=MagicMock(input_tokens=40, output_tokens=60),
    )
    adapter = AnthropicAdapter(_make_llm_config())
    adapter._client = mock_anthropic_client
    result = adapter.generate_step_definitions([_make_scenario_obj()], [])
    assert isinstance(result, StepDefinitionResponse)
    assert len(result.new_steps) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py -v -k "step_def"
```

Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement generate_step_definitions in openai.py**

In `testweavex/llm/openai.py`, replace the `generate_step_definitions` method (lines 84–87) with:

```python
    def generate_step_definitions(
        self, scenarios: list[Scenario], existing_steps: list[str]
    ) -> StepDefinitionResponse:
        prompt = _build_step_prompt(scenarios, existing_steps)
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
                steps = [StepDefinition(**s) for s in data.get("new_steps", [])]
                tokens = resp.usage.total_tokens if resp.usage else 0
                return StepDefinitionResponse(
                    new_steps=steps,
                    reused_count=len(existing_steps),
                    llm_model=self._config.model,
                    tokens_used=tokens,
                )
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_exc = exc
        raise LLMOutputError(
            f"OpenAI returned invalid step definitions after {self._config.max_retries} attempts"
        ) from last_exc
```

Also add this module-level helper at the bottom of `testweavex/llm/openai.py` (after the class, before end of file):

```python
def _build_step_prompt(scenarios: list[Scenario], existing_steps: list[str]) -> str:
    gherkin_text = "\n\n".join(s.gherkin for s in scenarios)
    existing_text = (
        "\n".join(f"- {s}" for s in existing_steps) if existing_steps else "None"
    )
    return (
        "You are a senior QA engineer generating pytest-bdd step definitions.\n\n"
        f"Feature scenarios:\n{gherkin_text}\n\n"
        f"Already implemented steps (do NOT re-generate these):\n{existing_text}\n\n"
        "Generate step definitions ONLY for steps not listed above.\n"
        'Return JSON: {"new_steps": [{"step_text": "...", "implementation": "...", '
        '"requires_new_module": false, "module_spec": null}]}'
    )
```

- [ ] **Step 4: Implement generate_step_definitions in anthropic.py**

In `testweavex/llm/anthropic.py`, replace the `generate_step_definitions` method (lines 87–90) with:

```python
    def generate_step_definitions(
        self, scenarios: list[Scenario], existing_steps: list[str]
    ) -> StepDefinitionResponse:
        prompt = _build_step_prompt(scenarios, existing_steps)
        last_exc: Exception | None = None
        for _ in range(self._config.max_retries):
            try:
                resp = self._client.messages.create(
                    model=self._config.model,
                    max_tokens=4096,
                    temperature=self._config.temperature,
                    system=_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = resp.content[0].text
                data = json.loads(raw)
                steps = [StepDefinition(**s) for s in data.get("new_steps", [])]
                tokens = resp.usage.input_tokens + resp.usage.output_tokens
                return StepDefinitionResponse(
                    new_steps=steps,
                    reused_count=len(existing_steps),
                    llm_model=self._config.model,
                    tokens_used=tokens,
                )
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_exc = exc
        raise LLMOutputError(
            f"Anthropic returned invalid step definitions after {self._config.max_retries} attempts"
        ) from last_exc
```

Also add this module-level helper at the bottom of `testweavex/llm/anthropic.py`:

```python
def _build_step_prompt(scenarios: list[Scenario], existing_steps: list[str]) -> str:
    gherkin_text = "\n\n".join(s.gherkin for s in scenarios)
    existing_text = (
        "\n".join(f"- {s}" for s in existing_steps) if existing_steps else "None"
    )
    return (
        f"Feature scenarios:\n{gherkin_text}\n\n"
        f"Already implemented steps (do NOT re-generate):\n{existing_text}\n\n"
        "Generate pytest-bdd step definitions ONLY for steps not already implemented.\n"
        'Return JSON: {"new_steps": [{"step_text": "...", "implementation": "...", '
        '"requires_new_module": false, "module_spec": null}]}'
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_llm.py -v -k "step_def"
```

Expected: 3 PASSED

- [ ] **Step 6: Run full test suite**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest -v
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add testweavex/llm/openai.py testweavex/llm/anthropic.py tests/test_llm.py
git commit -m "feat: implement generate_step_definitions in OpenAI and Anthropic adapters"
```

---

## Task 6: GenerationEngine + ReviewCallback

**Files:**
- Create: `testweavex/generation/engine.py`
- Modify: `tests/test_generation.py` (append engine tests)

- [ ] **Step 1: Append failing engine tests**

Append to `tests/test_generation.py`:

```python
# ─── GenerationEngine ─────────────────────────────────────────────────────────

def test_engine_dry_run_returns_result_with_no_files_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from testweavex.generation.engine import GenerationEngine
    cfg = TestWeaveXConfig()
    cfg.features_dir = str(tmp_path / "features")
    engine = GenerationEngine(_make_mock_adapter(), cfg, AutoApproveCallback())
    result = engine.run(_make_request(), category="UI", dry_run=True)
    assert result.dry_run is True
    assert result.written_files == []
    assert not (tmp_path / "features").exists()


def test_engine_run_writes_feature_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from testweavex.generation.engine import GenerationEngine
    cfg = TestWeaveXConfig()
    cfg.features_dir = str(tmp_path / "features")
    engine = GenerationEngine(_make_mock_adapter(), cfg, AutoApproveCallback())
    result = engine.run(_make_request(), category="UI", dry_run=False)
    assert result.scenarios_approved == 1
    assert result.scenarios_total == 1
    assert len(result.written_files) == 1


def test_engine_run_empty_review_returns_early(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from testweavex.generation.engine import GenerationEngine
    cfg = TestWeaveXConfig()
    cfg.features_dir = str(tmp_path / "features")
    engine = GenerationEngine(_make_mock_adapter(), cfg, RejectAllCallback())
    result = engine.run(_make_request(), category="UI", dry_run=False)
    assert result.scenarios_approved == 0
    assert result.written_files == []
    assert result.step_files_written == []


def test_engine_run_partial_approval_filters_scenarios(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from testweavex.generation.engine import GenerationEngine

    class PickOneCallback:
        def review_scenarios(self, scenarios, dry_run):
            return scenarios[:1]
        def review_new_modules(self, steps, dry_run):
            return steps

    scenarios = [
        _make_scenario("Login A"),
        _make_scenario("Login B"),
        _make_scenario("Login C"),
    ]
    cfg = TestWeaveXConfig()
    cfg.features_dir = str(tmp_path / "features")
    engine = GenerationEngine(_make_mock_adapter(scenarios), cfg, PickOneCallback())
    result = engine.run(_make_request(), category="UI", dry_run=False)
    assert result.scenarios_total == 3
    assert result.scenarios_approved == 1


def test_engine_run_counts_reused_steps(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from testweavex.generation.engine import GenerationEngine
    # Create an existing step def file that matches a step in our scenario
    step_dir = tmp_path / "tests" / "step_definitions"
    step_dir.mkdir(parents=True)
    (step_dir / "existing.py").write_text(
        '@given("I am on the login page")\ndef step(): pass\n'
    )
    cfg = TestWeaveXConfig()
    cfg.features_dir = str(tmp_path / "features")
    engine = GenerationEngine(_make_mock_adapter(), cfg, AutoApproveCallback())
    result = engine.run(_make_request(), category="UI", dry_run=False)
    assert result.reused_steps >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_generation.py -v -k "engine"
```

Expected: FAIL — `ModuleNotFoundError: No module named 'testweavex.generation.engine'`

- [ ] **Step 3: Implement engine.py**

Create `testweavex/generation/engine.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from rich.console import Console
from rich.table import Table

from testweavex.core.config import TestWeaveXConfig
from testweavex.core.models import (
    GenerationRequest,
    GenerationResult,
    Scenario,
    StepDefinition,
)
from testweavex.generation.codegen import StepDefinitionGenerator, StepMatcher
from testweavex.generation.gherkin import FeatureFileWriter
from testweavex.llm.base import LLMAdapter


@runtime_checkable
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
    """Interactive Rich terminal review. Auto-approves all in dry-run mode."""

    def __init__(self) -> None:
        self._console = Console()

    def review_scenarios(self, scenarios: list[Scenario], dry_run: bool) -> list[Scenario]:
        if dry_run:
            self._console.print(
                f"[dry-run] {len(scenarios)} scenario(s) would be generated:"
            )
            for i, s in enumerate(scenarios, 1):
                self._console.print(f"  {i}. {s.title} (confidence: {s.confidence:.0%})")
            return scenarios

        table = Table(title="Generated Scenarios", show_lines=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Title")
        table.add_column("Confidence", justify="right")
        table.add_column("Skill", style="dim")
        for i, s in enumerate(scenarios, 1):
            table.add_row(str(i), s.title, f"{s.confidence:.0%}", s.skill_used)
        self._console.print(table)

        choice = self._console.input(
            "Keep which? ([a]ll / [n]one / comma-separated numbers): "
        ).strip().lower()

        if choice in ("a", ""):
            return scenarios
        if choice == "n":
            return []
        try:
            indices = {int(x.strip()) - 1 for x in choice.split(",") if x.strip()}
            return [s for i, s in enumerate(scenarios) if i in indices]
        except ValueError:
            return scenarios

    def review_new_modules(
        self, new_steps: list[StepDefinition], dry_run: bool
    ) -> list[StepDefinition]:
        if dry_run:
            self._console.print(
                f"[dry-run] {len(new_steps)} new step definition(s) would be generated:"
            )
            for step in new_steps:
                self._console.print(f"  - {step.step_text}")
            return new_steps

        self._console.print(
            f"\n[bold]{len(new_steps)} new step definition(s) needed:[/bold]"
        )
        for i, step in enumerate(new_steps, 1):
            self._console.print(f"  {i}. {step.step_text}")

        choice = self._console.input(
            "Generate which? ([a]ll / [n]one / comma-separated numbers): "
        ).strip().lower()

        if choice in ("a", ""):
            return new_steps
        if choice == "n":
            return []
        try:
            indices = {int(x.strip()) - 1 for x in choice.split(",") if x.strip()}
            return [s for i, s in enumerate(new_steps) if i in indices]
        except ValueError:
            return new_steps


class GenerationEngine:

    def __init__(
        self,
        adapter: LLMAdapter,
        config: TestWeaveXConfig,
        callback: ReviewCallback | None = None,
    ) -> None:
        self._adapter = adapter
        self._config = config
        self._callback = callback or RichReviewCallback()

    def run(
        self,
        request: GenerationRequest,
        category: str,
        dry_run: bool = False,
    ) -> GenerationResult:
        gen_resp = self._adapter.generate_tests(request)
        scenarios_total = len(gen_resp.scenarios)

        approved = self._callback.review_scenarios(gen_resp.scenarios, dry_run)
        if not approved:
            return GenerationResult(
                written_files=[],
                step_files_written=[],
                reused_steps=0,
                new_steps=0,
                dry_run=dry_run,
                scenarios_approved=0,
                scenarios_total=scenarios_total,
            )

        writer = FeatureFileWriter(self._config)
        written_paths = writer.write(approved, category, request, dry_run)

        matcher = StepMatcher()
        existing_patterns = matcher.load_from_dirs(self._step_dirs())

        step_gen = StepDefinitionGenerator(self._adapter, self._config)
        new_step_stubs, reused_count = step_gen.analyze(approved, existing_patterns)

        step_files_written: list[Path] = []
        new_steps_count = 0

        if new_step_stubs:
            approved_stubs = self._callback.review_new_modules(new_step_stubs, dry_run)
            if approved_stubs:
                step_resp = self._adapter.generate_step_definitions(
                    approved, list(existing_patterns)
                )
                step_files_written = step_gen.write_step_definitions(
                    step_resp.new_steps, dry_run
                )
                new_steps_count = len(step_resp.new_steps)

        return GenerationResult(
            written_files=[str(p) for p in written_paths],
            step_files_written=[str(p) for p in step_files_written],
            reused_steps=reused_count,
            new_steps=new_steps_count,
            dry_run=dry_run,
            scenarios_approved=len(approved),
            scenarios_total=scenarios_total,
        )

    def _step_dirs(self) -> list[Path]:
        if self._config.step_defs_dir:
            return [Path(self._config.step_defs_dir)]
        return [Path.cwd() / "tests" / "step_definitions"]
```

- [ ] **Step 4: Run engine tests to verify they pass**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest tests/test_generation.py -v -k "engine"
```

Expected: all engine tests PASS

- [ ] **Step 5: Run full test suite**

```bash
/c/Users/panka/anaconda3/envs/remhelper/python.exe -m pytest -v
```

Expected: all tests PASS (60+ tests)

- [ ] **Step 6: Commit**

```bash
git add testweavex/generation/engine.py tests/test_generation.py
git commit -m "feat: add GenerationEngine with ReviewCallback protocol and RichReviewCallback"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** GenerationResult ✓, features_dir/step_defs_dir ✓, ReviewCallback protocol ✓, RichReviewCallback ✓, GenerationEngine.run() ✓, GherkinFormatter ✓, FeatureFileWriter (append+dedup) ✓, StepMatcher ✓, StepDefinitionGenerator ✓, generate_step_definitions in both adapters ✓, dry_run guarantee ✓, all test cases from spec covered ✓
- [x] **Placeholder scan:** No TBD/TODO in any code block. All implementations are complete.
- [x] **Type consistency:** `GenerationResult` used identically in Task 1 and Task 6. `StepDefinition.implementation: str` — Task 4 sets `implementation=""` for stubs, Task 5 sets real implementations. `_normalize_step` defined in codegen.py and used consistently in `StepMatcher` and `StepDefinitionGenerator`. `_slugify` defined in gherkin.py and imported via `from testweavex.generation.gherkin import _slugify` in tests.
