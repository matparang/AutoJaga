"""CLI commands for managing the DeepSeek MCP server."""

from __future__ import annotations

import json
import os

import typer
from rich.console import Console
from rich.table import Table

from jagabot.mcp.server_manager import MCPServerManager
from jagabot.mcp.client import DeepSeekMCPClient, MCPClientError

console = Console()
mcp_app = typer.Typer(help="Manage the local DeepSeek MCP server")


def _get_manager() -> MCPServerManager:
    port = int(os.environ.get("MCP_HTTP_PORT", "3001"))
    host = os.environ.get("MCP_HTTP_HOST", "127.0.0.1")
    return MCPServerManager(port=port, host=host)


def _get_client(manager: MCPServerManager) -> DeepSeekMCPClient:
    return DeepSeekMCPClient(host=manager.host, port=manager.port)


@mcp_app.command("status")
def cmd_status() -> None:
    """Show MCP server status and config."""
    manager = _get_manager()
    info = manager.detect_info()
    st = manager.status()

    status_str = st["status"]
    if status_str == "running":
        console.print(f"✅ MCP Server [bold green]running[/] (PID: {st['pid']})")
        console.print(f"   URL: {st.get('url', '')}{st.get('path', '')}")
    else:
        console.print("❌ MCP Server [bold red]stopped[/]")

    console.print(f"📁 Repo: {info['repo_path']}")
    console.print(f"🔧 Language: {info['language']}")
    console.print(f"🌐 Port: {info['port']}")
    console.print(f"🏗  Built: {'✅' if info['is_built'] else '❌ (run: npm run build)'}")


@mcp_app.command("start")
def cmd_start(
    api_key: str = typer.Option("", "--api-key", "-k", envvar="DEEPSEEK_API_KEY", help="DeepSeek API key"),
) -> None:
    """Start the MCP server in HTTP mode."""
    manager = _get_manager()
    result = manager.start(deepseek_api_key=api_key)
    if result.get("success"):
        already = result.get("already_running", False)
        pid = result.get("pid")
        if already:
            console.print(f"ℹ️  Already running (PID: {pid})")
        else:
            console.print(f"✅ MCP Server started (PID: {pid})")
    else:
        console.print(f"❌ Failed to start: {result.get('error')}")
        raise typer.Exit(1)


@mcp_app.command("stop")
def cmd_stop() -> None:
    """Stop the MCP server."""
    manager = _get_manager()
    result = manager.stop()
    if result.get("success"):
        console.print("✅ MCP Server stopped")
    else:
        console.print(f"❌ {result.get('error', 'Could not stop server')}")
        raise typer.Exit(1)


@mcp_app.command("restart")
def cmd_restart(
    api_key: str = typer.Option("", "--api-key", "-k", envvar="DEEPSEEK_API_KEY", help="DeepSeek API key"),
) -> None:
    """Restart the MCP server."""
    manager = _get_manager()
    stop_result = manager.stop()
    if stop_result.get("success"):
        console.print("🔄 Stopped. Restarting…")
    start_result = manager.start(deepseek_api_key=api_key)
    if start_result.get("success"):
        console.print(f"✅ MCP Server restarted (PID: {start_result['pid']})")
    else:
        console.print(f"❌ Failed to restart: {start_result.get('error')}")
        raise typer.Exit(1)


@mcp_app.command("tools")
def cmd_tools() -> None:
    """List all tools exposed by the MCP server."""
    manager = _get_manager()
    client = _get_client(manager)
    try:
        tools = client.list_tools()
    except MCPClientError as exc:
        console.print(f"❌ Cannot connect to MCP server: {exc}")
        console.print("💡 Try: jagabot mcp start")
        raise typer.Exit(1)

    if not tools:
        console.print("No tools found.")
        return

    table = Table(title="DeepSeek MCP Tools", show_lines=True)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description")
    for tool in tools:
        name = tool.get("name", "—")
        desc = ""
        schema = tool.get("inputSchema") or tool.get("input_schema") or {}
        desc = tool.get("description", schema.get("description", ""))
        table.add_row(name, desc)
    console.print(table)


@mcp_app.command("call")
def cmd_call(
    tool_name: str = typer.Argument(..., help="MCP tool name"),
    params: str = typer.Option("{}", "--params", "-p", help="JSON parameters"),
) -> None:
    """Call an MCP tool directly."""
    manager = _get_manager()
    client = _get_client(manager)
    try:
        args = json.loads(params)
    except json.JSONDecodeError as exc:
        console.print(f"❌ Invalid JSON params: {exc}")
        raise typer.Exit(1)

    try:
        result = client.call_tool(tool_name, args)
        console.print_json(json.dumps(result))
    except MCPClientError as exc:
        console.print(f"❌ MCP error: {exc}")
        raise typer.Exit(1)
