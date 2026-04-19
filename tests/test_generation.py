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
