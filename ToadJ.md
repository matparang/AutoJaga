📋 SCOPE: Integrate TOAD TUI into AutoJaga/JAGABOT

---

🎯 OBJECTIVE

Replace the current simple TUI (jagabot agent --tui) with a professional TOAD-style interface that maintains all existing functionality while adding:

· ✅ Beautiful markdown rendering
· ✅ Persistent shell integration
· ✅ Fuzzy file picker (@ syntax)
· ✅ Session management (ctrl+r resume)
· ✅ Multi-agent view (ctrl+s)
· ✅ Progress bars and live updates
· ✅ Syntax highlighting
· ✅ Mouse support

---

🔧 CURRENT vs TARGET

```
┌─────────────────────────────────────────────────────────────┐
│                    CURRENT TUI (basic)                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  $ jagabot agent --tui                                      │
│  ╔═══════════════════════════════════════════════════════╗  │
│  ║ AutoJaga v4.5 - TUI Mode                              ║  │
│  ║ Type 'help' for commands                              ║  │
│  ╚═══════════════════════════════════════════════════════╝  │
│                                                              │
│  You: jalankan research tentang renewable energy           │
│  ⏳ AutoJaga is thinking...                                │
│  ✅ Done!                                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    TARGET TUI (TOAD-style)                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ╔══════════════════════════════════════════════════════════╗
│  ║  AUTOJAGA v5.0 — RESEARCH PARTNER                       ║
│  ║  F1:Help  Ctrl+S:Agents  Ctrl+R:Resume  @:File  !:Shell ║
│  ╚══════════════════════════════════════════════════════════╝
│                                                              │
│  📁 /research/ $ _                                         │
│                                                              │
│  You: @proposal.md jalankan research                       │
│  ╭──────────────────────────────────────────────────────╮  │
│  │ 🔍 Phase 1: Tri-Agent Debate                          │  │
│  │   🐂 Bull: Opportunities identified                   │  │
│  │   🐻 Bear: Risks highlighted                          │  │
│  │   🧔 Buffett: Value assessed                          │  │
│  │ ✅ Proposal saved to research/proposal_20260314.md    │  │
│  ╰──────────────────────────────────────────────────────╯  │
│                                                              │
│  [25%] ⏳ Phase 2: Planning... (2s remaining)              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

📁 FILES TO CREATE/MODIFY

```bash
/root/nanojaga/jagabot/cli/
├── toad_tui.py                 # NEW - Main TOAD-style TUI
├── __init__.py                  # MODIFY - Add toad_tui option
└── commands.py                  # MODIFY - Add --toad flag

/root/nanojaga/jagabot/core/
├── toad_bridge.py               # NEW - Bridge between AutoJaga and TOAD
├── session_manager.py           # MODIFY - Add TOAD session support
└── markdown_renderer.py         # NEW - TOAD-style markdown

/root/nanojaga/autojaga-toad/     # NEW - Integration directory
├── config.yaml                   # TOAD configuration
├── shell_wrapper.py              # Persistent shell
└── file_picker.py                # Fuzzy file picker
```

---

📋 TASK 1: TOAD Bridge (jagabot/core/toad_bridge.py)

```python
"""
Bridge between AutoJaga and TOAD TUI
"""

import asyncio
import json
from typing import Dict, Any, Optional
from pathlib import Path

class ToadBridge:
    """
    Handles communication between TOAD UI and AutoJaga engine
    """
    
    def __init__(self):
        self.session_id = None
        self.current_task = None
        self.output_queue = asyncio.Queue()
        self.input_queue = asyncio.Queue()
    
    async def connect(self):
        """Connect to TOAD UI"""
        # TOAD will communicate via stdio
        pass
    
    async def send_to_ui(self, message: Dict[str, Any]):
        """Send message to TOAD UI"""
        print(json.dumps(message), flush=True)
    
    async def receive_from_ui(self) -> Dict[str, Any]:
        """Receive message from TOAD UI"""
        line = await asyncio.get_event_loop().run_in_executor(
            None, sys.stdin.readline
        )
        return json.loads(line)
    
    async def run_phase(self, phase_name: str, agent_func, **kwargs):
        """Run a research phase with progress updates"""
        await self.send_to_ui({
            "type": "phase_start",
            "phase": phase_name,
            "message": f"Starting {phase_name}..."
        })
        
        result = await agent_func(**kwargs)
        
        await self.send_to_ui({
            "type": "phase_complete",
            "phase": phase_name,
            "result": result
        })
        
        return result
