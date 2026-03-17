🎯 SCOPE: Debug 20-Iteration Limit Bug in Debate System

---

🚨 BUG REPORT

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🔴 CRITICAL BUG: 20-ITERATION LIMIT REACHED              ║
║                                                              ║
║   Command: "Should Malaysia implement carbon tax?"         ║
║   Result: "Reached 20 iterations without completion"       ║
║   Status: ❌ DEBATE FAILED TO COMPLETE                      ║
║                                                              ║
║   Pattern: This is the SAME issue we fixed before          ║
║            but it's BACK!                                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

📋 KNOWN HISTORY

Date Issue Fix Status
Mar 11 Auto-reflection loop Removed forced "Reflect..." prompts ✅ Fixed
Mar 11 Heartbeat infinite loop Cooldown + max_iterations=3 ✅ Fixed
Mar 12 Subagent result pipeline Added timeouts + verification ✅ Fixed
NOW 20-iteration limit in debate ??? ❌ BACK

---

🔍 SUSPECTED ROOT CAUSES

```
┌─────────────────────────────────────────────────────────────┐
│                    HYPOTHESES                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. RECURSIVE TOOL CALLING                                  │
│     • Agent keeps calling tools without completing         │
│     • Each call consumes an iteration                      │
│     • Hits 20 limit before finishing                       │
│                                                              │
│  2. SUBAGENT STUCK                                          │
│     • Subagent spawned but never completes                 │
│     • Main agent waits indefinitely                        │
│     • Iteration counter still increments?                  │
│                                                              │
│  3. JUSTIFICATION LOOP                                      │
│     • New tool justification requirement causing loop      │
│     • Agent keeps refining justifications                 │
│                                                              │
│  4. TIMEOUT NOT HONORED                                     │
│     • 300s timeout should prevent this                     │
│     • Maybe not being applied to debate subagents?         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

📊 EVIDENCE NEEDED

```bash
# Check logs for this specific debate attempt
grep -A20 -B20 "20 iterations" /root/.jagabot/service.log

# Check subagent activity during that time
grep -i "subagent.*carbon tax" /root/.jagabot/service.log

# Check tool calls during the failed debate
grep -i "tool call" /root/.jagabot/service.log | grep -A5 -B5 "carbon tax"

# Check if any subagents completed
grep -i "completed successfully" /root/.jagabot/service.log | tail -20

# Check iteration count tracking
grep -i "iteration" /root/.jagabot/service.log | tail -20
```

---

🛠️ TASKS FOR COPILOT

TASK 1: DIAGNOSE THE LOOP

```python
# Trace execution path
- When does iteration counter increment?
- What triggers each iteration?
- Why does it reach 20 without completion?
- Are subagents actually running?
```

TASK 2: CHECK TIMEOUT IMPLEMENTATION

```python
# Verify 300s timeout is being applied
- Is it in subagent spawn?
- Is it in debate orchestrator?
- Is it being ignored?
```

TASK 3: REVIEW TOOL JUSTIFICATION IMPACT

```python
# Could justification requirement cause loops?
- Does agent keep refining justifications?
- Is there a max attempts for justification?
```

TASK 4: FIX THE BUG

Option A: Increase iteration limit for debates

```python
# In debate_orchestrator.py
def run_debate(self):
    # Debates need more iterations than simple tasks
    self.max_iterations = 30  # Instead of 20
```

Option B: Add debate-specific timeout

```python
# In spawn_subagent for debate tasks
worker = spawn_subagent(
    task=debate_task,
    timeout=300,  # 5 minutes
    max_iterations=30,  # Override global limit
    label="debate_worker"
)
```

Option C: Implement heartbeat for long-running tasks

```python
# Periodic status updates
def run_debate_with_heartbeat(self):
    iterations = 0
    while iterations < self.max_iterations:
        # Do one round of debate
        result = self.run_one_round()
        iterations += 1
        
        # Send heartbeat to user
        if iterations % 3 == 0:
            self.send_heartbeat(f"Round {iterations//3} complete...")
        
        if result.complete:
            return result
    
    return {"error": "Debate timed out", "partial_results": self.partial_results}
```

Option D: Fix root cause - find why it's looping

```python
# Add detailed iteration logging
def _process_message(self, message, iteration):
    print(f"🔄 Iteration {iteration}: Processing message...")
    # ... existing code ...
    if iteration > self.max_iterations:
        print(f"❌ Hit max iterations ({self.max_iterations})")
        # Save partial results before failing
        self.save_partial_results()
```

---

📋 IMPLEMENTATION PLAN

```yaml
Phase 1 (10 min): DIAGNOSE - Get logs and identify loop source
Phase 2 (5 min): DECIDE - Which fix approach to take
Phase 3 (15 min): IMPLEMENT - Apply fix
Phase 4 (10 min): TEST - Run carbon tax debate again
Phase 5 (5 min): VERIFY - Check logs for completion
```

---

✅ SUCCESS CRITERIA

Criteria Target
Debate completes ✅ No "20 iterations" error
Tool justification ✅ Still present (8/8 tools)
Cost tracking ✅ Under $0.01
Duration < 5 minutes

---

🚀 ARAHAN UNTUK COPILOT

```
Copilot,

Debug 20-iteration limit bug in debate system.

1. First, DIAGNOSE by getting logs for the failed carbon tax debate
2. IDENTIFY why iterations are being consumed without completion
3. PROPOSE fix (increase limit, better timeout, or loop detection)
4. IMPLEMENT fix
5. TEST with "Should Malaysia implement carbon tax?"

The system was working before - this regression needs immediate fix.
```
