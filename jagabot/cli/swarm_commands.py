"""CLI commands for swarm mode — parallel financial analysis."""

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

swarm_app = typer.Typer(help="Swarm mode — parallel financial analysis across worker processes")
console = Console()


@swarm_app.command("analyze")
def swarm_analyze(
    query: str = typer.Argument(..., help="Financial analysis query"),
    workers: int = typer.Option(None, "--workers", "-w", help="Max worker processes"),
    locale: str = typer.Option("en", "--locale", "-l", help="Output locale (en/ms/id)"),
    timeout: float = typer.Option(120.0, "--timeout", "-t", help="Global timeout in seconds"),
) -> None:
    """Run a swarm analysis on a financial query."""
    from jagabot.swarm.memory_owner import SwarmOrchestrator

    console.print(f"[bold cyan]🐝 Jagabot Swarm[/bold cyan] — analyzing: [yellow]{query}[/yellow]")

    orchestrator = SwarmOrchestrator(max_workers=workers, locale=locale)
    try:
        report = orchestrator.process_query(query, global_timeout=timeout)
        console.print(Markdown(report))
    finally:
        orchestrator.shutdown()


@swarm_app.command("status")
def swarm_status() -> None:
    """Show swarm status — backend, workers, analysis history."""
    from jagabot.swarm.memory_owner import SwarmOrchestrator
    from jagabot.swarm.queue_backend import get_backend

    orchestrator = SwarmOrchestrator()
    try:
        info = orchestrator.status()
        backend = get_backend(prefer_redis=True)
        health = backend.health_check()

        table = Table(title="🐝 Swarm Status", show_header=False)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Backend", health["backend"])
        table.add_row("Backend Available", "✅" if health["available"] else "❌")
        table.add_row("Max Workers", str(info["max_workers"]))
        table.add_row("Available Tools", str(info["available_tools"]))
        table.add_row("Total Analyses", str(info["total_analyses"]))
        table.add_row("DB Path", info["db_path"])
        table.add_row("Locale", info["locale"])
        console.print(table)

        history = orchestrator.get_history(5)
        if history:
            htable = Table(title="Recent Analyses")
            htable.add_column("ID", style="dim")
            htable.add_column("Query")
            htable.add_column("Time", justify="right")
            htable.add_column("Date", style="dim")
            for h in history:
                htable.add_row(h["id"], h["query"][:50], f"{h['elapsed_s']:.1f}s", h["timestamp"])
            console.print(htable)
    finally:
        orchestrator.shutdown()


@swarm_app.command("workers")
def swarm_workers() -> None:
    """List all available swarm workers (tools)."""
    from jagabot.swarm.tool_registry import get_all_tool_names

    names = get_all_tool_names()
    table = Table(title=f"🐝 Swarm Workers ({len(names)} available)")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Tool Name", style="cyan")
    for i, name in enumerate(names, 1):
        table.add_row(str(i), name)
    console.print(table)


@swarm_app.command("history")
def swarm_history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of recent analyses to show"),
) -> None:
    """Show swarm analysis history."""
    from jagabot.swarm.memory_owner import SwarmOrchestrator

    orchestrator = SwarmOrchestrator()
    try:
        history = orchestrator.get_history(limit)
        if not history:
            console.print("[dim]No analyses yet. Run: jagabot swarm analyze \"your query\"[/dim]")
            return
        table = Table(title="📜 Swarm Analysis History")
        table.add_column("ID", style="dim")
        table.add_column("Query")
        table.add_column("Time", justify="right")
        table.add_column("Date", style="dim")
        for h in history:
            table.add_row(h["id"], h["query"][:60], f"{h['elapsed_s']:.1f}s", h["timestamp"])
        console.print(table)
    finally:
        orchestrator.shutdown()