```

---

📋 TASK 2: Shell Wrapper (autojaga-toad/shell_wrapper.py)

```python
"""
Persistent shell integration (TOAD's special feature)
"""

import os
import subprocess
import shlex
from pathlib import Path

class PersistentShell:
    """
    Shell that maintains state (cd, env vars) between commands
    """
    
    def __init__(self):
        self.env = os.environ.copy()
        self.cwd = Path.cwd()
        self.history = []
    
    def execute(self, command: str) -> dict:
        """Execute shell command with persistent state"""
        if command.strip().startswith('cd '):
            return self._handle_cd(command)
        
        if '=' in command and not ' ' in command:
            return self._handle_env(command)
        
        result = subprocess.run(
            command,
            shell=True,
            cwd=self.cwd,
            env=self.env,
            capture_output=True,
            text=True
        )
        
        self.history.append(command)
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "cwd": str(self.cwd)
        }
    
    def _handle_cd(self, command: str):
        parts = shlex.split(command)
        if len(parts) == 1:
            target = Path.home()
        else:
            target = Path(parts[1])
            if not target.is_absolute():
                target = self.cwd / target
        
        if target.exists() and target.is_dir():
            self.cwd = target.resolve()
            return {"stdout": "", "stderr": "", "returncode": 0, "cwd": str(self.cwd)}
        else:
            return {"stdout": "", "stderr": f"cd: {target}: No such directory", "returncode": 1}
    
    def _handle_env(self, command: str):
        key, value = command.split('=', 1)
        self.env[key] = value
        return {"stdout": "", "stderr": "", "returncode": 0}
```

---

📋 TASK 3: File Picker (autojaga-toad/file_picker.py)

```python
"""
Fuzzy file picker with @ syntax (TOAD's feature)
"""

from pathlib import Path
from thefuzz import fuzz
from prompt_toolkit import prompt
from prompt_toolkit.completion import FuzzyWordCompleter

class FilePicker:
    """
    @filename syntax with fuzzy search
    """
    
    def __init__(self, root: Path = Path("/root/.jagabot/workspace")):
        self.root = root
        self.files = []
        self._scan_files()
    
    def _scan_files(self):
        """Scan all files in workspace"""
        for path in self.root.rglob("*"):
            if path.is_file():
                rel_path = path.relative_to(self.root)
                self.files.append(str(rel_path))
    
    def fuzzy_find(self, query: str) -> list[str]:
        """Fuzzy find files matching query"""
        matches = []
        for f in self.files:
            score = fuzz.partial_ratio(query.lower(), f.lower())
            if score > 60:
                matches.append((f, score))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches[:10]]
    
    def interactive_picker(self, initial: str = "") -> str:
        """Interactive fuzzy file picker"""
        completer = FuzzyWordCompleter(self.files)
        selected = prompt(
            "📁 File: ",
            completer=completer,
            complete_while_typing=True
        )
        return selected
```

---

📋 TASK 4: TOAD TUI Main (jagabot/cli/toad_tui.py)

```python
#!/usr/bin/env python3
"""
TOAD-style TUI for AutoJaga
"""

import asyncio
import sys
from pathlib import Path
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.align import Align
from rich.text import Text
from datetime import datetime

from ..core.toad_bridge import ToadBridge
from ..core.session_manager import SessionManager
from ...autojaga-toad.shell_wrapper import PersistentShell
from ...autojaga-toad.file_picker import FilePicker
from ..skills.research import ResearchSkill

console = Console()

