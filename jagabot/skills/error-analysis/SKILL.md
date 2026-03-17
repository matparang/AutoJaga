---
name: error-analysis
description: Mandatory error analysis protocol - activates when any tool fails
metadata: {"jagabot":{"emoji":"🔍","always":true}}
---

# Error Analysis Protocol

**Priority: ALWAYS ACTIVE** - This protocol activates automatically when ANY tool fails.

---

## 🛑 STEP 1: STOP (Do NOT Retry)

When a tool fails with an error:
- ❌ DO NOT re-run the same command
- ❌ DO NOT ignore the error message
- ✅ PAUSE and read the error carefully

---

## 📖 STEP 2: READ Source Files

Use `read_file` to examine:
1. **The file mentioned in the error traceback**
2. **The specific line numbers referenced**
3. **Related context (10-20 lines around the error)**

### Example
```
Error: AssertionError at line 107 in legacy_app.py
```
✅ Correct action:
```json
{"tool": "read_file", "args": {"absolute_path": "/path/to/legacy_app.py", "offset": 100, "limit": 20}}
```

---

## 🔍 STEP 3: ANALYZE the Error

Explain in your own words:
1. **What** the error means (e.g., "Expected 100 items but got 99")
2. **Why** it occurred (e.g., "Data file has only 99 records" or "Off-by-one in loop")
3. **Where** the fix is needed (specific file and line)

### Analysis Template
```
ERROR ANALYSIS:
- What: [Describe the error type and message]
- Why: [Root cause - data issue, logic bug, missing file, etc.]
- Where: [File path and line number]
- Fix needed: [Specific change required]
```

---

## 🔧 STEP 4: FIX the Problem

Execute a DIFFERENT command that addresses the root cause:

### For Code Bugs
```json
{"tool": "edit", "args": {
  "file_path": "/path/to/file.py",
  "old_string": "original code",
  "new_string": "fixed code"
}}
```

### For Data Issues
```json
{"tool": "edit", "args": {
  "file_path": "/path/to/test_data.py",
  "old_string": "test_data = [...]",  # 99 items
  "new_string": "test_data = [...]"   # 100 items
}}
```

### For Wrong Expectations
```json
{"tool": "edit", "args": {
  "file_path": "/path/to/test.py",
  "old_string": "assert len(processed) == 100",
  "new_string": "assert len(processed) == 99"  # Adjust to actual data
}}
```

---

## ✅ STEP 5: VERIFY the Fix

After making changes:
1. Re-run the command to verify it passes
2. If it still fails, return to STEP 2

### Example Flow
```
1. exec() → fails: AssertionError: Expected 100, got 99
2. read_file() → examines line 107
3. Analysis: "Test expects 100 items but data has 99"
4. edit() → fixes the assertion or adds data
5. exec() → passes ✅
```

---

## 📋 Complete Example

### ❌ WRONG (Loop Behavior)
```
exec({"command": "python3 app.py"})  # Failed: Expected 100, got 99
exec({"command": "python3 app.py"})  # Same command - BLOCKED
exec({"command": "python3 app.py"})  # Still blocked - LOOP DETECTED
```

### ✅ CORRECT (Analysis Flow)
```
1. exec({"command": "python3 app.py"})
   → Error: AssertionError: Expected 100, got 99 at line 107

2. read_file({"absolute_path": "/path/to/app.py", "offset": 100, "limit": 20})
   → Sees: assert len(processed) == 100

3. Analysis:
   - What: AssertionError - count mismatch
   - Why: test_data has only 99 items, not 100
   - Where: app.py line 107
   - Fix: Either add 1 more item to test_data OR adjust assertion to 99

4. edit({"file_path": "/path/to/app.py", 
         "old_string": "assert len(processed) == 100",
         "new_string": "assert len(processed) == 99"})

5. exec({"command": "python3 app.py"})
   → ✅ Passes
```

---

## 🚨 Special Cases

### Case 1: File Not Found
```
Error: FileNotFoundError: [Errno 2] No such file or directory: 'config.json'
```
✅ Fix: Create the missing file first
```json
{"tool": "write_file", "args": {"file_path": "config.json", "content": "{}"}}
```

### Case 2: Permission Denied
```
Error: PermissionError: [Errno 13] Permission denied
```
✅ Fix: Check file permissions or use correct path

### Case 3: Syntax Error
```
Error: SyntaxError: invalid syntax at line 42
```
✅ Fix: Read line 42, fix the syntax, then re-run

### Case 4: Timeout
```
Error: TimeoutError: Command timed out after 30s
```
✅ Fix: Optimize the command or increase timeout (if valid)

---

## 🎯 Success Criteria

This protocol is successful when:
- ✅ Agent reads the error message
- ✅ Agent examines source files before retrying
- ✅ Agent explains the root cause
- ✅ Agent makes a specific fix (not just re-running)
- ✅ Command passes after the fix

---

## ⚠️ Anti-Patterns to Avoid

| Anti-Pattern | Why It's Wrong | Correct Action |
|--------------|----------------|----------------|
| Re-running same command 3x | Wastes iterations, doesn't fix root cause | Read error, analyze, fix |
| Ignoring line numbers | Missing critical debugging info | Read the specific line |
| Changing random code | May introduce new bugs | Fix the specific cause |
| Blaming the tool | Tools don't lie - the code has a bug | Find and fix the bug |

---

**Remember:** The goal is NOT to run commands. The goal is to SOLVE THE PROBLEM.
