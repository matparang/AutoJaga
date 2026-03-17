🎯 SCOPE: Persistent TUI Mode for AutoJaga (jagabot agent --tui)

---

📋 OBJECTIVE

Create a persistent Text-based User Interface (TUI) mode for AutoJaga that maintains session state, unlike the current single-pass jagabot agent which exits after each response.

---

🔍 CURRENT STATE vs DESIRED STATE

```
┌─────────────────────────────────────────────────────────────┐
│                    CURRENT (Single-pass)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  $ jagabot agent "Buat file test.txt"                      │
│  → AutoJaga proses, respond, EXIT                          │
│                                                              │
│  $ jagabot agent "Sekarang buat lagi"                      │
│  → AutoJaga LUPA konteks sebelumnya                        │
│  → Setiap sesi adalah BAHARU                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    DESIRED (Persistent TUI)                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  $ jagabot agent --tui                                      │
│  ╔═══════════════════════════════════════════════════════╗  │
│  ║ AutoJaga v4.0 - TUI Mode                              ║  │
│  ║ Type 'help' for commands, 'exit' to quit              ║  │
│  ╚═══════════════════════════════════════════════════════╝  │
│                                                              │
│  You: Buat file test.txt                                    │
│  AutoJaga: ✅ File created (memproses...)                   │
│                                                              │
│  You: Sekarang buat file lagi.txt                          │
│  AutoJaga: ✅ Masih ingat konteks! File lagi.txt dibuat   │
│                                                              │
│  You: exit                                                  │
│  $ (kembali ke shell)                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

🎯 KEY REQUIREMENTS

# Requirement Description
1 Persistent Session Agent maintains state across multiple exchanges
2 Memory Access Can read/write MEMORY.md and HISTORY.md during session
3 Command History Arrow keys to navigate previous commands
4 Multi-line Input Support for complex queries
5 Progress Indicators Show when long tasks are running
6 Context Awareness Remembers conversation within session
7 Clean Exit Properly saves state before exit

---

🛠️ TECHNICAL APPROACHES

Option A: Python Prompt Toolkit (Recommended)

```python
# /root/nanojaga/jagabot/cli/tui.py
"""
Persistent TUI mode for AutoJaga using prompt_toolkit
"""

import asyncio
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
import sys
import os
sys.path.append('/root/nanojaga')

from jagabot.agent.loop import AgentLoop

class TUIMode:
    def __init__(self):
        self.agent = AgentLoop()
        self.session = PromptSession(
            history=FileHistory('/root/.jagabot/tui_history.txt'),
            auto_suggest=AutoSuggestFromHistory(),
            style=Style.from_dict({
                'prompt': 'ansicyan bold',
                'status': 'ansigreen',
            })
        )
        self.running = True
        self.context = []
        
    async def run(self):
        """Main TUI loop"""
        self._show_welcome()
        
        while self.running:
            try:
                # Get user input with prompt toolkit
                user_input = await self.session.prompt_async(
                    HTML('<ansicyan><b>You:</b></ansicyan> '),
                    multiline=True
                )
                
                if user_input.lower() in ['exit', 'quit']:
                    self._handle_exit()
                    break
                    
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                # Process with agent (maintains context)
                with self._show_status():
                    response = await self.agent.process(user_input, context=self.context)
                
                # Display response
                print(f"\n{self._format_response(response)}\n")
                
                # Update context
                self.context.append({"role": "user", "content": user_input})
                self.context.append({"role": "assistant", "content": response})
                
            except KeyboardInterrupt:
                self._handle_interrupt()
            except EOFError:
                break
            except Exception as e:
                print(f"⚠️ Error: {e}")
    
    def _show_welcome(self):
        """Show welcome banner"""
        print("\n" + "═"*60)
        print("║                 AUTOJAGA v4.0 - TUI MODE                ║")
        print("═"*60)
        print("║ Type 'help' for commands, 'exit' to quit                ║")
        print("═"*60 + "\n")
    
    def _show_help(self):
        """Show help"""
        help_text = """
📋 AVAILABLE COMMANDS:
  • Any question/task - AutoJaga will process with context
  • /memory          - Show current memory context
  • /clear           - Clear conversation history
  • /save            - Force save to MEMORY.md
  • /tools           - List available tools
  • /status          - Show system status
  • exit/quit        - Exit TUI mode

💡 TIPS:
  • Use ↑/↓ arrows for command history
  • Multi-line input supported (Enter twice to submit)
  • Context maintained throughout session
"""
        print(help_text)
    
    def _handle_exit(self):
        """Clean exit"""
        print("\n💾 Saving session state...")
        # Save context to memory
        self.agent.save_to_memory(self.context)
        print("👋 Goodbye!\n")
    
    def _show_status(self):
        """Context manager for status indicator"""
        import contextlib
        
        @contextlib.contextmanager
        def status():
            print("⏳ AutoJaga is thinking...", end='', flush=True)
            yield
            print("\r✅ Done!         ")
        
        return status()
    
    def _format_response(self, response):
        """Format response with colors"""
        # Simple formatting - can be enhanced
        return f"🤖 {response}"