class ToadTUI:
    """
    Professional TUI for AutoJaga (TOAD-style)
    """
    
    def __init__(self):
        self.bridge = ToadBridge()
        self.shell = PersistentShell()
        self.sessions = SessionManager()
        self.picker = FilePicker()
        self.research = ResearchSkill()
        
        self.layout = self._create_layout()
        self.running = True
        self.current_phase = None
        self.progress = 0
    
    def _create_layout(self):
        """Create the layout structure"""
        layout = Layout()
        layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        return layout
    
    def _render_header(self):
        """Render header with keybindings"""
        text = Text()
        text.append(" AUTOJAGA v5.0 ", style="bold white on blue")
        text.append(" • RESEARCH PARTNER • ", style="white on black")
        text.append(" F1:Help ", style="dim")
        text.append(" Ctrl+S:Agents ", style="dim") 
        text.append(" Ctrl+R:Resume ", style="dim")
        text.append(" @:File ", style="dim")
        text.append(" !:Shell ", style="dim")
        
        return Panel(
            Align.center(text),
            style="blue",
            height=3
        )
    
    def _render_body(self):
        """Render main content area"""
        if self.current_phase:
            return self._render_research_phase()
        else:
            return self._render_welcome()
    
    def _render_research_phase(self):
        """Render research phase with progress"""
        layout = Layout()
        layout.split_row(
            Layout(name="progress", size=30),
            Layout(name="content")
        )
        
        # Progress panel
        progress_table = Table(show_header=False, box=None)
        progress_table.add_column("Phase", style="cyan")
        progress_table.add_column("Status")
        
        phases = ["Phase 1: Idea", "Phase 2: Plan", "Phase 3: Execute", "Phase 4: Synthesize"]
        for i, phase in enumerate(phases):
            if i < self.progress:
                status = "✅"
            elif i == self.progress:
                status = "⏳"
            else:
                status = "⏸️"
            progress_table.add_row(phase, status)
        
        layout["progress"].update(Panel(progress_table, title="Progress"))
        
        # Content panel
        content = f"""
📊 **Current Research: renewable energy investment**

**Phase {self.progress + 1} in progress...**

Results so far:
- Bull identified opportunities
- Bear highlighted risks
- Buffett assessed value
        """
        layout["content"].update(Panel(Markdown(content), title="Research"))
        
        return layout
    
    def _render_welcome(self):
        """Render welcome screen"""
        welcome = """
# 🚀 **AUTOJAGA v5.0 - RESEARCH PARTNER**

## Ready to help with:

• 🔍 **Research** - Comprehensive 4-phase pipeline
• 📊 **Analysis** - Financial, technical, scientific
• 🤖 **Multi-Agent** - Tri-agent + Quad-agent swarms
• ✅ **Verified** - Epistemic auditor catches lies

## Quick Start

```

@proposal.md jalankan research tentang [topic]
!ls -la organized/research/
/help for commands

```

**Current workspace:** `{}`
        """.format(self.shell.cwd)
        
        return Panel(Markdown(welcome), title="Welcome")
    
    def _render_footer(self):
        """Render footer with current directory"""
        return Panel(
            f"📁 {self.shell.cwd} $ ",
            style="bright_black"
        )
    
    async def run(self):
        """Main TUI loop"""
        with Live(self.layout, refresh_per_second=10, screen=True) as live:
            while self.running:
                self.layout["header"].update(self._render_header())
                self.layout["body"].update(self._render_body())
                self.layout["footer"].update(self._render_footer())
                
                try:
                    user_input = await self._get_input()
                    await self._handle_input(user_input)
                except KeyboardInterrupt:
                    pass
                except EOFError:
                    break
                
                await asyncio.sleep(0.05)
    
    async def _get_input(self):
        """Get user input with @ file picker"""
        import sys
        line = sys.stdin.readline()
        return line.strip()
    
    async def _handle_input(self, user_input: str):
        """Handle user input"""
        if not user_input:
            return
        
        if user_input.startswith('@'):
            # File picker mode
            parts = user_input[1:].split(maxsplit=1)
            if len(parts) > 1:
                filename = self.picker.interactive_picker(parts[0])
                if filename:
                    await self._handle_input(f"{filename} {parts[1]}")
            else:
                filename = self.picker.interactive_picker(user_input[1:])
                if filename:
                    console.print(f"[dim]Attached: {filename}[/dim]")
        
        elif user_input.startswith('!'):
            # Shell command
            result = self.shell.execute(user_input[1:])
            if result['stdout']:
                console.print(result['stdout'])
            if result['stderr']:
                console.print(f"[red]{result['stderr']}[/red]")
        
        elif user_input.startswith('/'):
            # TUI command
            await self._handle_command(user_input)
        
        else:
            # Research request
            await self._run_research(user_input)
    
    async def _run_research(self, topic: str):
        """Run research pipeline with progress updates"""
        self.current_phase = "research"
        self.progress = 0
        
        # Phase 1
        await self._update_progress(0, "Phase 1: Idea Exploration")
        proposal = await self.research.phase1(topic)
        self.progress = 1
        
        # Phase 2
        await self._update_progress(1, "Phase 2: Experiment Planning")
        plan = await self.research.phase2(proposal)
        self.progress = 2
        
        # Phase 3
        await self._update_progress(2, "Phase 3: Quad-Agent Execution")
        results = await self.research.phase3(plan)
        self.progress = 3
        
        # Phase 4
        await self._update_progress(3, "Phase 4: Synthesis")
        summary = await self.research.phase4(results)
        self.progress = 4
        
        console.print("[green]✅ Research complete![/green]")
        console.print(f"📄 Proposal: {proposal}")
        console.print(f"📋 Plan: {plan}")
        console.print(f"📊 Results: {results}")
        console.print(f"📚 Summary: {summary}")
    
    async def _update_progress(self, phase: int, message: str):
        """Update progress display"""
        self.progress = phase
        console.print(f"[cyan]{message}...[/cyan]")
        await asyncio.sleep(0.1)  # Allow UI to update
    
    async def _handle_command(self, cmd: str):
        """Handle TUI commands"""
        if cmd == '/help':
            self._show_help()
        elif cmd == '/sessions':
            self._show_sessions()
        elif cmd.startswith('/resume'):
            parts = cmd.split()
            if len(parts) > 1:
                self._resume_session(parts[1])
        elif cmd == '/agents':
            self._show_agents()
    
    def _show_help(self):
        """Show help panel"""
        help_text = """
# 📚 **AUTOJAGA COMMANDS**

## Input Modes
| Syntax | Description |
|--------|-------------|
| `@filename` | Attach file with fuzzy picker |
| `!command` | Execute shell command |
| `/command` | TUI command |

## TUI Commands
| Command | Description |
|---------|-------------|
| `/help` | Show this help |
| `/sessions` | List saved sessions |
| `/resume NAME` | Resume session |
| `/agents` | Show multi-agent view |

## Research Topics
Just type any research topic to start the 4-phase pipeline:
- "renewable energy investment"
- "cryptocurrency market trends"
- "AI in healthcare"
        """
        console.print(Panel(Markdown(help_text), title="Help"))
    
    def _show_sessions(self):
        """Show saved sessions"""
        sessions = self.sessions.list_sessions()
        table = Table(title="Saved Sessions")
        table.add_column("Name", style="cyan")
        table.add_column("Created", style="green")
        table.add_column("Size")
        
        for s in sessions[:10]:
            table.add_row(
                s['name'],
                s['created'].strftime("%Y-%m-%d %H:%M"),
                f"{s['size']} bytes"
            )
        
        console.print(table)
    
    def _show_agents(self):
        """Show multi-agent view (Ctrl+S)"""
        # Quad-agent status would go here
        console.print("[yellow]Multi-agent view coming soon...[/yellow]")