@swarm_app.command("dashboard")
def swarm_dashboard(
    refresh: float = typer.Option(2.0, "--refresh", "-r", help="Refresh interval in seconds"),
    once: bool = typer.Option(False, "--once", help="Print dashboard once and exit"),
) -> None:
    """Show Mission Control dashboard — real-time swarm monitoring."""
    from jagabot.swarm.memory_owner import SwarmOrchestrator
    from jagabot.swarm.dashboard import generate_dashboard

    orchestrator = SwarmOrchestrator()
    try:
        status = orchestrator.status()
        output = generate_dashboard(
            tracker=orchestrator.tracker,
            orchestrator_status=status,
            watchdog_health=orchestrator.watchdog.health(),
            cost_summary=orchestrator.costs.summary(),
        )
        console.print(output)
        if once:
            return

        import time
        try:
            while True:
                time.sleep(refresh)
                console.clear()
                status = orchestrator.status()
                output = generate_dashboard(
                    tracker=orchestrator.tracker,
                    orchestrator_status=status,
                    watchdog_health=orchestrator.watchdog.health(),
                    cost_summary=orchestrator.costs.summary(),
                )
                console.print(output)
        except KeyboardInterrupt:
            console.print("\n[dim]Dashboard stopped.[/dim]")
    finally:
        orchestrator.shutdown()


@swarm_app.command("schedule")
def swarm_schedule(
    action: str = typer.Argument("list", help="Action: list, add, remove, presets"),
    name: str = typer.Option("", "--name", "-n", help="Workflow name"),
    query: str = typer.Option("", "--query", "-q", help="Analysis query"),
    cron: str = typer.Option("", "--cron", "-c", help="Cron expression"),
    job_id: str = typer.Option("", "--id", help="Job ID (for remove)"),
    preset: str = typer.Option("", "--preset", "-p", help="Preset name (for add)"),
) -> None:
    """Manage scheduled swarm workflows."""
    from jagabot.swarm.scheduler import SwarmScheduler
    from jagabot.swarm.workflows import PRESETS, get_preset

    scheduler = SwarmScheduler()

    if action == "list":
        workflows = scheduler.list_workflows(include_disabled=True)
        if not workflows:
            console.print("[dim]No scheduled workflows. Use: jagabot swarm schedule add[/dim]")
            return
        table = Table(title="📅 Scheduled Workflows")
        table.add_column("ID", style="dim")
        table.add_column("Name")
        table.add_column("Schedule")
        table.add_column("Enabled")
        table.add_column("Last Status")
        for wf in workflows:
            table.add_row(
                wf.id, wf.name,
                wf.schedule.expr or f"every {wf.schedule.every_ms}ms",
                "✅" if wf.enabled else "❌",
                wf.state.last_status or "—",
            )
        console.print(table)

    elif action == "presets":
        table = Table(title="📋 Available Presets")
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Cron")
        for key, p in PRESETS.items():
            table.add_row(key, p.description, p.cron_expr)
        console.print(table)

    elif action == "add":
        if preset:
            p = get_preset(preset)
            if not p:
                console.print(f"[red]Unknown preset: {preset}. Use 'presets' to list.[/red]")
                return
            job = scheduler.add_workflow(p.name, p.query, p.cron_expr)
            console.print(f"[green]✅ Added preset '{p.name}' (ID: {job.id})[/green]")
        elif name and query and cron:
            job = scheduler.add_workflow(name, query, cron)
            console.print(f"[green]✅ Added workflow '{name}' (ID: {job.id})[/green]")
        else:
            console.print("[red]Provide --preset or (--name + --query + --cron)[/red]")

    elif action == "remove":
        if not job_id:
            console.print("[red]Provide --id to remove[/red]")
            return
        if scheduler.remove_workflow(job_id):
            console.print(f"[green]✅ Removed workflow {job_id}[/green]")
        else:
            console.print(f"[red]Workflow {job_id} not found[/red]")

    else:
        console.print(f"[red]Unknown action: {action}. Use: list, add, remove, presets[/red]")


