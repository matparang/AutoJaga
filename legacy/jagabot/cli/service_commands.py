"""CLI commands for service (daemon) management."""

import typer
from rich.console import Console

service_app = typer.Typer(help="Manage the jagabot background service (daemon mode)")
console = Console()


@service_app.command("start")
def service_start(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """Start jagabot as a persistent background service."""
    from jagabot.cli.daemon import start_service, LOG_FILE

    try:
        pid = start_service(port=port, verbose=verbose)
        console.print(f"[green]✓[/green] jagabot service started (PID {pid})")
        console.print(f"  Logs: {LOG_FILE}")
        console.print(f"  Stop: [bold]jagabot service stop[/bold]")
    except RuntimeError as exc:
        console.print(f"[red]✗[/red] {exc}")
        raise typer.Exit(1)


@service_app.command("stop")
def service_stop(
    timeout: int = typer.Option(10, "--timeout", "-t", help="Seconds to wait before force-kill"),
):
    """Stop the running jagabot service."""
    from jagabot.cli.daemon import stop_service, read_pid, is_running

    pid = read_pid()
    if pid is None or not is_running(pid):
        console.print("[yellow]Service is not running.[/yellow]")
        return

    console.print(f"Stopping jagabot service (PID {pid})...")
    ok = stop_service(timeout=timeout)
    if ok:
        console.print("[green]✓[/green] Service stopped.")
    else:
        console.print("[red]✗[/red] Failed to stop service — process may still be running.")
        raise typer.Exit(1)


@service_app.command("restart")
def service_restart(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
    timeout: int = typer.Option(10, "--timeout", "-t", help="Stop timeout"),
):
    """Restart the jagabot service (stop + start)."""
    from jagabot.cli.daemon import stop_service, read_pid, is_running

    pid = read_pid()
    if pid and is_running(pid):
        console.print(f"Stopping jagabot service (PID {pid})...")
        stop_service(timeout=timeout)

    import time
    time.sleep(0.5)

    service_start(port=port, verbose=verbose)


@service_app.command("status")
def service_status_cmd():
    """Show the status of the jagabot service."""
    from jagabot.cli.daemon import service_status

    info = service_status()

    if info["running"]:
        uptime = info.get("uptime_s")
        uptime_str = ""
        if uptime is not None:
            mins, secs = divmod(uptime, 60)
            hours, mins = divmod(mins, 60)
            uptime_str = f"  Uptime: {hours}h {mins}m {secs}s"

        console.print(f"[green]● running[/green]  PID {info['pid']}{uptime_str}")
    else:
        console.print("[dim]● stopped[/dim]")

    console.print(f"  PID file: {info['pid_file']}")
    console.print(f"  Log file: {info['log_file']}")


@service_app.command("logs")
def service_logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output (like tail -f)"),
):
    """View the jagabot service log."""
    from jagabot.cli.daemon import tail_log, follow_log

    if follow:
        follow_log()
    else:
        output = tail_log(lines)
        console.print(output)
