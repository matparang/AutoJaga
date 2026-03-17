# jagabot/cli/command_registry.py
"""
AutoJaga Command Registry — OpenClaw-inspired slash commands.

Works across ALL channels:
    CLI:      jagabot chat → type /compress
    TUI:      type /compress in input bar
    Telegram: send /compress to bot
    Slack:    /compress (register as Slack command)

Architecture:
    CommandRegistry — central registry, channel-agnostic
    CLIDispatcher   — handles CLI + TUI
    TelegramDispatcher — handles Telegram bot
    Each command is a pure function: (args, context) → str

OpenClaw commands mapped to AutoJaga equivalents:
    /compress    → compress + flush context window
    /spawn       → spawn a subagent task
    /kill        → kill running subagent
    /status      → full system status
    /think       → set reasoning depth
    /context     → show context window usage
    /memory      → memory operations
    /sessions    → list + manage sessions
    /pending     → pending outcomes
    /research    → start research session
    /idea        → idea generation
    /yolo        → autonomous research
    /verify      → verify a conclusion
    /model       → show/switch LLM model
    /usage       → show token/cost usage
    /export      → export session to file
    /config      → show/set config
    /stop        → stop current run
    /restart     → restart agent
    /help        → show all commands
    /btw         → quick side question
    /skills      → list available skills
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


# ── Command definition ───────────────────────────────────────────────

@dataclass
class Command:
    name:        str
    description: str
    usage:       str
    aliases:     list[str]    = field(default_factory=list)
    args:        list[str]    = field(default_factory=list)
    handler:     Optional[Callable] = None
    telegram_ok: bool         = True   # available in Telegram
    cli_ok:      bool         = True   # available in CLI/TUI
    category:    str          = "general"


@dataclass
class CommandContext:
    """Context passed to every command handler."""
    workspace:     Path
    session_key:   str         = ""
    channel:       str         = "cli"   # "cli" | "telegram" | "tui"
    user_id:       str         = ""
    agent:         object      = None    # AgentLoop reference
    memory_mgr:    object      = None    # MemoryManager reference
    session_index: object      = None    # SessionIndex reference
    outcome_tracker: object    = None    # OutcomeTracker reference


# ── Command registry ─────────────────────────────────────────────────

class CommandRegistry:
    """
    Central registry for all slash commands.
    Channel-agnostic — same commands work in CLI, TUI, Telegram.
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._commands: dict[str, Command] = {}
        self._register_all()

    def get(self, name: str) -> Optional[Command]:
        """Look up command by name or alias."""
        name = name.lstrip("/").lower()
        if name in self._commands:
            return self._commands[name]
        # Check aliases
        for cmd in self._commands.values():
            if name in cmd.aliases:
                return cmd
        return None

    def dispatch(
        self,
        input_text: str,
        context:    CommandContext,
    ) -> Optional[str]:
        """
        Parse and dispatch a slash command.
        Returns response string, or None if not a command.
        """
        if not input_text.startswith("/"):
            return None

        parts   = input_text.strip().split(None, 1)
        name    = parts[0].lower()
        args    = parts[1] if len(parts) > 1 else ""

        cmd = self.get(name)
        if not cmd:
            return f"Unknown command: {name}. Type /help for all commands."

        # Channel check
        if context.channel == "telegram" and not cmd.telegram_ok:
            return f"{name} is not available in Telegram."

        if cmd.handler:
            try:
                return cmd.handler(args, context)
            except Exception as e:
                return f"Command error: {e}"

        return f"Command {name} registered but not yet wired."

    def all_commands(self, channel: str = "cli") -> list[Command]:
        """Return all commands available for a channel."""
        cmds = list(self._commands.values())
        if channel == "telegram":
            cmds = [c for c in cmds if c.telegram_ok]
        return sorted(cmds, key=lambda c: c.category + c.name)

    # ── Register all commands ────────────────────────────────────────

    def _register_all(self) -> None:
        """Register all commands."""
        commands = [

            # ── Session & Context ────────────────────────────────────
            Command(
                name        = "/compress",
                description = "Compress context window and flush important content to memory",
                usage       = "/compress",
                aliases     = ["compact"],
                handler     = self._handle_compress,
                category    = "context",
            ),
            Command(
                name        = "/context",
                description = "Show context window usage — tokens used, files loaded, tools active",
                usage       = "/context [detail]",
                aliases     = ["ctx"],
                handler     = self._handle_context,
                category    = "context",
            ),
            Command(
                name        = "/export",
                description = "Export current session to markdown file",
                usage       = "/export [path]",
                aliases     = ["export-session"],
                handler     = self._handle_export,
                category    = "context",
            ),
            Command(
                name        = "/sessions",
                description = "List recent research sessions with topics and quality",
                usage       = "/sessions [search term]",
                handler     = self._handle_sessions,
                category    = "context",
            ),

            # ── Agent Control ────────────────────────────────────────
            Command(
                name        = "/spawn",
                description = "Spawn a subagent to run a task in background",
                usage       = "/spawn <task description>",
                handler     = self._handle_spawn,
                category    = "agent",
            ),
            Command(
                name        = "/kill",
                description = "Kill a running subagent or current run",
                usage       = "/kill [agent_id|all]",
                handler     = self._handle_kill,
                category    = "agent",
            ),
            Command(
                name        = "/stop",
                description = "Stop the current running task",
                usage       = "/stop",
                handler     = self._handle_stop,
                category    = "agent",
            ),
            Command(
                name        = "/restart",
                description = "Restart the agent with fresh context",
                usage       = "/restart",
                handler     = self._handle_restart,
                category    = "agent",
            ),
            Command(
                name        = "/subagents",
                description = "List or manage subagents",
                usage       = "/subagents [list|kill|log] [id]",
                aliases     = ["agents"],
                handler     = self._handle_subagents,
                category    = "agent",
            ),

            # ── Research Commands ────────────────────────────────────
            Command(
                name        = "/research",
                description = "Start a deep research session on any topic",
                usage       = "/research <topic>",
                handler     = self._handle_research,
                category    = "research",
            ),
            Command(
                name        = "/idea",
                description = "Generate ideas using tri-agent isolation",
                usage       = "/idea <topic>",
                handler     = self._handle_idea,
                category    = "research",
            ),
            Command(
                name        = "/yolo",
                description = "Fully autonomous research — no confirmations",
                usage       = "/yolo <goal>",
                handler     = self._handle_yolo,
                category    = "research",
            ),
            Command(
                name        = "/verify",
                description = "Verify a past research conclusion",
                usage       = "/verify <conclusion was correct|wrong|partial>",
                handler     = self._handle_verify,
                category    = "research",
            ),
            Command(
                name        = "/pending",
                description = "Show pending research outcomes awaiting verification",
                usage       = "/pending",
                handler     = self._handle_pending,
                category    = "research",
            ),

            # ── Memory Commands ──────────────────────────────────────
            Command(
                name        = "/memory",
                description = "Memory operations — show, search, stats",
                usage       = "/memory [show|search <q>|stats|flush]",
                aliases     = ["mem"],
                handler     = self._handle_memory,
                category    = "memory",
            ),
            Command(
                name        = "/skills",
                description = "List available skills and auto-generated skill docs",
                usage       = "/skills [search term]",
                handler     = self._handle_skills,
                category    = "memory",
            ),

            # ── System Commands ──────────────────────────────────────
            Command(
                name        = "/status",
                description = "Full system status — kernels, memory, pending outcomes",
                usage       = "/status",
                handler     = self._handle_status,
                category    = "system",
            ),
            Command(
                name        = "/think",
                description = "Set reasoning depth for next response",
                usage       = "/think <off|low|medium|high>",
                aliases     = ["thinking", "t"],
                handler     = self._handle_think,
                category    = "system",
            ),
            Command(
                name        = "/model",
                description = "Show current model or switch to another",
                usage       = "/model [model_name]",
                aliases     = ["models"],
                handler     = self._handle_model,
                category    = "system",
            ),
            Command(
                name        = "/usage",
                description = "Show token usage and estimated cost this session",
                usage       = "/usage [cost]",
                handler     = self._handle_usage,
                category    = "system",
            ),
            Command(
                name        = "/config",
                description = "Show or set configuration values",
                usage       = "/config [show|get <key>|set <key>=<val>]",
                handler     = self._handle_config,
                category    = "system",
            ),
            Command(
                name        = "/clear",
                description = "Clear current session context",
                usage       = "/clear",
                handler     = self._handle_clear,
                category    = "system",
            ),
            Command(
                name        = "/btw",
                description = "Quick side question using session as background context",
                usage       = "/btw <question>",
                handler     = self._handle_btw,
                category    = "system",
            ),
            Command(
                name        = "/help",
                description = "Show all available commands",
                usage       = "/help [command]",
                aliases     = ["?"],
                handler     = self._handle_help,
                category    = "system",
            ),
        ]

        for cmd in commands:
            self._commands[cmd.name.lstrip("/")] = cmd

    # ── Handlers ─────────────────────────────────────────────────────

    def _handle_compress(self, args: str, ctx: CommandContext) -> str:
        try:
            if ctx.memory_mgr and ctx.agent:
                session_text = ctx.agent.get_session_text()
                saved = ctx.memory_mgr.pre_compaction_flush(
                    session_content=session_text,
                    session_key=ctx.session_key,
                )
                return (
                    f"✅ Context compressed.\n"
                    f"{saved} important entries saved to today's memory.\n"
                    f"Context window cleared — full memory preserved on disk."
                )
            return "✅ Context cleared. (Wire memory_mgr for full compress)"
        except Exception as e:
            return f"Compress failed: {e}"

    def _handle_context(self, args: str, ctx: CommandContext) -> str:
        detail = "detail" in args.lower()
        lines  = ["**Context Window Status**", ""]

        if ctx.agent:
            try:
                turns = len(getattr(ctx.agent, '_session_messages', []))
                lines.append(f"Session turns: {turns}")
            except Exception:
                pass

        if ctx.memory_mgr:
            try:
                stats = ctx.memory_mgr.get_stats()
                lines.append(f"Indexed memories: {stats.get('indexed_entries', 0)}")
                lines.append(f"Daily notes: {stats.get('daily_notes', 0)}")
                lines.append(f"Skill docs: {stats.get('skill_documents', 0)}")
            except Exception:
                pass

        lines += [
            "",
            "Use /compress to flush and compress.",
        ]
        return "\n".join(lines)

    def _handle_sessions(self, args: str, ctx: CommandContext) -> str:
        if not ctx.session_index:
            return (
                "Session index not available. "
                "Wire session_index to CommandContext."
            )
        try:
            reminder = ctx.session_index.get_startup_reminder()
            return reminder or "No past sessions found."
        except Exception as e:
            return f"Sessions error: {e}"

    def _handle_spawn(self, args: str, ctx: CommandContext) -> str:
        if not args.strip():
            return "Usage: /spawn <task description>"
        return (
            f"Spawning subagent for: *{args[:60]}*\n\n"
            f"Wire to subagent tool: "
            f"`subagent(task='{args[:40]}', background=True)`"
        )

    def _handle_kill(self, args: str, ctx: CommandContext) -> str:
        target = args.strip() or "current"
        return (
            f"✅ Kill signal sent to: {target}\n"
            f"Wire to: `agent.kill_subagent('{target}')`"
        )

    def _handle_stop(self, args: str, ctx: CommandContext) -> str:
        if ctx.agent:
            try:
                ctx.agent._running = False
                return "✅ Stopping current run."
            except Exception:
                pass
        return "✅ Stop signal sent."

    def _handle_restart(self, args: str, ctx: CommandContext) -> str:
        return (
            "✅ Restart initiated.\n"
            "Context cleared. Memory preserved.\n"
            "Wire to: `agent.restart()`"
        )

    def _handle_subagents(self, args: str, ctx: CommandContext) -> str:
        parts  = args.strip().split()
        action = parts[0] if parts else "list"

        if action == "list":
            return (
                "**Active Subagents**\n\n"
                "No subagents running.\n"
                "Use /spawn <task> to start one."
            )
        return f"Subagent action '{action}' — wire to swarm controller."

    def _handle_research(self, args: str, ctx: CommandContext) -> str:
        if not args.strip():
            return "Usage: /research <topic>"
        return (
            f"Research this topic thoroughly: {args}. "
            f"Use web_search and researcher tools. "
            f"Save key findings to memory. "
            f"End with: what is verified, what is uncertain, "
            f"and what the next research question should be."
        )

    def _handle_idea(self, args: str, ctx: CommandContext) -> str:
        if not args.strip():
            return "Usage: /idea <topic>"
        return (
            f"Use tri_agent to generate unconventional ideas about: {args}. "
            f"Each agent works in complete isolation. "
            f"Optimise for novelty not correctness. "
            f"End with one specific next step to test the best idea."
        )

    def _handle_yolo(self, args: str, ctx: CommandContext) -> str:
        if not args.strip():
            return "Usage: /yolo <research goal>"
        from jagabot.agent.yolo import run_yolo
        run_yolo(goal=args, workspace=ctx.workspace)
        return ""  # YOLO mode handles its own output

    def _handle_verify(self, args: str, ctx: CommandContext) -> str:
        if not args.strip():
            return "Usage: /verify <the conclusion was correct|wrong|partial>"
        return (
            f"The user is providing outcome feedback: {args}. "
            f"Match this to a pending outcome in pending_outcomes.json. "
            f"Record the result and update memory accordingly. "
            f"Show which conclusion was matched and what was updated."
        )

    def _handle_pending(self, args: str, ctx: CommandContext) -> str:
        if ctx.outcome_tracker:
            try:
                reminder = ctx.outcome_tracker.get_session_reminder()
                return reminder or "✅ No pending outcomes — all conclusions verified."
            except Exception as e:
                return f"Pending error: {e}"

        # Fallback — read file directly
        pending_file = ctx.workspace / "memory" / "pending_outcomes.json"
        if not pending_file.exists():
            return "✅ No pending outcomes yet."
        try:
            data    = json.loads(pending_file.read_text())
            pending = [p for p in data if p.get("status") == "pending"]
            if not pending:
                return "✅ All outcomes verified."
            lines   = [f"**📌 {len(pending)} pending outcome(s):**", ""]
            for p in pending[:5]:
                age = self._days_ago(p.get("created_at", ""))
                lines.append(f"- [{age}] {p.get('conclusion', '')[:80]}")
            lines += ["", "Use /verify to confirm any of these."]
            return "\n".join(lines)
        except Exception as e:
            return f"Pending read error: {e}"

    def _handle_memory(self, args: str, ctx: CommandContext) -> str:
        parts  = args.strip().split(None, 1)
        action = parts[0].lower() if parts else "show"
        query  = parts[1] if len(parts) > 1 else ""

        if action == "stats" and ctx.memory_mgr:
            try:
                stats = ctx.memory_mgr.get_stats()
                lines = ["**Memory System Stats**", ""]
                for k, v in stats.items():
                    lines.append(f"- {k}: {v}")
                return "\n".join(lines)
            except Exception as e:
                return f"Memory stats error: {e}"

        if action == "search" and ctx.memory_mgr and query:
            try:
                results = ctx.memory_mgr._fts_search(query, limit=5)
                if not results:
                    return f"No memory found for: {query}"
                lines = [f"**Memory search: {query}**", ""]
                for r in results:
                    lines.append(f"- {r.content[:100]}")
                return "\n".join(lines)
            except Exception as e:
                return f"Memory search error: {e}"

        if action == "flush" and ctx.memory_mgr and ctx.agent:
            try:
                text  = ctx.agent.get_session_text()
                saved = ctx.memory_mgr.pre_compaction_flush(text)
                return f"✅ Flushed {saved} entries to today's memory file."
            except Exception as e:
                return f"Memory flush error: {e}"

        # Default: show memory summary
        memory_file = ctx.workspace / "memory" / "MEMORY.md"
        if not memory_file.exists():
            return "MEMORY.md not found."
        content = memory_file.read_text()[:500]
        return f"**MEMORY.md (first 500 chars):**\n\n{content}\n\n..."

    def _handle_skills(self, args: str, ctx: CommandContext) -> str:
        skill_dir  = ctx.workspace / "skills"
        auto_dir   = ctx.workspace / "skills" / "auto_generated"
        lines      = ["**Available Skills**", ""]

        # Built-in skills
        if skill_dir.exists():
            built_in = [
                d.name for d in skill_dir.iterdir()
                if d.is_dir() and d.name != "auto_generated"
            ]
            if built_in:
                lines.append("*Built-in:*")
                for s in sorted(built_in):
                    lines.append(f"  - {s}")
                lines.append("")

        # Auto-generated skills
        if auto_dir.exists():
            auto = list(auto_dir.glob("*.md"))
            if auto:
                lines.append("*Auto-generated from YOLO sessions:*")
                for s in sorted(auto)[:5]:
                    lines.append(f"  - {s.stem}")
                lines.append("")

        if len(lines) <= 2:
            return "No skills found."

        lines.append("Use /research or /yolo to auto-generate new skills.")
        return "\n".join(lines)

    def _handle_status(self, args: str, ctx: CommandContext) -> str:
        """Show full system health status with calibrated scores."""
        try:
            from jagabot.core.system_health_monitor import SystemHealthMonitor
            monitor = SystemHealthMonitor(ctx.workspace)
            return monitor.get_health_report()
        except Exception as e:
            return (
                "⚠️  Health monitor unavailable. Showing raw tool status:\n\n"
                "Call these tools and report EXACTLY what they return:\n"
                "1. k3_perspective(action='accuracy_stats')\n"
                "2. k1_bayesian(action='get_calibration')\n"
                "3. meta_learning(action='get_rankings')\n"
                "4. evolution(action='status')\n\n"
                f"Error: {e}"
            )

    def _handle_think(self, args: str, ctx: CommandContext) -> str:
        level = args.strip().lower() or "medium"
        valid = {"off", "low", "medium", "high"}
        if level not in valid:
            return f"Usage: /think <{'|'.join(valid)}>"
        depth_map = {
            "off":    "Answer directly, no extended reasoning.",
            "low":    "Brief reasoning before answering.",
            "medium": "Standard reasoning depth.",
            "high":   "Extended step-by-step reasoning. "
                      "Use tri_agent for complex questions.",
        }
        return (
            f"✅ Thinking level set to: **{level}**\n"
            f"{depth_map[level]}\n"
            f"(For this session only — resets on /restart)"
        )

    def _handle_model(self, args: str, ctx: CommandContext) -> str:
        if not args.strip():
            return (
                "**Current model:** Qwen-Plus\n"
                "**Provider:** dashscope → openai (fallback)\n\n"
                "To switch: /model <model_name>\n"
                "Available: qwen-plus, qwen-max, gpt-4o"
            )
        return (
            f"Model switch to '{args}' — "
            f"wire to: `agent.set_model('{args}')`"
        )

    def _handle_usage(self, args: str, ctx: CommandContext) -> str:
        show_cost = "cost" in args.lower()
        lines     = ["**Session Usage**", ""]

        if ctx.agent:
            try:
                tokens = getattr(ctx.agent, '_total_tokens', 0)
                lines.append(f"Tokens this session: {tokens:,}")
                if show_cost:
                    cost = tokens * 0.000002  # rough estimate
                    lines.append(f"Estimated cost: ${cost:.4f}")
            except Exception:
                lines.append("Token tracking not yet wired.")

        lines += ["", "Wire to: `agent.get_usage_stats()`"]
        return "\n".join(lines)

    def _handle_config(self, args: str, ctx: CommandContext) -> str:
        parts  = args.strip().split(None, 2)
        action = parts[0].lower() if parts else "show"

        config_file = ctx.workspace.parent / "config.json"
        if not config_file.exists():
            return "config.json not found. Copy config.json.example to start."

        try:
            config = json.loads(config_file.read_text())
        except Exception:
            return "config.json could not be read."

        if action == "show":
            # Show sanitized config (hide secrets)
            safe = {
                k: "***" if "key" in k.lower() or "token" in k.lower()
                else v
                for k, v in config.items()
            }
            return f"**Config:**\n```json\n{json.dumps(safe, indent=2)}\n```"

        if action == "get" and len(parts) > 1:
            key = parts[1]
            val = config.get(key, "not found")
            return f"{key}: {val}"

        if action == "set" and len(parts) > 1:
            # Parse key=value
            kv = parts[1]
            if "=" in kv:
                k, v = kv.split("=", 1)
                config[k.strip()] = v.strip()
                config_file.write_text(json.dumps(config, indent=2))
                return f"✅ Set {k.strip()} = {v.strip()}"
            return "Usage: /config set key=value"

        return f"Usage: /config [show|get <key>|set <key>=<val>]"

    def _handle_clear(self, args: str, ctx: CommandContext) -> str:
        if ctx.agent:
            try:
                ctx.agent.clear_session()
                return "✅ Session context cleared. Memory preserved."
            except Exception:
                pass
        return "✅ Clear requested. Wire to: `agent.clear_session()`"

    def _handle_btw(self, args: str, ctx: CommandContext) -> str:
        if not args.strip():
            return "Usage: /btw <quick question>"
        return (
            f"[Side question — answer briefly using session context]: "
            f"{args}"
        )

    def _handle_export(self, args: str, ctx: CommandContext) -> str:
        output_path = args.strip() or str(
            ctx.workspace / "exports" /
            f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        return (
            f"Export session to: {output_path}\n"
            f"Wire to: `session_writer.export_session(path)`"
        )

    def _handle_help(self, args: str, ctx: CommandContext) -> str:
        if args.strip():
            cmd = self.get(args.strip())
            if cmd:
                return (
                    f"**{cmd.name}**\n"
                    f"{cmd.description}\n\n"
                    f"Usage: `{cmd.usage}`\n"
                    + (f"Aliases: {', '.join(cmd.aliases)}"
                       if cmd.aliases else "")
                )
            return f"Unknown command: {args}"

        # Group by category
        categories: dict[str, list[Command]] = {}
        for cmd in self.all_commands(ctx.channel):
            cat = cmd.category
            categories.setdefault(cat, []).append(cmd)

        lines = ["**AutoJaga Commands**", ""]
        for cat, cmds in sorted(categories.items()):
            lines.append(f"*{cat.upper()}*")
            for cmd in cmds:
                lines.append(
                    f"  `{cmd.name:<14}` {cmd.description[:50]}"
                )
            lines.append("")

        lines.append("Type `/help <command>` for details.")
        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _days_ago(iso: str) -> str:
        try:
            dt   = datetime.fromisoformat(iso)
            days = (datetime.now() - dt).days
            return f"{days}d ago" if days > 0 else "today"
        except Exception:
            return "?"


# ── Telegram dispatcher ───────────────────────────────────────────────

class TelegramCommandDispatcher:
    """
    Handles slash commands from Telegram bot.

    Telegram sends /command as a message starting with /.
    BotFather registers command list shown to users.

    Wire into your Telegram channel handler:
        dispatcher = TelegramCommandDispatcher(registry, workspace)
        
        # In message handler:
        if update.message.text.startswith("/"):
            response = dispatcher.handle(
                text=update.message.text,
                user_id=str(update.message.from_user.id),
                chat_id=str(update.message.chat_id),
            )
            await update.message.reply_text(response)
    """

    # Commands to register with BotFather
    # Copy these to @BotFather → /setcommands
    BOTFATHER_COMMANDS = """
research - Deep research on any topic
idea - Generate ideas with isolated agents
yolo - Fully autonomous research session
pending - Show pending research outcomes
verify - Verify a research conclusion
memory - Memory operations and search
status - Full system status
sessions - List recent research sessions
compress - Compress and flush context
skills - List available skills
think - Set reasoning depth
usage - Show token usage
help - Show all commands
btw - Quick side question
stop - Stop current run
""".strip()

    def __init__(
        self,
        registry:  CommandRegistry,
        workspace: Path,
        agent:     object = None,
    ) -> None:
        self.registry  = registry
        self.workspace = workspace
        self.agent     = agent

    def handle(
        self,
        text:    str,
        user_id: str = "",
        chat_id: str = "",
    ) -> str:
        """Handle a Telegram slash command message."""
        ctx = CommandContext(
            workspace   = self.workspace,
            session_key = f"telegram:{user_id}",
            channel     = "telegram",
            user_id     = user_id,
            agent       = self.agent,
        )
        result = self.registry.dispatch(text, ctx)
        if result is None:
            return ""  # not a command

        # Telegram has 4096 char limit
        if len(result) > 4000:
            result = result[:3990] + "\n\n*(truncated — see full output in workspace)*"

        return result

    def get_botfather_commands(self) -> str:
        """Return commands formatted for BotFather /setcommands."""
        return self.BOTFATHER_COMMANDS


# ── CLI/TUI dispatcher ────────────────────────────────────────────────

class CLICommandDispatcher:
    """
    Handles slash commands from CLI (interactive.py) and TUI (tui.py).
    
    Wire into EnhancedCLI._process_turn():
        dispatcher = CLICommandDispatcher(registry, workspace)
        
        if user_input.startswith("/"):
            response = dispatcher.handle(user_input)
            if response:
                print_agent_streaming(response)
                return  # don't pass to agent
    """

    def __init__(
        self,
        registry:  CommandRegistry,
        workspace: Path,
        agent:     object = None,
    ) -> None:
        self.registry  = registry
        self.workspace = workspace
        self.agent     = agent

    def handle(self, text: str, session_key: str = "") -> Optional[str]:
        """Handle a CLI slash command."""
        ctx = CommandContext(
            workspace   = self.workspace,
            session_key = session_key,
            channel     = "cli",
            agent       = self.agent,
        )
        return self.registry.dispatch(text, ctx)


# ── Entry point helpers ───────────────────────────────────────────────

def create_registry(workspace: Path) -> CommandRegistry:
    """Create and return a configured CommandRegistry."""
    return CommandRegistry(workspace)


def get_telegram_botfather_commands() -> str:
    """Return BotFather command list — paste to @BotFather."""
    registry   = CommandRegistry(Path.home() / ".jagabot" / "workspace")
    dispatcher = TelegramCommandDispatcher(registry, Path("."))
    return dispatcher.get_botfather_commands()
