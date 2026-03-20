"""CLI commands for jagabot."""

import asyncio
import os
import signal
from pathlib import Path
import select
import sys
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout

from jagabot import __version__, __logo__

app = typer.Typer(
    name="jagabot",
    help=f"{__logo__} jagabot - Personal AI Assistant",
    no_args_is_help=True,
)

# Register Lab sub-commands (v3.4 Phase 2)
from jagabot.cli.lab_commands import lab_app
app.add_typer(lab_app, name="lab", help="Lab — tool execution & parallel workflows")

# Register MCP sub-commands (v3.9.0)
from jagabot.cli.mcp_commands import mcp_app
app.add_typer(mcp_app, name="mcp", help="Manage the local DeepSeek MCP server")

# Register Upsonic sub-commands (v3.11.0)
from jagabot.cli.upsonic_commands import upsonic_app
app.add_typer(upsonic_app, name="upsonic", help="Memory-backed chat sessions via Upsonic Agent")

# Register Task sub-commands (v4.0)
from jagabot.cli.task_commands import task_app
app.add_typer(task_app, name="task", help="Persistent task board with dependency graph")

console = Console()
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}

# ---------------------------------------------------------------------------
# CLI input: prompt_toolkit for editing, paste, history, and display
# ---------------------------------------------------------------------------

_PROMPT_SESSION: PromptSession | None = None
_SAVED_TERM_ATTRS = None  # original termios settings, restored on exit


def _flush_pending_tty_input() -> None:
    """Drop unread keypresses typed while the model was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return


def _restore_terminal() -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


def _init_prompt_session() -> None:
    """Create the prompt_toolkit session with persistent file history."""
    global _PROMPT_SESSION, _SAVED_TERM_ATTRS

    # Save terminal state so we can restore it on exit
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    history_file = Path.home() / ".jagabot" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),
        enable_open_in_editor=False,
        multiline=False,   # Enter submits (single line mode)
    )


def _print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response with consistent terminal styling."""
    content = response or ""
    body = Markdown(content) if render_markdown else Text(content)
    console.print()
    console.print(f"[cyan]{__logo__} jagabot[/cyan]")
    console.print(body)
    console.print()


def _is_exit_command(command: str) -> bool:
    """Return True when input should end interactive chat."""
    return command.lower() in EXIT_COMMANDS


async def _read_interactive_input_async() -> str:
    """Read user input using prompt_toolkit (handles paste, history, display).

    prompt_toolkit natively handles:
    - Multiline paste (bracketed paste mode)
    - History navigation (up/down arrows)
    - Clean display (no ghost characters or artifacts)
    """
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    try:
        with patch_stdout():
            return await _PROMPT_SESSION.prompt_async(
                HTML("<b fg='ansiblue'>You:</b> "),
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc



def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} jagabot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """jagabot - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize jagabot configuration and workspace."""
    from jagabot.config.loader import get_config_path, load_config, save_config
    from jagabot.config.schema import Config
    from jagabot.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    
    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        console.print("  [bold]y[/bold] = overwrite with defaults (existing values will be lost)")
        console.print("  [bold]N[/bold] = refresh config, keeping existing values and adding new fields")
        if typer.confirm("Overwrite?"):
            config = Config()
            save_config(config)
            console.print(f"[green]✓[/green] Config reset to defaults at {config_path}")
        else:
            config = load_config()
            save_config(config)
            console.print(f"[green]✓[/green] Config refreshed at {config_path} (existing values preserved)")
    else:
        save_config(Config())
        console.print(f"[green]✓[/green] Created config at {config_path}")
    
    # Create workspace
    workspace = get_workspace_path()
    
    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Created workspace at {workspace}")
    
    # Create default bootstrap files
    _create_workspace_templates(workspace)
    
    console.print(f"\n{__logo__} jagabot is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.jagabot/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]jagabot agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/WhatsApp? See: https://github.com/HKUDS/jagabot#-chat-apps[/dim]")




def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    templates = {
        "AGENTS.md": """# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Guidelines

- Always explain what you're doing before taking actions
- Ask for clarification when the request is ambiguous
- Use tools to help accomplish tasks
- Remember important information in memory/MEMORY.md; past events are logged in memory/HISTORY.md
""",
        "SOUL.md": """# Soul

I am jagabot, a lightweight AI assistant.

## Personality

- Helpful and friendly
- Concise and to the point
- Curious and eager to learn

## Values

- Accuracy over speed
- User privacy and safety
- Transparency in actions
""",
        "USER.md": """# User

Information about the user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
""",
    }
    
    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content)
            console.print(f"  [dim]Created {filename}[/dim]")
    
    # Create memory directory and MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about the user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)
