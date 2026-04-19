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
