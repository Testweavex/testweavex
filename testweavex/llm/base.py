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


def _build_gap_prompt(test_case: TestCase) -> str:
    return (
        f"Manual test case to automate:\n"
        f"Title: {test_case.title}\n"
        f"Type: {test_case.test_type.value}\n"
        f"Gherkin:\n{test_case.gherkin}\n\n"
        "Generate exactly 1 Gherkin scenario that automates this test case.\n"
        'Return JSON: {"scenarios": [{"title": "...", "gherkin": "...", '
        '"confidence": 0.9, "rationale": "Automates the manual test case.", '
        '"suggested_tags": []}]}'
    )


def get_llm_adapter(config: TestWeaveXConfig) -> LLMAdapter:
    provider = config.llm.provider
    if provider == "openai":
        from testweavex.llm.openai import OpenAIAdapter
        return OpenAIAdapter(config.llm)
    if provider == "anthropic":
        from testweavex.llm.anthropic import AnthropicAdapter
        return AnthropicAdapter(config.llm)
    if provider == "ollama":
        from testweavex.llm.ollama import OllamaAdapter
        return OllamaAdapter(config.llm)
    if provider == "azure":
        from testweavex.llm.azure import AzureOpenAIAdapter
        return AzureOpenAIAdapter(config.llm)
    raise ConfigError(
        f"Unsupported LLM provider: '{provider}'. Choose: openai, anthropic, ollama, azure"
    )
