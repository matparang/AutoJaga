🎯 SCOPE PROMPT UNTUK COPILOT - AUTOJAGA CRITICAL BUGS

---

```
# 🚨 URGENT: AutoJaga Critical Bugs - Shell Access & Tool Failures

## SITUATION
AutoJaga has two critical bugs that need immediate attention:

### BUG 1: NO SHELL COMMAND ACCESS
AutoJaga claims to have `exec` (shell command) capability but it's completely blocked:
- Cannot run any shell commands directly
- Even simple commands like `mkdir`, `mv`, `ls` fail
- This breaks basic functionality like workspace cleanup
- Error: "blocked due to safety restrictions"

### BUG 2: TOOLS NOT WORKING / MISMATCHED
Major disconnect between claimed tools vs working tools:

| Tool | Claimed | Actual | Issue |
|------|---------|--------|-------|
| `list_dir` | ✅ Yes | ❌ No | Permission denied |
| `web_search` | ✅ Yes | ❌ No | Missing API key/config |
| `exec` (shell) | ✅ Yes | ❌ No | Safety restrictions |
| `cron` | ✅ Yes | ⚠️ Partial | In-process only, not system cron |
| Debate system | ❌ Not mentioned | ✅ Working | Agent unaware of its own capability |
| Financial tools | ✅ Yes | ✅ Working | OK |

---

## 📋 **BUG DETAILS**

### BUG 1: Shell Access Completely Blocked
```python
# Attempting any shell command fails:
subprocess.run(["ls", "-la"])  # ❌ Permission denied / blocked
os.mkdir("/tmp/test")  # ❌ May also fail
```

Evidence from logs:

· Cleanup subagent reported success but files didn't move
· Directory creation created wrong path with curly braces
· Permission errors in various operations

BUG 2: Tool Registry Mismatch

```python
# AutoJaga thinks these work, but they don't:
- list_dir()  # Permission denied
- web_search()  # Missing API key
- exec()  # Blocked by restrictions

# AutoJaga doesn't know about working tools:
- debate system (Bull/Bear/Buffett) - works perfectly
- fact library (socio_economic_facts.json) - works
```

---

🔍 TASKS FOR COPILOT

TASK 1: DIAGNOSE SHELL ACCESS

```bash
# Run these and report what works/doesn't
python3 -c "import subprocess; print(subprocess.run(['echo', 'test'], capture_output=True))"
python3 -c "import os; print(os.system('echo test'))"
python3 -c "import os; print(os.listdir('/root/.jagabot/workspace/'))"
python3 -c "import os; os.mkdir('/tmp/autojaga_test')"
```

TASK 2: CHECK PERMISSIONS

```bash
# Check what user AutoJaga runs as
ps aux | grep jagabot
whoami
id

# Check workspace permissions
ls -la /root/.jagabot/workspace/
stat /root/.jagabot/workspace/
```

TASK 3: REVIEW SAFETY RESTRICTIONS

```bash
# Check config.json for restrictions
cat /root/.jagabot/config.json | grep -A5 "restrictToWorkspace"
cat /root/.jagabot/config.json | grep -A5 "allowed_paths"
```

TASK 4: AUDIT ACTUAL VS CLAIMED TOOLS

```python
# Create comprehensive tool audit script
"""
audit_tools.py - Check which tools actually work
"""

import importlib
import os
import sys

TOOLS_TO_TEST = [
    "read_file",
    "write_file", 
    "edit_file",
    "list_dir",
    "spawn_subagent",
    "web_search",
    "exec",
    "cron",
    "monte_carlo",
    "var_calculation",
    "cvar",
    "portfolio_optimization",
    "debate_agent"  # May be in different location
]

def test_tool(tool_name):
    """Test if a tool can be imported and basic function exists"""
    try:
        # Try different import paths
        paths = [
            f"jagabot.tools.{tool_name}",
            f"autoresearch.{tool_name}",
            f"autoresearch.debate_tools.{tool_name}",
            tool_name
        ]
        
        for path in paths:
            try:
                module = importlib.import_module(path)
                print(f"  ✅ {tool_name}: Found at {path}")
                return True
            except ImportError:
                continue
        
        print(f"  ❌ {tool_name}: Not found")
        return False
    except Exception as e:
        print(f"  ❌ {tool_name}: Error - {str(e)}")
        return False

print("🔍 AUTOJAGA TOOL AUDIT")
print("="*60)
for tool in TOOLS_TO_TEST:
    test_tool(tool)
```

TASK 5: FIX SHELL ACCESS (Options)

Option A: Update safety config

```json
// In config.json - relax restrictions
{
  "restrictToWorkspace": false,
  "allowed_paths": [
    "/root/.jagabot/workspace",
    "/tmp",
    "/usr/bin"
  ],
  "allowed_commands": [
    "mkdir",
    "mv",
    "cp", 
    "rm",
    "ls",
    "echo"
  ]
}
```

Option B: Create shell tool with proper permissions

```python
# /root/nanojaga/jagabot/tools/safe_shell.py
"""
Safe shell execution with permission checks
"""

