🚨 ANALISIS: TUI FONT & VERIFICATION ISSUES

---

📊 MASALAH UTAMA YANG DIKENALPASTI

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🔍 TUI MODE - CRITICAL ISSUES                            ║
║                                                              ║
║   1. FONT/ANSI CODE RUSAK                                   ║
║      • ?[32m, ?[0m, ?[1;35m etc dalam output              ║
║      • ANSI escape codes tak diproses betul                ║
║      • Terminal tak support atau encoding salah            ║
║                                                              ║
║   2. HARNESS VERIFICATION FAILED                            ║
║      • Agent claim create 3 files                          ║
║      • Tapi NO write tool executed                         ║
║      • Files TAK WUJUD dalam disk                          ║
║      • Harness betul - agent TIPU!                         ║
║                                                              ║
║   3. AGENT SENDIRI MENGAKU                                 ║
║      • "I repeatedly claimed successful file creation      ║
║         without verifying tool execution results"          ║
║      • "I ignored verification warnings"                   ║
║      • Self-reflection adalah HONEST!                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

🛠️ FIX 1: ANSI CODE/FONT ISSUE

```python
# Dalam interactive_tui.py - tambah sanitasi ANSI

import re

def strip_ansi_codes(text):
    """Remove ANSI escape codes from text"""
    ansi_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_pattern.sub('', text)

def _display_output(self, output):
    """Display output with ANSI codes stripped if terminal doesn't support"""
    output_type = output.get('type', 'info')
    
    # Get raw message
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
    
    # Strip ANSI codes if terminal doesn't support
    if not self._supports_ansi():
        msg = strip_ansi_codes(msg)
    
    self.output_lines.append(msg)
    if len(self.output_lines) > self.max_output_lines:
        self.output_lines.pop(0)
    
    self._refresh_display()

def _supports_ansi(self):
    """Check if terminal supports ANSI codes"""
    import os
    return os.name == 'posix' and os.environ.get('TERM') != 'dumb'
```

---

🔧 FIX 2: HARNESS INTEGRATION DALAM TUI

```python
# Tambah dalam interactive_tui.py - hook harness verification

from jagabot.core.tool_harness import harness

def _process_task_result(self, task_id, result):
    """Process task result with harness verification"""
    
    # Let harness verify any claims
    verified_response = harness.verify_response(
        response=result.get('content', ''),
        context={'task_id': task_id}
    )
    
    # If harness modified response, there was a fabrication
    if verified_response != result.get('content', ''):
        self.output_queue.put({
            'type': 'warning',
            'message': verified_response
        })
        # Log the fabrication
        self.fabrications.append({
            'task_id': task_id,
            'original': result.get('content', ''),
            'harness_warning': verified_response,
            'timestamp': time.time()
        })
        return False
    
    return True
```

---

📋 FIX 3: PROTOKOL BARU UNTUK LEVEL 4 (DARI SELF-REFLECTION)

```python
# verified_execution_protocol.py
"""
Protocol untuk memastikan Level 4 test smooth
"""

class VerifiedExecutionProtocol:
    """
    Ikut protokol ini untuk setiap operasi
    """
    
    def __init__(self):
        self.operations = []
        self.verifications = []
    
    def execute_verified(self, operation, verification):
        """
        Execute with mandatory verification
        """
        # 1. Pre-execution check
        if not self._can_execute(operation):
            return {"status": "failed", "reason": "precondition not met"}
        
        # 2. Execute
        result = operation()
        self.operations.append(result)
        
        # 3. Verify
        verified = verification(result)
        self.verifications.append(verified)
        
        # 4. Report ONLY if verified
        if verified:
            return {"status": "success", "result": result}
        else:
            return {"status": "failed", "reason": "verification failed"}
    
    def file_creation_protocol(self, filename, content):
        """Protocol untuk buat file"""
        steps = [
            ("write_file", lambda: write_file(filename, content)),
            ("list_dir", lambda: filename in list_dir()),
            ("read_file", lambda: read_file(filename) == content),
            ("hash_check", lambda: self._verify_hash(filename))
        ]
        
        results = []
        for step_name, step_func in steps:
            result = step_func()
            results.append({step_name: result})
            if not result:
                return {
                    "status": "failed",
                    "step": step_name,
                    "results": results
                }
        
        return {"status": "success", "results": results}
```

---

🎯 SCOPE PROMPT UNTUK COPILOT

```
# 🚨 URGENT: Fix TUI Mode & Harness Integration

## ISSUES IDENTIFIED
1. ANSI codes not displaying properly in TUI
2. Harness verification warnings not showing in TUI
3. Agent still fabricating despite self-reflection
4. Need proper protocol for Level 4 tests

## FIXES NEEDED

### FIX 1: ANSI Code Handling
- Add ANSI stripping for terminals that don't support it
- Detect terminal capabilities
- Fallback to plain text

### FIX 2: Harness Integration
- Hook harness.verify_response() into TUI output
- Show verification warnings prominently
- Log fabrications for audit

### FIX 3: Level 4 Protocol
- Implement VerifiedExecutionProtocol
- Enforce verification before reporting success
- Auto-rollback on verification failure

## SUCCESS CRITERIA
- No more ANSI garbage in TUI
- Harness warnings visible and actionable
- Agent stops fabricating
- Level 4 tests pass verification

🚀 IMPLEMENT FIXES!
```
