# jagabot/cli/onboard.py
"""
AutoJaga Onboarding Wizard — OpenClaw-inspired interactive setup.

Replaces manual config.json editing with a guided wizard.
Works first-run AND for reconfiguration.

Usage:
    jagabot setup          # first-time setup
    jagabot setup --quick  # quickstart with defaults
    jagabot configure      # reconfigure specific section
    jagabot doctor         # check + fix configuration

Steps:
    0. Check existing install (upgrade vs fresh)
    1. Use case / template selection
    2. LLM provider + API key
    3. Workspace location
    4. Agent identity (AGENTS.md)
    5. Channels (Telegram, CLI only, etc.)
    6. Tools profile
    7. Health check
    8. Done — launch
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.theme import Theme

# ── Theme ────────────────────────────────────────────────────────────
SETUP_THEME = Theme({
    "setup.header":  "bold #52d68a",
    "setup.step":    "bold #8ab8ff",
    "setup.success": "bold #52d68a",
    "setup.warn":    "bold yellow",
    "setup.error":   "bold #d65252",
    "setup.dim":     "dim #3d5a50",
    "setup.input":   "#e8e0d0",
    "setup.choice":  "bold cyan",
})

console = Console(theme=SETUP_THEME)

# ── Defaults ──────────────────────────────────────────────────────────
DEFAULT_WORKSPACE  = Path.home() / ".jagabot"
DEFAULT_PORT       = 8765
CONFIG_FILE        = "config.json"
AGENTS_MD_FILE     = "AGENTS.md"
CORE_IDENTITY_FILE = "core_identity.md"


# ── Templates ─────────────────────────────────────────────────────────

USE_CASE_TEMPLATES = {
    "research": {
        "label":       "🔬 Research Partner",
        "description": "Deep research, hypothesis tracking, learning loops",
        "tools":       ["web_search", "researcher", "tri_agent",
                        "quad_agent", "memory_fleet"],
        "model_hint":  "qwen-plus",
    },
    "financial": {
        "label":       "📊 Financial Analysis",
        "description": "Portfolio analysis, risk, Monte Carlo, IPW",
        "tools":       ["financial_cv", "monte_carlo", "var",
                        "portfolio_analyzer", "decision_engine"],
        "model_hint":  "qwen-plus",
    },
    "coding": {
        "label":       "💻 Coding Assistant",
        "description": "Code review, debugging, refactoring",
        "tools":       ["exec", "write_file", "read_file",
                        "shell", "web_search"],
        "model_hint":  "qwen-plus",
    },
    "general": {
        "label":       "🐈 General Assistant",
        "description": "All-purpose — research + coding + analysis",
        "tools":       ["web_search", "exec", "memory_fleet",
                        "tri_agent"],
        "model_hint":  "qwen-plus",
    },
    "custom": {
        "label":       "⚙️  Custom",
        "description": "Configure everything manually",
        "tools":       [],
        "model_hint":  "",
    },
}

LLM_PROVIDERS = {
    "qwen":      {
        "label":    "Qwen (DashScope) — Recommended",
        "env_key":  "DASHSCOPE_API_KEY",
        "models":   ["qwen-plus", "qwen-max", "qwen-turbo"],
        "default":  "qwen-plus",
        "docs_url": "https://dashscope.aliyuncs.com",
    },
    "openai":    {
        "label":    "OpenAI (GPT-4o, GPT-4)",
        "env_key":  "OPENAI_API_KEY",
        "models":   ["gpt-4o", "gpt-4", "gpt-3.5-turbo"],
        "default":  "gpt-4o",
        "docs_url": "https://platform.openai.com",
    },
    "anthropic": {
        "label":    "Anthropic (Claude)",
        "env_key":  "ANTHROPIC_API_KEY",
        "models":   ["claude-sonnet-4-6", "claude-opus-4-6"],
        "default":  "claude-sonnet-4-6",
        "docs_url": "https://console.anthropic.com",
    },
    "ollama":    {
        "label":    "Ollama (local, no API key)",
        "env_key":  None,
        "models":   ["llama3", "mistral", "qwen2.5"],
        "default":  "llama3",
        "docs_url": "https://ollama.ai",
    },
    "custom":    {
        "label":    "Custom OpenAI-compatible endpoint",
        "env_key":  "CUSTOM_API_KEY",
        "models":   [],
        "default":  "",
        "docs_url": "",
    },
}

CHANNEL_OPTIONS = {
    "cli":      "CLI / Terminal (always enabled)",
    "telegram": "Telegram Bot",
    "slack":    "Slack",
    "discord":  "Discord",
    "whatsapp": "WhatsApp (via signal-cli)",
    "email":    "Email (SMTP/IMAP)",
}


# ── Config dataclass ──────────────────────────────────────────────────

@dataclass
class SetupConfig:
    """Collected setup configuration."""
    use_case:       str   = "research"
    provider:       str   = "qwen"
    api_key:        str   = ""
    model:          str   = "qwen-plus"
    workspace:      Path  = field(
        default_factory=lambda: DEFAULT_WORKSPACE
    )
    agent_name:     str   = "jagabot"
    agent_emoji:    str   = "🐈"
    channels:       list  = field(default_factory=lambda: ["cli"])
    tools_profile:  str   = "research"
    telegram_token: str   = ""
    quick_mode:     bool  = False

    def to_config_json(self) -> dict:
        """Convert to config.json format."""
        return {
            "provider":   self.provider,
            "model":      self.model,
            "api_key":    self.api_key,
            "workspace":  str(self.workspace / "workspace"),
            "agent": {
                "name":       self.agent_name,
                "emoji":      self.agent_emoji,
                "use_case":   self.use_case,
            },
            "channels":   self.channels,
            "tools": {
                "profile":    self.tools_profile,
                "enabled":    USE_CASE_TEMPLATES.get(
                    self.use_case, {}
                ).get("tools", []),
            },
            "telegram": {
                "token": self.telegram_token,
            } if self.telegram_token else {},
            "memory": {
                "workspace":  str(self.workspace / "workspace" / "memory"),
                "fts_enabled":True,
                "daily_notes":True,
            },
        }


# ── Wizard steps ──────────────────────────────────────────────────────

class OnboardWizard:
    """
    Interactive setup wizard for AutoJaga.
    OpenClaw-inspired: guided, friendly, skippable.
    """

    def __init__(
        self,
        quick:     bool = False,
        section:   str  = None,
        workspace: Path = None,
    ) -> None:
        self.quick     = quick
        self.section   = section   # for --section partial reconfig
        self.workspace = workspace or DEFAULT_WORKSPACE
        self.config    = SetupConfig(quick_mode=quick)
        self.is_first  = not (self.workspace / CONFIG_FILE).exists()

    def run(self) -> bool:
        """
        Run the full wizard.
        Returns True if setup completed successfully.
        """
        self._print_welcome()

        # Section-specific reconfigure
        if self.section:
            return self._run_section(self.section)

        # Check existing install
        if not self.is_first:
            if not self._confirm_reconfigure():
                return False

        # Quick vs Advanced
        if not self.quick:
            self.quick = self._ask_mode()

        # Run steps
        steps = [
            ("use_case",  self._step_use_case),
            ("provider",  self._step_provider),
            ("workspace", self._step_workspace),
            ("identity",  self._step_identity),
            ("channels",  self._step_channels),
            ("tools",     self._step_tools),
        ]

        for step_name, step_fn in steps:
            console.print()
            console.rule(style="setup.dim")
            try:
                step_fn()
            except KeyboardInterrupt:
                console.print(
                    "\n[setup.warn]Setup cancelled.[/] "
                    "Run [bold]jagabot setup[/] to retry."
                )
                return False

        # Write config
        console.print()
        console.rule(style="setup.dim")
        self._write_config()

        # Health check
        self._step_health_check()

        # Done
        self._print_done()
        return True

    # ── Welcome ───────────────────────────────────────────────────────

    def _print_welcome(self) -> None:
        action = "Reconfiguring" if not self.is_first else "Setting up"
        console.print()
        console.print(Panel(
            f"[setup.header]🐈 AutoJaga Setup Wizard[/]\n\n"
            f"[setup.dim]{action} your autonomous research partner.[/]\n"
            f"[setup.dim]Press Ctrl+C at any time to cancel.[/]",
            border_style="#1e3a2f",
            padding=(0, 2),
        ))
        console.print()

    def _ask_mode(self) -> bool:
        """QuickStart vs Advanced."""
        console.print("[setup.step]Setup Mode[/]")
        console.print()
        console.print(
            "  [setup.choice][Q]uickstart[/]  "
            "[setup.dim]Sensible defaults, up in 2 minutes[/]"
        )
        console.print(
            "  [setup.choice][A]dvanced[/]    "
            "[setup.dim]Full control over every setting[/]"
        )
        console.print()
        choice = Prompt.ask(
            "[setup.dim]Choice[/]",
            choices=["q", "a", "Q", "A"],
            default="q",
        )
        return choice.lower() == "q"

    def _confirm_reconfigure(self) -> bool:
        """Ask if user wants to reconfigure existing install."""
        console.print(
            "[setup.warn]Existing AutoJaga configuration found.[/]\n"
            "Running setup again will update your config.json.\n"
            "Your memory and research data will NOT be affected."
        )
        console.print()
        return Confirm.ask("Continue with reconfiguration?", default=True)

    # ── Step 1: Use case ──────────────────────────────────────────────

    def _step_use_case(self) -> None:
        if self.quick:
            self.config.use_case = "research"
            console.print(
                "[setup.success]✅ Use case:[/] Research Partner (default)"
            )
            return

        console.print("[setup.step]Step 1 — Use Case[/]")
        console.print(
            "[setup.dim]Choose how you'll primarily use AutoJaga.[/]\n"
            "[setup.dim]This sets default tools and prompts.[/]"
        )
        console.print()

        table = Table(show_header=False, border_style="#1e3a2f")
        table.add_column("Key",   style="setup.choice", width=4)
        table.add_column("Name",  style="setup.header", width=20)
        table.add_column("Desc",  style="setup.dim")

        keys = list(USE_CASE_TEMPLATES.keys())
        for i, (key, tmpl) in enumerate(USE_CASE_TEMPLATES.items(), 1):
            table.add_row(
                str(i), tmpl["label"], tmpl["description"]
            )
        console.print(table)
        console.print()

        choice = Prompt.ask(
            "[setup.dim]Choice (1-5)[/]",
            default="1",
        )
        try:
            idx = int(choice) - 1
            self.config.use_case = keys[idx]
        except (ValueError, IndexError):
            self.config.use_case = "research"

        tmpl = USE_CASE_TEMPLATES[self.config.use_case]
        console.print(
            f"[setup.success]✅ Use case:[/] {tmpl['label']}"
        )

    # ── Step 2: Provider + API key ─────────────────────────────────────

    def _step_provider(self) -> None:
        if self.quick:
            self._auto_detect_provider()
            return

        console.print("[setup.step]Step 2 — LLM Provider & API Key[/]")
        console.print(
            "[setup.dim]Choose your language model provider.[/]"
        )
        console.print()

        table = Table(show_header=False, border_style="#1e3a2f")
        table.add_column("Key",  style="setup.choice", width=4)
        table.add_column("Name", style="setup.header")

        keys = list(LLM_PROVIDERS.keys())
        for i, (key, prov) in enumerate(LLM_PROVIDERS.items(), 1):
            table.add_row(str(i), prov["label"])
        console.print(table)
        console.print()

        choice = Prompt.ask(
            "[setup.dim]Choice (1-5)[/]",
            default="1",
        )
        try:
            idx = int(choice) - 1
            self.config.provider = keys[idx]
        except (ValueError, IndexError):
            self.config.provider = "qwen"

        prov = LLM_PROVIDERS[self.config.provider]

        # Model selection
        if prov["models"] and not self.quick:
            console.print()
            console.print(
                f"[setup.dim]Available models: "
                f"{', '.join(prov['models'])}[/]"
            )
            self.config.model = Prompt.ask(
                "[setup.dim]Model[/]",
                default=prov["default"],
            )
        else:
            self.config.model = prov["default"]

        # API key
        if prov["env_key"]:
            existing = os.environ.get(prov["env_key"], "")
            if existing:
                console.print(
                    f"[setup.success]✅ Found {prov['env_key']} "
                    f"in environment.[/]"
                )
                self.config.api_key = existing
            else:
                console.print()
                console.print(
                    f"[setup.dim]Get your key at: "
                    f"{prov['docs_url']}[/]"
                )
                key = Prompt.ask(
                    f"[setup.dim]Paste {prov['env_key']} "
                    f"(or press Enter to skip)[/]",
                    default="",
                    password=True,
                )
                self.config.api_key = key

        console.print(
            f"[setup.success]✅ Provider:[/] "
            f"{prov['label']} / {self.config.model}"
        )

    def _auto_detect_provider(self) -> None:
        """Auto-detect provider from environment variables."""
        for key, prov in LLM_PROVIDERS.items():
            if prov["env_key"] and os.environ.get(prov["env_key"]):
                self.config.provider = key
                self.config.api_key  = os.environ[prov["env_key"]]
                self.config.model    = prov["default"]
                console.print(
                    f"[setup.success]✅ Provider:[/] "
                    f"{prov['label']} (auto-detected)"
                )
                return

        # Default to Qwen — ask for key
        self.config.provider = "qwen"
        self.config.model    = "qwen-plus"
        prov = LLM_PROVIDERS["qwen"]
        console.print(
            f"[setup.warn]No API key found in environment.[/]\n"
            f"[setup.dim]Get your DashScope key at: "
            f"{prov['docs_url']}[/]"
        )
        key = Prompt.ask(
            "[setup.dim]Paste DASHSCOPE_API_KEY "
            "(or press Enter to skip)[/]",
            default="",
            password=True,
        )
        self.config.api_key = key
        console.print(
            f"[setup.success]✅ Provider:[/] Qwen-Plus"
        )

    # ── Step 3: Workspace ─────────────────────────────────────────────

    def _step_workspace(self) -> None:
        if self.quick:
            self.config.workspace = DEFAULT_WORKSPACE
            console.print(
                f"[setup.success]✅ Workspace:[/] "
                f"{DEFAULT_WORKSPACE}"
            )
            return

        console.print("[setup.step]Step 3 — Workspace Location[/]")
        console.print(
            "[setup.dim]Where should AutoJaga store memory, "
            "research outputs, and config?[/]"
        )
        console.print()

        path_str = Prompt.ask(
            "[setup.dim]Workspace path[/]",
            default=str(DEFAULT_WORKSPACE),
        )
        self.config.workspace = Path(path_str).expanduser()
        console.print(
            f"[setup.success]✅ Workspace:[/] {self.config.workspace}"
        )

    # ── Step 4: Identity ──────────────────────────────────────────────

    def _step_identity(self) -> None:
        if self.quick:
            console.print(
                "[setup.success]✅ Identity:[/] jagabot 🐈 (default)"
            )
            return

        console.print("[setup.step]Step 4 — Agent Identity[/]")
        console.print(
            "[setup.dim]Name your agent and set its personality.[/]"
        )
        console.print()

        self.config.agent_name = Prompt.ask(
            "[setup.dim]Agent name[/]",
            default="jagabot",
        )
        self.config.agent_emoji = Prompt.ask(
            "[setup.dim]Agent emoji[/]",
            default="🐈",
        )

        # AGENTS.md customisation
        console.print()
        agents_md = self.config.workspace / AGENTS_MD_FILE
        if agents_md.exists():
            console.print(
                "[setup.dim]AGENTS.md found — keeping existing.[/]"
            )
        else:
            edit = Confirm.ask(
                "Set up AGENTS.md now? "
                "(defines personality and rules)",
                default=True,
            )
            if edit:
                self._setup_agents_md()

        console.print(
            f"[setup.success]✅ Identity:[/] "
            f"{self.config.agent_name} {self.config.agent_emoji}"
        )

    def _setup_agents_md(self) -> None:
        """Interactive AGENTS.md setup."""
        console.print()
        console.print(
            "[setup.dim]AGENTS.md defines how your agent thinks "
            "and behaves.[/]\n"
            "[setup.dim]You can always edit it later at:[/]\n"
            f"[setup.dim]{self.config.workspace}/{AGENTS_MD_FILE}[/]"
        )
        console.print()

        # Choose template
        templates = {
            "1": ("Research Partner",
                  "Thorough, honest, cites sources"),
            "2": ("Financial Analyst",
                  "Quantitative, risk-aware, no fabrication"),
            "3": ("General Assistant",
                  "Helpful, balanced, multi-purpose"),
            "4": ("Custom",
                  "Start from blank"),
        }

        for key, (name, desc) in templates.items():
            console.print(
                f"  [setup.choice][{key}][/] "
                f"[setup.header]{name}[/] "
                f"[setup.dim]— {desc}[/]"
            )
        console.print()

        choice = Prompt.ask(
            "[setup.dim]Template[/]",
            choices=list(templates.keys()),
            default="1",
        )

        name, _ = templates[choice]
        # Seed from core_identity.md template
        seed_path = Path(__file__).parent.parent / "templates" / \
            f"agents_md_{choice}.md"
        if not seed_path.exists():
            # Fallback — write minimal AGENTS.md
            content = (
                f"# {self.config.agent_name} — Agent Identity\n\n"
                f"## Identity\n"
                f"Name: {self.config.agent_name}\n"
                f"Emoji: {self.config.agent_emoji}\n"
                f"Template: {name}\n\n"
                f"## Core Rules\n"
                f"- Never fabricate. Call tool first, report result.\n"
                f"- Label illustrative numbers: [e.g. 0.72]\n"
                f"- Explain mode: no exec for conceptual questions.\n"
                f"- Always interpret results + suggest next step.\n"
            )
            agents_md_path = self.config.workspace / AGENTS_MD_FILE
            agents_md_path.parent.mkdir(parents=True, exist_ok=True)
            agents_md_path.write_text(content)
            console.print(
                f"[setup.success]✅ AGENTS.md created.[/] "
                f"Edit at: {agents_md_path}"
            )

    # ── Step 5: Channels ──────────────────────────────────────────────

    def _step_channels(self) -> None:
        if self.quick:
            self.config.channels = ["cli"]
            console.print(
                "[setup.success]✅ Channels:[/] CLI only (default)"
            )
            return

        console.print("[setup.step]Step 5 — Channels[/]")
        console.print(
            "[setup.dim]Which channels should AutoJaga listen on?[/]\n"
            "[setup.dim]CLI is always enabled.[/]"
        )
        console.print()

        for key, label in CHANNEL_OPTIONS.items():
            if key == "cli":
                console.print(
                    f"  [setup.success]✅ {label}[/]"
                )
            else:
                enabled = Confirm.ask(
                    f"  Enable {label}?",
                    default=False,
                )
                if enabled:
                    self.config.channels.append(key)
                    if key == "telegram":
                        self._setup_telegram()

        console.print(
            f"[setup.success]✅ Channels:[/] "
            f"{', '.join(self.config.channels)}"
        )

    def _setup_telegram(self) -> None:
        """Telegram bot token setup."""
        console.print()
        console.print(
            "[setup.dim]To create a Telegram bot:[/]\n"
            "[setup.dim]1. Message @BotFather on Telegram[/]\n"
            "[setup.dim]2. Send /newbot[/]\n"
            "[setup.dim]3. Follow prompts to get your token[/]"
        )
        console.print()
        token = Prompt.ask(
            "[setup.dim]Paste Telegram bot token "
            "(or press Enter to skip)[/]",
            default="",
            password=True,
        )
        self.config.telegram_token = token
        if token:
            console.print(
                "[setup.success]✅ Telegram token saved.[/]\n"
                "[setup.dim]Register commands with BotFather:[/]\n"
                "[setup.dim]jagabot setup --botfather[/]"
            )

    # ── Step 6: Tools ─────────────────────────────────────────────────

    def _step_tools(self) -> None:
        if self.quick:
            self.config.tools_profile = self.config.use_case
            console.print(
                f"[setup.success]✅ Tools:[/] "
                f"{self.config.use_case} profile (default)"
            )
            return

        console.print("[setup.step]Step 6 — Tools Profile[/]")
        console.print(
            "[setup.dim]Which tools should be active by default?[/]"
        )
        console.print()

        tmpl    = USE_CASE_TEMPLATES.get(self.config.use_case, {})
        default = tmpl.get("tools", [])

        console.print(
            f"[setup.dim]Recommended for {self.config.use_case}: "
            f"{', '.join(default)}[/]"
        )
        console.print()

        use_default = Confirm.ask(
            "Use recommended tool set?",
            default=True,
        )
        if not use_default:
            console.print(
                "[setup.dim]Edit tools in config.json after setup.[/]"
            )

        self.config.tools_profile = self.config.use_case
        console.print(
            f"[setup.success]✅ Tools:[/] "
            f"{self.config.use_case} profile"
        )

    # ── Health check ──────────────────────────────────────────────────

    def _step_health_check(self) -> None:
        console.print("[setup.step]Health Check[/]")
        console.print()

        checks = [
            ("Config file",    self._check_config),
            ("Workspace",      self._check_workspace),
            ("API key",        self._check_api_key),
            ("AGENTS.md",      self._check_agents_md),
            ("Python deps",    self._check_deps),
        ]

        all_ok = True
        for name, check_fn in checks:
            ok, msg = check_fn()
            icon = "[setup.success]✅[/]" if ok else "[setup.warn]⚠️[/]"
            console.print(f"  {icon} {name:<18} {msg}")
            if not ok:
                all_ok = False

        console.print()
        if all_ok:
            console.print(
                "[setup.success]All checks passed.[/]"
            )
        else:
            console.print(
                "[setup.warn]Some checks need attention.[/]\n"
                "[setup.dim]Run [bold]jagabot doctor[/] for details.[/]"
            )

    def _check_config(self) -> tuple[bool, str]:
        path = self.config.workspace / CONFIG_FILE
        return path.exists(), str(path)

    def _check_workspace(self) -> tuple[bool, str]:
        ws = self.config.workspace / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        return True, str(ws)

    def _check_api_key(self) -> tuple[bool, str]:
        if self.config.provider == "ollama":
            return True, "local (no key needed)"
        if self.config.api_key:
            return True, "configured ✓"
        env_key = LLM_PROVIDERS.get(
            self.config.provider, {}
        ).get("env_key", "")
        if env_key and os.environ.get(env_key):
            return True, f"from {env_key} env var"
        return False, "missing — run jagabot configure --section provider"

    def _check_agents_md(self) -> tuple[bool, str]:
        path = self.config.workspace / AGENTS_MD_FILE
        return path.exists(), str(path)

    def _check_deps(self) -> tuple[bool, str]:
        try:
            import rich
            import typer
            return True, "rich, typer installed"
        except ImportError as e:
            return False, f"missing: {e}"

    # ── Write config ──────────────────────────────────────────────────

    def _write_config(self) -> None:
        """Write config.json and .env file."""
        console.print("[setup.step]Writing Configuration[/]")
        console.print()

        # Create workspace
        self.config.workspace.mkdir(parents=True, exist_ok=True)
        (self.config.workspace / "workspace").mkdir(
            parents=True, exist_ok=True
        )

        # Write config.json
        config_path = self.config.workspace / CONFIG_FILE
        config_data = self.config.to_config_json()
        # Remove API key from config.json — store in .env
        api_key = config_data.pop("api_key", "")
        config_path.write_text(
            json.dumps(config_data, indent=2),
            encoding="utf-8",
        )
        console.print(
            f"[setup.success]✅ config.json[/] → {config_path}"
        )

        # Write .env (API keys stored separately)
        if api_key:
            env_path = self.config.workspace / ".env"
            prov     = LLM_PROVIDERS.get(self.config.provider, {})
            env_key  = prov.get("env_key", "API_KEY")
            existing = {}
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        existing[k.strip()] = v.strip()
            existing[env_key] = api_key
            env_content = "\n".join(
                f"{k}={v}" for k, v in existing.items()
            )
            env_path.write_text(env_content, encoding="utf-8")
            env_path.chmod(0o600)  # owner read-only
            console.print(
                f"[setup.success]✅ .env[/] → {env_path} (mode 600)"
            )

        # Write core_identity.md if missing
        identity_path = self.config.workspace / CORE_IDENTITY_FILE
        if not identity_path.exists():
            self._write_core_identity(identity_path)
            console.print(
                f"[setup.success]✅ core_identity.md[/] "
                f"→ {identity_path}"
            )

    def _write_core_identity(self, path: Path) -> None:
        """Write minimal core_identity.md."""
        content = (
            f"# {self.config.agent_name}\n"
            f"Truthful executor. Never present inference as fact.\n"
            f"Call tool FIRST, then report what it returned.\n"
            f"Label illustrative numbers: [e.g. 0.72]\n\n"
            f"## Response Mode\n"
            f"Explain questions → NLP only, no exec.\n"
            f"Calculation questions → exec to verify.\n"
            f"After tool call → interpret + suggest next step.\n"
        )
        path.write_text(content, encoding="utf-8")

    # ── Done ──────────────────────────────────────────────────────────

    def _print_done(self) -> None:
        console.print()
        console.print(Panel(
            f"[setup.success]🐈 AutoJaga is ready![/]\n\n"
            f"[setup.dim]Start chatting:[/]  "
            f"[bold]jagabot chat[/]\n"
            f"[setup.dim]Full dashboard:[/]  "
            f"[bold]jagabot tui[/]\n"
            f"[setup.dim]Autonomous run:[/]  "
            f"[bold]jagabot yolo \"your goal\"[/]\n"
            f"[setup.dim]Reconfigure:[/]     "
            f"[bold]jagabot configure[/]\n"
            f"[setup.dim]Health check:[/]    "
            f"[bold]jagabot doctor[/]",
            border_style="#1e3a2f",
            padding=(0, 2),
        ))
        console.print()

    # ── Section reconfigure ───────────────────────────────────────────

    def _run_section(self, section: str) -> bool:
        """Run only one section for partial reconfiguration."""
        section_map = {
            "provider":  self._step_provider,
            "model":     self._step_provider,
            "workspace": self._step_workspace,
            "identity":  self._step_identity,
            "channels":  self._step_channels,
            "telegram":  self._setup_telegram,
            "tools":     self._step_tools,
        }
        fn = section_map.get(section.lower())
        if not fn:
            console.print(
                f"[setup.error]Unknown section: {section}[/]\n"
                f"[setup.dim]Valid: "
                f"{', '.join(section_map.keys())}[/]"
            )
            return False

        fn()
        self._write_config()
        console.print(
            f"\n[setup.success]✅ {section} reconfigured.[/]"
        )
        return True


# ── Doctor command ────────────────────────────────────────────────────

class DoctorChecker:
    """
    Checks and fixes AutoJaga configuration.
    Equivalent to openclaw doctor.
    """

    def __init__(self, workspace: Path = None) -> None:
        self.workspace = workspace or DEFAULT_WORKSPACE

    def run(self) -> bool:
        """Run all checks. Returns True if all pass."""
        console.print()
        console.print("[setup.step]🔍 AutoJaga Doctor[/]")
        console.print()

        checks = [
            ("config.json exists",      self._check_config_exists),
            ("config.json valid JSON",  self._check_config_valid),
            ("API key configured",      self._check_api_key),
            ("workspace writable",      self._check_workspace),
            ("AGENTS.md exists",        self._check_agents_md),
            ("core_identity.md exists", self._check_identity),
            ("memory directory",        self._check_memory_dir),
            ("Python 3.11+",            self._check_python),
            ("rich installed",          self._check_rich),
            ("typer installed",         self._check_typer),
        ]

        all_ok   = True
        failures = []

        for name, check_fn in checks:
            ok, msg, fix = check_fn()
            icon = (
                "[setup.success]✅[/]" if ok
                else "[setup.error]❌[/]"
            )
            console.print(f"  {icon} {name:<30} {msg}")
            if not ok:
                all_ok = False
                failures.append((name, fix))

        console.print()

        if all_ok:
            console.print(
                "[setup.success]All checks passed. "
                "AutoJaga is healthy.[/]"
            )
            return True

        console.print(
            f"[setup.error]{len(failures)} issue(s) found.[/]"
        )
        console.print()

        # Offer to auto-fix
        for name, fix_fn in failures:
            if fix_fn:
                console.print(
                    f"[setup.warn]Fix: {name}[/]"
                )
                if Confirm.ask("Auto-fix this?", default=True):
                    try:
                        fix_fn()
                        console.print(
                            "[setup.success]  Fixed.[/]"
                        )
                    except Exception as e:
                        console.print(
                            f"[setup.error]  Fix failed: {e}[/]"
                        )

        console.print()
        console.print(
            "[setup.dim]Run [bold]jagabot setup[/] "
            "to reconfigure from scratch.[/]"
        )
        return False

    def _check_config_exists(self):
        path = self.workspace / CONFIG_FILE
        ok   = path.exists()
        fix  = (lambda: Path(path).write_text("{}")) if not ok else None
        return ok, str(path), fix

    def _check_config_valid(self):
        path = self.workspace / CONFIG_FILE
        if not path.exists():
            return False, "file missing", None
        try:
            json.loads(path.read_text())
            return True, "valid JSON", None
        except json.JSONDecodeError as e:
            return False, f"invalid: {e}", None

    def _check_api_key(self):
        config_path = self.workspace / CONFIG_FILE
        if not config_path.exists():
            return False, "config.json missing", None
        try:
            config   = json.loads(config_path.read_text())
            provider = config.get("provider", "qwen")
            prov     = LLM_PROVIDERS.get(provider, {})
            env_key  = prov.get("env_key", "")
            if provider == "ollama":
                return True, "ollama (no key needed)", None
            if env_key and os.environ.get(env_key):
                return True, f"found in {env_key}", None
            env_path = self.workspace / ".env"
            if env_path.exists() and env_key in env_path.read_text():
                return True, "found in .env", None
            return False, f"{env_key} not set", None
        except Exception as e:
            return False, str(e), None

    def _check_workspace(self):
        ws  = self.workspace / "workspace"
        ok  = ws.exists() and os.access(ws, os.W_OK)
        fix = (lambda: ws.mkdir(parents=True, exist_ok=True)) if not ok else None
        return ok, str(ws), fix

    def _check_agents_md(self):
        path = self.workspace / AGENTS_MD_FILE
        return path.exists(), str(path), None

    def _check_identity(self):
        path = self.workspace / CORE_IDENTITY_FILE
        return path.exists(), str(path), None

    def _check_memory_dir(self):
        path = self.workspace / "workspace" / "memory"
        ok   = path.exists()
        fix  = (lambda: path.mkdir(parents=True, exist_ok=True)) if not ok else None
        return ok, str(path), fix

    def _check_python(self):
        ok  = sys.version_info >= (3, 11)
        msg = f"{sys.version_info.major}.{sys.version_info.minor}"
        return ok, msg, None

    def _check_rich(self):
        try:
            import rich
            return True, f"v{rich.__version__}", None
        except ImportError:
            fix = lambda: subprocess.run(
                [sys.executable, "-m", "pip", "install",
                 "rich", "--break-system-packages"]
            )
            return False, "not installed", fix

    def _check_typer(self):
        try:
            import typer
            return True, f"v{typer.__version__}", None
        except ImportError:
            fix = lambda: subprocess.run(
                [sys.executable, "-m", "pip", "install",
                 "typer", "--break-system-packages"]
            )
            return False, "not installed", fix


# ── Entry points ──────────────────────────────────────────────────────

def run_setup(
    quick:   bool = False,
    section: str  = None,
) -> None:
    """Run the setup wizard. Called from commands.py."""
    wizard = OnboardWizard(quick=quick, section=section)
    wizard.run()


def run_doctor() -> None:
    """Run the doctor checker. Called from commands.py."""
    checker = DoctorChecker()
    checker.run()


# ── Add to commands.py ────────────────────────────────────────────────
#
# @app.command()
# def setup(
#     quick: bool = typer.Option(False, "--quick", "-q",
#                                help="QuickStart with defaults"),
#     section: str = typer.Option(None, "--section", "-s",
#                                 help="Reconfigure one section only"),
# ):
#     """Interactive setup wizard — OpenClaw style."""
#     from jagabot.cli.onboard import run_setup
#     run_setup(quick=quick, section=section)
#
#
# @app.command()
# def configure(
#     section: str = typer.Argument(
#         None,
#         help="Section to configure: provider/workspace/channels/tools"
#     ),
# ):
#     """Reconfigure a specific section."""
#     from jagabot.cli.onboard import run_setup
#     run_setup(section=section)
#
#
# @app.command()
# def doctor():
#     """Check and fix AutoJaga configuration."""
#     from jagabot.cli.onboard import run_doctor
#     run_doctor()


if __name__ == "__main__":
    import sys
    quick   = "--quick" in sys.argv or "-q" in sys.argv
    section = None
    for i, arg in enumerate(sys.argv):
        if arg == "--section" and i + 1 < len(sys.argv):
            section = sys.argv[i + 1]
    run_setup(quick=quick, section=section)
