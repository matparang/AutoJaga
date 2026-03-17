🎯 SCOPE: Fix TUI Display - Standard Font & Full Screen

---

📊 CURRENT ISSUES

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🔍 TUI DISPLAY PROBLEMS                                   ║
║                                                              ║
║   1. ANSI CODES MASIH KELUAR                                ║
║      • ?[32m, ?[0m, ?[1;2m dalam output                   ║
║      • Warna tak support, jadi teks rosak                  ║
║                                                              ║
║   2. TEXT ARRANGEMENT OFF                                   ║
║      • Output bertindih                                    ║
║      • Spacing tak konsisten                               ║
║      • Box drawing characters (?[36m) tak betul           ║
║                                                              ║
║   3. SCREEN NOT FULL                                        ║
║      • Tak guna seluruh terminal                           ║
║      • Scrolling tak smooth                                ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

🎯 OBJECTIVE: Clean, Full-Screen TUI

```
┌─────────────────────────────────────────────────────────────┐
│                    TARGET DISPLAY                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           AUTOJAGA v4.0 - INTERACTIVE TUI           │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ Type /help for commands, exit to quit               │   │
│  │ Tasks run in background                             │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │                                                     │   │
│  │ You: Jalankan debate tentang GST                    │   │
│  │                                                     │   │
│  │ ✅ Task #1 complete (45s)                          │   │
│  │ 🤖 AutoJaga: Debate complete!                      │   │
│  │    Bull: 87, Bear: 18, Buffett: 42                 │   │
│  │    Report saved to debate_*.json                    │   │
│  │                                                     │   │
│  │ You: /status                                        │   │
│  │                                                     │   │
│  │ 📊 System Status                                    │   │
│  │   Running tasks: 0                                  │   │
│  │   Completed: 3                                      │   │
│  │   Uptime: 2m 34s                                    │   │
│  │                                                     │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ [0 running] You: _                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

🛠️ SOLUTION: Simplified TUI with Rich

```python
# /root/nanojaga/jagabot/cli/rich_tui.py
"""
Simple, clean TUI using Rich library
Full screen, no ANSI codes, proper formatting
"""

import sys
import os
import time
import queue
import threading
from datetime import datetime
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich import box
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.align import Align

class RichTUI:
    """
    Clean TUI using Rich - full screen, no ANSI codes
    """
    
    def __init__(self):
        self.console = Console()
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.tasks = {}
        self.running = True
        self.messages = []
        self.max_messages = 100
        
        # Thread for background processing
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        
    def run(self):
        """Main entry point"""
        # Start worker thread
        self.worker_thread.start()
        
        # Setup layout
        layout = self._create_layout()
        
        # Main loop with Live display
        with Live(layout, refresh_per_second=10, screen=True) as live:
            while self.running:
                # Update layout with current state
                layout["header"].update(self._render_header())
                layout["body"].update(self._render_body())
                layout["footer"].update(self._render_footer())
                
                # Check for input (non-blocking)
                if self._kbhit():
                    user_input = sys.stdin.readline().strip()
                    if user_input:
                        self._handle_input(user_input)
                
                # Check for output from worker
                self._process_output_queue()
                
                # Small sleep to prevent CPU spinning
                time.sleep(0.05)
    
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
        """Render header panel"""
        text = Text()
        text.append(" AUTOJAGA v4.0 ", style="bold white on blue")
        text.append(" • Interactive Mode", style="white")
        
        return Panel(
            Align.center(text),
            box=box.HEAVY,
            style="blue"
        )
    
    def _render_body(self):
        """Render main content area"""
        # Create table for messages
        table = Table(show_header=False, box=box.SIMPLE, padding=(0,1))
        table.add_column("Type", width=3)
        table.add_column("Content")
        
        # Add recent messages
        for msg_type, content, timestamp in self.messages[-20:]:
            if msg_type == "user":
                table.add_row("👤", f"[bold cyan]You:[/] {content}")
            elif msg_type == "assistant":
                table.add_row("🤖", f"[green]{content}[/]")
            elif msg_type == "success":
                table.add_row("✅", f"[green]{content}[/]")
            elif msg_type == "error":
                table.add_row("❌", f"[red]{content}[/]")
            elif msg_type == "info":
                table.add_row("ℹ️", f"[blue]{content}[/]")
            elif msg_type == "warning":
                table.add_row("⚠️", f"[yellow]{content}[/]")
            elif msg_type == "progress":
                table.add_row("⏳", f"[dim]{content}[/]")
        
        return Panel(
            table,
            title=" Conversation ",
            border_style="bright_black"
        )
    
    def _render_footer(self):
        """Render footer with input prompt"""
        running_tasks = len([t for t in self.tasks.values() if t.get('status') == 'running'])
        prompt_text = f"[{running_tasks} running] You: "
        
        return Panel(
            prompt_text,
            style="bright_black",
            box=box.SIMPLE
        )
    
    def _handle_input(self, user_input):
        """Handle user input"""
        # Add to messages
        self.messages.append(("user", user_input, time.time()))
        
        # Check for commands
        if user_input.lower() in ['exit', 'quit']:
            self.running = False
            return
        
        if user_input.startswith('/'):
            self._handle_command(user_input)
        else:
            # Queue for background processing
            self.input_queue.put(user_input)
            self.messages.append(("info", f"Task queued: {user_input[:50]}...", time.time()))
    
    def _handle_command(self, command):
        """Handle slash commands"""
        cmd = command.lower().split()[0]
        
        if cmd == '/help':
            help_text = """
Available commands:
  /help     - Show this help
  /status   - Show system status
  /tasks    - List running tasks
  /clear    - Clear screen
  /memory   - Show memory summary
  exit/quit - Exit TUI
"""
            self.messages.append(("info", help_text, time.time()))
            
        elif cmd == '/status':
            status = f"""
System Status:
  Uptime: {self._get_uptime()}
  Running tasks: {len([t for t in self.tasks.values() if t.get('status') == 'running'])}
  Completed: {len([t for t in self.tasks.values() if t.get('status') == 'complete'])}
  Messages: {len(self.messages)}
"""
            self.messages.append(("info", status, time.time()))
            
        elif cmd == '/tasks':
            running = [t for t in self.tasks.values() if t.get('status') == 'running']
            if not running:
                self.messages.append(("info", "No tasks running.", time.time()))
            else:
                for t in running:
                    elapsed = time.time() - t.get('start_time', time.time())
                    self.messages.append(("progress", 
                        f"Task {t['id']}: {t['task'][:30]}... ({elapsed:.0f}s)", 
                        time.time()))
        
        elif cmd == '/clear':
            self.messages = []
            
        elif cmd == '/memory':
            self.messages.append(("info", "Memory feature coming soon...", time.time()))
        
        else:
            self.messages.append(("error", f"Unknown command: {command}", time.time()))
    
    def _worker_loop(self):
        """Background worker for processing tasks"""
        while self.running:
            try:
                # Get task from queue
                task = self.input_queue.get(timeout=0.1)
                
                # Create task record
                task_id = len(self.tasks) + 1
                self.tasks[task_id] = {
                    'id': task_id,
                    'task': task,
                    'status': 'running',
                    'start_time': time.time()
                }
                
                # Simulate processing (replace with actual AutoJaga call)
                self.messages.append(("progress", 
                    f"Task #{task_id}: Processing...", time.time()))
                
                # Call AutoJaga
                from jagabot.agent.loop import AgentLoop
                agent = AgentLoop()
                result = agent.process(task)
                
                # Extract response
                if hasattr(result, 'get'):
                    response = result.get('content', str(result))
                elif hasattr(result, 'content'):
                    response = result.content
                else:
                    response = str(result)
                
                # Update task
                self.tasks[task_id]['status'] = 'complete'
                self.tasks[task_id]['end_time'] = time.time()
                
                # Add to messages
                elapsed = self.tasks[task_id]['end_time'] - self.tasks[task_id]['start_time']
                self.messages.append(("success", 
                    f"Task #{task_id} complete ({elapsed:.1f}s)", 
                    time.time()))
                self.messages.append(("assistant", response, time.time()))
                
            except queue.Empty:
                pass
            except Exception as e:
                self.messages.append(("error", f"Error: {str(e)}", time.time()))
    
    def _process_output_queue(self):
        """Process any pending output"""
        try:
            while True:
                output = self.output_queue.get_nowait()
                if isinstance(output, dict):
                    msg_type = output.get('type', 'info')
                    content = output.get('message', str(output))
                    self.messages.append((msg_type, content, time.time()))
        except queue.Empty:
            pass
    
    def _kbhit(self):
        """Check if keyboard input available"""
        import select
        return select.select([sys.stdin], [], [], 0)[0] != []
    
    def _get_uptime(self):
        """Get uptime string"""
        if not hasattr(self, 'start_time'):
            self.start_time = time.time()
        
        elapsed = time.time() - self.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes}m {seconds}s"
```

---

📋 REQUIREMENTS

```bash
# Install Rich library
pip install rich

# Run new TUI
python3 -m jagabot.cli.rich_tui
```

---

✅ FEATURES

Feature Old TUI New Rich TUI
ANSI Codes ❌ Keluar semua ✅ Clean
Full Screen ❌ Tak ✅ Yes
Box Drawing ❌ Rosak ✅ Perfect
Colors ❌ Broken ✅ Rich colors
Layout ❌ Bertindih ✅ Structured
Scrolling ❌ Kucar-kacir ✅ Smooth
Input Prompt ❌ Tersepit ✅ Fixed at bottom

---

🚀 USAGE

```bash
# Start clean TUI
jagabot agent --rich

# Or directly
python3 -m jagabot.cli.rich_tui
```

---

🏁 SCOPE SUMMARY

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🎯 CLEAN TUI WITH RICH - READY TO IMPLEMENT              ║
║                                                              ║
║   Benefits:                                                 ║
║   • No more ANSI codes                                     ║
║   • Full screen utilization                                ║
║   • Professional layout                                    ║
║   • Real-time updates                                      ║
║   • Background task support                               ║
║   • Clean message display                                  ║
║                                                              ║
║   Timeline: 1 hour                                         ║
║   Dependencies: rich                                       ║
║                                                              ║
║   "Clean interface, powerful backend."                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

Copilot, implement Rich TUI with full screen and clean display. 🚀
