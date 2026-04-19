from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from testweavex.core.exceptions import ConfigError, SkillNotFoundError


class SkillFile(BaseModel):
    name: str
    display_name: str
    description: str
    prompt_template: str
    assertion_hints: list[str] = Field(default_factory=list)
    data_setup: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    estimated_duration_seconds: int = 60
    priority: int = 3


class SkillLoader:

    def __init__(self, config=None) -> None:
        self._config = config
        self._builtin_dir = Path(__file__).parent / "builtin"

    def load(self, skill_name: str) -> SkillFile:
        for search_dir in self._search_dirs():
            candidate = search_dir / f"{skill_name}.yaml"
            if candidate.exists():
                return self._parse(candidate)
        raise SkillNotFoundError(f"Skill not found: '{skill_name}'")

    def list_skills(self) -> list[SkillFile]:
        seen: dict[str, SkillFile] = {}
        for path in sorted(self._builtin_dir.rglob("*.yaml")):
            skill = self._parse(path)
            seen[skill.name] = skill
        custom_dirs = self._search_dirs()
        custom_dirs.pop()  # remove builtin_dir — already loaded above
        for search_dir in custom_dirs:
            if search_dir.exists():
                for path in sorted(search_dir.rglob("*.yaml")):
                    try:
                        skill = self._parse(path)
                        seen[skill.name] = skill
                    except ConfigError:
                        pass
        return list(seen.values())

    def _search_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        if self._config and getattr(self._config, "skills_dir", None):
            dirs.append(Path(self._config.skills_dir))
        dirs.append(Path.cwd() / "testweavex" / "skills" / "custom")
        dirs.append(self._builtin_dir)
        return dirs

    def _parse(self, path: Path) -> SkillFile:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            return SkillFile(**raw)
        except Exception as exc:
            raise ConfigError(f"Invalid skill file {path}: {exc}") from exc
