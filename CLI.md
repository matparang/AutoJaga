🎯 SCOPE: True Interactive TUI for AutoJaga (Like Gemini CLI / Agent Zero)

---

📋 CURRENT vs DESIRED

```
┌─────────────────────────────────────────────────────────────┐
│                    CURRENT (Turn-based)                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  You: Buat file test.txt                                    │
│  AutoJaga: ✅ File created                                  │
│  (AutoJaga STOPS - menunggu input next)                    │
│                                                              │
│  You: Sekarang buat lagi                                    │
│  AutoJaga: ✅ File lagi.txt created                         │
│  (AutoJaga STOPS lagi)                                      │
│                                                              │
│  ❌ Agent hanya respond bila dipanggil                      │
│  ❌ Tak boleh interrupt atau async                          │
│  ❌ Macam chat biasa                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    DESIRED (True Interactive)               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  You: Jalankan debate tentang GST                           │
│  AutoJaga: ⏳ Debate started... (RUNNING in background)    │
│           [Progress: Round 1 complete - Bull 85]           │
│           [Progress: Round 2 complete - Bear 22]           │
│           [Progress: Round 3 complete - Buffett 42]        │
│                                                              │
│  You: (while debate still running)                         │
│       /status                                               │
│  AutoJaga: 📊 Debate at round 3, 45s remaining             │
│                                                              │
│  You: /memory                                               │
│  AutoJaga: 📚 Showing memory (while debate still runs)     │
│                                                              │
│  AutoJaga: ✅ Debate complete! Report saved...             │
│           (agent PUSHES update without being asked)        │
│                                                              │
│  ✅ Agent ACTIVE sepanjang masa                             │
│  ✅ Boleh interrupt, check status, multi-task              │
│  ✅ Agent PUSH updates                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

🎯 KEY REQUIREMENTS FOR TRUE INTERACTIVE TUI

# Requirement Description Example
1 Async Processing Tasks run in background, don't block UI Debate runs while user types
2 Push Notifications Agent updates without being asked "Debate complete!" appears automatically
3 Interruptible Can check status anytime /status while task runs
4 Multi-threaded UI thread + worker thread(s) One thread for input, one for tasks
5 Real-time Updates Progress bars, timers Show debate progress in real-time
6 Command Queue Multiple commands can be queued User can type next command while previous runs
7 Split View Input area + output area + status bar Like Gemini CLI or htop

---

🛠️ TECHNICAL APPROACH: AsyncIO + Threads

```python
# /root/nanojaga/jagabot/cli/interactive_tui.py
"""
True Interactive TUI for AutoJaga - Like Gemini CLI / Agent Zero
"""

import asyncio
import threading
import queue
import time
from datetime import datetime
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import ProgressBar
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
import sys
sys.path.append('/root/nanojaga')

