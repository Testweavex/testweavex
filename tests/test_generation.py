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
