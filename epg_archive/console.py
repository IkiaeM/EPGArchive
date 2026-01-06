"""Rich console utilities for beautiful CLI output."""

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
import logging
from typing import Dict, Any

console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Configure rich logging with colors and formatting."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                show_time=True,
                show_path=verbose,
                markup=True,
            )
        ],
    )
    
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def create_progress() -> Progress:
    """Create a rich progress bar for long operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def print_header() -> None:
    """Print application header."""
    header = Text()
    header.append("📺 ", style="bold")
    header.append("EPG Archive", style="bold cyan")
    header.append(" - Long-term EPG archiving system", style="dim")
    console.print(Panel(header, box=box.ROUNDED, border_style="cyan"))


def print_stats(stats: Dict[str, Any]) -> None:
    """Print archive statistics in a beautiful table."""
    table = Table(
        title="📊 Archive Statistics",
        box=box.ROUNDED,
        border_style="green",
        title_style="bold green",
    )
    
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold white", justify="right")
    
    table.add_row("📅 Total Days", str(stats.get("total_days", 0)))
    table.add_row("📺 Total Programmes", f"{stats.get('total_programmes', 0):,}")
    
    date_range = stats.get("date_range")
    if date_range:
        table.add_row("📆 Date Range", date_range)
    
    console.print()
    console.print(table)
    console.print()


def print_source_status(name: str, status: str, details: str = "") -> None:
    """Print source fetch status with icon."""
    icons = {
        "fetching": "🔄",
        "success": "✅",
        "error": "❌",
        "parsing": "📄",
        "skipped": "⏭️",
    }
    icon = icons.get(status, "•")
    
    if status == "success":
        style = "green"
    elif status == "error":
        style = "red"
    elif status == "fetching" or status == "parsing":
        style = "yellow"
    else:
        style = "dim"
    
    msg = f"{icon} [{style}]{name}[/{style}]"
    if details:
        msg += f" [dim]{details}[/dim]"
    
    console.print(msg)


def print_summary(
    sources_ok: int,
    sources_failed: int,
    programmes_before: int,
    programmes_after: int,
    days_exported: int,
) -> None:
    """Print operation summary."""
    console.print()
    
    panel_content = []
    
    if sources_failed == 0:
        panel_content.append(f"[green]✓[/green] All {sources_ok} sources fetched successfully")
    else:
        panel_content.append(
            f"[yellow]![/yellow] {sources_ok} sources OK, {sources_failed} failed"
        )
    
    panel_content.append(
        f"[cyan]→[/cyan] {programmes_before:,} programmes merged to {programmes_after:,}"
    )
    panel_content.append(f"[blue]📁[/blue] {days_exported} days exported to archive")
    
    console.print(
        Panel(
            "\n".join(panel_content),
            title="[bold]Summary[/bold]",
            box=box.ROUNDED,
            border_style="blue",
        )
    )


def print_error(message: str) -> None:
    """Print error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_success(message: str) -> None:
    """Print success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[bold yellow]![/bold yellow] {message}")
