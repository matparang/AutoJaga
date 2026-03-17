🎯 SCOPE PROMPT FOR COPILOT - WORKSPACE FILE VERIFICATION & FIX

---

📋 SITUATION

```
AutoJaga (autonomous agent) claims it has created and saved multiple files:
- risk_analyzer.py
- file_processor.py  
- elixir_bridge.py
- experiment_tracker.py
- token_tracker.py
- spawn_with_proof.py
- VERSION.md (with completion status)
- Various log files in /root/.jabagot/logs/experiments/

However, when checking ~/.jagabot/workspace/, these files are NOT present.
The agent may be saving files to WRONG LOCATIONS or not saving at all.

CRITICAL: AutoJaga's workspace should be ~/.jagabot/workspace/ but files are missing.
This suggests a path configuration issue or the agent is hallucinating file creation.
```

---

🎯 OBJECTIVE

```
FORENSIC INVESTIGATION:

1. DISCOVER where files are ACTUALLY being saved
2. IDENTIFY why agent thinks files are in workspace when they're not
3. FIX path configuration to ensure ALL files go to ~/.jabagot/workspace/
4. VERIFY all claimed files exist (or create them properly)
5. PREVENT future path confusion with enforced workspace policy
```

---

🔍 INITIAL EVIDENCE

```bash
# Expected location (should have files)
ls -la ~/.jagabot/workspace/
# Currently: EMPTY or missing files

# Known locations to check:
find /root -name "risk_analyzer.py" 2>/dev/null
find /root -name "file_processor.py" 2>/dev/null
find /root -name "VERSION.md" 2>/dev/null
find /root -name "*.jsonl" 2>/dev/null | grep -E "(experiments|token)"

# Check AutoJaga's current working directory
cat /proc/$(pgrep -f jagabot)/cwd 2>/dev/null || echo "Process not found"

# Check config for workspace path
cat /root/.jagabot/config.json 2>/dev/null | grep -i workspace
cat /root/nanojaga/config.json 2>/dev/null | grep -i workspace
```

---

🛠️ ROOT CAUSE HYPOTHESES

```
Hypothesis 1: WRONG PATH HARDCODED
   - Agent saving to /root/nanojaga/ instead of ~/.jagabot/workspace/
   - Evidence: risk_analyzer.py found at /root/nanojaga/tools/ earlier

Hypothesis 2: WORKSPACE NOT CREATED
   - Directory ~/.jabagot/workspace/ doesn't exist
   - Agent failing silently when trying to write

Hypothesis 3: PERMISSION ISSUES
   - Agent can't write to workspace due to permissions
   - Files being written to /tmp/ instead

Hypothesis 4: CONFIG MISMATCH
   - Agent using different workspace path than expected
   - Check environment variables or config files
```

---

📋 EXECUTION PLAN

PHASE 1: DISCOVERY - Find Where Files Actually Are

```bash
# Create comprehensive search script
cat > /tmp/find_autojaga_files.sh << 'EOF'
#!/bin/bash
echo "🔍 AUTOJAGA FILE DISCOVERY"
echo "=========================="

# Locations to search
LOCATIONS=(
  "/root/.jagabot"
  "/root/nanojaga"
  "/root"
  "/tmp"
  "/var/tmp"
)

# Files to find
FILES=(
  "risk_analyzer.py"
  "file_processor.py"
  "elixir_bridge.py"
  "experiment_tracker.py"
  "token_tracker.py"
  "spawn_with_proof.py"
  "VERSION.md"
  "*.jsonl"
  "*.log"
)

echo -e "\n📁 SEARCHING ALL LOCATIONS..."
for loc in "${LOCATIONS[@]}"; do
  echo -e "\n📍 Checking: $loc"
  for file in "${FILES[@]}"; do
    find "$loc" -name "$file" -type f 2>/dev/null | while read found; do
      echo "   ✅ FOUND: $found"
      ls -la "$found"
    done
  done
done

echo -e "\n📊 SUMMARY BY FILE TYPE:"
for file in "${FILES[@]}"; do
  count=$(find / -name "$file" -type f 2>/dev/null | wc -l)
  echo "   $file: $count occurrences"
done
EOF

chmod +x /tmp/find_autojaga_files.sh
/tmp/find_autojaga_files.sh | tee /tmp/discovery_results.txt
```

