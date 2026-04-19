from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from testweavex.core.exceptions import ConfigError

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _interpolate(value: object) -> object:
    if isinstance(value, str):
        def _replace(m: re.Match) -> str:
            var = m.group(1)
            return os.environ.get(var, "")
        return _ENV_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(i) for i in value]
    return value


@dataclass
class LLMConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key: str = ""
    temperature: float = 0.3
    max_retries: int = 3
    timeout_seconds: int = 30
    base_url: Optional[str] = None
    azure_endpoint: Optional[str] = None
    api_version: Optional[str] = None
    deployment_name: Optional[str] = None


@dataclass
class GapAnalysisConfig:
    scoring_weights: dict = field(default_factory=lambda: {
        "priority": 0.30,
        "test_type": 0.25,
        "defects": 0.20,
        "frequency": 0.15,
        "staleness": 0.10,
    })
    match_threshold: float = 0.65
    top_gaps_default: int = 10
    min_runs_for_flaky: int = 5


@dataclass
class TCMConfig:
    provider: str = "none"
    testrail: dict = field(default_factory=dict)
    xray: dict = field(default_factory=dict)


@dataclass
class TestWeaveXConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    tcm: TCMConfig = field(default_factory=TCMConfig)
    gap_analysis: GapAnalysisConfig = field(default_factory=GapAnalysisConfig)
    results_server: Optional[str] = None
    skills_dir: Optional[str] = None


def _find_project_root(start: Path) -> Path:
    markers = {"pyproject.toml", "pytest.ini", "setup.cfg", "setup.py"}
    current = start.resolve()
    while True:
        if any((current / m).exists() for m in markers):
            return current
        parent = current.parent
        if parent == current:
            return start.resolve()
        current = parent


def load_config(start_dir: Optional[Path] = None) -> TestWeaveXConfig:
    root = _find_project_root(start_dir or Path.cwd())
    config_path = root / "testweavex.config.yaml"

    if not config_path.exists():
        return TestWeaveXConfig()

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse {config_path}: {exc}") from exc

    raw = _interpolate(raw)

    cfg = TestWeaveXConfig()

    if llm_raw := raw.get("llm"):
        cfg.llm = LLMConfig(**{k: v for k, v in llm_raw.items() if hasattr(LLMConfig, k)})

    if rs := raw.get("results_server"):
        cfg.results_server = rs or None

    if sd := raw.get("skills_dir"):
        cfg.skills_dir = sd or None

    if tcm_raw := raw.get("tcm"):
        cfg.tcm = TCMConfig(
            provider=tcm_raw.get("provider", "none"),
            testrail=tcm_raw.get("testrail", {}),
            xray=tcm_raw.get("xray", {}),
        )

    if gap_raw := raw.get("gap_analysis"):
        cfg.gap_analysis = GapAnalysisConfig(
            scoring_weights=gap_raw.get("scoring_weights", GapAnalysisConfig().scoring_weights),
            match_threshold=gap_raw.get("match_threshold", 0.65),
            top_gaps_default=gap_raw.get("top_gaps_default", 10),
            min_runs_for_flaky=gap_raw.get("min_runs_for_flaky", 5),
        )

    return cfg
