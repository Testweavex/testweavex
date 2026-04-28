from __future__ import annotations

from rich.console import Console
from rich.table import Table

from testweavex.events import EventBus, GapAnalysisComplete, SessionFinished
from testweavex.reporters.base import BaseReporter


class ConsoleReporter(BaseReporter):

    def __init__(self) -> None:
        self._console = Console()

    def register(self, bus: EventBus) -> None:
        bus.subscribe("session_finished", self._on_session)
        bus.subscribe("gap_analysis_complete", self._on_gaps)

    def _on_session(self, event: SessionFinished) -> None:
        table = Table(title="TestWeaveX Run Summary", show_header=True)
        table.add_column("Metric", style="bold")
        table.add_column("Value")
        table.add_row("Run ID", event.run_id[:8] + "...")
        table.add_row("Total", str(event.total))
        table.add_row("Passed", f"[green]{event.passed}[/green]")
        table.add_row("Failed", f"[red]{event.failed}[/red]")
        table.add_row("Skipped", f"[yellow]{event.skipped}[/yellow]")
        table.add_row("Duration", f"{event.duration_ms / 1000:.2f}s")
        self._console.print(table)

    def _on_gaps(self, event: GapAnalysisComplete) -> None:
        self._console.print(
            f"\n[bold yellow]Gap Analysis:[/bold yellow] "
            f"{event.gaps_found} gaps found. "
            f"Top {len(event.top_gaps)} shown below."
        )
        if event.top_gaps:
            t = Table(show_header=True, header_style="bold")
            t.add_column("Score")
            t.add_column("Reason")
            t.add_column("Test Case ID")
            for g in event.top_gaps[:10]:
                t.add_row(
                    f"{g.get('priority_score', 0):.2f}",
                    g.get("gap_reason", ""),
                    g.get("test_case_id", "")[:16] + "...",
                )
            self._console.print(t)