class InteractiveTUI:
    """
    True interactive TUI with background processing and push notifications
    """
    
    def __init__(self):
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.running = True
        self.tasks = {}
        self.task_id_counter = 0
        
        # Setup prompt session
        self.session = PromptSession(
            history=FileHistory('/root/.jagabot/tui_history.txt'),
            style=Style.from_dict({
                'prompt': '#ansicyan bold',
                'status': '#ansigreen',
                'error': '#ansired',
                'info': '#ansiyellow',
            })
        )
        
        # UI layout
        self.output_lines = []
        self.max_output_lines = 100
        self.status_line = ""
        
    def run(self):
        """Main entry point - starts all threads"""
        # Start worker thread for background tasks
        worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        worker_thread.start()
        
        # Start UI thread
        self._ui_loop()
    
    def _worker_loop(self):
        """Background worker that processes tasks"""
        while self.running:
            try:
                # Check for new tasks
                task = self.input_queue.get(timeout=0.1)
                self._execute_task(task)
            except queue.Empty:
                pass
            
            # Check running tasks for updates
            self._check_task_progress()
            
            # Push any status updates to UI
            self._push_updates()
    
    def _ui_loop(self):
        """Main UI thread - handles input and displays output"""
        with patch_stdout():
            self._clear_screen()
            self._show_banner()
            
            while self.running:
                try:
                    # Show status line
                    self._update_status_bar()
                    
                    # Get user input (non-blocking with timeout)
                    user_input = self._get_input_nonblocking()
                    
                    if user_input:
                        self._handle_input(user_input)
                    
                    # Check for output from worker
                    self._process_output_queue()
                    
                    # Small sleep to prevent CPU spinning
                    time.sleep(0.05)
                    
                except KeyboardInterrupt:
                    self._handle_interrupt()
    
    def _get_input_nonblocking(self):
        """Get input without blocking (returns None if no input)"""
        # This is a simplified version - in reality we'd use
        # prompt_toolkit's async capabilities
        import select
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.readline().strip()
        return None
    
    def _execute_task(self, task):
        """Execute a task in background"""
        task_id = self.task_id_counter
        self.task_id_counter += 1
        
        self.tasks[task_id] = {
            'task': task,
            'status': 'running',
            'start_time': time.time(),
            'progress': 0,
            'updates': []
        }
        
        # Simulate long-running task (replace with actual AutoJaga call)
        def run():
            try:
                # For debate, this would call the actual debate system
                if 'debate' in task.lower():
                    self._run_debate(task_id, task)
                elif 'file' in task.lower():
                    self._create_file(task_id, task)
                else:
                    self._generic_task(task_id, task)
            except Exception as e:
                self.tasks[task_id]['status'] = 'error'
                self.tasks[task_id]['error'] = str(e)
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
    
    def _run_debate(self, task_id, task):
        """Simulate debate with progress updates"""
        stages = [
            "Round 1: Bull argument",
            "Round 1: Bear argument",
            "Round 1: Buffett argument",
            "Round 2: Bull counter",
            "Round 2: Bear counter",
            "Round 2: Buffett analysis",
            "Round 3: Final arguments",
            "Consensus check"
        ]
        
        for i, stage in enumerate(stages):
            time.sleep(5)  # Simulate processing
            progress = (i + 1) / len(stages) * 100
            
            self.tasks[task_id]['progress'] = progress
            self.tasks[task_id]['updates'].append({
                'time': time.time(),
                'message': stage
            })
            
            # Push update to UI
            self.output_queue.put({
                'type': 'progress',
                'task_id': task_id,
                'stage': stage,
                'progress': progress
            })
        
        # Debate complete
        self.tasks[task_id]['status'] = 'complete'
        self.tasks[task_id]['result'] = {
            'bull': 87,
            'bear': 18,
            'buffett': 42,
            'file': f'/root/.jagabot/workspace/debate_{int(time.time())}.json'
        }
        
        self.output_queue.put({
            'type': 'complete',
            'task_id': task_id,
            'result': self.tasks[task_id]['result']
        })
    
    def _handle_input(self, user_input):
        """Handle user input"""
        if user_input.lower() in ['exit', 'quit']:
            self.running = False
            self._show_goodbye()
            return
        
        if user_input.startswith('/'):
            self._handle_command(user_input)
        else:
            # Queue task for background processing
            self.input_queue.put(user_input)
            self.output_queue.put({
                'type': 'info',
                'message': f'Task queued: {user_input[:50]}...'
            })
    
    def _handle_command(self, command):
        """Handle slash commands"""
        cmd = command.lower().split()[0]
        
        if cmd == '/status':
            self._show_status()
        elif cmd == '/memory':
            self._show_memory()
        elif cmd == '/tasks':
            self._show_tasks()
        elif cmd == '/help':
            self._show_help()
        elif cmd == '/clear':
            self.output_lines = []
            self._clear_screen()
        else:
            self.output_queue.put({
                'type': 'error',
                'message': f'Unknown command: {command}'
            })
    
    def _push_updates(self):
        """Worker pushes updates to UI"""
        # This would be called from worker thread
        pass
    
    def _process_output_queue(self):
        """Process any pending output"""
        try:
            while True:
                output = self.output_queue.get_nowait()
                self._display_output(output)
        except queue.Empty:
            pass
    
    def _display_output(self, output):
        """Display output in UI"""
        output_type = output.get('type', 'info')
        
        if output_type == 'progress':
            msg = (f"[{output['progress']:.0f}%] "
                   f"Task {output['task_id']}: {output['stage']}")
        elif output_type == 'complete':
            msg = (f"\n✅ Task {output['task_id']} complete!\n"
                   f"Result: {output['result']}")
        elif output_type == 'error':
            msg = f"❌ {output['message']}"
        elif output_type == 'info':
            msg = f"ℹ️ {output['message']}"
        else:
            msg = str(output)
        
        self.output_lines.append(msg)
        if len(self.output_lines) > self.max_output_lines:
            self.output_lines.pop(0)
        
        self._refresh_display()
    
    def _refresh_display(self):
        """Refresh the entire display"""
        self._clear_screen()
        self._show_banner()
        
        # Show output area
        for line in self.output_lines[-20:]:  # Show last 20 lines
            print(line)
        
        # Show status bar
        print("\n" + "─" * 80)
        print(f"⏳ Active tasks: {len([t for t in self.tasks.values() if t['status'] == 'running'])}")
        print("You: ", end='', flush=True)
    
    def _show_banner(self):
        """Show welcome banner"""
        print("╔" + "═"*78 + "╗")
        print("║" + " " * 78 + "║")
        print("║" + " " * 28 + "🤖 AUTOJAGA v4.0 - INTERACTIVE TUI" + " " * 27 + "║")
        print("║" + " " * 78 + "║")
        print("╠" + "═"*78 + "╣")
        print("║ Type /help for commands | Tasks run in background | Push notifications active ║")
        print("╚" + "═"*78 + "╝")
        print()
    
    def _show_help(self):
        """Show help"""
        help_text = """
📋 COMMANDS:
  /help           - Show this help
  /status         - Show system status
  /tasks          - List running tasks
  /memory         - Show memory summary
  /clear          - Clear screen
  exit/quit       - Exit TUI

💡 FEATURES:
  • Tasks run in background - you can keep typing!
  • Push notifications when tasks complete
  • Check status anytime with /status
  • Multiple tasks can run simultaneously
  
  Just type anything - it will be queued for processing!
"""
        self.output_lines.append(help_text)
        self._refresh_display()
    
    def _show_status(self):
        """Show system status"""
        status = f"""
📊 SYSTEM STATUS
  Running tasks: {len([t for t in self.tasks.values() if t['status'] == 'running'])}
  Completed tasks: {len([t for t in self.tasks.values() if t['status'] == 'complete'])}
  Failed tasks: {len([t for t in self.tasks.values() if t['status'] == 'error'])}
  Uptime: {time.time() - self.start_time:.0f}s
"""
        self.output_lines.append(status)
        self._refresh_display()
    
    def _show_tasks(self):
        """Show running tasks"""
        running = [t for t in self.tasks.values() if t['status'] == 'running']
        if not running:
            self.output_lines.append("No tasks currently running.")
        else:
            lines = ["\n🔄 RUNNING TASKS:"]
            for t in running:
                elapsed = time.time() - t['start_time']
                lines.append(f"  • {t['task'][:50]}... ({elapsed:.0f}s, {t['progress']:.0f}%)")
            self.output_lines.extend(lines)
        self._refresh_display()
    
    def _clear_screen(self):
        """Clear terminal"""
        import os
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def _show_goodbye(self):
        """Show goodbye message"""
        self._clear_screen()
        print("\n" + "="*60)
        print("👋 Thank you for using AutoJaga v4.0!")
        print("="*60 + "\n")