@swarm_app.command("costs")
def swarm_costs(
    budget: float = typer.Option(None, "--budget", "-b", help="Set daily budget (e.g. 1.00)"),
    monthly_budget: float = typer.Option(None, "--monthly-budget", help="Set monthly budget"),
) -> None:
    """Show cost tracking and manage budgets."""
    from jagabot.swarm.costs import CostTracker

    tracker = CostTracker()
    try:
        if budget is not None:
            tracker.set_budget("daily", budget)
            console.print(f"[green]✅ Daily budget set to ${budget:.4f}[/green]")

        if monthly_budget is not None:
            tracker.set_budget("monthly", monthly_budget)
            console.print(f"[green]✅ Monthly budget set to ${monthly_budget:.4f}[/green]")

        summary = tracker.summary()
        table = Table(title="💰 Swarm Costs")
        table.add_column("Period", style="cyan")
        table.add_column("Cost", justify="right")
        table.add_row("Today", f"${summary['daily']:.6f}")
        table.add_row("This Month", f"${summary['monthly']:.6f}")
        console.print(table)

        budgets = summary.get("budgets", {})
        if budgets:
            btable = Table(title="📊 Budgets")
            btable.add_column("Period")
            btable.add_column("Limit", justify="right")
            for period, amount in budgets.items():
                btable.add_row(period, f"${amount:.4f}")
            console.print(btable)

        by_tool = summary.get("by_tool", [])
        if by_tool:
            ttable = Table(title="🔧 Cost by Tool")
            ttable.add_column("Tool", style="cyan")
            ttable.add_column("Invocations", justify="right")
            ttable.add_column("Total Cost", justify="right")
            ttable.add_column("Avg Time", justify="right")
            for t in by_tool:
                ttable.add_row(
                    t["tool"], str(t["invocations"]),
                    f"${t['total_cost']:.6f}", f"{t['avg_time']:.3f}s",
                )
            console.print(ttable)

        alerts = summary.get("recent_alerts", [])
        if alerts:
            atable = Table(title="⚠️ Recent Budget Alerts")
            atable.add_column("Period")
            atable.add_column("Budget", justify="right")
            atable.add_column("Actual", justify="right")
            atable.add_column("When", style="dim")
            for a in alerts:
                atable.add_row(a["period"], f"${a['budget']:.4f}", f"${a['actual']:.4f}", a["triggered_at"])
            console.print(atable)
    finally:
        tracker.shutdown()


@swarm_app.command("health")
def swarm_health() -> None:
    """Show watchdog health and system metrics."""
    from jagabot.swarm.memory_owner import SwarmOrchestrator

    orchestrator = SwarmOrchestrator()
    try:
        wd_health = orchestrator.watchdog.health()
        table = Table(title="🏥 Swarm Health")
        table.add_column("Metric", style="cyan")
        table.add_column("Value")
        table.add_row("Watchdog", "✅ Running" if wd_health["running"] else "❌ Stopped")
        table.add_row("Check Interval", f"{wd_health['check_interval_s']}s")
        table.add_row("Total Alerts", str(wd_health["total_alerts"]))
        table.add_row("Recent Critical", str(wd_health["recent_critical"]))

        sys_info = wd_health.get("system", {})
        if "cpu_percent" in sys_info:
            table.add_row("CPU Usage", f"{sys_info['cpu_percent']:.1f}%")
            table.add_row("Memory Usage", f"{sys_info['memory_percent']:.1f}%")
            table.add_row("Memory Available", f"{sys_info.get('memory_available_mb', '?')}MB")
        elif "note" in sys_info:
            table.add_row("System Metrics", sys_info["note"])
        console.print(table)

        tracker_stats = orchestrator.tracker.stats()
        stable = Table(title="👷 Worker Stats")
        stable.add_column("Metric", style="cyan")
        stable.add_column("Value")
        stable.add_row("Running", str(tracker_stats["running"]))
        stable.add_row("Stalled", str(tracker_stats["stalled"]))
        stable.add_row("Completed", str(tracker_stats["completed"]))
        stable.add_row("Errors", str(tracker_stats["errors"]))
        stable.add_row("Avg Time", f"{tracker_stats['avg_elapsed_s']:.3f}s")
        console.print(stable)

        alerts = orchestrator.watchdog.get_alerts(10)
        if alerts:
            atable = Table(title="🚨 Recent Watchdog Alerts")
            atable.add_column("Level")
            atable.add_column("Source")
            atable.add_column("Message")
            for a in alerts:
                level_icon = "🔴" if a.level == "critical" else "🟡"
                atable.add_row(f"{level_icon} {a.level}", a.source, a.message[:80])
            console.print(atable)
    finally:
        orchestrator.shutdown()
