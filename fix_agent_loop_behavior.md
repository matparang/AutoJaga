# Fix: Agent Loop Repetition Problem

## Problem Summary

Agent gets stuck in a loop of re-running the same failing command instead of:
1. Analyzing the error
2. Reading source files
3. Making code changes to fix the issue

### Example from User Report
```
AssertionError: Expected 100, got 99
```
Agent response: Re-runs the same `exec` command → Same error → Repeat

## Root Cause Analysis

### Current Safeguards (Already Implemented)

| Safeguard | Location | Threshold | Action |
|-----------|----------|-----------|--------|
| Duplicate command detection | `loop.py:438-450` | 3 identical commands | Warning message |
| Circuit breaker | `loop.py:452-464` | 3 consecutive failures | Skip tool, suggest alternatives |
| Audit loop retries | `auditor.py` | 2 retries | Feedback to LLM |

### Why They're Not Working

1. **Duplicate detection uses hash of args** - If the command string is identical, it triggers. But the warning is soft ("This is not advancing the task") and the agent can still continue.

2. **Circuit breaker only trips after 3 consecutive failures** - The agent can interleave other commands between failures to reset the counter.

3. **No "error analysis" requirement** - When a tool fails, there's no强制 (mandatory) step to read/analyze before retrying.

4. **LLM doesn't understand the error** - The error message is passed back, but without explicit instructions to "read the source file first", the LLM may just retry.

## Solutions

### Solution 1: Add "Error Analysis" Protocol (RECOMMENDED)

**File to modify:** `jagabot/agent/loop.py`

**Change:** When a tool fails, inject a mandatory analysis step before allowing retry.

```python
# In _run_agent_loop, after tool failure:
if isinstance(result, str) and result.startswith("Error"):
    # Inject mandatory analysis prompt
    analysis_prompt = (
        f"\n\n⚠️ ERROR ANALYSIS REQUIRED:\n"
        f"Tool '{tool_call.name}' failed with:\n{result}\n\n"
        "BEFORE retrying, you MUST:\n"
        "1. Read the relevant source file(s) to understand the error\n"
        "2. Explain WHY the error occurred\n"
        "3. Propose a specific fix\n"
        "4. THEN execute the fix (not just re-run the same command)\n"
    )
    messages = self.context.add_tool_result(
        messages, tool_call.id, tool_call.name, result + analysis_prompt,
    )
```

### Solution 2: Reduce Duplicate Threshold

**File to modify:** `jagabot/agent/loop.py`

**Change:** Reduce from 3 to 2 identical commands before hard block.

```python
# Line 447: Change from >= 3 to >= 2
if _duplicate_commands[cmd_key] >= 2:  # Was: >= 3
    result = (
        f"🛑 DUPLICATE COMMAND BLOCKED: You have run '{tool_call.name}' "
        f"with identical arguments {_duplicate_commands[cmd_key]} times. "
        f"This is not advancing the task.\n\n"
        f"REQUIRED: Read the error message, analyze the source code, "
        f"and propose a DIFFERENT approach.\n"
        f"Available tools: {', '.join(t['function']['name'] for t in self.tools.get_definitions())}"
    )
```

### Solution 3: Add "Read File First" Skill for Errors

**File to create:** `jagabot/skills/error-analysis/SKILL.md`

```markdown
# Error Analysis Protocol

When ANY tool fails with an error:

## Step 1: STOP
Do NOT re-run the same command.

## Step 2: READ
Use `read_file` to examine:
- The file mentioned in the error traceback
- Line numbers referenced in the error
- Related configuration files

## Step 3: ANALYZE
Explain in your own words:
- What the error means
- Why it occurred
- What specific change is needed

## Step 4: FIX
Execute a DIFFERENT command that:
- Modifies the source code, OR
- Adjusts test data, OR
- Changes the approach entirely

## Example

❌ WRONG:
```
exec({"command": "python3 app.py"})  # Failed
exec({"command": "python3 app.py"})  # Same command - BLOCKED
```

✅ CORRECT:
```
exec({"command": "python3 app.py"})  # Failed: Expected 100, got 99
read_file({"absolute_path": "/path/to/app.py", "offset": 100, "limit": 20})
# Analysis: Line 107 expects 100 items but data only has 99
edit({"file_path": "/path/to/app.py", "old_string": "...", "new_string": "..."})
exec({"command": "python3 app.py"})  # Now passes
```
```

