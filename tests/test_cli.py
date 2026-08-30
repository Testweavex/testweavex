import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from testweavex.cli import app
from testweavex.core.models import TestCase, TestType, TestStatus, generate_stable_id

runner = CliRunner()


def test_tw_init_creates_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--llm-provider", "anthropic"])
    assert result.exit_code == 0
    config_file = tmp_path / "testweavex.config.yaml"
    assert config_file.exists()
    assert "anthropic" in config_file.read_text()


def test_tw_init_openai(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--llm-provider", "openai"])
    assert result.exit_code == 0
    assert "openai" in (tmp_path / "testweavex.config.yaml").read_text()


def test_tw_status_empty_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Coverage" in result.output or "0" in result.output


def test_tw_status_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["status", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "coverage_percentage" in data


def test_tw_history_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["history"])
    assert result.exit_code == 0


def test_tw_gaps_empty_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["gaps"])
    assert result.exit_code == 0
    assert "No gaps found" in result.output


def _mock_adapter(health=True):
    adapter = MagicMock()
    adapter.health_check.return_value = health
    return adapter


def _mock_result(approved=2, total=3, files=None, step_files=None, reused=0, new_steps=0):
    from testweavex.core.models import GenerationResult
    return GenerationResult(
        written_files=files or ["features/generated/smoke/login.feature"],
        step_files_written=step_files or [],
        reused_steps=reused,
        new_steps=new_steps,
        dry_run=False,
        scenarios_approved=approved,
        scenarios_total=total,
    )


def test_tw_generate_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("testweavex.llm.base.get_llm_adapter", return_value=_mock_adapter()), \
         patch("testweavex.generation.engine.GenerationEngine.run", return_value=_mock_result()):
        result = runner.invoke(app, ["generate", "--feature", "User login", "--skill", "functional/smoke"])
    assert result.exit_code == 0
    assert "Generated 2/3" in result.output
    assert "login.feature" in result.output


def test_tw_generate_dry_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dry_result = _mock_result(approved=3, total=3, files=[])
    dry_result = dry_result.model_copy(update={"dry_run": True})
    with patch("testweavex.llm.base.get_llm_adapter", return_value=_mock_adapter()), \
         patch("testweavex.generation.engine.GenerationEngine.run", return_value=dry_result):
        result = runner.invoke(app, ["generate", "--feature", "login", "--dry-run"])
    assert result.exit_code == 0


def test_tw_generate_config_error(tmp_path, monkeypatch):
    from testweavex.core.exceptions import ConfigError
    monkeypatch.chdir(tmp_path)
    with patch("testweavex.llm.base.get_llm_adapter", side_effect=ConfigError("no API key")):
        result = runner.invoke(app, ["generate", "--feature", "login"])
    assert result.exit_code == 1
    assert "Configuration error" in result.output


def test_tw_generate_llm_unavailable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("testweavex.llm.base.get_llm_adapter", return_value=_mock_adapter(health=False)):
        result = runner.invoke(app, ["generate", "--feature", "login"])
    assert result.exit_code == 1
    assert "not available" in result.output


def test_tw_generate_no_scenarios_approved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    empty_result = _mock_result(approved=0, total=3, files=[])
    with patch("testweavex.llm.base.get_llm_adapter", return_value=_mock_adapter()), \
         patch("testweavex.generation.engine.GenerationEngine.run", return_value=empty_result):
        result = runner.invoke(app, ["generate", "--feature", "login"])
    assert result.exit_code == 0
    assert "No scenarios approved" in result.output


def test_tw_generate_llm_output_error(tmp_path, monkeypatch):
    from testweavex.core.exceptions import LLMOutputError
    monkeypatch.chdir(tmp_path)
    with patch("testweavex.llm.base.get_llm_adapter", return_value=_mock_adapter()), \
         patch("testweavex.generation.engine.GenerationEngine.run", side_effect=LLMOutputError("bad JSON")):
        result = runner.invoke(app, ["generate", "--feature", "login"])
    assert result.exit_code == 1
    assert "Generation failed" in result.output


def test_tw_generate_with_step_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rich_result = _mock_result(
        approved=2, total=2,
        files=["features/generated/smoke/login.feature"],
        step_files=["tests/step_definitions/login_steps.py"],
        new_steps=3,
        reused=1,
    )
    with patch("testweavex.llm.base.get_llm_adapter", return_value=_mock_adapter()), \
         patch("testweavex.generation.engine.GenerationEngine.run", return_value=rich_result):
        result = runner.invoke(app, ["generate", "--feature", "login"])
    assert result.exit_code == 0
    assert "login_steps.py" in result.output
    assert "reused" in result.output


