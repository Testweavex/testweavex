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
            if approved_stubs and not dry_run:
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