### Solution 4: Add Circuit Breaker for `exec` Tool Specifically

**File to modify:** `jagabot/agent/loop.py` or `jagabot/agent/tools/shell.py`

**Change:** Add stricter limits for `exec` tool since it's most prone to loops.

```python
# Add to _run_agent_loop:
_EXEC_TOOL_FAILURES = 0
_MAX_EXEC_FAILURES = 2

if tool_call.name == "exec" and isinstance(result, str) and result.startswith("Error"):
    _EXEC_TOOL_FAILURES += 1
    if _EXEC_TOOL_FAILURES >= _MAX_EXEC_FAILURES:
        result = (
            f"🛑 EXEC TOOL BLOCKED: The exec command has failed {_EXEC_TOOL_FAILURES} times.\n\n"
            f"REQUIRED ACTION:\n"
            f"1. Use `read_file` to examine the error location\n"
            f"2. Analyze WHY the command failed\n"
            f"3. Use `edit` or `write_file` to fix the code\n"
            f"4. THEN re-run exec (with a DIFFERENT approach if needed)\n"
        )
else:
    _EXEC_TOOL_FAILURES = 0  # Reset on success
```

### Solution 5: Enhance Auditor to Detect Loop Patterns

**File to modify:** `jagabot/core/auditor.py` or `jagabot/core/causal_tracer.py`

**Change:** Detect when the same tool is called with same args across iterations.

```python
# In CausalTracer:
def verify_claims(self, content: str) -> AuditResult:
    # Check for repeated tool calls without progress
    tool_sequence = [(e.tool_name, e.result_text[:100]) for e in self._history[-5:]]
    
    # Detect repetition pattern
    if len(tool_sequence) >= 4:
        last_3 = tool_sequence[-3:]
        if all(t[0] == last_3[0][0] for t in last_3):  # Same tool 3x
            if all(t[1] == last_3[0][1] for t in last_3):  # Same result
                return AuditResult(
                    approved=False,
                    feedback=(
                        "🛑 LOOP DETECTED: You've called the same tool 3 times "
                        "with the same result. This is a loop.\n\n"
                        "REQUIRED: Change your approach. Read files, analyze errors, "
                        "and propose a DIFFERENT solution."
                    )
                )
    return AuditResult(approved=True, feedback=None)
```

## Recommended Implementation Order

```
Phase 1 (Quick Win) - ✅ IMPLEMENTED:
  → Solution 2: Reduce duplicate threshold (loop.py line 475)
  → Solution 1: Add error analysis prompt (loop.py lines 524-533)
  → Solution 3: Create error-analysis skill pack (jagabot/skills/error-analysis/SKILL.md)

Phase 2 (Behavioral) - PENDING:
  → Solution 4: Add exec-specific circuit breaker

Phase 3 (Advanced) - PENDING:
  → Solution 5: Enhance causal tracer for loop detection
```

## Testing

After implementing, test with:

```python
# Test case: Intentional failing command
# 1. Run a command that fails (e.g., assertion error)
# 2. Agent should NOT re-run same command 3x
# 3. Agent SHOULD read file, analyze, and fix

# Expected behavior:
# exec() → fails
# read_file() → analyzes
# edit() → fixes
# exec() → passes
```

## Files Modified

| File | Lines | Change Type | Status |
|------|-------|-------------|--------|
| `jagabot/agent/loop.py` | 475 | Duplicate threshold 3→2 | ✅ Done |
| `jagabot/agent/loop.py` | 524-533 | Error analysis prompt injection | ✅ Done |
| `jagabot/skills/error-analysis/SKILL.md` | New file | Error analysis skill pack | ✅ Done |
| `jagabot/core/causal_tracer.py` | TBD | Loop detection | Pending |

## Migration Notes

- Existing sessions: No impact (changes are forward-looking)
- Tool behavior: More restrictive, but prevents wasted iterations
- User experience: Faster resolution (less looping)