def test_tw_serve_is_registered(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "port" in result.output.lower()


def test_tw_migrate_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # No config file: provider defaults to "none", mismatches "testrail" → exit 1
    result = runner.invoke(app, ["migrate", "--source", "testrail"])
    assert result.exit_code == 1


def test_tw_sync_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # No config file: provider defaults to "none", mismatches "testrail" → exit 1
    result = runner.invoke(app, ["sync", "--tcm", "testrail"])
    assert result.exit_code == 1



def _cli_test_case(title: str = "Login test") -> TestCase:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return TestCase(
        id=generate_stable_id("12", "101"),
        title=title,
        feature_id=generate_stable_id("12", "45"),
        gherkin="Scenario: Login\n  Given I am on login page",
        test_type=TestType.sanity,
        skill="builtin",
        status=TestStatus.pending,
        is_automated=False,
        tcm_id="101",
        tags=[],
        priority=2,
        created_at=now,
        updated_at=now,
    )


def test_migrate_dry_run_prints_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: testrail\n  testrail:\n    url: https://t.io\n    username: u\n    api_key: k\n    project_id: 12\n")

    mock_connector = MagicMock()
    mock_connector.health_check.return_value = True
    mock_connector.fetch_all_test_cases.return_value = [_cli_test_case()]

    with patch("testweavex.cli.get_connector", return_value=mock_connector):
        result = runner.invoke(app, ["migrate", "--source", "testrail", "--dry-run"])

    assert result.exit_code == 0
    assert "Login test" in result.output or "1" in result.output
    assert not (tmp_path / "features").exists()


def test_migrate_imports_and_writes_feature_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: testrail\n  testrail:\n    url: https://t.io\n    username: u\n    api_key: k\n    project_id: 12\n")

    mock_connector = MagicMock()
    mock_connector.health_check.return_value = True
    mock_connector.fetch_all_test_cases.return_value = [_cli_test_case("Login test")]

    with patch("testweavex.cli.get_connector", return_value=mock_connector):
        result = runner.invoke(app, ["migrate", "--source", "testrail"])

    assert result.exit_code == 0
    feature_files = list((tmp_path / "features").glob("*.feature"))
    assert len(feature_files) == 1
    content = feature_files[0].read_text()
    assert "Login test" in content


def test_migrate_source_mismatch_exits_with_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: xray\n  xray:\n    jira_url: https://j.io\n    client_id: c\n    client_secret: s\n    project_key: QA\n")

    result = runner.invoke(app, ["migrate", "--source", "testrail"])
    assert result.exit_code != 0
    assert "testrail" in result.output.lower() or "mismatch" in result.output.lower() or "xray" in result.output.lower()


def test_migrate_health_check_failure_aborts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: testrail\n  testrail:\n    url: https://t.io\n    username: u\n    api_key: k\n    project_id: 12\n")

    mock_connector = MagicMock()
    mock_connector.health_check.return_value = False

    with patch("testweavex.cli.get_connector", return_value=mock_connector):
        result = runner.invoke(app, ["migrate", "--source", "testrail"])

    assert result.exit_code != 0
    assert "connect" in result.output.lower() or "health" in result.output.lower() or "failed" in result.output.lower()


def test_sync_upserts_test_cases_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: testrail\n  testrail:\n    url: https://t.io\n    username: u\n    api_key: k\n    project_id: 12\n")

    mock_connector = MagicMock()
    mock_connector.health_check.return_value = True
    mock_connector.fetch_all_test_cases.return_value = [_cli_test_case()]

    with patch("testweavex.cli.get_connector", return_value=mock_connector):
        result = runner.invoke(app, ["sync", "--tcm", "testrail"])

    assert result.exit_code == 0
    assert not (tmp_path / "features").exists()
    assert "1" in result.output or "synced" in result.output.lower() or "imported" in result.output.lower()


def test_sync_tcm_mismatch_exits_with_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: xray\n  xray:\n    jira_url: https://j.io\n    client_id: c\n    client_secret: s\n    project_key: QA\n")

    result = runner.invoke(app, ["sync", "--tcm", "testrail"])
    assert result.exit_code != 0


def test_sync_health_check_failure_aborts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / "testweavex.config.yaml"
    config_file.write_text("tcm:\n  provider: testrail\n  testrail:\n    url: https://t.io\n    username: u\n    api_key: k\n    project_id: 12\n")

    mock_connector = MagicMock()
    mock_connector.health_check.return_value = False

    with patch("testweavex.cli.get_connector", return_value=mock_connector):
        result = runner.invoke(app, ["sync", "--tcm", "testrail"])

    assert result.exit_code != 0


# ── tw gaps: reporting only, never analysis ───────────────────────────────

def _seed_gap_db(tmp_path, *, gap_status="closed", score=0.75):
    """Create a .testweavex DB with one automated test case and one gap."""
    from testweavex.core.models import Gap, GapStatus
    from testweavex.storage.sqlite import SQLiteRepository

    db_dir = tmp_path / ".testweavex"
    db_dir.mkdir(exist_ok=True)
    repo = SQLiteRepository(db_url=f"sqlite:///{db_dir / 'results.db'}")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    repo.upsert_test_case(TestCase(
        id="tc-login",
        title="Login smoke check",
        feature_id="feat-auth",
        gherkin="Scenario: Login smoke check",
        test_type=TestType.smoke,
        skill="functional/smoke",
        is_automated=True,
        source_file=str(tmp_path / "test_login.py"),
        created_at=now,
        updated_at=now,
    ))
    repo.save_gaps([Gap(
        id="gap-login",
        test_case_id="tc-login",
        priority_score=score,
        gap_reason="uncollected",
        status=GapStatus(gap_status),
        detected_at=now,
        closed_at=None if gap_status == "open" else now,
    )])
    return repo


def test_tw_gaps_does_not_reopen_closed_gaps(tmp_path, monkeypatch):
    """tw gaps reports; it must not re-run analysis and resurrect closed gaps."""
    repo = _seed_gap_db(tmp_path, gap_status="closed")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["gaps"])

    assert result.exit_code == 0
    assert repo.get_gaps(limit=50, status="open") == []


def test_tw_gaps_shows_test_case_title(tmp_path, monkeypatch):
    _seed_gap_db(tmp_path, gap_status="open")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["gaps"])

    assert result.exit_code == 0
    assert "Login smoke check" in result.output


def test_tw_gaps_empty_db_points_at_pytest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["gaps"])
    assert result.exit_code == 0
    assert "pytest --gaps" in result.output


def test_tw_gaps_rejects_removed_generate_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["gaps", "--generate"])
    assert result.exit_code != 0
