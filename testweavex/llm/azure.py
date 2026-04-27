# testweavex/llm/azure.py
from __future__ import annotations

import json
import time

import openai
from pydantic import ValidationError

from testweavex.core.config import LLMConfig
from testweavex.core.exceptions import ConfigError, LLMOutputError
from testweavex.core.models import (
    GenerationRequest,
    GenerationResponse,
    Scenario,
    StepDefinition,
    StepDefinitionResponse,
    TestCase,
)
from testweavex.llm.base import LLMAdapter, _build_gap_prompt, _deduplicate
from testweavex.skills.loader import SkillLoader

_SYSTEM_PROMPT = (
    "You are a senior QA engineer. Respond ONLY with valid JSON. "
    "No markdown, no explanation, no code fences — just the JSON object."
)


class AzureOpenAIAdapter(LLMAdapter):

    def __init__(self, config: LLMConfig) -> None:
        if not config.azure_endpoint:
            raise ConfigError("LLMConfig.azure_endpoint is required for provider 'azure'")
        if not config.api_version:
            raise ConfigError("LLMConfig.api_version is required for provider 'azure'")
        if not config.deployment_name:
            raise ConfigError("LLMConfig.deployment_name is required for provider 'azure'")
        self._config = config
        self._deployment = config.deployment_name
        self._client = openai.AzureOpenAI(
            api_key=config.api_key,
            azure_endpoint=config.azure_endpoint,
            api_version=config.api_version,
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
            llm_model=self._deployment,
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
                    model=self._deployment,
                    temperature=self._config.temperature,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
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
            f"Azure OpenAI returned invalid output after {self._config.max_retries} attempts"
        ) from last_exc

    def generate_step_definitions(
        self, scenarios: list[Scenario], existing_steps: list[str]
    ) -> StepDefinitionResponse:
        from testweavex.llm.openai import _build_step_prompt
        prompt = _build_step_prompt(scenarios, existing_steps)
        last_exc: Exception | None = None
        for _ in range(self._config.max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self._deployment,
                    temperature=self._config.temperature,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )
                raw = resp.choices[0].message.content
                data = json.loads(raw)
                steps = [StepDefinition(**s) for s in data.get("new_steps", [])]
                tokens = resp.usage.total_tokens if resp.usage else 0
                return StepDefinitionResponse(
                    new_steps=steps,
                    reused_count=0,
                    llm_model=self._deployment,
                    tokens_used=tokens,
                )
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_exc = exc
        raise LLMOutputError(
            f"Azure OpenAI returned invalid step definitions after {self._config.max_retries} attempts"
        ) from last_exc

    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse:
        prompt = _build_gap_prompt(manual_test)
        scenarios, tokens = self._call_with_retry(prompt, "gap_automation")
        return GenerationResponse(
            scenarios=scenarios,
            skill_used="gap_automation",
            llm_model=self._deployment,
            tokens_used=tokens,
            generation_time_ms=0,
        )

    def health_check(self) -> bool:
        try:
            self._client.chat.completions.create(
                model=self._deployment,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": "ping"},
                ],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