import subprocess
import shlex
import os

class SafeShellTool:
    """Execute allowed shell commands safely"""
    
    ALLOWED_COMMANDS = [
        "mkdir", "mv", "cp", "ls", "echo", "cat",
        "pwd", "date", "whoami", "id"
    ]
    
    ALLOWED_PATHS = [
        "/root/.jagabot/workspace",
        "/tmp"
    ]
    
    def execute(self, command: str, timeout: int = 10):
        """
        Execute command if allowed
        """
        # Parse command
        parts = shlex.split(command)
        if not parts:
            return {"error": "Empty command"}
        
        cmd_name = parts[0]
        
        # Check if command is allowed
        if cmd_name not in self.ALLOWED_COMMANDS:
            return {"error": f"Command '{cmd_name}' not allowed"}
        
        # Check if paths are allowed
        for arg in parts[1:]:
            if arg.startswith('/') and not any(arg.startswith(p) for p in self.ALLOWED_PATHS):
                return {"error": f"Path '{arg}' not allowed"}
        
        try:
            result = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0
            }
        except Exception as e:
            return {"error": str(e)}
```

Option C: Use subagent for all shell operations (Workaround)

```python
# Instead of direct shell, always spawn subagent
def run_shell_via_subagent(command):
    worker = spawn_subagent(
        task={"type": "shell", "command": command},
        label="shell_worker"
    )
    return worker.get_result()
```

TASK 6: UPDATE AGENT SELF-KNOWLEDGE

```markdown
# Add to AGENTS.md or system prompt

## AUTOJAGA ACTUAL CAPABILITIES (2026-03-12)

### ✅ WORKING:
- File operations (read/write/edit with verification)
- Subagent spawning
- Financial analysis (Monte Carlo, VaR, CVaR, portfolio)
- Memory system (MEMORY.md, HISTORY.md)
- **Debate system** (Bull/Bear/Buffett personas) ✅ NEW
- **Fact library** (socio_economic_facts.json) ✅ NEW
- Three-tier model routing (qwen-max/plus/turbo)

### ❌ NOT WORKING / NEED FIX:
- Shell commands (blocked - use subagent instead)
- Directory listing (permission denied)
- Web search (needs API key config)
- System cron (in-process only)

### ⚠️ WORKAROUNDS:
- For shell commands: spawn subagent with shell task
- For web search: will be fixed soon
```

TASK 7: CREATE COMPREHENSIVE TEST SUITE

```python
# test_all_capabilities.py
"""
Test all AutoJaga capabilities and report working/broken
"""

import asyncio
import sys
sys.path.append('/root/nanojaga')

async def test_capabilities():
    results = {
        "working": [],
        "broken": [],
        "partial": []
    }
    
    # Test 1: File operations
    try:
        from jagabot.tools.write_file import WriteFileTool
        result = WriteFileTool().execute("/tmp/test.txt", "test")
        if "verified on disk" in result:
            results["working"].append("write_file")
        else:
            results["broken"].append("write_file")
    except Exception as e:
        results["broken"].append(f"write_file: {str(e)}")
    
    # Test 2: Subagent spawn
    try:
        from jagabot.tools.spawn import spawn_subagent
        worker = spawn_subagent(task={"type": "test"}, label="test")
        if worker:
            results["working"].append("spawn_subagent")
    except Exception as e:
        results["broken"].append(f"spawn_subagent: {str(e)}")
    
    # Test 3: Shell (should fail)
    try:
        import subprocess
        subprocess.run(["echo", "test"], check=True)
        results["working"].append("shell")
    except Exception as e:
        results["broken"].append(f"shell: blocked")
    
    # Test 4: Debate system
    try:
        from autoresearch.debate_agent import PersonaDebateAgent
        results["working"].append("debate_system")
    except ImportError:
        results["broken"].append("debate_system: not found")
    except Exception as e:
        results["broken"].append(f"debate_system: {str(e)}")
    
    return results

if __name__ == "__main__":
    results = asyncio.run(test_capabilities())
    print("\n📊 CAPABILITY REPORT")
    print("="*60)
    print(f"\n✅ WORKING: {len(results['working'])}")
    for item in results['working']:
        print(f"  • {item}")
    print(f"\n❌ BROKEN: {len(results['broken'])}")
    for item in results['broken']:
        print(f"  • {item}")
```

---

📊 SUCCESS CRITERIA

Task Success Looks Like
Diagnose shell Clear understanding of why blocked
Audit tools Complete list of working/broken
Fix shell Option A/B/C implemented
Update self-knowledge Agent knows actual capabilities
Test suite Can verify fixes work

---

🚀 IMPLEMENTATION ORDER

```yaml
Phase 1: Diagnose shell access (Task 1-3)
Phase 2: Audit all tools (Task 4)
Phase 3: Fix shell access (Task 5 - choose option)
Phase 4: Update agent self-knowledge (Task 6)
Phase 5: Create test suite (Task 7)
Phase 6: Verify fixes with test suite
```

---

🏁 READY TO IMPLEMENT

Copilot, diagnose shell access first, then audit tools, then fix. 🚀

```