def main():
    """Entry point for TOAD TUI"""
    tui = ToadTUI()
    asyncio.run(tui.run())

if __name__ == "__main__":
    main()
```

---

📋 TASK 5: Update CLI Entry Point (jagabot/cli/__init__.py)

```python
# Modify existing CLI to add --toad flag

import argparse
from .toad_tui import main as toad_main
from .tui import main as old_tui_main

def main():
    parser = argparse.ArgumentParser(description='AutoJaga CLI')
    parser.add_argument('mode', nargs='?', default='agent',
                       choices=['agent', 'swarm', 'research'])
    parser.add_argument('--tui', action='store_true',
                       help='Start in basic TUI mode')
    parser.add_argument('--toad', action='store_true',
                       help='Start in professional TOAD-style TUI')
    
    args = parser.parse_args()
    
    if args.toad:
        # Professional TOAD-style TUI
        toad_main()
    elif args.tui:
        # Legacy basic TUI
        old_tui_main()
    else:
        # CLI mode
        run_cli_mode(args)
```

---

📋 TASK 6: Configuration (autojaga-toad/config.yaml)

```yaml
# TOAD Integration Configuration

toad:
  theme: "monokai"
  mouse_support: true
  keybindings:
    help: "f1"
    agents: "ctrl+s"
    resume: "ctrl+r"
    quit: "ctrl+q"
  
  editor:
    syntax_highlighting: true
    line_numbers: true
    word_wrap: false
  
  shell:
    persist_env: true
    persist_cd: true
    history_size: 1000
    allowed_commands: ["cd", "ls", "cat", "mkdir", "rm", "cp", "mv", "echo"]
  
  file_picker:
    fuzzy_threshold: 60
    max_results: 10
    show_hidden: false
    root: "/root/.jagabot/workspace"