PHASE 2: ANALYZE - Identify Path Configuration

```python
# /tmp/analyze_paths.py
"""
Analyze where AutoJaga thinks it should save files
"""

import os
import json
import glob

print("🔧 AUTOJAGA PATH ANALYSIS")
print("========================")

# Check all possible config locations
config_locations = [
    "/root/.jagabot/config.json",
    "/root/nanojaga/config.json",
    "/root/.jagabot/workspace/config.json",
    "/root/nanojaga/jagabot/config.json"
]

print("\n📋 CONFIG FILES:")
for cfg in config_locations:
    if os.path.exists(cfg):
        print(f"   ✅ Found: {cfg}")
        try:
            with open(cfg, 'r') as f:
                data = json.load(f)
                print(f"      Content: {json.dumps(data, indent=2)[:200]}...")
                
                # Look for workspace paths
                if 'workspace' in str(data):
                    print(f"      ⚠️ Contains 'workspace' reference")
                if 'path' in str(data):
                    print(f"      ⚠️ Contains 'path' reference")
        except:
            print(f"      ❌ Cannot parse JSON")
    else:
        print(f"   ❌ Not found: {cfg}")

# Check environment variables
print("\n🌍 ENVIRONMENT VARIABLES:")
env_vars = os.popen('env | grep -i "jaga\|workspace\|path"').read()
print(env_vars if env_vars else "   None found")

# Check running process
print("\n🔄 RUNNING PROCESS:")
pid = os.popen('pgrep -f jagabot').read().strip()
if pid:
    cwd = os.popen(f'readlink /proc/{pid}/cwd').read().strip()
    print(f"   PID: {pid}")
    print(f"   CWD: {cwd}")
    print(f"   CMD: {os.popen(f'cat /proc/{pid}/cmdline').read()}")
```

PHASE 3: FIX - Create Proper Workspace Structure

