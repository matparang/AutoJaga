🎯 SCOPE PROMPT UNTUK COPILOT - COMPREHENSIVE AUDIT & "GOD CODE" DETECTION

---

```
# 🚨 URGENT: AUTOJAGA COMPREHENSIVE FORENSIC AUDIT

## SITUATION
AutoJaga has undergone 4+ fix sessions over 8+ hours:
1. autojagafix - Memory JSON parsing
2. jagafilefix - Workspace enforcement
3. Eaudit - WriteFileTool fsync + verification
4. NEaudit - Memory consolidation max_tokens

**YET THE PROBLEM PERSISTS:**
- Agent claims files are created (post_final_fix.txt)
- WriteFileTool logs show NO tool call
- Files DON'T exist on disk
- Memory consolidation STILL fails (logs show truncated JSON)
- Each fix creates 2-3 new issues

## SUSPECTED: "GOD CODE" / ARCHITECTURE CANCER

We suspect there is a fundamental architectural flaw - "God Code" that:
- Is too complex to understand
- Has multiple responsibilities
- Contains hidden bugs
- Causes cascading failures
- Makes every fix introduce new bugs

## LOCATIONS TO AUDIT

```

/root/nanojaga/
├── jagabot/
│   ├── agent/
│   │   ├── loop.py              # Main agent loop (SUSPECTED GOD CODE)
│   │   ├── subagent.py
│   │   └── orchestrator.py
│   ├── tools/
│   │   ├── write_file.py        # Already fixed
│   │   ├── read_file.py
│   │   ├── edit_file.py         # Already fixed
│   │   ├── cron.py              # SUSPECTED BROKEN
│   │   └── memory_fleet.py      # Memory system
│   ├── core/
│   │   ├── memory.py
│   │   └── consolidation.py     # Memory consolidation (PARTIALLY FIXED)
│   └── main.py
└── workspace_enforcer.py

```

## TASKS FOR COPILOT

### TASK 1: "GOD CODE" DETECTION
Analyze each major file and identify if it suffers from:

```python
# SIGNS OF GOD CODE:
- Lines > 500 (monster file)
- Functions > 100 lines
- Too many responsibilities (does everything)
- Deep nesting (>4 levels)
- Too many dependencies
- No clear single responsibility
- Complex error handling
- Mix of concerns (UI + logic + data + tools)
```

TASK 2: ARCHITECTURE MAPPING

Create a dependency graph showing:

· Which files depend on which
· Circular dependencies
· Dead code
· Unused imports
· Redundant code

TASK 3: CRITICAL BUG HUNT

Find specific bugs in:

loop.py (Main agent loop)

· Why does agent sometimes simulate vs execute?
· How are tool calls actually triggered?
· Where does the "verified on disk" message come from if no tool call?

cron.py

· Why are cron jobs never created?
· Is it using system cron or just simulation?
· Where are jobs stored?

memory consolidation

· Why does JSON still truncate after max_tokens fix?
· Is the LLM call actually using the new parameters?
· Where is the consolidation prompt?

tool execution path

· Trace exactly what happens when agent "calls" WriteFileTool
· Why do logs show some calls but not others?
· Is there a caching/memoization layer?

TASK 4: EVIDENCE GAP ANALYSIS

Compare:

· What agent CLAIMS in response vs
· What LOGS show vs
· What FILESYSTEM shows

Create a matrix for the last 5 interactions:

```
| Interaction | Claim | Log Entry | File Exists | Discrepancy |
|-------------|-------|-----------|-------------|-------------|
| post_final_fix.txt | ✅ Created | ❌ No log | ❌ No file | AGENT LIED |
| protocol_test.txt | ✅ Created | ✅ Log | ✅ File | TRUTH |
| test_20260312_0002.txt | ✅ Created | ✅ Log | ✅ File | TRUTH |
| Test_now.txt | ✅ Created | ❌ No log | ❌ No file | AGENT LIED |
```

TASK 5: ARCHITECTURE RECOMMENDATION

Based on findings, recommend:

1. REFACTOR - Which files need complete rewrite
2. REMOVE - Which files are dead/unused
3. SIMPLIFY - How to reduce complexity
4. ISOLATE - Which components can be separated
5. REBUILD - If starting fresh, what architecture?

DELIVERABLE FORMAT

```markdown
# AUTOJAGA COMPREHENSIVE AUDIT REPORT

## EXECUTIVE SUMMARY
[Overall health assessment]

## "GOD CODE" DETECTION
### loop.py - [PASS/FAIL] - [lines] - [assessment]
### [file2] - [PASS/FAIL] - [lines] - [assessment]
...

## ARCHITECTURE MAP
[ASCII diagram showing dependencies]

## CRITICAL BUGS FOUND
### BUG 1: [description]
- Location: [file:line]
- Impact: [HIGH/MEDIUM/LOW]
- Evidence: [log/file evidence]
- Fix: [recommendation]

### BUG 2: [description]
...

## EVIDENCE GAP MATRIX
[Table showing claim vs reality]

## HEALTH METRICS
- Total files: X
- God files: Y
- Circular dependencies: Z
- Dead code lines: W
- Test coverage: %

## FINAL RECOMMENDATION
### Option A: Salvage (if debt < 50%)
- Steps to fix
- Estimated time

### Option B: Partial Rewrite (if debt 50-70%)
- Which components to rewrite
- Which to keep

### Option C: Full Rewrite (if debt > 70%)
- New architecture proposal
- Estimated time
- Lessons from current system

## VERIFICATION STEPS
How to test each finding
```

URGENCY

CRITICAL - AutoJaga currently UNRELIABLE. Need definitive answer:

· Can it be saved?
· Or must we abandon?

Proceed with comprehensive audit.

```
