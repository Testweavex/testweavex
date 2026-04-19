from __future__ import annotations

import re
from pathlib import Path

from testweavex.core.config import TestWeaveXConfig
from testweavex.core.exceptions import GenerationError
from testweavex.core.models import GenerationRequest, Scenario

_SCENARIO_HEADING_RE = re.compile(r"^\s*Scenario:\s*(.+)$", re.MULTILINE)
_NON_ALNUM_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = _NON_ALNUM_RE.sub("", text)
    text = _WHITESPACE_RE.sub("_", text)
    return text[:40]


class GherkinFormatter:

    def format_feature_file(self, feature_name: str, scenarios: list[Scenario]) -> str:
        lines = [f"Feature: {feature_name}", ""]
        for i, scenario in enumerate(scenarios):
            lines.append(f"  Scenario: {scenario.title}")
            for line in scenario.gherkin.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.lower().startswith("scenario:"):
                    continue
                lines.append(f"    {stripped}")
            if i < len(scenarios) - 1:
                lines.append("")
        return "\n".join(lines) + "\n"


class FeatureFileWriter:

    def __init__(self, config: TestWeaveXConfig) -> None:
        self._config = config

    def _features_root(self) -> Path:
        if self._config.features_dir:
            return Path(self._config.features_dir)
        return Path.cwd() / "features"

    def resolve_path(
        self, category: str, skill_name: str, functionality_name: str
    ) -> Path:
        short_skill = skill_name.split("/")[-1] if "/" in skill_name else skill_name
        return self._features_root() / category / short_skill / f"{functionality_name}.feature"

    def write(
        self,
        scenarios: list[Scenario],
        category: str,
        request: GenerationRequest,
        dry_run: bool,
    ) -> list[Path]:
        if not scenarios:
            return []

        functionality_name = _slugify(request.feature_description)
        skill_name = request.skill_names[0]
        target = self.resolve_path(category, skill_name, functionality_name)
        formatter = GherkinFormatter()

        if target.exists():
            existing_content = target.read_text(encoding="utf-8")
            existing_titles = {
                m.group(1).lower().strip()
                for m in _SCENARIO_HEADING_RE.finditer(existing_content)
            }
            scenarios = [
                s for s in scenarios
                if s.title.lower().strip() not in existing_titles
            ]

        if not scenarios:
            return []

        new_content = formatter.format_feature_file(request.feature_description, scenarios)

        if dry_run:
            print(f"[dry-run] Would write to: {target}")
            print(new_content)
            return []

        try:
            if target.exists():
                existing = target.read_text(encoding="utf-8").rstrip("\n")
                scenario_block = _scenarios_only(new_content)
                target.write_text(
                    existing + "\n\n" + scenario_block + "\n",
                    encoding="utf-8",
                )
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(new_content, encoding="utf-8")
        except OSError as exc:
            raise GenerationError(f"Cannot write feature file {target}: {exc}") from exc

        return [target]


def _scenarios_only(content: str) -> str:
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("Scenario:"):
            return "\n".join(lines[i:])
    return content
