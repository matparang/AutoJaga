"""CLI commands for JAGABOT Lab — parallel tool execution.

Registered as a typer sub-app under the main ``jagabot`` CLI.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

lab_app = typer.Typer(
    name="lab",
    help="JAGABOT Lab — tool execution and parallel workflows.",
    no_args_is_help=True,
)

console = Console()


@lab_app.command("list-tools")
def list_tools(
    category: str = typer.Option(None, "--category", "-c", help="Filter by category"),
) -> None:
    """List all registered tools with categories."""
    from jagabot.ui.lab.tool_registry import LabToolRegistry

    reg = LabToolRegistry()
    cats = reg.get_categories()

    table = Table(title=f"JAGABOT Tools ({reg.tool_count()})")
    table.add_column("Category", style="cyan")
    table.add_column("Tool", style="green")
    table.add_column("Methods", style="yellow")

    for cat, names in sorted(cats.items()):
        if category and cat != category:
            continue
        for name in sorted(names):
            methods = reg.get_tool_methods(name)
            table.add_row(cat, name, ", ".join(methods) if methods else "—")

    console.print(table)


@lab_app.command("run-workflow")
def run_workflow(
    workflow: str = typer.Argument(..., help="Workflow name: risk_analysis, portfolio_review, full_analysis"),
    params_file: Path = typer.Option(None, "--params", "-p", help="JSON file with workflow parameters"),
    params_json: str = typer.Option(None, "--json", "-j", help="Inline JSON parameters"),
) -> None:
    """Run a predefined parallel workflow."""
    from jagabot.lab.parallel import ParallelLab

    if params_file and params_file.exists():
        data = json.loads(params_file.read_text(encoding="utf-8"))
    elif params_json:
        data = json.loads(params_json)
    else:
        console.print("[red]Provide --params <file> or --json '<json>'[/red]")
        raise typer.Exit(1)

    plab = ParallelLab()
    available = plab.available_workflows()
    if workflow not in available:
        console.print(f"[red]Unknown workflow '{workflow}'. Available: {available}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Running workflow: {workflow}...[/cyan]")
    result = asyncio.run(plab.execute_workflow(workflow, data))

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"Workflow: {workflow}")
    table.add_column("Tool", style="green")
    table.add_column("Success", style="cyan")
    table.add_column("Time (s)", style="yellow")

    for r in result.get("results", []):
        task = r.get("task", {})
        table.add_row(
            task.get("tool", "?"),
            "✅" if r.get("success") else "❌",
            str(r.get("execution_time", "—")),
        )

    console.print(table)
    console.print(
        f"\n[bold]Status:[/bold] {result['status']} | "
        f"[bold]Completed:[/bold] {result['completed']}/{result['total']} | "
        f"[bold]Wall time:[/bold] {result['wall_time']}s | "
        f"[bold]Speedup:[/bold] {result.get('speedup_estimate', '?')}x"
    )


@lab_app.command("list-workflows")
def list_workflows() -> None:
    """Show available parallel workflows."""
    from jagabot.lab.parallel import ParallelLab

    for name in ParallelLab.available_workflows():
        spec = ParallelLab._WORKFLOWS[name]
        tools = [e["tool"] for e in spec]
        console.print(f"  [cyan]{name}[/cyan]: {', '.join(tools)}")


@lab_app.command("run-tool")
def run_tool(
    tool_name: str = typer.Argument(..., help="Tool name (e.g. monte_carlo)"),
    params_json: str = typer.Option("{}", "--json", "-j", help="JSON parameters"),
) -> None:
    """Execute a single tool via LabService."""
    from jagabot.lab.service import LabService

    lab = LabService()
    params = json.loads(params_json)

    result = asyncio.run(lab.execute(tool_name, params))

    if result.get("success"):
        console.print(f"[green]✅ {tool_name}[/green] ({result['execution_time']}s)")
        console.print(json.dumps(result["output"], indent=2, default=str))
    else:
        console.print(f"[red]❌ {tool_name}[/red]: {result.get('error', 'Unknown error')}")


@lab_app.command("scaling-status")
def scaling_status() -> None:
    """Show current auto-scaling configuration and capabilities."""
    from jagabot.lab.scaling import ScalingConfig

    cfg = ScalingConfig()

    table = Table(title="Auto-Scaling Configuration (v3.5)")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Min workers", str(cfg.min_workers))
    table.add_row("Max workers", str(cfg.max_workers))
    table.add_row("Scale up threshold", f"{cfg.scale_up_threshold} queued tasks")
    table.add_row("Scale down threshold", f"{cfg.scale_down_threshold} queued tasks")
    table.add_row("Cooldown period", f"{cfg.cooldown_period}s")
    table.add_row("Scale up factor", f"{cfg.scale_up_factor}x")
    table.add_row("Scale down factor", f"{cfg.scale_down_factor}x")
    table.add_row("Monitor interval", f"{cfg.monitor_interval}s")

    console.print(table)


@lab_app.command("run-scaled")
def run_scaled(
    workflow: str = typer.Argument(..., help="Workflow: risk_analysis, portfolio_review, full_analysis"),
    params_file: Path = typer.Option(None, "--params", "-p", help="JSON file with workflow parameters"),
    params_json: str = typer.Option(None, "--json", "-j", help="Inline JSON parameters"),
    min_workers: int = typer.Option(2, "--min", help="Minimum workers"),
    max_workers: int = typer.Option(16, "--max", help="Maximum workers"),
) -> None:
    """Run a workflow with auto-scaling worker pool."""
    from jagabot.lab.parallel import ParallelLab
    from jagabot.lab.scaling import ScalingConfig

    if params_file and params_file.exists():
        data = json.loads(params_file.read_text(encoding="utf-8"))
    elif params_json:
        data = json.loads(params_json)
    else:
        console.print("[red]Provide --params <file> or --json '<json>'[/red]")
        raise typer.Exit(1)

    config = ScalingConfig(min_workers=min_workers, max_workers=max_workers)
    plab = ParallelLab(auto_scale=True, scaling_config=config)
    available = plab.available_workflows()
    if workflow not in available:
        console.print(f"[red]Unknown workflow '{workflow}'. Available: {available}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Running scaled workflow: {workflow} (workers: {min_workers}-{max_workers})...[/cyan]")
    result = asyncio.run(plab.execute_workflow(workflow, data))

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"Scaled Workflow: {workflow}")
    table.add_column("Tool", style="green")
    table.add_column("Success", style="cyan")
    table.add_column("Time (s)", style="yellow")

    for r in result.get("results", []):
        task = r.get("task", {})
        table.add_row(
            task.get("tool", "?"),
            "✅" if r.get("success") else "❌",
            str(r.get("execution_time", "—")),
        )

    console.print(table)
    console.print(
        f"\n[bold]Status:[/bold] {result['status']} | "
        f"[bold]Completed:[/bold] {result['completed']}/{result['total']} | "
        f"[bold]Wall time:[/bold] {result['wall_time']}s | "
        f"[bold]Speedup:[/bold] {result.get('speedup_estimate', '?')}x"
    )
