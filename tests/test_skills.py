from __future__ import annotations

import pytest
from pathlib import Path

from testweavex.skills.loader import SkillFile, SkillLoader
from testweavex.core.exceptions import SkillNotFoundError, ConfigError


class TestSkillLoaderBuiltins:
    def test_load_builtin_smoke_returns_skill_file(self):
        loader = SkillLoader()
        skill = loader.load("functional/smoke")
        assert skill.name == "functional/smoke"
        assert skill.display_name != ""
        assert "{feature_description}" in skill.prompt_template

    def test_load_all_10_builtins_valid(self):
        loader = SkillLoader()
        skill_names = [
            "functional/smoke",
            "functional/sanity",
            "functional/happy_path",
            "functional/edge_cases",
            "functional/data_driven",
            "functional/integration",
            "functional/system",
            "functional/e2e",
            "nonfunctional/accessibility",
            "nonfunctional/cross_browser",
        ]
        for name in skill_names:
            skill = loader.load(name)
            assert skill.name == name, f"Expected name={name}, got {skill.name}"

    def test_skill_not_found_raises(self):
        loader = SkillLoader()
        with pytest.raises(SkillNotFoundError):
            loader.load("functional/nonexistent")

    def test_list_skills_returns_all_builtins(self):
        loader = SkillLoader()
        skills = loader.list_skills()
        names = {s.name for s in skills}
        assert "functional/smoke" in names
        assert "nonfunctional/accessibility" in names
        assert len(skills) >= 10


class TestSkillLoaderCustom:
    def test_custom_skill_overrides_builtin(self, tmp_path):
        custom_dir = tmp_path / "testweavex" / "skills" / "custom" / "functional"
        custom_dir.mkdir(parents=True)
        (custom_dir / "smoke.yaml").write_text(
            "name: functional/smoke\n"
            "display_name: Custom Smoke\n"
            "description: Custom override\n"
            "prompt_template: 'Custom {feature_description} {acceptance_criteria} "
            "{existing_scenarios} {n_suggestions}'\n",
            encoding="utf-8",
        )
        loader = SkillLoader()
        import os
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            skill = loader.load("functional/smoke")
            assert skill.display_name == "Custom Smoke"
        finally:
            os.chdir(old_cwd)

    def test_list_skills_custom_overrides_builtin_in_list(self, tmp_path):
        custom_dir = tmp_path / "testweavex" / "skills" / "custom" / "functional"
        custom_dir.mkdir(parents=True)
        (custom_dir / "smoke.yaml").write_text(
            "name: functional/smoke\n"
            "display_name: Custom Smoke\n"
            "description: Custom\n"
            "prompt_template: '{feature_description} {acceptance_criteria} "
            "{existing_scenarios} {n_suggestions}'\n",
            encoding="utf-8",
        )
        import os
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            loader = SkillLoader()
            skills = loader.list_skills()
            smoke_skills = [s for s in skills if s.name == "functional/smoke"]
            assert len(smoke_skills) == 1
            assert smoke_skills[0].display_name == "Custom Smoke"
        finally:
            os.chdir(old_cwd)

    def test_config_path_takes_priority_over_custom(self, tmp_path):
        from testweavex.core.config import TestWeaveXConfig, LLMConfig
        config_skills_dir = tmp_path / "config-skills" / "functional"
        config_skills_dir.mkdir(parents=True)
        (config_skills_dir / "smoke.yaml").write_text(
            "name: functional/smoke\n"
            "display_name: Config Smoke\n"
            "description: From config path\n"
            "prompt_template: '{feature_description} {acceptance_criteria} "
            "{existing_scenarios} {n_suggestions}'\n",
            encoding="utf-8",
        )
        config = TestWeaveXConfig(skills_dir=str(tmp_path / "config-skills"))
        loader = SkillLoader(config=config)
        skill = loader.load("functional/smoke")
        assert skill.display_name == "Config Smoke"

    def test_invalid_yaml_raises_config_error(self, tmp_path):
        custom_dir = tmp_path / "testweavex" / "skills" / "custom" / "functional"
        custom_dir.mkdir(parents=True)
        (custom_dir / "bad.yaml").write_text(
            "name: functional/bad\n"
            "this_is_not_valid_yaml: [unclosed\n",
            encoding="utf-8",
        )
        import os
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            loader = SkillLoader()
            with pytest.raises(ConfigError):
                loader.load("functional/bad")
        finally:
            os.chdir(old_cwd)
