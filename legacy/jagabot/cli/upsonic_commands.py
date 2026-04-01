"""jagabot upsonic — CLI sub-app for memory-backed chat sessions via Upsonic."""
from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

try:
    from jagabot.agent.upsonic_chat import (
        UpsonicChatAgent,
        UpsonicChatAgentError,
        _UPSONIC_AVAILABLE,
        _SAFETY_AVAILABLE,
        _session_registry,
    )
except ImportError:
    UpsonicChatAgent = None  # type: ignore[assignment,misc]
    UpsonicChatAgentError = RuntimeError  # type: ignore[assignment,misc]
    _UPSONIC_AVAILABLE = False
    _SAFETY_AVAILABLE = False
    _session_registry = {}  # type: ignore[assignment]

upsonic_app = typer.Typer(
    name="upsonic",
    help="Memory-backed multi-turn chat sessions powered by Upsonic Agent.",
    no_args_is_help=True,
)
console = Console()


def _run(coro):
    """Run an async coroutine from sync CLI context."""
    return asyncio.run(coro)


@upsonic_app.command("chat")
def upsonic_chat(
    message: str = typer.Argument(..., help="Message to send"),
    session: str = typer.Option(
        "default", "--session", "-s", help="Session ID (for memory continuity)"
    ),
    model: str = typer.Option(
        "openai/gpt-4o", "--model", "-m", help="Model in provider/model format"
    ),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render as Markdown"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Send a message to Upsonic Agent with persistent session memory."""
    if UpsonicChatAgent is None:
        console.print("[red]Error:[/red] Upsonic not installed. Run: pip install -e Upsonic/")
        raise typer.Exit(1)

    if not json_output:
        console.print(f"[dim]Session:[/dim] [cyan]{session}[/cyan]  [dim]Model:[/dim] [cyan]{model}[/cyan]")

    try:
        agent = UpsonicChatAgent.get_or_create(session_id=session, model=model)
        response = _run(agent.chat_async(message))
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    if json_output:
        typer.echo(json.dumps({"session": session, "response": response}))
        return

    if markdown:
        console.print(Panel(Markdown(response), title="[bold green]JAGABOT[/bold green]", border_style="green"))
    else:
        console.print(response)


@upsonic_app.command("status")
def upsonic_status() -> None:
    """Show active Upsonic sessions and availability status."""
    status_color = "green" if _UPSONIC_AVAILABLE else "red"
    safety_color = "green" if _SAFETY_AVAILABLE else "yellow"

    console.print(Panel(
        f"[bold]Upsonic:[/bold] [{status_color}]{'installed' if _UPSONIC_AVAILABLE else 'not installed'}[/{status_color}]\n"
        f"[bold]Safety Engine:[/bold] [{safety_color}]{'available' if _SAFETY_AVAILABLE else 'unavailable'}[/{safety_color}]\n"
        f"[bold]Active sessions:[/bold] {len(_session_registry)}",
        title="[bold]Upsonic Status[/bold]",
    ))

    if not _session_registry:
        console.print("[dim]No active sessions.[/dim]")
        return

    table = Table(title="Active Sessions")
    table.add_column("Session ID", style="cyan")
    table.add_column("Model", style="blue")
    table.add_column("Messages", justify="right")

    for session_id, agent in _session_registry.items():
        stats = agent.stats()
        table.add_row(session_id, stats["model"], str(stats["message_count"]))

    console.print(table)


@upsonic_app.command("clear")
def upsonic_clear(
    session: str = typer.Argument(..., help="Session ID to clear"),
) -> None:
    """Clear a session from memory."""
    if UpsonicChatAgent is None:
        console.print("[red]Error:[/red] Upsonic not installed.")
        raise typer.Exit(1)

    removed = UpsonicChatAgent.clear_session(session)
    if removed:
        console.print(f"[green]✓[/green] Session [cyan]{session}[/cyan] cleared.")
    else:
        console.print(f"[yellow]Session [cyan]{session}[/cyan] not found.[/yellow]")
