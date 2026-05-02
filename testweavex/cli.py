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
from testweavex.tcm import get_connector

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
    import os
    url = os.getenv("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return SQLiteRepository(db_url=url)
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
    limit: int = typer.Option(10, "--limit", help="Max gaps to show"),
    min_score: float = typer.Option(0.0, "--min-score", help="Minimum priority score"),
    generate: bool = typer.Option(False, "--generate", help="Generate tests for top gaps"),
) -> None:
    """Show and optionally generate tests for automation gaps."""
    from testweavex.events import EventBus
    from testweavex.gap.analyzer import GapAnalyzer
    repo = _get_repo()
    bus = EventBus()
    config = load_config()
    analyzer = GapAnalyzer(repo, bus, config.gap_analysis)

    runs = repo.list_runs(limit=1)
    run_id = runs[0].id if runs else "standalone"

    analyzer.run(run_id, collected_ids=[])
    all_gaps = repo.get_gaps(limit=limit, status="open")
    filtered = [g for g in all_gaps if g.priority_score >= min_score]

    if not filtered:
        console.print("No gaps found matching criteria.")
        return

    table = Table(title=f"Top {len(filtered)} Automation Gaps")
    table.add_column("Score", justify="right")
    table.add_column("Reason")
    table.add_column("Test Case ID")
    for g in filtered:
        table.add_row(
            f"{g.priority_score:.3f}",
            g.gap_reason,
            g.test_case_id[:16] + "...",
        )
    console.print(table)


@app.command()
def generate(
    feature: str = typer.Option(..., "--feature"),
    skill: str = typer.Option("functional/smoke", "--skill"),
) -> None:
    """Generate tests with LLM for a given feature description."""
    console.print("[red]tw generate is not yet wired to the generation engine in this release.[/red]")
    raise typer.Exit(code=1)


@app.command()
def serve(
    port: int = typer.Option(8080, "--port", help="Port to listen on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind"),
) -> None:
    """Start the TestWeaveX web UI."""
    import uvicorn
    from testweavex.web.app import create_app
    config = load_config()
    application = create_app(config)
    console.print(f"[green]TestWeaveX UI:[/green] http://{host}:{port}")
    uvicorn.run(application, host=host, port=port)


@app.command()
def migrate(
    source: str = typer.Option(..., "--source", help="TCM source: testrail or xray"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
) -> None:
    """Import test cases from an external TCM into TestWeaveX."""
    import re

    config = load_config()
    if config.tcm.provider.lower() != source.lower():
        console.print(
            f"[red]Source mismatch:[/red] config has provider=[bold]{config.tcm.provider}[/bold]"
            f" but --source={source}"
        )
        raise typer.Exit(code=1)

    connector = get_connector(config.tcm)
    if not connector.health_check():
        console.print(f"[red]Cannot connect to {source}. Check your config credentials.[/red]")
        raise typer.Exit(code=1)

    console.print(f"Fetching test cases from {source}…")
    test_cases = connector.fetch_all_test_cases()

    if dry_run:
        table = Table(title=f"Dry Run — {len(test_cases)} test case(s) from {source}")
        table.add_column("TCM ID")
        table.add_column("Title")
        table.add_column("Automated")
        for tc in test_cases:
            table.add_row(tc.tcm_id or "", tc.title, "yes" if tc.is_automated else "no")
        console.print(table)
        return

    repo = _get_repo()
    features_dir = Path(config.features_dir or "features")
    features_dir.mkdir(parents=True, exist_ok=True)

    def _safe_filename(title: str) -> str:
        return re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_").lower()[:80]

    errors: list[str] = []
    for tc in test_cases:
        try:
            repo.upsert_test_case(tc)
            feature_path = features_dir / f"{_safe_filename(tc.title)}.feature"
            feature_path.write_text(
                f"Feature: {tc.title}\n\n{tc.gherkin}\n",
                encoding="utf-8",
            )
        except Exception as exc:
            errors.append(f"{tc.tcm_id}: {exc}")

    console.print(f"[green]Imported {len(test_cases) - len(errors)} test case(s)[/green]"
                  f" → {features_dir}")
    if errors:
        console.print(f"[yellow]{len(errors)} error(s):[/yellow]")
        for e in errors:
            console.print(f"  {e}")


@app.command()
def sync(
    tcm: str = typer.Option(..., "--tcm", help="TCM provider: testrail or xray"),
) -> None:
    """Pull test cases from external TCM into TestWeaveX (one-way sync)."""
    config = load_config()
    if config.tcm.provider.lower() != tcm.lower():
        console.print(
            f"[red]Provider mismatch:[/red] config has provider=[bold]{config.tcm.provider}[/bold]"
            f" but --tcm={tcm}"
        )
        raise typer.Exit(code=1)

    connector = get_connector(config.tcm)
    if not connector.health_check():
        console.print(f"[red]Cannot connect to {tcm}. Check your config credentials.[/red]")
        raise typer.Exit(code=1)

    console.print(f"Syncing test cases from {tcm}…")
    test_cases = connector.fetch_all_test_cases()

    repo = _get_repo()
    errors: list[str] = []
    for tc in test_cases:
        try:
            repo.upsert_test_case(tc)
        except Exception as exc:
            errors.append(f"{tc.tcm_id}: {exc}")

    console.print(
        f"[green]Synced {len(test_cases) - len(errors)} test case(s)[/green] from {tcm}"
    )
    if errors:
        console.print(f"[yellow]{len(errors)} error(s):[/yellow]")
        for e in errors:
            console.print(f"  {e}")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in _SUBCOMMANDS:
        import pytest
        sys.exit(pytest.main(args))
    app()