```python
# /tmp/fix_workspace.py
"""
Force AutoJaga to use correct workspace ~/.jagabot/workspace/
"""

import os
import shutil
import json
from datetime import datetime

WORKSPACE = "/root/.jagabot/workspace"
TOOLS_DIR = "/root/nanojaga/jagabot/tools"
LOG_DIR = "/root/.jagabot/logs"
EXPERIMENTS_DIR = f"{LOG_DIR}/experiments"
PROOFS_DIR = "/root/.jagabot/proofs"

print("🔧 AUTOJAGA WORKSPACE FIX")
print("========================")

# Step 1: Create workspace structure
print("\n📁 CREATING WORKSPACE STRUCTURE...")
os.makedirs(WORKSPACE, exist_ok=True)
os.makedirs(f"{WORKSPACE}/memory", exist_ok=True)
os.makedirs(f"{WORKSPACE}/skills", exist_ok=True)
os.makedirs(EXPERIMENTS_DIR, exist_ok=True)
os.makedirs(PROOFS_DIR, exist_ok=True)

print(f"   ✅ {WORKSPACE} created")
print(f"   ✅ {WORKSPACE}/memory created")
print(f"   ✅ {WORKSPACE}/skills created")
print(f"   ✅ {EXPERIMENTS_DIR} created")
print(f"   ✅ {PROOFS_DIR} created")

# Step 2: Find and move VERSION.md
print("\n📋 LOCATING VERSION.MD...")
version_locations = [
    "/root/nanojaga/VERSION.md",
    "/root/VERSION.md",
    "/tmp/VERSION.md",
    "/root/.jagabot/VERSION.md"
]

version_found = None
for loc in version_locations:
    if os.path.exists(loc):
        version_found = loc
        print(f"   ✅ Found at: {loc}")
        break

if version_found:
    shutil.copy2(version_found, f"{WORKSPACE}/VERSION.md")
    print(f"   ✅ Copied to: {WORKSPACE}/VERSION.md")
else:
    print("   ❌ VERSION.md not found - creating default")
    default_version = {
        "created": datetime.now().isoformat(),
        "version": "4.0",
        "status": "initialized",
        "files": []
    }
    with open(f"{WORKSPACE}/VERSION.md", 'w') as f:
        json.dump(default_version, f, indent=2)
    print(f"   ✅ Created default: {WORKSPACE}/VERSION.md")

# Step 3: Find all tool files and create symlinks/verify
print("\n🔧 VERIFYING TOOL FILES...")
tool_files = [
    "risk_analyzer.py",
    "file_processor.py",
    "elixir_bridge.py",
    "experiment_tracker.py",
    "token_tracker.py",
    "spawn_with_proof.py"
]

for tool in tool_files:
    # Check tools directory
    tool_path = f"{TOOLS_DIR}/{tool}"
    if os.path.exists(tool_path):
        print(f"   ✅ {tool} exists at {tool_path}")
        # Create symlink in workspace for reference
        if not os.path.exists(f"{WORKSPACE}/{tool}"):
            os.symlink(tool_path, f"{WORKSPACE}/{tool}")
            print(f"      🔗 Symlinked to workspace")
    else:
        print(f"   ❌ {tool} NOT FOUND at {tool_path}")
        # Search elsewhere
        found = os.popen(f'find /root -name "{tool}" 2>/dev/null').read().strip()
        if found:
            print(f"      ⚠️ Found elsewhere: {found}")
            # Copy to correct location
            shutil.copy2(found, tool_path)
            print(f"      ✅ Copied to correct location")

# Step 4: Create config file if missing
config_path = "/root/.jagabot/config.json"
if not os.path.exists(config_path):
    print("\n📝 CREATING CONFIG FILE...")
    config = {
        "workspace": WORKSPACE,
        "tools_dir": TOOLS_DIR,
        "log_dir": LOG_DIR,
        "experiments_dir": EXPERIMENTS_DIR,
        "proofs_dir": PROOFS_DIR,
        "version_file": f"{WORKSPACE}/VERSION.md",
        "memory_dir": f"{WORKSPACE}/memory"
    }
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"   ✅ Created: {config_path}")

# Step 5: Update all Python files to use correct paths
print("\n🔧 PATCHING PYTHON FILES TO USE WORKSPACE...")

for tool in tool_files:
    tool_path = f"{TOOLS_DIR}/{tool}"
    if os.path.exists(tool_path):
        with open(tool_path, 'r') as f:
            content = f.read()
        
        # Replace hardcoded paths
        if "/root/nanojaga/" in content:
            content = content.replace("/root/nanojaga/", f"{WORKSPACE}/")
            with open(tool_path, 'w') as f:
                f.write(content)
            print(f"   ✅ Patched {tool}")

# Step 6: Verification
print("\n✅ FINAL VERIFICATION:")
print(f"   Workspace exists: {os.path.exists(WORKSPACE)}")
print(f"   VERSION.md exists: {os.path.exists(f'{WORKSPACE}/VERSION.md')}")
print(f"   Config exists: {os.path.exists(config_path)}")
print(f"   Tool files in tools dir: {len([f for f in tool_files if os.path.exists(f'{TOOLS_DIR}/{f}')])}/{len(tool_files)}")

print("\n🎯 FIX COMPLETE. AutoJaga should now use correct workspace.")
```

PHASE 4: VERIFY - Check All Files Present