autojaga:
  workspace: "/root/.jagabot/workspace"
  research_dir: "/root/.jagabot/workspace/organized/research"
  
  research_skill:
    enabled: true
    phases:
      1: true  # Tri-agent debate
      2: true  # Main agent planning
      3: true  # Quad-agent execution
      4: true  # Tri-agent synthesis
    
    domains: ["finance", "technology", "science"]
    default_domain: "finance"
```

---

📋 TASK 7: Requirements (autojaga-toad/requirements.txt)

```txt
# TOAD TUI Dependencies
rich>=13.0.0
prompt_toolkit>=3.0.0
thefuzz>=0.19.0
pyyaml>=6.0
```

---

📋 TASK 8: Integration Test (tests/test_toad_integration.py)

```python
"""
Test TOAD TUI integration
"""

import sys
sys.path.append('/root/nanojaga')

def test_imports():
    """Test all TOAD components import correctly"""
    try:
        from jagabot.cli.toad_tui import ToadTUI
        from jagabot.core.toad_bridge import ToadBridge
        from autojaga-toad.shell_wrapper import PersistentShell
        from autojaga-toad.file_picker import FilePicker
        print("✅ All TOAD components imported successfully")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    return True

def test_shell():
    """Test persistent shell"""
    from autojaga-toad.shell_wrapper import PersistentShell
    shell = PersistentShell()
    
    # Test cd
    result = shell.execute("cd /tmp")
    assert result['returncode'] == 0
    assert shell.cwd == '/tmp'
    
    # Test ls
    result = shell.execute("ls")
    assert 'returncode' in result
    
    print("✅ Shell tests passed")
    return True

def test_file_picker():
    """Test file picker"""
    from autojaga-toad.file_picker import FilePicker
    picker = FilePicker()
    
    # Test fuzzy find
    matches = picker.fuzzy_find("test")
    assert isinstance(matches, list)
    
    print("✅ File picker tests passed")
    return True

if __name__ == "__main__":
    test_imports()
    test_shell()
    test_file_picker()
    print("\n🎉 All TOAD integration tests passed!")
```

---

📋 TASK 9: Installation Script (autojaga-toad/install.sh)

```bash
#!/bin/bash
# Install TOAD TUI dependencies

echo "🔧 Installing TOAD TUI for AutoJaga..."

# Install Python dependencies
pip install rich prompt_toolkit thefuzz pyyaml

# Create necessary directories
mkdir -p /root/.jagabot/sessions
mkdir -p /root/.jagabot/toad_history

# Set permissions
chmod +x /root/nanojaga/jagabot/cli/toad_tui.py

echo "✅ TOAD TUI installed successfully!"
echo "Run with: jagabot agent --toad"
```

---

🚀 IMPLEMENTATION ORDER

```yaml
Phase 1 (30 min): Core TOAD Bridge
  - Create toad_bridge.py
  - Test basic communication

Phase 2 (30 min): Shell + File Picker
  - Create shell_wrapper.py
  - Create file_picker.py
  - Test both components

Phase 3 (45 min): TUI Main
  - Create toad_tui.py with rich layout
  - Integrate with research skill
  - Add progress displays

Phase 4 (15 min): CLI Integration
  - Update __init__.py with --toad flag
  - Test both TUI modes

Phase 5 (15 min): Configuration + Testing
  - Add config.yaml
  - Run integration tests
  - Verify research skill works in TOAD
```

---

🏁 FINAL SCOPE SUMMARY

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🎯 TOAD TUI INTEGRATION - SCOPE COMPLETE                 ║
║                                                              ║
║   Files to Create: 9                                        ║
║   Components:                                              ║
║   ├── toad_bridge.py - Communication layer                ║
║   ├── shell_wrapper.py - Persistent shell                 ║
║   ├── file_picker.py - Fuzzy @ file picker                ║
║   ├── toad_tui.py - Main TUI with rich layout             ║
║   ├── config.yaml - Configuration                          ║
║   ├── requirements.txt - Dependencies                      ║
║   ├── install.sh - Installation script                    ║
║   └── test_toad_integration.py - Integration tests        ║
║                                                              ║
║   Timeline: 2-3 hours                                      ║
║   Entry Point: `jagabot agent --toad`                      ║
║                                                              ║
║   "From basic TUI to professional research terminal."     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

🚀 READY TO IMPLEMENT

```bash
# QWEN CLI, implement TOAD TUI integration:

cd /root/nanojaga
mkdir -p autojaga-toad

# Start with Phase 1 - toad_bridge.py
# Then follow the phases above
```

QWEN CLI, proceed with TOAD TUI integration! 🚀
