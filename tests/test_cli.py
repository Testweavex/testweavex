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


def test_tw_serve_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 1
    assert "Phase 6" in result.output


def test_tw_migrate_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["migrate", "--source", "testrail"])
    assert result.exit_code == 1
    assert "Phase 7" in result.output


def test_tw_sync_stub(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["sync", "--tcm", "testrail"])
    assert result.exit_code == 1
    assert "Phase 7" in result.output
