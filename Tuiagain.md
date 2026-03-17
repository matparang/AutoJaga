🎯 ANALISIS: ANSI CODES MASIH KELUAR!

---

📊 MASALAH YANG SAMA BERULANG

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🔍 TUI DISPLAY - ANSI CODES MASIH NAMPAK                 ║
║                                                              ║
║   Output yang sepatutnya:                                   ║
║   ✅ Task #1 complete (5s)                                  ║
║   🤖 AutoJaga: Hello!...                                    ║
║                                                              ║
║   Output yang keluar:                                       ║
║   ❌ ?[32m✅ Task #?[0m?[1;32m1?[0m?[32m complete?[0m      ║
║   ❌ ?[1;2m(?[0m?[2m5s?[0m?[1;2m)?[0m                     ║
║   ❌ ?[36m🤖 AutoJaga?[0m                                   ║
║                                                              ║
║   ✅ Teks biasa "Hello!..." masih OK                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

🧠 PUNCA SEBENARNYA

```
┌─────────────────────────────────────────────────────────────┐
│                    ANSI CODES ORIGIN                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Kod-kod ni datang dari:                                   │
│  • ?[32m - green text                                       │
│  • ?[1;32m - bold green                                     │
│  • ?[0m - reset                                             │
│  • ?[36m - cyan text                                        │
│                                                              │
│  AutoJaga output DARI LOG mengandungi ANSI codes:          │
│  • "✅ Task #1 complete" - hijau                            │
│  • "(5s)" - dim (grey)                                      │
│  • "🤖 AutoJaga" - cyan                                     │
│                                                              │
│  TUI kita capture output, TAPI tak strip ANSI codes!      │
│  Fungsi strip_ansi_codes() mungkin tak dipanggil?         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

🛠️ FIX: PASTIKAN ANSI STRIP DIPANGGIL

```python
# /root/nanojaga/jagabot/cli/interactive_tui.py

import re
import os

class InteractiveTUI:
    def __init__(self):
        # ... existing init ...
        self.use_ansi = self._check_ansi_support()
    
    def _check_ansi_support(self):
        """Check if terminal supports ANSI codes"""
        # Check TERM environment
        term = os.environ.get('TERM', '')
        if term in ('dumb', 'unknown'):
            return False
        
        # Check if stdout is a terminal
        if not sys.stdout.isatty():
            return False
        
        return True
    
    def _strip_ansi_codes(self, text):
        """Remove ALL ANSI escape codes from text"""
        # Pattern for standard ANSI codes (\x1b[...m)
        ansi_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        text = ansi_pattern.sub('', text)
        
        # Pattern for broken codes (?[...m format)
        broken_pattern = re.compile(r'\?\[\d+(?:;\d+)?[m]')
        text = broken_pattern.sub('', text)
        
        # Pattern for any remaining ?[ sequences
        question_pattern = re.compile(r'\?\[\d*(?:;\d*)*[a-zA-Z]?')
        text = question_pattern.sub('', text)
        
        return text
    
    def _process_output_queue(self):
        """Process any pending output with ANSI stripping"""
        try:
            while True:
                output = self.output_queue.get_nowait()
                
                # Extract message
                if isinstance(output, dict):
                    msg = output.get('message', str(output))
                else:
                    msg = str(output)
                
                # STRIP ANSI CODES (critical!)
                if not self.use_ansi:
                    msg = self._strip_ansi_codes(msg)
                
                # Add to display
                self.output_lines.append(msg)
                if len(self.output_lines) > self.max_output_lines:
                    self.output_lines.pop(0)
                
                self._refresh_display()
                
        except queue.Empty:
            pass
    
    def _refresh_display(self):
        """Refresh screen with stripped content"""
        self._clear_screen()
        self._show_banner()
        
        # Show output (already stripped)
        for line in self.output_lines[-20:]:
            print(line)
        
        # Show status
        running = len([t for t in self.tasks.values() if t.get('status') == 'running'])
        print(f"\n[{running} running] You: ", end='', flush=True)
```

---

🔧 FIX 2: PASTIKAN QUEUE MESSAGE STRIP

```python
# Dalam worker thread, strip sebelum queue

def _process_task_result(self, task_id, result):
    """Process task result with ANSI stripping"""
    
    # Get content
    content = ""
    if hasattr(result, 'get'):
        content = result.get('content', str(result))
    elif hasattr(result, 'content'):
        content = result.content
    else:
        content = str(result)
    
    # STRIP ANSI before putting in queue
    if not self.use_ansi:
        content = self._strip_ansi_codes(content)
    
    # Let harness verify claims (harness works on stripped text)
    verified_response = harness.verify_response(
        response=content,
        context={'task_id': task_id}
    )
    
    # Put in queue (already stripped)
    self.output_queue.put({
        'type': 'success',
        'message': verified_response
    })
    
    return True
```

---

📋 SCOPE PROMPT UNTUK COPILOT

```
# 🚨 URGENT: Fix ANSI Codes in TUI

## PROBLEM
ANSI escape codes (?[32m, ?[0m, etc.) still appearing in TUI output
Function strip_ansi_codes exists but not being called properly

## CHECKLIST
1. Verify _strip_ansi_codes() is called for EVERY output
2. Check queue processing path
3. Check task result processing path
4. Check harness output path

## FIXES NEEDED
- Add ANSI stripping in _process_output_queue()
- Add ANSI stripping in _process_task_result()
- Add terminal detection (use_ansi flag)
- Strip before putting in queue, not after

## TEST
- After fix, no more ?[32m codes
- Should see plain "✅ Task #1 complete"

🚀 IMPLEMENT NOW!
```
