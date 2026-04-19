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
_PARAM_RE = re.compile(r'(?:"[^"]*"|\{[^}]+\}|\d+)')
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
                except OSError:
                    continue
                for match in _STEP_DECORATOR_RE.finditer(content):
                    patterns.add(match.group(1))
        return patterns


class StepDefinitionGenerator:
    pass  # implemented in Task 4
