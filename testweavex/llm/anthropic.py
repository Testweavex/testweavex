from __future__ import annotations

import json
import time

import anthropic
from pydantic import ValidationError

from testweavex.core.config import LLMConfig
from testweavex.core.exceptions import LLMOutputError
from testweavex.core.models import (
    GenerationRequest,
    GenerationResponse,
    Scenario,
    StepDefinition,
    StepDefinitionResponse,
    TestCase,
)
from testweavex.llm.base import LLMAdapter, _deduplicate
from testweavex.skills.loader import SkillLoader

_SYSTEM_PROMPT = (
    "You are a senior QA engineer. Respond ONLY with valid JSON. "
    "No markdown, no explanation, no code fences — just the JSON object."
)


class AnthropicAdapter(LLMAdapter):

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        self._client = anthropic.Anthropic(api_key=config.api_key)
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
            llm_model=self._config.model,
            tokens_used=total_tokens,
            generation_time_ms=elapsed,
        )

    def _call_with_retry(
        self, prompt: str, skill_name: str
    ) -> tuple[list[Scenario], int]:
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
                raw_list = data.get("scenarios", data if isinstance(data, list) else [])
                scenarios = [Scenario(**s, skill_used=skill_name) for s in raw_list]
                tokens = resp.usage.input_tokens + resp.usage.output_tokens
                return scenarios, tokens
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_exc = exc
        raise LLMOutputError(
            f"Anthropic returned invalid output after {self._config.max_retries} attempts"
        ) from last_exc

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
                    reused_count=0,
                    llm_model=self._config.model,
                    tokens_used=tokens,
                )
            except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
                last_exc = exc
        raise LLMOutputError(
            f"Anthropic returned invalid step definitions after {self._config.max_retries} attempts"
        ) from last_exc

    def suggest_gap_automation(self, manual_test: TestCase) -> GenerationResponse:
        from testweavex.llm.base import _build_gap_prompt
        prompt = _build_gap_prompt(manual_test)
        scenarios, tokens = self._call_with_retry(prompt, "gap_automation")
        return GenerationResponse(
            scenarios=scenarios,
            skill_used="gap_automation",
            llm_model=self._config.model,
            tokens_used=tokens,
            generation_time_ms=0,
        )

    def health_check(self) -> bool:
        try:
            self._client.messages.create(
                model=self._config.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False


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
