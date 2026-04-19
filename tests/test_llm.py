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