```

---

📋 IMPLEMENTATION PLAN

```yaml
Phase 1: Async Foundation (30 min)
  - Setup queue system for input/output
  - Create worker thread pool
  - Basic non-blocking input

Phase 2: Background Processing (45 min)
  - Integrate actual AutoJaga tools
  - Progress reporting from tasks
  - Multiple task support

Phase 3: Push Notifications (30 min)
  - Auto-update UI when tasks complete
  - Status bar with active tasks
  - Real-time progress bars

Phase 4: Command System (15 min)
  - /status, /tasks, /memory
  - Task management commands
  - Help system

Phase 5: Polish (30 min)
  - Error handling
  - Screen refresh optimization
  - History and logging
```

---

✅ SUCCESS CRITERIA

Test Expected Behavior
Start debate "Debate started..." + progress updates
Type while debate runs Input accepted, commands work
/status mid-debate Shows debate progress
Multiple tasks All run simultaneously
Push notification "Task complete!" appears automatically
Interrupt Ctrl+C handled gracefully

---

🚀 USAGE EXAMPLE

```bash
jagabot agent --interactive

# Start long task
You: Jalankan debate tentang GST
🤖: ⏳ Debate started (task #1)
🤖: [25%] Round 1 complete - Bull 85
🤖: [50%] Round 2 complete - Bear 22

# While debate runs, do something else
You: /status
🤖: 📊 Task #1: debate (45s remaining)

You: Buat file laporan.txt
🤖: ⏳ File creation queued (task #2)
🤖: ✅ File created (0.3s)

You: /tasks
🤖: 🔄 Task #1: debate (67% complete)
🤖: ✅ Task #2: file creation (done)

🤖: [PUSH] ✅ Debate complete! Results saved...
```

---

🏁 SCOPE SUMMARY

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🎯 TRUE INTERACTIVE TUI - SCOPE READY                     ║
║                                                              ║
║   Features:                                                 ║
║   ├── Background task processing                           ║
║   ├── Push notifications                                   ║
║   ├── Real-time progress updates                           ║
║   ├── Multiple concurrent tasks                            ║
║   ├── Interruptible commands                               ║
║   └── Professional UI like Gemini CLI                      ║
║                                                              ║
║   Timeline: 2-3 hours                                      ║
║   Complexity: Medium-High                                  ║
║   Dependencies: threading, queue, prompt_toolkit           ║
║                                                              ║
║   "From turn-based to true interactive."                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

Copilot, implement true interactive TUI with background processing. 🚀
