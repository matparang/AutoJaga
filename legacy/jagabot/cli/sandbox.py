"""Sandbox CLI commands for Jagabot — test, configure, and monitor Docker sandbox."""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

sandbox_app = typer.Typer(
    help="Manage Docker sandbox for secure code execution"
)

console = Console()


@sandbox_app.command("status")
def sandbox_status() -> None:
    """Check sandbox status — Docker availability, permissions, and config."""
    import shutil
    from jagabot.config.loader import load_config
    from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig

    cfg = load_config()
    scfg = SandboxConfig.from_pydantic(cfg.tools.sandbox)
    exe = SafePythonExecutor(scfg)

    table = Table(title="🐳 Sandbox Status")
    table.add_column("Check", style="cyan")
    table.add_column("Result")

    docker_bin = shutil.which("docker")
    table.add_row("Docker binary", f"✅ {docker_bin}" if docker_bin else "❌ Not found")
    table.add_row(
        "Docker available",
        "✅ Yes" if exe.docker_available else "❌ No (force_fallback or missing)",
    )
    table.add_row("Force fallback", "⚠️  Yes" if scfg.force_fallback else "No")
    table.add_row("Subprocess fallback", "✅ Enabled" if scfg.allow_subprocess_fallback else "❌ Disabled")
    table.add_row("Timeout", f"{scfg.timeout_s}s")
    table.add_row("Memory limit", scfg.memory_limit)
    table.add_row("CPU limit", str(scfg.cpu_limit))
    table.add_row("Network", "Enabled" if scfg.network else "Disabled (isolated)")
    table.add_row("Image", scfg.image)

    console.print(table)


@sandbox_app.command("test")
def sandbox_test(
    timeout: int = typer.Option(5, "--timeout", "-t", help="Timeout in seconds"),
) -> None:
    """Test sandbox with a simple Python execution (print(2+2))."""
    from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig

    scfg = SandboxConfig(timeout_s=timeout)
    exe = SafePythonExecutor(scfg)

    console.print("[bold]Running sandbox test:[/bold] print(2+2)")
    result = asyncio.run(exe.execute("print(2+2)"))

    if result.success and "4" in result.output:
        console.print(f"✅ [green]Success[/green] — output: {result.output.strip()}")
    else:
        console.print(f"❌ [red]Failed[/red] — error: {result.error}")

    console.print(f"   Engine: {result.engine}")
    console.print(f"   Duration: {result.duration_ms:.1f}ms")


@sandbox_app.command("config")
def sandbox_config_show() -> None:
    """Show current sandbox configuration from config.json."""
    from jagabot.config.loader import load_config

    cfg = load_config()
    scfg = cfg.tools.sandbox

    table = Table(title="⚙️  Sandbox Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("timeout", f"{scfg.timeout}s")
    table.add_row("memory_limit", scfg.memory_limit)
    table.add_row("cpu_limit", str(scfg.cpu_limit))
    table.add_row("network", str(scfg.network))
    table.add_row("image", scfg.image)
    table.add_row("allow_fallback", str(scfg.allow_fallback))
    table.add_row("log_executions", str(scfg.log_executions))
    table.add_row("force_fallback", str(scfg.force_fallback))

    console.print(table)


@sandbox_app.command("set")
def sandbox_config_set(
    timeout: Optional[int] = typer.Option(None, "--timeout", help="Timeout in seconds"),
    memory: Optional[str] = typer.Option(None, "--memory", help='Memory limit (e.g. "256m")'),
    cpus: Optional[float] = typer.Option(None, "--cpus", help="CPU limit (e.g. 1.0)"),
    force_fallback: Optional[bool] = typer.Option(None, "--force-fallback/--no-force-fallback", help="Force subprocess mode"),
) -> None:
    """Update sandbox settings in config.json."""
    from jagabot.config.loader import load_config, save_config

    cfg = load_config()
    changed = []

    if timeout is not None:
        cfg.tools.sandbox.timeout = timeout
        changed.append(f"timeout → {timeout}s")
    if memory is not None:
        cfg.tools.sandbox.memory_limit = memory
        changed.append(f"memory_limit → {memory}")
    if cpus is not None:
        cfg.tools.sandbox.cpu_limit = cpus
        changed.append(f"cpu_limit → {cpus}")
    if force_fallback is not None:
        cfg.tools.sandbox.force_fallback = force_fallback
        changed.append(f"force_fallback → {force_fallback}")

    if not changed:
        console.print("[yellow]No settings changed.[/yellow] Use --timeout, --memory, --cpus, or --force-fallback.")
        return

    save_config(cfg)
    for c in changed:
        console.print(f"  ✅ {c}")
    console.print("[green]Configuration saved.[/green]")


@sandbox_app.command("logs")
def sandbox_logs(
    n: int = typer.Option(20, "--last", "-n", help="Number of recent entries"),
) -> None:
    """Show recent sandbox execution logs from the tracker database."""
    from jagabot.sandbox.tracker import SandboxTracker

    tracker = SandboxTracker()
    try:
        records = tracker.get_recent(n)
        if not records:
            console.print("[dim]No sandbox executions recorded yet.[/dim]")
            return

        table = Table(title=f"📋 Last {len(records)} Sandbox Executions")
        table.add_column("ID", style="dim")
        table.add_column("Subagent")
        table.add_column("Type")
        table.add_column("Engine")
        table.add_column("Success")
        table.add_column("Time (ms)")
        table.add_column("Timestamp")

        for r in records:
            ok = "✅" if r.success else "❌"
            table.add_row(
                str(r.id),
                r.subagent or "-",
                r.calc_type or "-",
                r.engine,
                ok,
                f"{r.exec_time_ms:.1f}",
                r.timestamp,
            )
        console.print(table)

        # Usage summary
        report = tracker.get_usage_report()
        if report:
            stable = Table(title="📊 Usage by Subagent")
            stable.add_column("Subagent")
            stable.add_column("Total")
            stable.add_column("Successes")
            stable.add_column("Avg Time (ms)")
            for row in report:
                stable.add_row(
                    row["subagent"] or "(unnamed)",
                    str(row["total"]),
                    str(row["successes"]),
                    f"{row['avg_time_ms']:.1f}",
                )
            console.print(stable)
    finally:
        tracker.close()


@sandbox_app.command("force-fallback")
def sandbox_force_fallback(
    enable: bool = typer.Option(True, "--enable/--disable", help="Enable or disable forced fallback"),
) -> None:
    """Toggle forced subprocess fallback mode (skips Docker)."""
    from jagabot.config.loader import load_config, save_config

    cfg = load_config()
    cfg.tools.sandbox.force_fallback = enable
    save_config(cfg)

    if enable:
        console.print("⚠️  [yellow]Force fallback ENABLED[/yellow] — Docker sandbox will be skipped.")
    else:
        console.print("✅ [green]Force fallback DISABLED[/green] — Docker sandbox will be used when available.")