```bash
# /tmp/verify_workspace.sh
#!/bin/bash
echo "🔍 WORKSPACE VERIFICATION"
echo "========================"

WORKSPACE="/root/.jagabot/workspace"
TOOLS="/root/nanojaga/jabagot/tools"
LOGS="/root/.jagabot/logs"

echo -e "\n📁 WORKSPACE CONTENTS:"
ls -la $WORKSPACE/

echo -e "\n📄 VERSION.MD:"
if [ -f "$WORKSPACE/VERSION.md" ]; then
  echo "   ✅ EXISTS"
  head -20 "$WORKSPACE/VERSION.md"
else
  echo "   ❌ MISSING"
fi

echo -e "\n🔧 TOOL FILES IN WORKSPACE (symlinks):"
for tool in risk_analyzer.py file_processor.py elixir_bridge.py experiment_tracker.py token_tracker.py spawn_with_proof.py; do
  if [ -L "$WORKSPACE/$tool" ]; then
    echo "   ✅ $tool -> $(readlink $WORKSPACE/$tool)"
  elif [ -f "$WORKSPACE/$tool" ]; then
    echo "   ✅ $tool (file)"
  else
    echo "   ❌ $tool missing"
  fi
done

echo -e "\n📊 EXPERIMENT LOGS:"
ls -la $LOGS/experiments/ | tail -20

echo -e "\n✅ VERIFICATION COMPLETE"
```

PHASE 5: PREVENT - Enforce Workspace Policy

```python
# /root/nanojaga/jagabot/tools/workspace_enforcer.py
"""
Enforce that ALL files go to ~/.jagabot/workspace/
"""

import os
import inspect

class WorkspaceEnforcer:
    """
    Ensures all file operations use correct workspace
    """
    
    WORKSPACE = "/root/.jabagot/workspace"
    
    @classmethod
    def get_path(cls, filename):
        """Force path to be within workspace"""
        
        # Remove any leading paths
        basename = os.path.basename(filename)
        
        # Always put in workspace
        return os.path.join(cls.WORKSPACE, basename)
    
    @classmethod
    def verify_path(cls, func):
        """Decorator to verify file paths"""
        def wrapper(*args, **kwargs):
            # Check if any arg looks like a file path
            for i, arg in enumerate(args):
                if isinstance(arg, str) and ('/' in arg or '.py' in arg or '.md' in arg):
                    # Force to workspace path
                    args = list(args)
                    args[i] = cls.get_path(arg)
                    args = tuple(args)
            
            # Call original function
            result = func(*args, **kwargs)
            
            # Verify file was created in workspace
            if 'file' in str(args) or 'path' in str(kwargs):
                # Check last written file
                pass
            
            return result
        return wrapper
```

---

📋 FINAL DELIVERABLE FORMAT

```markdown
# AUTOJAGA WORKSPACE FORENSIC REPORT
Date: 2026-03-11
Auditor: Copilot

## 🔍 DISCOVERY FINDINGS
[Where files were ACTUALLY found vs claimed]

## 📊 PATH ANALYSIS
[What configuration caused the issue]

## 🛠️ FIXES APPLIED
[What was done to correct paths]

## ✅ VERIFICATION RESULTS
[All files now in ~/.jagabot/workspace/]

## 🚀 PREVENTION MEASURES
[How to ensure it never happens again]

## 📋 COMMANDS TO VERIFY
\`\`\`bash
ls -la ~/.jagabot/workspace/
cat ~/.jagabot/workspace/VERSION.md
\`\`\`
```

---

🚀 EXECUTION REQUEST

```
Please execute the forensic investigation:

1. Run /tmp/find_autojaga_files.sh to discover where files ACTUALLY are
2. Run /tmp/analyze_paths.py to identify configuration issues
3. Run /tmp/fix_workspace.py to move/copy all files to correct location
4. Run /tmp/verify_workspace.sh to confirm everything is in place

After fixes, AutoJaga should save ALL files to ~/.jagabot/workspace/
No exceptions.

Start the audit and fix now.
```
