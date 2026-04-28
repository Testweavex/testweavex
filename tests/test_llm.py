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

    @patch("testweavex.llm.ollama.openai.OpenAI")
    def test_get_llm_adapter_ollama_returns_ollama_adapter(self, _mock):
        from testweavex.llm.base import get_llm_adapter
        from testweavex.llm.ollama import OllamaAdapter

        cfg = _config("openai")
        cfg.llm.provider = "ollama"
        adapter = get_llm_adapter(cfg)
        assert isinstance(adapter, OllamaAdapter)

    @patch("testweavex.llm.azure.openai.AzureOpenAI")
    def test_get_llm_adapter_azure_returns_azure_adapter(self, _mock):
        from testweavex.llm.base import get_llm_adapter
        from testweavex.llm.azure import AzureOpenAIAdapter
        from testweavex.core.config import LLMConfig

        cfg = _config("openai")
        cfg.llm = LLMConfig(
            provider="azure",
            model="gpt-4",
            api_key="key",
            azure_endpoint="https://x.openai.azure.com/",
            api_version="2024-02-01",
            deployment_name="gpt-4-prod",
        )
        adapter = get_llm_adapter(cfg)
        assert isinstance(adapter, AzureOpenAIAdapter)

    def test_get_llm_adapter_unknown_provider_error_message_lists_all_four(self):
        from testweavex.llm.base import get_llm_adapter
        from testweavex.core.exceptions import ConfigError

        cfg = _config("openai")
        cfg.llm.provider = "unknown"
        with pytest.raises(ConfigError) as exc_info:
            get_llm_adapter(cfg)
        msg = str(exc_info.value)
        assert "ollama" in msg
        assert "azure" in msg


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


# ─── generate_step_definitions ───────────────────────────────────────────────

def _make_llm_config():
    return LLMConfig(
        provider="openai",
        model="gpt-4o",
        api_key="test-key",
        temperature=0.3,
        max_retries=3,
        timeout_seconds=30,
    )


@pytest.fixture
def mock_openai_client():
    return MagicMock()


@pytest.fixture
def mock_anthropic_client():
    return MagicMock()


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
    assert result.reused_count == 0


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
    assert mock_openai_client.chat.completions.create.call_count == 3


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


def test_anthropic_generate_step_definitions_retries_then_raises(mock_anthropic_client):
    from testweavex.llm.anthropic import AnthropicAdapter
    from testweavex.core.exceptions import LLMOutputError
    mock_anthropic_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="not json")],
        usage=MagicMock(input_tokens=10, output_tokens=10),
    )
    adapter = AnthropicAdapter(_make_llm_config())
    adapter._client = mock_anthropic_client
    with pytest.raises(LLMOutputError):
        adapter.generate_step_definitions([_make_scenario_obj()], [])
    assert mock_anthropic_client.messages.create.call_count == 3


# ── Ollama adapter tests ───────────────────────────────────────────────────────

class TestOllamaAdapter:

    @patch("testweavex.llm.ollama.SkillLoader")
    @patch("testweavex.llm.ollama.openai.OpenAI")
    def test_ollama_generate_tests_uses_openai_compat_client(
        self, mock_openai_class, mock_loader_class
    ):
        from testweavex.llm.ollama import OllamaAdapter

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _openai_response([SCENARIO_DATA])

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load.return_value = _fake_skill("functional/smoke")

        cfg = _config("openai")
        cfg.llm.provider = "ollama"
        cfg.llm.model = "llama3"

        adapter = OllamaAdapter(cfg.llm)
        request = GenerationRequest(
            feature_description="Login",
            skill_names=["functional/smoke"],
        )
        response = adapter.generate_tests(request)

        assert len(response.scenarios) == 1
        assert response.llm_model == "llama3"

    @patch("testweavex.llm.ollama.openai.OpenAI")
    def test_ollama_uses_default_base_url_when_not_configured(self, mock_openai_class):
        from testweavex.llm.ollama import OllamaAdapter

        cfg = _config("openai")
        cfg.llm.provider = "ollama"
        cfg.llm.model = "llama3"
        cfg.llm.base_url = None

        OllamaAdapter(cfg.llm)

        _, kwargs = mock_openai_class.call_args
        assert kwargs["base_url"] == "http://localhost:11434/v1"

    @patch("testweavex.llm.ollama.openai.OpenAI")
    def test_ollama_uses_custom_base_url_when_configured(self, mock_openai_class):
        from testweavex.llm.ollama import OllamaAdapter

        cfg = _config("openai")
        cfg.llm.provider = "ollama"
        cfg.llm.base_url = "http://my-ollama:11434/v1"

        OllamaAdapter(cfg.llm)

        _, kwargs = mock_openai_class.call_args
        assert kwargs["base_url"] == "http://my-ollama:11434/v1"

    @patch("testweavex.llm.ollama.openai.OpenAI")
    def test_ollama_health_check_returns_false_on_exception(self, mock_openai_class):
        from testweavex.llm.ollama import OllamaAdapter

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("connection refused")

        cfg = _config("openai")
        cfg.llm.provider = "ollama"
        adapter = OllamaAdapter(cfg.llm)

        assert adapter.health_check() is False

    @patch("testweavex.llm.ollama.openai.OpenAI")
    def test_ollama_suggest_gap_automation_returns_generation_response(self, mock_openai_class):
        from testweavex.llm.ollama import OllamaAdapter
        from testweavex.core.models import TestCase, TestType, TestStatus, generate_stable_id
        from datetime import datetime, timezone

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _openai_response([SCENARIO_DATA])

        cfg = _config("openai")
        cfg.llm.provider = "ollama"
        cfg.llm.model = "llama3"
        adapter = OllamaAdapter(cfg.llm)

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        tc = TestCase(
            id="tc-1",
            title="Login with valid creds",
            feature_id=generate_stable_id("features/login.feature"),
            gherkin="Scenario: Login\n  Given I am on login page",
            test_type=TestType.smoke,
            skill="functional/smoke",
            is_automated=False,
            created_at=now,
            updated_at=now,
        )
        response = adapter.suggest_gap_automation(tc)

        assert len(response.scenarios) == 1
        assert response.skill_used == "gap_automation"


