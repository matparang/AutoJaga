# Agent Loop Fix - Summary

## Problem
Agent was stuck in a loop re-running the same failing command instead of analyzing errors and fixing them.

### Example
```
AssertionError: Expected 100, got 99
→ Agent re-runs same command → Same error → Repeat (loop)
```

## Solution Implemented

### 1. Reduced Duplicate Command Threshold
**File:** `jagabot/agent/loop.py` (line 475)

**Before:** Blocked on 3rd occurrence (`>= 3`)
**After:** Blocked on 2nd occurrence (`>= 2`)

```python
# Old code
if _duplicate_commands[cmd_key] >= 3:

# New code  
if _duplicate_commands[cmd_key] >= 2:
```

**Effect:** Agent is now blocked from running the same command after just 1 retry, forcing it to try a different approach.

---

### 2. Added Error Analysis Prompt
**File:** `jagabot/agent/loop.py` (lines 524-533)

When any tool fails, the following prompt is automatically appended to the error message:

```
⚠️ ERROR ANALYSIS REQUIRED BEFORE RETRY:
Tool 'exec' failed. BEFORE running it again:
1. READ the relevant source file(s) using read_file
2. ANALYZE the error traceback (note line numbers and file paths)
3. EXPLAIN why the error occurred in your own words
4. PROPOSE and EXECUTE a specific fix (edit code, adjust data, or change approach)
5. DO NOT re-run the same command without making changes first
```

**Effect:** Agent is explicitly instructed to read files and analyze before retrying.

---

### 3. Created Error Analysis Skill Pack
**File:** `jagabot/skills/error-analysis/SKILL.md`

A comprehensive skill pack that teaches the agent:
- When to STOP (don't retry immediately)
- How to READ source files
- How to ANALYZE errors
- How to FIX problems properly
- Complete examples of correct vs wrong behavior

**Effect:** Agent has detailed guidance on proper error handling workflow.

---

## Expected Behavior After Fix

### ❌ Before (Loop Behavior)
```
1. exec({"command": "python3 app.py"})
   → Error: Expected 100, got 99

2. exec({"command": "python3 app.py"})  # Same command
   → Error: Expected 100, got 99

3. exec({"command": "python3 app.py"})  # Still same - LOOP
   → Error: Expected 100, got 99
```

### ✅ After (Analysis Flow)
```
1. exec({"command": "python3 app.py"})
   → Error: Expected 100, got 99
   → ⚠️ ERROR ANALYSIS REQUIRED...

2. read_file({"absolute_path": "app.py", "offset": 100, "limit": 20})
   → Sees assertion at line 107

3. [Agent analyzes: "Data has 99 items, not 100"]

4. edit({"file_path": "app.py", 
         "old_string": "assert len(processed) == 100",
         "new_string": "assert len(processed) == 99"})

5. exec({"command": "python3 app.py"})
   → ✅ Passes
```

---

## Files Modified

| File | Change | Status |
|------|--------|--------|
| `jagabot/agent/loop.py` | Duplicate threshold 3→2 | ✅ |
| `jagabot/agent/loop.py` | Error analysis prompt injection | ✅ |
| `jagabot/skills/error-analysis/SKILL.md` | New skill pack | ✅ |
| `tests/test_loop_duplicate_detection.py` | New tests | ✅ |
| `fix_agent_loop_behavior.md` | Documentation | ✅ |

---

## Testing

```bash
# Run tests
python3 -m pytest tests/test_loop_duplicate_detection.py -v

# Expected output:
# test_duplicate_command_threshold PASSED
# test_different_commands_not_blocked PASSED
# test_error_analysis_prompt_content PASSED
```

---

## Migration Notes

- **No breaking changes** - existing functionality preserved
- **Forward-looking** - only affects new tool executions
- **No config changes needed** - works automatically
- **Skills auto-loaded** - error-analysis skill is marked as "always" active

---

## Future Enhancements (Not Implemented)

1. **Exec-specific circuit breaker** - Stricter limits for `exec` tool
2. **Causal tracer loop detection** - Detect repetition patterns in audit layer
3. **Progress tracking** - Verify each retry makes progress toward fix

---

## Related Documentation

- Full analysis: `fix_agent_loop_behavior.md`
- Skill protocol: `jagabot/skills/error-analysis/SKILL.md`
- Code location: `jagabot/agent/loop.py` (lines 475, 524-533)