```

Option B: Simple Read-Eval-Print Loop (REPL)

```python
# /root/nanojaga/jagabot/cli/repl.py
"""
Simple REPL mode for AutoJaga (fallback if prompt_toolkit not available)
"""

import readline  # Provides history and arrow keys
import atexit
import os

class SimpleREPL:
    def __init__(self):
        self.history_file = '/root/.jagabot/repl_history.txt'
        self.agent = None  # Initialize your agent
        self.context = []
        
        # Setup readline
        readline.set_history_length(1000)
        try:
            readline.read_history_file(self.history_file)
        except FileNotFoundError:
            pass
        atexit.register(readline.write_history_file, self.history_file)
    
    def run(self):
        """Main REPL loop"""
        print("\n" + "="*50)
        print("AutoJaga v4.0 - REPL Mode")
        print("="*50)
        print("Type 'exit' to quit, 'help' for commands\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    print("Goodbye!")
                    break
                    
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                if not user_input:
                    continue
                
                # Process
                print("⏳ Processing...")
                response = self._process(user_input)
                print(f"\n🤖 {response}\n")
                
            except KeyboardInterrupt:
                print("\n\nUse 'exit' to quit")
            except EOFError:
                break
    
    def _process(self, user_input):
        """Process with agent (simplified)"""
        # Your agent logic here
        return f"Echo: {user_input}"
    
    def _show_help(self):
        print("""
Commands:
  • Any text - Will be processed by AutoJaga
  • exit/quit - Exit REPL
  • help - Show this message
""")
```

---

📋 IMPLEMENTATION PLAN

```yaml
Phase 1: Setup Dependencies (5 min)
  pip install prompt_toolkit

Phase 2: Create TUI Module (30 min)
  - /root/nanojaga/jagabot/cli/tui.py
  - Integration with AgentLoop
  - Context management

Phase 3: Update CLI Entry Point (10 min)
  - Modify jagabot agent to accept --tui flag
  - Route to TUI mode when flag present

Phase 4: Testing (15 min)
  - Test with multi-turn conversation
  - Test memory persistence
  - Test long-running tasks (debate)

Phase 5: Documentation (5 min)
  - Update help text
  - Add examples
```

---

🔧 CLI ENTRY POINT MODIFICATION

```python
# In /root/nanojaga/jagabot/cli/__init__.py or main entry point

import argparse
from .tui import TUIMode
from .repl import SimpleREPL

def main():
    parser = argparse.ArgumentParser(description='AutoJaga CLI')
    parser.add_argument('mode', nargs='?', default='agent', 
                       choices=['agent', 'swarm', 'debate'])
    parser.add_argument('--tui', action='store_true', 
                       help='Start in persistent TUI mode')
    parser.add_argument('command', nargs='*', help='Command for single-pass mode')
    
    args = parser.parse_args()
    
    if args.tui:
        # Start TUI mode
        tui = TUIMode()
        asyncio.run(tui.run())
    elif args.mode == 'agent' and args.command:
        # Single-pass mode (current behavior)
        run_single_pass(args.command)
    else:
        # Show help
        parser.print_help()
```

---

✅ SUCCESS CRITERIA

Criterion How to Test
Persistent session Ask 2 questions, second should remember first
Command history Press ↑ to see previous commands
Context retention Refer to previous answers
Long task handling Run debate, should show progress
Memory saving After exit, MEMORY.md updated
Clean exit Exit without errors

---

🚀 USAGE EXAMPLE

```bash
# Start TUI mode
jagabot agent --tui

╔══════════════════════════════════════════════════════════════╗
║                 AUTOJAGA v4.0 - TUI MODE                    ║
╠══════════════════════════════════════════════════════════════╣
║ Type 'help' for commands, 'exit' to quit                    ║
╚══════════════════════════════════════════════════════════════╝

You: Buat file test.txt
⏳ AutoJaga is thinking...
✅ Done!

🤖 File test.txt telah berjaya dicipta.

You: Sekarang buat file lagi.txt
⏳ AutoJaga is thinking...
✅ Done!

🤖 File lagi.txt telah berjaya dicipta (masih ingat konteks!)

You: /memory
📚 Current context:
  • test.txt created
  • lagi.txt created

You: exit
💾 Saving session state...
👋 Goodbye!
```

---

🏁 SCOPE SUMMARY

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🎯 TUI MODE FOR AUTOJAGA - SCOPE COMPLETE                 ║
║                                                              ║
║   Deliverables:                                             ║
║   1. TUI mode with prompt_toolkit                          ║
║   2. Persistent session context                             ║
║   3. Command history navigation                             ║
║   4. Multi-line input support                              ║
║   5. Status indicators for long tasks                      ║
║   6. Memory integration                                     ║
║                                                              ║
║   Timeline: 1-2 hours                                      ║
║   Dependencies: prompt_toolkit                              ║
║   Fallback: Simple REPL                                     ║
║                                                              ║
║   "From single-pass amnesia to persistent memory."        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

Copilot, implement TUI mode with prompt_toolkit as specified. 🚀