# ── Azure adapter tests ───────────────────────────────────────────────────────

def _azure_config():
    return LLMConfig(
        provider="azure",
        model="gpt-4",
        api_key="azure-key",
        temperature=0.3,
        max_retries=3,
        timeout_seconds=30,
        azure_endpoint="https://myorg.openai.azure.com/",
        api_version="2024-02-01",
        deployment_name="gpt-4-prod",
    )


class TestAzureOpenAIAdapter:

    @patch("testweavex.llm.azure.openai.AzureOpenAI")
    def test_azure_raises_config_error_when_endpoint_missing(self, _mock):
        from testweavex.llm.azure import AzureOpenAIAdapter
        from testweavex.core.exceptions import ConfigError

        cfg = _azure_config()
        cfg.azure_endpoint = None
        with pytest.raises(ConfigError, match="azure_endpoint"):
            AzureOpenAIAdapter(cfg)

    @patch("testweavex.llm.azure.openai.AzureOpenAI")
    def test_azure_raises_config_error_when_api_version_missing(self, _mock):
        from testweavex.llm.azure import AzureOpenAIAdapter
        from testweavex.core.exceptions import ConfigError

        cfg = _azure_config()
        cfg.api_version = None
        with pytest.raises(ConfigError, match="api_version"):
            AzureOpenAIAdapter(cfg)

    @patch("testweavex.llm.azure.openai.AzureOpenAI")
    def test_azure_raises_config_error_when_deployment_name_missing(self, _mock):
        from testweavex.llm.azure import AzureOpenAIAdapter
        from testweavex.core.exceptions import ConfigError

        cfg = _azure_config()
        cfg.deployment_name = None
        with pytest.raises(ConfigError, match="deployment_name"):
            AzureOpenAIAdapter(cfg)

    @patch("testweavex.llm.azure.SkillLoader")
    @patch("testweavex.llm.azure.openai.AzureOpenAI")
    def test_azure_generate_tests_uses_deployment_as_model(
        self, mock_azure_class, mock_loader_class
    ):
        from testweavex.llm.azure import AzureOpenAIAdapter

        mock_client = MagicMock()
        mock_azure_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _openai_response([SCENARIO_DATA])

        mock_loader = MagicMock()
        mock_loader_class.return_value = mock_loader
        mock_loader.load.return_value = _fake_skill("functional/smoke")

        adapter = AzureOpenAIAdapter(_azure_config())
        request = GenerationRequest(
            feature_description="Login",
            skill_names=["functional/smoke"],
        )
        response = adapter.generate_tests(request)

        assert len(response.scenarios) == 1
        assert response.llm_model == "gpt-4-prod"
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4-prod"

    @patch("testweavex.llm.azure.openai.AzureOpenAI")
    def test_azure_health_check_returns_false_on_exception(self, mock_azure_class):
        from testweavex.llm.azure import AzureOpenAIAdapter

        mock_client = MagicMock()
        mock_azure_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("auth error")

        adapter = AzureOpenAIAdapter(_azure_config())
        assert adapter.health_check() is False


def _make_test_case() -> "TestCase":
    from testweavex.core.models import TestCase, TestType, generate_stable_id
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return TestCase(
        id="tc-gap",
        title="Login with valid credentials",
        feature_id=generate_stable_id("features/login.feature"),
        gherkin="Scenario: Login\n  Given I am on login page\n  When I enter valid creds\n  Then I am logged in",
        test_type=TestType.smoke,
        skill="functional/smoke",
        is_automated=False,
        created_at=now,
        updated_at=now,
    )


@patch("testweavex.llm.openai.SkillLoader")
@patch("testweavex.llm.openai.openai.OpenAI")
def test_openai_suggest_gap_automation_returns_generation_response(
    mock_openai_class, mock_loader_class
):
    from testweavex.llm.openai import OpenAIAdapter

    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.return_value = _openai_response([SCENARIO_DATA])
    mock_loader_class.return_value = MagicMock()

    adapter = OpenAIAdapter(_config("openai").llm)
    response = adapter.suggest_gap_automation(_make_test_case())

    assert len(response.scenarios) == 1
    assert response.skill_used == "gap_automation"


@patch("testweavex.llm.anthropic.SkillLoader")
@patch("testweavex.llm.anthropic.anthropic.Anthropic")
def test_anthropic_suggest_gap_automation_returns_generation_response(
    mock_anthropic_class, mock_loader_class
):
    from testweavex.llm.anthropic import AnthropicAdapter

    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = _anthropic_response([SCENARIO_DATA])
    mock_loader_class.return_value = MagicMock()

    adapter = AnthropicAdapter(_config("anthropic").llm)
    response = adapter.suggest_gap_automation(_make_test_case())

    assert len(response.scenarios) == 1
    assert response.skill_used == "gap_automation"
