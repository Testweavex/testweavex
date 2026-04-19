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
