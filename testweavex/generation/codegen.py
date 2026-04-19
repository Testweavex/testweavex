from __future__ import annotations

import re
from pathlib import Path

from testweavex.core.config import TestWeaveXConfig
from testweavex.core.exceptions import GenerationError
from testweavex.core.models import Scenario, StepDefinition, StepDefinitionResponse
from testweavex.llm.base import LLMAdapter

_STEP_DECORATOR_RE = re.compile(
    r'@(?:given|when|then)\s*\(\s*["\'](.+?)["\']\s*\)',
    re.IGNORECASE,
)
_STEP_LINE_RE = re.compile(r"^\s*(given|when|then|and|but)\s+(.+)", re.IGNORECASE)
_PARAM_RE = re.compile(r'(?:"[^"]*"|\{[^}]*\}|\b\d+\b)')
_KEYWORD_RE = re.compile(r"^\s*(?:given|when|then|and|but)\s+", re.IGNORECASE)


def _normalize_step(text: str) -> str:
    text = _KEYWORD_RE.sub("", text).lower().strip()
    text = _PARAM_RE.sub("<arg>", text)
    return text


class StepMatcher:
    """Scans directories for pytest-bdd step definitions and extracts existing patterns."""

    def load_from_dirs(self, step_dirs: list[Path]) -> set[str]:
        """Load step patterns from @given/@when/@then decorators in .py files.

        Args:
            step_dirs: List of directories to scan recursively.

        Returns:
            Set of step pattern strings extracted from decorators.
        """
        patterns: set[str] = set()
        for d in step_dirs:
            if not d.is_dir():
                continue
            for py_file in sorted(d.rglob("*.py")):
                try:
                    content = py_file.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                for match in _STEP_DECORATOR_RE.finditer(content):
                    patterns.add(match.group(1))
        return patterns


class StepDefinitionGenerator:

    def __init__(self, adapter: LLMAdapter, config: TestWeaveXConfig) -> None:
        self._adapter = adapter
        self._config = config

    def _step_defs_root(self) -> Path:
        if self._config.step_defs_dir:
            return Path(self._config.step_defs_dir)
        return Path.cwd() / "tests" / "step_definitions"

    def analyze(
        self,
        scenarios: list[Scenario],
        existing_patterns: set[str],
    ) -> tuple[list[StepDefinition], int]:
        normalized_existing = {_normalize_step(p) for p in existing_patterns}
        seen: set[str] = set()
        new_steps: list[StepDefinition] = []
        reused_count = 0

        for scenario in scenarios:
            for line in scenario.gherkin.splitlines():
                if not _STEP_LINE_RE.match(line):
                    continue
                step_text = line.strip()
                norm = _normalize_step(step_text)
                if norm in seen:
                    continue
                seen.add(norm)
                if norm in normalized_existing:
                    reused_count += 1
                else:
                    new_steps.append(StepDefinition(step_text=step_text, implementation=""))
        return new_steps, reused_count

    def write_step_definitions(
        self,
        steps: list[StepDefinition],
        dry_run: bool,
    ) -> list[Path]:
        if not steps:
            return []

        default_file = self._step_defs_root() / "generated_steps.py"
        groups: dict[Path, list[StepDefinition]] = {}
        for step in steps:
            if step.requires_new_module and step.module_spec:
                candidate = (self._step_defs_root() / step.module_spec).resolve()
                root = self._step_defs_root().resolve()
                target = candidate if str(candidate).startswith(str(root)) else default_file
            else:
                target = default_file
            groups.setdefault(target, []).append(step)

        written: list[Path] = []
        for target, group_steps in groups.items():
            content = _render_steps(group_steps)
            if dry_run:
                print(f"[dry-run] Would write step definitions to: {target}")
                print(content)
                continue
            try:
                if target.exists():
                    existing = target.read_text(encoding="utf-8").rstrip("\n")
                    target.write_text(existing + "\n\n" + content + "\n", encoding="utf-8")
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    header = "from pytest_bdd import given, when, then\n\n"
                    target.write_text(header + content + "\n", encoding="utf-8")
                written.append(target)
            except OSError as exc:
                raise GenerationError(
                    f"Cannot write step definitions to {target}: {exc}"
                ) from exc

        return written


def _render_steps(steps: list[StepDefinition]) -> str:
    lines = []
    for step in steps:
        if step.implementation:
            lines.append(step.implementation)
        else:
            lines.append(f"# Step: {step.step_text}\npass")
        lines.append("")
    return "\n".join(lines)
