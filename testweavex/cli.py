from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from testweavex.core.config import load_config
from testweavex.storage.sqlite import SQLiteRepository

app = typer.Typer(
    name="tw",
    help="TestWeaveX — unified test management and execution.",
    invoke_without_command=True,
    no_args_is_help=False,
)
console = Console()

_SUBCOMMANDS = {
    "init", "status", "history", "gaps",
    "generate", "serve", "migrate", "sync",
}


def _get_repo() -> SQLiteRepository:
    db_dir = Path.cwd() / ".testweavex"
    db_dir.mkdir(exist_ok=True)
    return SQLiteRepository(db_url=f"sqlite:///{db_dir / 'results.db'}")


@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        import pytest
        sys.exit(pytest.main(sys.argv[1:]))


@app.command()
def init(
    llm_provider: str = typer.Option("anthropic", "--llm-provider", help="LLM provider"),
) -> None:
    """Create testweavex.config.yaml in the current directory."""
    config_path = Path.cwd() / "testweavex.config.yaml"
    model_defaults = {
        "anthropic": "claude-sonnet-4-6",
        "openai": "gpt-4o",
        "ollama": "llama3",
        "azure": "gpt-4",
    }
    model = model_defaults.get(llm_provider, "claude-sonnet-4-6")
    content = f"""\
llm:
  provider: {llm_provider}
  model: {model}
  api_key: ${{ANTHROPIC_API_KEY}}
  temperature: 0.3
  max_retries: 3
  timeout_seconds: 30

gap_analysis:
  scoring_weights:
    priority: 0.30
    test_type: 0.25
    defects: 0.20
    frequency: 0.15
    staleness: 0.10
  match_threshold: 0.65
  top_gaps_default: 10
"""
    config_path.write_text(content, encoding="utf-8")
    console.print(f"[green]Created[/green] {config_path}")


@app.command()
def status(
    format: str = typer.Option("table", "--format", help="Output format: table|json"),
) -> None:
    """Show test coverage and automation status."""
    repo = _get_repo()
    coverage = repo.get_coverage_percentage()
    all_cases = repo.get_all_test_cases()

    type_counts: Counter = Counter()
    type_automated: Counter = Counter()
    for tc in all_cases:
        type_counts[tc.test_type.value] += 1
        if tc.is_automated:
            type_automated[tc.test_type.value] += 1

    if format == "json":
        data = {
            "coverage_percentage": coverage,
            "total_test_cases": len(all_cases),
            "automated": sum(type_automated.values()),
            "by_type": {
                t: {"total": type_counts[t], "automated": type_automated.get(t, 0)}
                for t in type_counts
            },
        }
        typer.echo(json.dumps(data, indent=2))
        return

    table = Table(title=f"TestWeaveX Status — Coverage: {coverage:.1f}%")
    table.add_column("Test Type")
    table.add_column("Total", justify="right")
    table.add_column("Automated", justify="right")
    table.add_column("Gap", justify="right")
    for t in sorted(type_counts):
        total = type_counts[t]
        automated = type_automated.get(t, 0)
        table.add_row(t, str(total), str(automated), str(total - automated))
    console.print(table)


@app.command()
def history(
    last_n: int = typer.Option(10, "--last-n", help="Number of runs to show"),
) -> None:
    """Show recent test run history."""
    repo = _get_repo()
    runs = repo.list_runs(limit=last_n)
    if not runs:
        console.print("No test runs recorded yet.")
        return
    table = Table(title="Recent Test Runs")
    table.add_column("Run ID")
    table.add_column("Suite")
    table.add_column("Environment")
    table.add_column("Started")
    for run in runs:
        table.add_row(
            run.id[:8] + "...",
            run.suite,
            run.environment,
            run.started_at.strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)


@app.command()
def gaps(
    limit: int = typer.Option(10, "--limit"),
    min_score: float = typer.Option(0.0, "--min-score"),
    generate: bool = typer.Option(False, "--generate"),
) -> None:
    """Show automation gap analysis. (Requires Phase 5)"""
    console.print("[red]tw gaps requires Phase 5 — not yet available.[/red]")
    raise typer.Exit(code=1)


@app.command()
def generate(
    feature: str = typer.Option(..., "--feature"),
    skill: str = typer.Option("functional/smoke", "--skill"),
) -> None:
    """Generate tests with LLM. (Requires Phase 5)"""
    console.print("[red]tw generate requires Phase 5 — not yet available.[/red]")
    raise typer.Exit(code=1)


@app.command()
def serve(
    port: int = typer.Option(8080, "--port"),
) -> None:
    """Start the TestWeaveX web UI. (Requires Phase 6)"""
    console.print("[red]tw serve requires Phase 6 — not yet available.[/red]")
    raise typer.Exit(code=1)


@app.command()
def migrate(
    source: str = typer.Option(..., "--source"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Migrate from external TCM. (Requires Phase 7)"""
    console.print("[red]tw migrate requires Phase 7 — not yet available.[/red]")
    raise typer.Exit(code=1)


@app.command()
def sync(
    tcm: str = typer.Option(..., "--tcm"),
) -> None:
    """Sync results to external TCM. (Requires Phase 7)"""
    console.print("[red]tw sync requires Phase 7 — not yet available.[/red]")
    raise typer.Exit(code=1)


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in _SUBCOMMANDS:
        import pytest
        sys.exit(pytest.main(args))
    app()
