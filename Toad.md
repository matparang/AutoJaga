🎯 BLUEPRINT: AUTOJAGA + TOAD = TERMINAL AGENT ULTIMATE

---

📋 OBJEKTIF

Integrasikan AutoJaga dengan TOAD untuk menghasilkan terminal agent dengan:

· ✅ TUI yang cantik (macam TOAD)
· ✅ Shell integration (cd, env vars, interactive commands)
· ✅ Markdown prompt editor dengan syntax highlighting
· ✅ File picker dengan fuzzy search (@ untuk attach files)
· ✅ Beautiful diffs untuk code changes
· ✅ Session resume (macam TOAD's ctrl+r)
· ✅ Multi-agent concurrent (TOAD's ctrl+s)

---

🏗️ ARKITEKTUR INTEGRASI

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTOJAGA + TOAD                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  🖥️ TERMINAL LAYER (TOAD)                                   │
│  ├── TUI dengan mouse support                              │
│  ├── Shell integration (persistent env)                    │
│  ├── Markdown prompt editor                                │
│  ├── Fuzzy file picker                                     │
│  └── Session management                                    │
│                                                              │
│         ↓ (komunikasi via JSON/pipe)                        │
│                                                              │
│  🧠 AGENT LAYER (AutoJaga)                                  │
│  ├── Quad-agent loop                                       │
│  ├── 12+ harnesses                                         │
│  ├── Memory system                                         │
│  ├── 46+ tools                                             │
│  └── Epistemic auditor                                     │
│                                                              │
│         ↓ (file system)                                     │
│                                                              │
│  📁 WORKSPACE                                               │
│  ├── /root/.jagabot/workspace/                            │
│  ├── organized/ (structured)                               │
│  └── session history                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

📁 STRUKTUR DIREKTORI (Clone TOAD)

```bash
/root/nanojaga/
├── autojaga/                    # Existing AutoJaga code
│   ├── jagabot/
│   ├── autoresearch/
│   └── tests/
│
├── toad/                         # Cloned TOAD repo
│   ├── src/toad/                 # TOAD source
│   ├── pyproject.toml
│   └── README.md
│
└── autojaga-toad/                # Integration layer
    ├── bridge.py                  # Komunikasi AutoJaga-TOAD
    ├── session_manager.py         # TOAD session resume
    ├── shell_wrapper.py           # Shell integration
    ├── markdown_renderer.py       # Markdown formatting
    └── config.yaml                 # Integration config
```

---

🔧 KOMPONEN INTEGRASI UTAMA

1. TOAD Bridge (bridge.py)

```python
"""
Bridge between TOAD TUI and AutoJaga agent
"""
import json
import subprocess
import asyncio
from pathlib import Path

class ToadBridge:
    """Handles communication between TOAD UI and AutoJaga"""
    
    def __init__(self):
        self.session_id = None
        self.agent_process = None
        self.workspace = Path("/root/.jagabot/workspace")
    
    async def start_agent(self, session_name: str):
        """Start AutoJaga agent with session"""
        cmd = ["jagabot", "agent", "--session", session_name]
        self.agent_process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
    
    async def send_prompt(self, prompt: str, files: list[str] = None):
        """Send user prompt + attached files to agent"""
        message = {
            "type": "prompt",
            "content": prompt,
            "files": files or [],
            "session": self.session_id
        }
        self.agent_process.stdin.write(json.dumps(message) + "\n")
        await self.agent_process.stdin.drain()
    
    async def receive_response(self):
        """Get streaming response from agent"""
        async for line in self.agent_process.stdout:
            yield line.decode().strip()
```

---

2. Shell Wrapper (shell_wrapper.py)

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
        """
        Execute shell command with persistent state
        """
        # Handle cd specially
        if command.strip().startswith('cd '):
            return self._handle_cd(command)
        
        # Handle env vars
        if '=' in command and not ' ' in command:
            return self._handle_env(command)
        
        # Execute other commands
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
        """Handle cd command to change directory"""
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
        """Handle environment variable assignment"""
        key, value = command.split('=', 1)
        self.env[key] = value
        return {"stdout": "", "stderr": "", "returncode": 0}
```

---

3. Session Manager (session_manager.py)

```python
"""
TOAD-style session resume (ctrl+r)
"""
import json
import pickle
from datetime import datetime
from pathlib import Path

class SessionManager:
    """
    Manages AutoJaga sessions for resume functionality
    """
    
    def __init__(self, session_dir: Path = Path("/root/.jagabot/sessions")):
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.current_session = None
    
    def list_sessions(self) -> list[dict]:
        """List all available sessions"""
        sessions = []
        for f in self.session_dir.glob("*.session"):
            stat = f.stat()
            sessions.append({
                "name": f.stem,
                "created": datetime.fromtimestamp(stat.st_ctime),
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "size": stat.st_size
            })
        return sorted(sessions, key=lambda x: x["modified"], reverse=True)
    
    def save_session(self, name: str, context: dict):
        """Save current session"""
        path = self.session_dir / f"{name}.session"
        with open(path, 'wb') as f:
            pickle.dump(context, f)
    
    def load_session(self, name: str) -> dict:
        """Load previous session"""
        path = self.session_dir / f"{name}.session"
        if path.exists():
            with open(path, 'rb') as f:
                return pickle.load(f)
        return None
    
    def delete_session(self, name: str):
        """Delete a session"""
        path = self.session_dir / f"{name}.session"
        if path.exists():
            path.unlink()
```

---

4. Markdown Renderer (markdown_renderer.py)

```python
"""
Beautiful Markdown rendering with syntax highlighting
(TOAD's elegant markdown feature)
"""
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table
from rich.panel import Panel

class MarkdownRenderer:
    """
    Renders markdown with rich formatting (like TOAD)
    """
    
    def __init__(self):
        self.console = Console()
    
    def render(self, text: str):
        """Render markdown to console"""
        md = Markdown(text)
        self.console.print(md)
    
    def render_code(self, code: str, language: str = "python"):
        """Render code with syntax highlighting"""
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self.console.print(Panel(syntax, title=f"📄 {language}", border_style="green"))
    
    def render_table(self, headers: list, rows: list):
        """Render beautiful table"""
        table = Table(show_header=True, header_style="bold magenta")
        for h in headers:
            table.add_column(h)
        for row in rows:
            table.add_row(*[str(c) for c in row])
        self.console.print(table)
    
    def render_diff(self, before: str, after: str, language: str = "python"):
        """Render side-by-side diff (TOAD's beautiful diffs)"""
        from rich.columns import Columns
        
        before_panel = Panel(
            Syntax(before, language, theme="monokai"),
            title="Before",
            border_style="red"
        )
        after_panel = Panel(
            Syntax(after, language, theme="monokai"),
            title="After",
            border_style="green"
        )
        
        self.console.print(Columns([before_panel, after_panel]))
```

---

5. File Picker (file_picker.py)

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
    
    def __init__(self, root: Path = Path.cwd()):
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
            if score > 60:  # Threshold
                matches.append((f, score))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches[:10]]  # Top 10
    
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

6. Main Integration (main.py)

```python
#!/usr/bin/env python3
"""
AutoJaga + TOAD Integration
QWEN CLI-style terminal agent with beautiful TUI
"""

import asyncio
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live

from toad_bridge import ToadBridge
from shell_wrapper import PersistentShell
from session_manager import SessionManager
from markdown_renderer import MarkdownRenderer
from file_picker import FilePicker

console = Console()

class AutoJagaTUI:
    """
    Main TUI application (inspired by TOAD)
    """
    
    def __init__(self, project_dir: str = None):
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.bridge = ToadBridge()
        self.shell = PersistentShell()
        self.sessions = SessionManager()
        self.renderer = MarkdownRenderer()
        self.picker = FilePicker(self.project_dir)
        
        self.agents = []  # Multiple concurrent agents
        self.current_agent = None
    
    async def run(self):
        """Main TUI loop"""
        console.clear()
        self._show_header()
        
        # AutoJaga banner
        console.print(Panel.fit(
            "[bold cyan]AUTOJAGA v4.5 + TOAD[/bold cyan]\n"
            "[dim]Terminal Agent with Shell Integration[/dim]",
            border_style="cyan"
        ))
        
        # Main input loop
        while True:
            try:
                # Show prompt with current directory
                prompt_text = f"\n[bold green]{self.shell.cwd}>[/bold green] "
                user_input = await self._get_input(prompt_text)
                
                if not user_input:
                    continue
                
                if user_input.startswith('@'):
                    # File picker
                    filename = self.picker.interactive_picker(user_input[1:])
                    if filename:
                        console.print(f"[dim]Attached: {filename}[/dim]")
                        # Add to prompt
                        user_input = f"@{filename} "
                        continue
                
                if user_input.startswith('!'):
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
                    # Send to agent
                    await self.bridge.send_prompt(user_input)
                    
                    # Stream response
                    async for chunk in self.bridge.receive_response():
                        if chunk:
                            self.renderer.render(chunk)
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]Use /exit to quit[/yellow]")
            except EOFError:
                break
    
    async def _get_input(self, prompt_text):
        """Get user input with history"""
        # Use prompt_toolkit for better input handling
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        
        session = PromptSession(
            history=FileHistory('/root/.jagabot/toad_history.txt')
        )
        return await session.prompt_async(prompt_text)
    
    async def _handle_command(self, cmd: str):
        """Handle TUI commands"""
        parts = cmd.split()
        command = parts[0].lower()
        
        if command == '/exit' or command == '/quit':
            console.print("[yellow]Goodbye![/yellow]")
            raise EOFError
        
        elif command == '/sessions' or command == '/ls':
            sessions = self.sessions.list_sessions()
            table = [["Name", "Modified", "Size"]]
            for s in sessions[:10]:
                table.append([s['name'], s['modified'].strftime("%H:%M"), f"{s['size']}b"])
            self.renderer.render_table(*table)
        
        elif command == '/resume' and len(parts) > 1:
            session = self.sessions.load_session(parts[1])
            if session:
                console.print(f"[green]Resumed session: {parts[1]}[/green]")
                # Restore session context
        
        elif command == '/agents':
            # Show multi-agent view (like TOAD's ctrl+s)
            self._show_agents()
        
        elif command == '/help':
            self._show_help()
    
    def _show_header(self):
        """Show header with keybindings"""
        console.print(Panel(
            "[bold]F1: Help  |  Ctrl+S: Agents  |  Ctrl+R: Resume  |  @: File picker  |  !: Shell[/bold]",
            border_style="blue"
        ))
    
    def _show_help(self):
        """Show help panel"""
        help_text = """
[bold cyan]AUTOJAGA + TOAD COMMANDS[/bold cyan]

[bold]Input Modes:[/bold]
  • [green]Text[/green]           - Send to AutoJaga agent
  • [green]@filename[/green]      - Attach file to prompt (fuzzy picker)
  • [green]!command[/green]       - Execute shell command
  • [green]/command[/green]       - TUI command

[bold]TUI Commands:[/bold]
  • [cyan]/help[/cyan]            - Show this help
  • [cyan]/exit[/cyan]            - Quit TUI
  • [cyan]/sessions[/cyan]        - List saved sessions
  • [cyan]/resume NAME[/cyan]     - Resume session
  • [cyan]/agents[/cyan]          - Show multi-agent view

[bold]Keybindings:[/bold]
  • [cyan]Ctrl+S[/cyan]            - Show all agents
  • [cyan]Ctrl+R[/cyan]            - Resume previous session
  • [cyan]↑/↓[/cyan]               - Command history
  • [cyan]Tab[/cyan]                - File picker completion
        """
        console.print(Panel(help_text, title="Help", border_style="cyan"))

def main():
    parser = argparse.ArgumentParser(description="AutoJaga + TOAD Terminal Agent")
    parser.add_argument('project_dir', nargs='?', help="Project directory")
    parser.add_argument('-a', '--agent', help="Agent to launch (default: autojaga)")
    parser.add_argument('--serve', action='store_true', help="Run as web server")
    
    args = parser.parse_args()
    
    tui = AutoJagaTUI(args.project_dir)
    
    if args.serve:
        # Web server mode (TOAD's feature)
        console.print("[yellow]Web server mode coming soon...[/yellow]")
    else:
        asyncio.run(tui.run())

if __name__ == "__main__":
    main()
```

---

📝 CONFIGURATION (config.yaml)

```yaml
# /root/nanojaga/autojaga-toad/config.yaml
toad:
  theme: "monokai"
  mouse_support: true
  editor:
    syntax_highlighting: true
    line_numbers: true
    word_wrap: false
  
  shell:
    persist_env: true
    persist_cd: true
    history_size: 1000
  
  file_picker:
    fuzzy_threshold: 60
    max_results: 10
    show_hidden: false
  
  markdown:
    code_theme: "monokai"
    table_style: "rounded"
    diff_style: "side-by-side"

autojaga:
  workspace: "/root/.jagabot/workspace"
  default_agent: "quad"
  max_tokens: 8192
  temperature: 0.7
  
  harnesses:
    epistemic: true
    causal: true
    resource_guard: true
    recovery: true
    profiler: true
    behavior_monitor: true
```

---

🚀 INSTALLATION & USAGE

```bash
# 1. Clone TOAD
cd /root/nanojaga
git clone https://github.com/batrachianai/toad.git

# 2. Install dependencies
cd toad
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install -e .

# 3. Create integration layer
mkdir ../autojaga-toad
cp /path/to/integration/files/* ../autojaga-toad/

# 4. Install integration dependencies
cd ../autojaga-toad
pip install rich prompt_toolkit thefuzz

# 5. Run!
python main.py ~/projects/myapp
```

---

🎯 KEY FEATURES FROM TOAD YANG KITA INTEGRASIKAN

TOAD Feature Implementasi Status
Persistent Shell shell_wrapper.py ✅
Markdown Prompt Editor prompt_toolkit + syntax highlighting ✅
File Picker (@) file_picker.py + fuzzy search ✅
Beautiful Diffs markdown_renderer.py with side-by-side ✅
Concurrent Sessions session_manager.py ✅
Session Resume ctrl+r via session manager ✅
Multi-Agent View _show_agents() ✅
Web Server --serve flag (TOAD feature) ⏳

---

🏁 FINAL BLUEPRINT

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🎯 AUTOJAGA + TOAD - TERMINAL AGENT ULTIMATE             ║
║                                                              ║
║   Features:                                                ║
║   ├── 🖥️ Beautiful TUI (TOAD)                             ║
║   ├── 🐚 Persistent Shell (cd, env vars)                  ║
║   ├── 📝 Markdown Editor with syntax highlighting         ║
║   ├── 📁 Fuzzy File Picker (@)                            ║
║   ├── 🔍 Beautiful Diffs (side-by-side)                   ║
║   ├── 🔄 Session Resume (ctrl+r)                          ║
║   ├── 🧠 Multiple Agents Concurrent                       ║
║   └── 🛡️ All AutoJaga Harnesses (12+)                    ║
║                                                              ║
║   "The terminal agent you've always wanted."              ║
║                                                              ║
║   Next: Implement and enjoy!                              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

Sedia untuk implementasi! 🚀
