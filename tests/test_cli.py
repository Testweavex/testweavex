import json
from typer.testing import CliRunner
from testweavex.cli import app

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


def test_tw_generate_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["generate", "--feature", "login", "--skill", "functional/smoke"])
    assert result.exit_code == 1
    assert "Phase 5" in result.output


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
    result = runner.invoke(app, ["sync", "--tcm", "testrail"])
    assert result.exit_code == 1
    assert "Phase 7" in result.output


from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from testweavex.core.models import TestCase, TestType, TestStatus, generate_stable_id


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