""")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")
    
    history_file = memory_dir / "HISTORY.md"
    if not history_file.exists():
        history_file.write_text("")
        console.print("  [dim]Created memory/HISTORY.md[/dim]")

    # Create skills directory for custom user skills
    skills_dir = workspace / "skills"
    skills_dir.mkdir(exist_ok=True)


def _make_provider(config):
    """Create LiteLLMProvider from config — single provider, no fallback."""
    from jagabot.providers.litellm_provider import LiteLLMProvider

    p = config.get_provider()
    model = config.agents.defaults.model
    if not (p and p.api_key) and not model.startswith("bedrock/"):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.jagabot/config.json under providers section")
        raise typer.Exit(1)

    primary_name = config.get_provider_name()
    primary = LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=primary_name,
    )

    # NO FALLBACK — single provider only
    return primary


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def model(
    preset: str = typer.Argument(
        "status",
        help="Model preset: 1 (fast), 2 (smart), auto (automatic), status (show status)"
    ),
):
    """
    Switch model presets or show status.
    
    Examples:
        jagabot model 1      # Switch to fast model (gpt-4o-mini)
        jagabot model 2      # Switch to smart model (gpt-4o)
        jagabot model auto   # Restore automatic switching
        jagabot model status # Show current model and stats
    """
    from pathlib import Path
    from jagabot.core.model_switchboard import ModelSwitchboard
    
    switchboard = ModelSwitchboard(
        config_path=Path.home() / ".jagabot" / "config.json",
        workspace=Path.home() / ".jagabot" / "workspace",
    )
    
    if preset.lower() == "status":
        console.print(switchboard.get_status())
    elif preset.lower() == "auto":
        console.print(switchboard.set_auto())
    elif preset in ["1", "2"]:
        console.print(switchboard.manual_switch(preset))
    else:
        console.print(f"❌ Unknown preset: {preset}")
        console.print("Use: jagabot model [1|2|auto|status]")


@app.command()
def resume():
    """
    Resume last session from checkpoint.
    
    Use this when session was interrupted or budget exceeded.
    """
    from pathlib import Path
    from jagabot.core.session_checkpoint import load_latest_checkpoint
    
    workspace = Path.home() / ".jagabot" / "workspace"
    checkpoint = load_latest_checkpoint(workspace)
    
    if checkpoint:
        console.print(f"✅ Found checkpoint from turn {checkpoint['turn']}")
        console.print(f"   Timestamp: {checkpoint['timestamp']}")
        console.print(f"   Messages: {checkpoint['message_count']}")
        console.print(f"   Token estimate: ~{checkpoint['token_estimate']:,}")
        console.print("")
        console.print("⚠️  Note: Resume feature is coming soon.")
        console.print("   For now, your conversation is safely saved in:")
        console.print(f"   {workspace}/checkpoints/")
    else:
        console.print("❌ No checkpoint found.")
        console.print("   Checkpoints are saved automatically when budget is exceeded.")


@app.command()
def stack(
    mode: str = typer.Argument("status", help="status|stats"),
):
    """
    Show CognitiveStack M1/M2 routing stats.
    
    Examples:
        jagabot stack status  # Show current status
        jagabot stack stats   # Show session statistics
    """
    from pathlib import Path
    
    # Try to get agent instance (this requires running agent)
    # For now, show info message
    workspace = Path.home() / ".jagabot" / "workspace"
    
    console.print("**CognitiveStack Status**")
    console.print("")
    console.print("Model 1 (gpt-4o-mini): Classifier + Executor")
    console.print("Model 2 (gpt-4o): Planner only")
    console.print("")
    console.print("Usage:")
    console.print("  /stack status  # Show current routing status")
    console.print("  /stack stats   # Show session M1/M2 call counts")
    console.print("")
    console.print("⚠️  Full stats available when agent is running.")


@app.command()
def gateway(
    port: int = typer.Option(18800, "--port", "-p", help="WebSocket gateway port (PinchChat connects here)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    token: str = typer.Option("", "--token", "-t", help="Auth token (empty = no auth required)"),
    name: str = typer.Option("Jagabot", "--name", "-n", help="Agent display name"),
):
    """Start the jagabot WebSocket gateway for PinchChat."""
    from jagabot.config.loader import load_config, get_data_dir
    from jagabot.bus.queue import MessageBus
    from jagabot.agent.loop import AgentLoop
    from jagabot.channels.manager import ChannelManager
    from jagabot.session.manager import SessionManager
    from jagabot.cron.service import CronService
    from jagabot.cron.types import CronJob
    from jagabot.heartbeat.service import HeartbeatService
    from jagabot.gateway.server import GatewayServer

    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        import os
        os.environ["JAGABOT_VERBOSE"] = "1"

    console.print(f"{__logo__} Starting jagabot gateway on ws://0.0.0.0:{port}")
    
    config = load_config()
    bus = MessageBus()
    provider = _make_provider(config)
    session_manager = SessionManager(config.workspace_path)
    
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)
    
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=config.agents.defaults.temperature,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
    )
    
    async def on_cron_job(job: CronJob) -> str | None:
        response = await agent.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )
        if job.payload.deliver and job.payload.to:
            from jagabot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response or ""
            ))
        return response
    cron.on_job = on_cron_job
    
    async def on_heartbeat(prompt: str) -> str:
        from jagabot.heartbeat.service import HEARTBEAT_MAX_ITERATIONS
        return await agent.process_direct(
            prompt, session_key="heartbeat",
            max_iterations=HEARTBEAT_MAX_ITERATIONS,
        )
    
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,
        enabled=True,
    )
    
    channels = ChannelManager(config, bus)
    
    # Create the WebSocket gateway server
    gw = GatewayServer(
        agent_loop=agent,
        session_manager=session_manager,
        workspace=config.workspace_path,
        auth_token=token,
        port=port,
        agent_name=name,
        agent_emoji="🐯",
    )
    
    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels: {', '.join(channels.enabled_channels)}")
    
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} jobs")
    
    console.print(f"[green]✓[/green] Heartbeat: every 30m")
    console.print(f"[green]✓[/green] Gateway: ws://0.0.0.0:{port}")
    console.print(f"[blue]→[/blue] Connect PinchChat to [bold]ws://localhost:{port}[/bold]")
    
    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
                gw.start(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
    
    asyncio.run(run())




# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show jagabot runtime logs during chat"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose reasoning output"),
    tui: bool = typer.Option(False, "--tui", help="Start persistent TUI mode with slash commands"),
):
    """Interact with the agent directly."""
    from jagabot.config.loader import load_config
    from jagabot.bus.queue import MessageBus
    from jagabot.agent.loop import AgentLoop
    from loguru import logger

    config = load_config()

    bus = MessageBus()
    provider = _make_provider(config)

    if logs or verbose:
        logger.enable("jagabot")
    else:
        logger.disable("jagabot")

    # Enable verbose reasoning tracker
    if verbose:
        import os
        os.environ["JAGABOT_VERBOSE"] = "1"
    
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        temperature=config.agents.defaults.temperature,
        memory_window=config.agents.defaults.memory_window,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
    )
    
    # Show spinner when logs are off (no output to miss); skip when logs are on
    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        # Animated spinner is safe to use with prompt_toolkit input handling
        return console.status("[dim]jagabot is thinking...[/dim]", spinner="dots")

    # ── TUI mode ─────────────────────────────────────────────────
    if tui:
        # Launch the new Textual TUI
        from jagabot.cli.tui import run_tui
        run_tui()
        return

    if message:
        # Single message mode
        async def run_once():
            with _thinking_ctx():
                response = await agent_loop.process_direct(message, session_id)
            _print_agent_response(response, render_markdown=markdown)
        
        asyncio.run(run_once())
    else:
        # Interactive mode
        _init_prompt_session()
        console.print(f"{__logo__} Interactive mode (type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit)\n")

        def _exit_on_sigint(signum, frame):
            _restore_terminal()
            console.print("\nGoodbye!")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)
        
        async def run_interactive():
            while True:
                try:
                    _flush_pending_tty_input()
                    user_input = await _read_interactive_input_async()
                    command = user_input.strip()
                    if not command:
                        continue

                    if _is_exit_command(command):
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
                    
                    with _thinking_ctx():
                        response = await agent_loop.process_direct(user_input, session_id)
                    _print_agent_response(response, render_markdown=markdown)
                except KeyboardInterrupt:
                    _restore_terminal()
                    console.print("\nGoodbye!")
                    break
                except EOFError:
                    _restore_terminal()
                    console.print("\nGoodbye!")
                    break
        
        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


# Channels sub-commands (extracted to channels_commands.py)
from jagabot.cli.channels_commands import channels_app
app.add_typer(channels_app, name="channels")


# ============================================================================
# Cron Commands (extracted to cron_commands.py)
# ============================================================================

from jagabot.cli.cron_commands import cron_app
app.add_typer(cron_app, name="cron")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show jagabot status."""
    from jagabot.config.loader import load_config, get_config_path

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} jagabot Status\n")

    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        from jagabot.providers.registry import PROVIDERS

        console.print(f"Model: {config.agents.defaults.model}")

        # Check API keys from registry
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green]✓ {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                console.print(f"{spec.label}: {'[green]✓[/green]' if has_key else '[dim]not set[/dim]'}")


@app.command()
def budget(
    action: str = typer.Argument("status", help="status|set-session|set-daily"),
    value: int = typer.Argument(None, help="Budget value in tokens (for set-session/set-daily)"),
):
    """
    View or set token budget limits.
    
    Examples:
        jagabot budget status        # Show current limits and usage
        jagabot budget set-session 1000000  # Set session limit to 1M tokens
        jagabot budget set-daily 5000000    # Set daily limit to 5M tokens
    """
    from jagabot.core.token_budget import SESSION_LIMIT, DAILY_LIMIT, STATE_PATH, _load_daily
    
    if action == "status":
        daily = _load_daily()
        console.print("## 💰 Token Budget Status\n")
        console.print(f"**Session Limit:** {SESSION_LIMIT:,} tokens")
        console.print(f"**Daily Limit:** {DAILY_LIMIT:,} tokens\n")
        console.print(f"**Today's Usage:** {daily.get('total', 0):,} tokens ({daily.get('calls', 0)} calls)")
        console.print(f"**Daily Remaining:** {max(0, DAILY_LIMIT - daily.get('total', 0)):,} tokens\n")
        if STATE_PATH.exists():
            console.print(f"Budget state: {STATE_PATH}")
        else:
            console.print("Budget state: Not initialized (starts on first LLM call)")
        
        console.print("\n💡 **Tip:** Default session limit is 500k tokens.")
        console.print("   Use `jagabot budget set-session <tokens>` to increase.")
        console.print("   Example: `jagabot budget set-session 1000000` for 1M tokens\n")
        
    elif action == "set-session":
        if value is None:
            console.print("❌ Error: Please specify token limit")
            console.print("   Example: jagabot budget set-session 1000000")
            raise typer.Exit(1)
        
        # Update environment variable for current session
        os.environ["JAGABOT_SESSION_LIMIT"] = str(value)
        
        # Also update config if possible
        from jagabot.config.loader import load_config, get_config_path
        config_path = get_config_path()
        if config_path.exists():
            try:
                import json
                config = json.loads(config_path.read_text())
                if "budget" not in config:
                    config["budget"] = {}
                config["budget"]["session_limit"] = value
                config_path.write_text(json.dumps(config, indent=2))
                console.print(f"✅ Session budget saved to config: {value:,} tokens")
            except Exception as e:
                console.print(f"⚠️  Could not save to config: {e}")
                console.print(f"   Budget set for current session only: {value:,} tokens")
        else:
            console.print(f"✅ Session budget set for current session: {value:,} tokens")
        
        console.print(f"\n💡 Restart jagabot agent to apply new limit.")
        
    elif action == "set-daily":
        if value is None:
            console.print("❌ Error: Please specify token limit")
            console.print("   Example: jagabot budget set-daily 5000000")
            raise typer.Exit(1)
        
        # Update environment variable for current session
        os.environ["JAGABOT_DAILY_LIMIT"] = str(value)
        
        # Also update config if possible
        from jagabot.config.loader import load_config, get_config_path
        config_path = get_config_path()
        if config_path.exists():
            try:
                import json
                config = json.loads(config_path.read_text())
                if "budget" not in config:
                    config["budget"] = {}
                config["budget"]["daily_limit"] = value
                config_path.write_text(json.dumps(config, indent=2))
                console.print(f"✅ Daily budget saved to config: {value:,} tokens")
            except Exception as e:
                console.print(f"⚠️  Could not save to config: {e}")
                console.print(f"   Budget set for current session only: {value:,} tokens")
        else:
            console.print(f"✅ Daily budget set for current session: {value:,} tokens")
        
        console.print(f"\n💡 Restart jagabot agent to apply new limit.")
        
    else:
        console.print(f"❌ Unknown action: {action}")
        console.print("   Use: status | set-session | set-daily")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()


# ============================================================================
# Service (daemon) Commands (extracted to service_commands.py)
# ============================================================================

from jagabot.cli.service_commands import service_app
app.add_typer(service_app, name="service")


# ---------------------------------------------------------------------------
# Sandbox commands
# ---------------------------------------------------------------------------

from jagabot.cli.sandbox import sandbox_app
app.add_typer(sandbox_app, name="sandbox")


# ---------------------------------------------------------------------------
# Swarm commands (extracted to swarm_commands.py)
# ---------------------------------------------------------------------------

from jagabot.cli.swarm_commands import swarm_app
app.add_typer(swarm_app, name="swarm")


# ---------------------------------------------------------------------------
# TUI command (Terminal UI)
# ---------------------------------------------------------------------------

@app.command("tui")
def launch_tui():
    """Launch the full terminal UI with split panes."""
    from jagabot.cli.tui import run_tui
    run_tui()


@app.command()
def chat(
    stream: bool = typer.Option(True, help="Stream output word by word"),
    model:  str  = typer.Option("Qwen-Plus", help="LLM model name"),
):
    """Launch enhanced interactive CLI (Claude Code style)."""
    from jagabot.cli.interactive import run_interactive
    from pathlib import Path
    run_interactive(
        workspace  = Path.home() / ".jagabot",
        model_name = model,
        stream     = stream,
    )


@app.command()
def yolo(
    goal: str = typer.Argument(
        ...,
        help="Research goal e.g. 'research quantum computing in drug discovery'"
    ),
):
    """
    YOLO mode — fully autonomous research.
    AutoJaga runs all steps without asking for confirmation.
    Sandboxed to ~/.jagabot/workspace/ only.
    """
    from jagabot.agent.yolo import run_yolo
    from pathlib import Path
    run_yolo(
        goal      = goal,
        workspace = Path.home() / ".jagabot" / "workspace",
        agent     = None,  # wire to real AgentLoop
    )


# ── Onboarding / Setup commands ──────────────────────────────────────

@app.command()
def setup(
    quick: bool = typer.Option(False, "--quick", "-q", help="Quickstart mode"),
    section: Optional[str] = typer.Option(None, "--section", "-s", help="Configure specific section only"),
    botfather: bool = typer.Option(False, "--botfather", help="Print Telegram BotFather commands"),
):
    """
    Interactive setup wizard for first-time installation.
    
    Guides you through:
    - Use case selection (Research, Financial, Coding, General)
    - LLM provider + API key configuration
    - Workspace location
    - Agent identity (AGENTS.md)
    - Channels (CLI, Telegram, etc.)
    - Tools profile
    
    Use --quick for 2-minute setup with defaults.
    """
    if botfather:
        from jagabot.cli.onboard import get_telegram_botfather_commands
        print(get_telegram_botfather_commands())
        return
    
    from jagabot.cli.onboard import OnboardWizard
    from pathlib import Path
    
    wizard = OnboardWizard(
        quick=quick,
        section=section,
        workspace=Path.home() / ".jagabot",
    )
    success = wizard.run()
    
    if success:
        console.print("\n[green]✅ Setup complete![/]")
    else:
        console.print("\n[yellow]⚠️  Setup incomplete.[/] Run 'jagabot setup' to retry.")


@app.command("configure")
def configure(
    section: Optional[str] = typer.Option(None, "--section", "-s", help="Configure specific section only"),
):
    """
    Reconfigure existing AutoJaga installation.
    
    Use --section to reconfigure only one part:
    - model: Change LLM provider/model
    - workspace: Change workspace location
    - channels: Add/remove channels
    - telegram: Set up Telegram bot
    - identity: Change agent name/personality
    """
    from jagabot.cli.onboard import OnboardWizard
    from pathlib import Path
    
    wizard = OnboardWizard(
        quick=False,
        section=section,
        workspace=Path.home() / ".jagabot",
    )
    wizard.run()


@app.command()
def doctor():
    """
    Check configuration and auto-fix issues.
    
    Runs health checks on:
    - Config file existence
    - Workspace permissions
    - API keys configured
    - AGENTS.md exists
    - Python version
    - Required dependencies
    
    Offers to fix each issue automatically.
    """
    from jagabot.cli.onboard import run_doctor
    run_doctor()
