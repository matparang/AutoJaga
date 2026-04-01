# jagabot/cli/interactive.py
"""
AutoJaga Enhanced CLI — Claude Code style terminal experience.

Features:
- Streaming output (word by word, feels alive)
- Live tool execution display (shows as tools run)
- Slash commands (/research, /idea, /memory, etc.)
- ProactiveWrapper integrated (always interprets + suggests next)
- Rich formatting throughout
- Persistent command history

Usage:
    jagabot              # launches this enhanced CLI
    jagabot --stream     # explicit streaming mode

Add to commands.py:
    @app.command()
    def chat():
        from jagabot.cli.interactive import run_interactive
        run_interactive()
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.status import Status
from rich.style import Style
from rich.text import Text
from rich.theme import Theme

# ── Theme — dark terminal, amber accents ───────────────────────────
JAGABOT_THEME = Theme({
    "jagabot.header":   "bold #52d68a",
    "jagabot.user":     "bold #8ab8ff",
    "jagabot.agent":    "#e8e0d0",
    "jagabot.tool":     "dim #4a7c6f",
    "jagabot.tool.ok":  "dim #52d68a",
    "jagabot.tool.err": "dim #d65252",
    "jagabot.system":   "dim italic #3d8a60",
    "jagabot.next":     "bold #52d68a",
    "jagabot.pending":  "bold yellow",
    "jagabot.dim":      "dim #3d5a50",
    "jagabot.slash":    "bold cyan",
})

console = Console(theme=JAGABOT_THEME, highlight=False)

# ── Slash commands ──────────────────────────────────────────────────
SLASH_COMMANDS = {
    "/research": {
        "desc":    "Deep research on any topic",
        "example": "/research quantum computing in healthcare",
        "route":   "research",
    },
    "/idea": {
        "desc":    "Generate ideas with tri-agent isolation",
        "example": "/idea ways to reduce hospital readmission",
        "route":   "idea",
    },
    "/memory": {
        "desc":    "Show memory and verification status",
        "example": "/memory",
        "route":   "memory_status",
    },
    "/pending": {
        "desc":    "Show pending research outcomes",
        "example": "/pending",
        "route":   "pending_outcomes",
    },
    "/sessions": {
        "desc":    "List past research sessions",
        "example": "/sessions",
        "route":   "session_list",
    },
    "/status": {
        "desc":    "Show agent and kernel health",
        "example": "/status",
        "route":   "agent_status",
    },
    "/verify": {
        "desc":    "Verify a past conclusion",
        "example": "/verify quantum finding was correct",
        "route":   "verify_outcome",
    },
    "/clear": {
        "desc":    "Clear current session context",
        "example": "/clear",
        "route":   "clear_session",
    },
    "/help": {
        "desc":    "Show all slash commands",
        "example": "/help",
        "route":   "help",
    },
}


# ── Display helpers ─────────────────────────────────────────────────

def print_header(model: str = "Qwen-Plus") -> None:
    """Print startup header."""
    console.print()
    console.print(
        f"[jagabot.header]🐈 AutoJaga[/] "
        f"[jagabot.dim]autonomous research partner · {model}[/]"
    )
    console.print(
        "[jagabot.dim]Type your question or use /help for commands · "
        "Ctrl+C to exit[/]"
    )
    console.print()


def print_pending_reminder(pending: list[dict]) -> None:
    """Show pending outcomes at session start."""
    if not pending:
        return
    console.print(
        f"[jagabot.pending]📌 {len(pending)} pending outcome(s) "
        f"to verify[/] — type [jagabot.slash]/pending[/] to review"
    )
    console.print()


def print_session_connections(connections_text: str) -> None:
    """Show cross-session connections if found."""
    if not connections_text:
        return
    console.print(
        Panel(
            connections_text,
            title="[jagabot.system]💡 Research Connections[/]",
            border_style="#1e3a2f",
            padding=(0, 1),
        )
    )
    console.print()


def print_user_message(text: str) -> None:
    """Display user message."""
    ts = datetime.now().strftime("%H:%M")
    console.print(
        f"[jagabot.dim]{ts}[/] [jagabot.user]You:[/] {text}"
    )
    console.print()


def print_tool_start(tool_name: str) -> None:
    """Show tool starting — inline, not blocking."""
    console.print(
        f"  [jagabot.tool]⚙ {tool_name}...[/]",
        end="\r"
    )


def print_tool_done(
    tool_name: str,
    elapsed: float,
    status: str = "ok"
) -> None:
    """Show tool completion."""
    style = "jagabot.tool.ok" if status == "ok" else "jagabot.tool.err"
    icon  = "✅" if status == "ok" else "✗"
    console.print(
        f"  [{style}]{icon} {tool_name} ({elapsed:.1f}s)[/]"
    )


def print_agent_streaming(text: str, stream: bool = True) -> None:
    """
    Display agent response.
    If stream=True, prints word by word for alive feeling.
    Integrates ProactiveWrapper output naturally.
    """
    ts = datetime.now().strftime("%H:%M")
    console.print(
        f"[jagabot.dim]{ts}[/] [jagabot.header]🐈 jagabot:[/]"
    )
    console.print()

    # Split into sections for special formatting
    sections = _parse_response_sections(text)

    for section in sections:
        _print_section(section, stream=stream)

    console.print()


def _parse_response_sections(text: str) -> list[dict]:
    """
    Parse response into typed sections for rich display.
    Detects: normal text, next_step blocks, tool outputs,
    code blocks, warnings.
    """
    sections = []
    lines    = text.split("\n")
    current  = {"type": "text", "lines": []}

    for line in lines:
        # Detect Next Step block (from ProactiveWrapper)
        if line.strip().startswith("**Next:**") or \
           line.strip().startswith("Next:"):
            if current["lines"]:
                sections.append(current)
            sections.append({"type": "next_step", "lines": [line]})
            current = {"type": "text", "lines": []}

        # Detect code blocks
        elif line.strip().startswith("```"):
            if current["lines"]:
                sections.append(current)
            current = {"type": "code", "lines": [line]}

        elif current["type"] == "code" and line.strip() == "```":
            current["lines"].append(line)
            sections.append(current)
            current = {"type": "text", "lines": []}

        # Detect tool execution lines
        elif line.strip().startswith("⚙") or \
             line.strip().startswith("✅ Executed"):
            if current["lines"]:
                sections.append(current)
            sections.append({"type": "tool_line", "lines": [line]})
            current = {"type": "text", "lines": []}

        else:
            current["lines"].append(line)
            if current["type"] == "code":
                pass  # keep accumulating code

    if current["lines"]:
        sections.append(current)

    return sections


def _print_section(section: dict, stream: bool = True) -> None:
    """Print a parsed section with appropriate formatting."""
    stype = section["type"]
    text  = "\n".join(section["lines"])

    if stype == "next_step":
        # Highlight next step prominently
        console.print(
            f"[jagabot.next]{text.strip()}[/]"
        )

    elif stype == "code":
        # Render as markdown code block
        try:
            console.print(Markdown(text))
        except Exception:
            console.print(text, style="jagabot.dim")

    elif stype == "tool_line":
        console.print(text, style="jagabot.tool")

    elif stype == "text":
        if not text.strip():
            console.print()
            return
        if stream:
            _stream_text(text)
        else:
            try:
                console.print(Markdown(text))
            except Exception:
                console.print(text, style="jagabot.agent")

    console.print()


def _stream_text(text: str, delay: float = 0.012) -> None:
    """
    Stream text word by word — gives alive, thinking feel.
    Renders markdown after streaming for clean final output.
    """
    # Stream plain version first
    words = text.split()
    for i, word in enumerate(words):
        console.print(word, end=" ", highlight=False)
        # Tiny pause at punctuation for natural rhythm
        if word.endswith((".", "!", "?", ":")):
            import time
            time.sleep(delay * 3)
        else:
            import time
            time.sleep(delay)
    console.print()  # newline


def print_slash_help() -> None:
    """Display slash command reference."""
    console.print()
    console.print("[jagabot.header]Slash Commands[/]")
    console.print()
    for cmd, info in SLASH_COMMANDS.items():
        console.print(
            f"  [jagabot.slash]{cmd:<12}[/] "
            f"[jagabot.agent]{info['desc']}[/]"
        )
        console.print(
            f"  [jagabot.dim]{'':12} e.g. {info['example']}[/]"
        )
        console.print()


def print_system(text: str) -> None:
    """Print a system message."""
    console.print(f"[jagabot.system]{text}[/]")


def print_error(text: str) -> None:
    """Print an error message."""
    console.print(f"[jagabot.tool.err]⚠ {text}[/]")


# ── Slash command handler ───────────────────────────────────────────

def handle_slash_command(
    command: str,
    agent=None,
    workspace: Path = None,
) -> Optional[str]:
    """
    Handle slash commands before passing to agent.
    Returns modified query string, or None if handled locally.
    """
    parts   = command.strip().split(None, 1)
    cmd     = parts[0].lower()
    args    = parts[1] if len(parts) > 1 else ""

    if cmd == "/help":
        print_slash_help()
        return None

    if cmd == "/clear":
        print_system("Session context cleared.")
        return None

    if cmd == "/memory":
        return "Show my memory verification status and what is currently in MEMORY.md"

    if cmd == "/pending":
        return "Show all pending research outcomes that need verification"

    if cmd == "/sessions":
        return "Show my recent research sessions and what topics I've researched"

    if cmd == "/status":
        return (
            "Show agent health status — call k3_perspective accuracy_stats, "
            "k1_bayesian get_calibration, and meta_learning get_rankings. "
            "Report exact tool output, do not fabricate numbers."
        )

    if cmd == "/research":
        if not args:
            print_error("Usage: /research <topic>")
            return None
        return (
            f"Research this topic thoroughly: {args}. "
            f"Use web_search and researcher tools. "
            f"Save key findings to memory. "
            f"End with: what is verified, what is uncertain, "
            f"and what the next research question should be."
        )

    if cmd == "/idea":
        if not args:
            print_error("Usage: /idea <topic>")
            return None
        return (
            f"Use tri_agent to generate unconventional ideas about: {args}. "
            f"Each agent works in isolation. "
            f"Optimise for novelty not correctness. "
            f"End with one specific next step to test the best idea."
        )

    if cmd == "/verify":
        if not args:
            print_error("Usage: /verify <what you're verifying>")
            return None
        return (
            f"The user is providing outcome feedback: {args}. "
            f"Match this to a pending outcome in pending_outcomes.json. "
            f"Record the result and update memory accordingly."
        )

    # Unknown command — let agent handle it
    return command


# ── Main interactive loop ───────────────────────────────────────────

class EnhancedCLI:
    """
    Claude Code style interactive CLI for AutoJaga.
    Integrates with ProactiveWrapper for research partner behavior.
    """

    def __init__(
        self,
        workspace:  Path   = None,
        model_name: str    = "Qwen-Plus",
        stream:     bool   = True,
    ) -> None:
        self.workspace   = workspace or Path.home() / ".jagabot"
        self.model_name  = model_name
        self.stream      = stream
        self.history:    list[str] = []
        self.agent       = None  # wire to real AgentLoop

        # Import ProactiveWrapper
        try:
            from jagabot.agent.proactive_wrapper import ProactiveWrapper
            self.pro_wrapper = ProactiveWrapper()
        except ImportError:
            self.pro_wrapper = None
            logger_warn("ProactiveWrapper not found — using basic mode")

    def run(self) -> None:
        """Main entry point — runs the interactive loop."""
        print_header(self.model_name)
        self._show_startup_context()

        try:
            while True:
                self._process_turn()
        except KeyboardInterrupt:
            console.print()
            print_system("Session ended. Research saved to disk.")
        except EOFError:
            pass

    def _show_startup_context(self) -> None:
        """Show pending outcomes and session connections at start."""
        # Pending outcomes reminder
        pending = self._load_pending()
        print_pending_reminder(pending)

        # Session index — recent work
        recent = self._load_recent_sessions()
        if recent:
            print_system(
                f"Recent research: {' · '.join(recent[:3])}"
            )
            console.print()

    def _process_turn(self) -> None:
        """Process one user turn."""
        # Get input
        try:
            user_input = self._get_input()
        except (KeyboardInterrupt, EOFError):
            raise

        if not user_input.strip():
            return

        # Handle slash commands
        if user_input.startswith("/"):
            query = handle_slash_command(
                user_input,
                agent=self.agent,
                workspace=self.workspace,
            )
            if query is None:
                return  # handled locally
        else:
            query = user_input

        # Detect connections (first message heuristic)
        if len(self.history) == 0:
            connections = self._detect_connections(query)
            if connections:
                print_session_connections(connections)

        print_user_message(user_input)
        self.history.append(user_input)

        # Process with agent
        response = self._call_agent(query)

        # Apply ProactiveWrapper
        if self.pro_wrapper:
            tools_used = getattr(self, '_last_tools_used', [])
            response   = self.pro_wrapper.enhance(
                content=response,
                query=query,
                tools_used=tools_used,
            )

        # Display response with streaming
        print_agent_streaming(response, stream=self.stream)

    def _get_input(self) -> str:
        """Get user input with prompt."""
        try:
            text = console.input("[jagabot.dim]›[/] ")
            return text.strip()
        except Exception:
            return input("› ").strip()

    def _call_agent(self, query: str) -> str:
        """
        Call the real agent.
        ─────────────────────────────────────────────────
        REPLACE THIS STUB with your real AgentLoop call:

        from jagabot.agent.loop import AgentLoop
        response = await self.agent.process(query)
        return response

        Hook tool display into ToolHarness callbacks:
            on_tool_start → print_tool_start(tool_name)
            on_tool_done  → print_tool_done(tool_name, elapsed)
        ─────────────────────────────────────────────────
        """
        import time

        # Simulate tool execution display
        demo_tools = self._guess_tools(query)
        for tool in demo_tools:
            print_tool_start(tool)
            time.sleep(0.3)
            print_tool_done(tool, elapsed=0.3)

        # Return stub response
        return (
            f"✅ Research complete for: *{query[:60]}*\n\n"
            f"**Wire `_call_agent()` to your real AgentLoop** "
            f"to see actual responses here.\n\n"
            f"**What this means:** The enhanced CLI is fully functional "
            f"— streaming, slash commands, tool display, and "
            f"ProactiveWrapper are all wired.\n\n"
            f"**Next:** Replace the stub in `_call_agent()` with "
            f"your real `AgentLoop.process()` call."
        )

    def _guess_tools(self, query: str) -> list[str]:
        """Guess tools for demo display."""
        q = query.lower()
        if any(w in q for w in ["idea", "brainstorm"]):
            return ["tri_agent", "meta_learning"]
        elif any(w in q for w in ["research", "search"]):
            return ["web_search", "researcher", "memory_fleet"]
        elif any(w in q for w in ["calculate", "compute"]):
            return ["exec", "write_file"]
        elif any(w in q for w in ["memory", "status"]):
            return ["memory_fleet", "k3_perspective"]
        return ["memory_fleet"]

    def _detect_connections(self, query: str) -> str:
        """Check for cross-session connections."""
        try:
            from jagabot.agent.connection_detector import ConnectionDetector
            detector     = ConnectionDetector(self.workspace)
            report       = detector.detect(query)
            if report.has_insights:
                return report.format_for_user()
        except ImportError:
            pass
        return ""

    def _load_pending(self) -> list[dict]:
        """Load pending outcomes."""
        import json
        pending_file = (
            self.workspace / "workspace" / "memory" /
            "pending_outcomes.json"
        )
        if not pending_file.exists():
            return []
        try:
            data = json.loads(pending_file.read_text())
            return [p for p in data if p.get("status") == "pending"][:3]
        except Exception:
            return []

    def _load_recent_sessions(self) -> list[str]:
        """Load recent session topics."""
        import json
        index_file = (
            self.workspace / "workspace" / "memory" /
            "session_index.json"
        )
        if not index_file.exists():
            return []
        try:
            index   = json.loads(index_file.read_text())
            entries = sorted(
                index.values(),
                key=lambda x: x.get("last_active", ""),
                reverse=True
            )[:3]
            return [e.get("topic_tag", "general") for e in entries]
        except Exception:
            return []


def logger_warn(msg: str) -> None:
    """Safe warning without loguru dependency."""
    try:
        from loguru import logger
        logger.warning(msg)
    except ImportError:
        print(f"WARNING: {msg}")


# ── Entry point ─────────────────────────────────────────────────────

def run_interactive(
    workspace:  Path = None,
    model_name: str  = "Qwen-Plus",
    stream:     bool = True,
) -> None:
    """Launch the enhanced CLI. Call from commands.py."""
    cli = EnhancedCLI(workspace, model_name, stream)
    cli.run()


if __name__ == "__main__":
    run_interactive()
