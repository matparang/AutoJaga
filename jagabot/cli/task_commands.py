"""jagabot task — CLI sub-app for persistent task management with dependencies."""
from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jagabot.core.task_manager import TaskManager, TaskManagerError

task_app = typer.Typer(
    name="task",
    help="Persistent task board with dependency graph.",
    no_args_is_help=True,
)
console = Console()

DEFAULT_TASKS_DIR = Path.home() / ".jagabot" / "tasks"


def _get_manager() -> TaskManager:
    return TaskManager(DEFAULT_TASKS_DIR)


@task_app.command("create")
def task_create(
    subject: str = typer.Argument(..., help="Task subject"),
    description: str = typer.Option("", "--desc", "-d", help="Task description"),
    blocked_by: str = typer.Option("", "--blocked-by", "-b", help="Comma-separated task IDs this is blocked by"),
) -> None:
    """Create a new task."""
    tm = _get_manager()
    deps = [int(x.strip()) for x in blocked_by.split(",") if x.strip()] if blocked_by else []
    task = tm.create(subject=subject, description=description, blocked_by=deps)
    console.print(f"[green]✓[/green] Created task [cyan]#{task['id']}[/cyan]: {task['subject']}")


@task_app.command("list")
def task_list(
    status: str = typer.Option("", "--status", "-s", help="Filter by status"),
    ready: bool = typer.Option(False, "--ready", "-r", help="Show only ready (unblocked pending) tasks"),
) -> None:
    """List tasks on the board."""
    tm = _get_manager()
    if ready:
        tasks = tm.list_ready()
    elif status:
        tasks = tm.list_by_status(status)
    else:
        tasks = tm.list_all()

    if not tasks:
        console.print("[dim]No tasks found.[/dim]")
        return

    table = Table(title="Task Board")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Status", style="bold")
    table.add_column("Subject")
    table.add_column("Owner", style="blue")
    table.add_column("Blocked By")

    markers = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]", "failed": "[!]"}
    for t in tasks:
        blocked = ", ".join(str(b) for b in t.get("blocked_by", []))
        table.add_row(
            str(t["id"]),
            markers.get(t["status"], "?"),
            t["subject"],
            t.get("owner", ""),
            blocked or "—",
        )
    console.print(table)


@task_app.command("get")
def task_get(
    task_id: int = typer.Argument(..., help="Task ID"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Get details of a specific task."""
    tm = _get_manager()
    try:
        task = tm.get(task_id)
    except TaskManagerError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if json_output:
        typer.echo(json.dumps(task, indent=2))
        return

    console.print(Panel(
        f"[bold]Subject:[/bold] {task['subject']}\n"
        f"[bold]Description:[/bold] {task.get('description', '—')}\n"
        f"[bold]Status:[/bold] {task['status']}\n"
        f"[bold]Owner:[/bold] {task.get('owner') or '—'}\n"
        f"[bold]Blocked by:[/bold] {task.get('blocked_by') or '—'}\n"
        f"[bold]Blocks:[/bold] {task.get('blocks') or '—'}",
        title=f"[cyan]Task #{task['id']}[/cyan]",
    ))


@task_app.command("update")
def task_update(
    task_id: int = typer.Argument(..., help="Task ID"),
    status: str = typer.Option("", "--status", "-s", help="New status (pending/in_progress/completed/failed)"),
    owner: str = typer.Option(None, "--owner", "-o", help="Assign owner"),
    blocked_by: str = typer.Option("", "--add-blocked-by", help="Comma-separated task IDs to add as blockers"),
    blocks: str = typer.Option("", "--add-blocks", help="Comma-separated task IDs this blocks"),
) -> None:
    """Update a task's status, owner, or dependencies."""
    tm = _get_manager()
    try:
        add_bb = [int(x.strip()) for x in blocked_by.split(",") if x.strip()] if blocked_by else None
        add_bl = [int(x.strip()) for x in blocks.split(",") if x.strip()] if blocks else None
        task = tm.update(
            task_id,
            status=status or None,
            owner=owner,
            add_blocked_by=add_bb,
            add_blocks=add_bl,
        )
        console.print(f"[green]✓[/green] Updated task [cyan]#{task['id']}[/cyan] → status={task['status']}")
    except TaskManagerError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@task_app.command("render")
def task_render() -> None:
    """Print a compact text view of the task board."""
    tm = _get_manager()
    console.print(tm.render())
