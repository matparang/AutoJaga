# Harness Blueprint — Complete Wiring Guide
# All 4 phases wired into loop.py

---

## File locations

```
jagabot/core/trajectory_monitor.py   ← Phase 1
jagabot/kernels/brier_scorer.py      ← Phase 2
jagabot/core/librarian.py            ← Phase 3
jagabot/core/strategic_interceptor.py← Phase 4
```

---

## loop.py — Complete __init__ additions

```python
from jagabot.core.trajectory_monitor    import TrajectoryMonitor
from jagabot.kernels.brier_scorer       import BrierScorer
from jagabot.core.librarian             import Librarian
from jagabot.core.strategic_interceptor import StrategicInterceptor

# Phase 1 — Trajectory Monitor
self.trajectory_monitor = TrajectoryMonitor(
    max_steps_without_tool    = 5,
    max_total_steps           = 30,
    max_tokens_without_action = 800,
    log_dir                   = workspace / "memory",
)

# Phase 2 — Brier Scorer
self.brier = BrierScorer(
    db_path = workspace / "memory" / "brier.db"
)

# Phase 3 — Librarian
self.librarian = Librarian(
    workspace    = workspace,
    brier_scorer = self.brier,
)

# Phase 4 — Strategic Interceptor
self.interceptor = StrategicInterceptor(
    brier_scorer  = self.brier,
    tool_registry = self.tool_registry,
    workspace     = workspace,
)
```

---

## loop.py — _process_message (complete wiring)

```python
async def _process_message(self, msg):

    # ── START: Reset monitors ─────────────────────────────────────
    self.trajectory_monitor.reset()
    self.interceptor.reset_turn()
    
    # ── CONTEXT: Inject negative constraints (Phase 3) ───────────
    topic    = self.router.route(msg.content).task_type.value
    negative = self.librarian.get_constraints(topic)
    
    system_prompt = self.ctx_builder.build(
        query       = msg.content,
        session_key = session.key,
    )
    if negative:
        system_prompt = negative + "\n\n---\n\n" + system_prompt
    
    # ── GENERATION: Watch trajectory (Phase 1) ───────────────────
    # In your _run_agent_loop, wrap each text generation:
    # should_continue = self.trajectory_monitor.on_text_generated(
    #     text=chunk, has_tool_call=bool(tool_calls)
    # )
    # if not should_continue:
    #     inject = self.trajectory_monitor.get_intervention_message()
    #     # Add inject to next LLM call as system note
    
    # After each tool call:
    # self.trajectory_monitor.on_tool_called(tool_name)
    
    # ── INTERCEPT: Check calibration (Phase 4) ───────────────────
    result = self.interceptor.intercept(
        response    = final_content,
        query       = msg.content,
        tools_used  = tools_used,
        session_key = session.key,
    )
    
    if result.needs_pivot:
        # Re-run with pivot injection
        pivot_prompt = self.interceptor.build_rerun_prompt(
            original_query = msg.content,
            pivot_message  = result.pivot_message,
        )
        logger.info(
            f"Interceptor: pivoting from "
            f"{result.perspective_used} — {result.reason}"
        )
        # Re-run agent with pivot injected
        final_content = await self._run_with_injection(pivot_prompt)
    else:
        final_content = result.adjusted_response
    
    # ── RECORD: Feed Brier Scorer (Phase 2) ──────────────────────
    # Done in outcome_tracker.py when verdicts are given:
    # self.brier.record(
    #     perspective = perspective,
    #     domain      = topic,
    #     forecast    = predicted_prob,
    #     actual      = 1 if result == "correct" else 0,
    #     claim       = conclusion_text,
    # )
    
    # ── SAVE ─────────────────────────────────────────────────────
    self.writer.save(...)
    
    return OutboundMessage(content=final_content, ...)
```

---

## outcome_tracker.py — Feed Brier Scorer

```python
# In record_outcome() after recording to K1/K3:
if hasattr(self, 'brier_scorer') and self.brier_scorer:
    actual = 1 if result == "correct" else 0
    if result != "inconclusive":  # only record definitive outcomes
        self.brier_scorer.record(
            perspective = perspective or "general",
            domain      = topic_tag or "general",
            forecast    = predicted_prob or 0.7,
            actual      = actual,
            claim       = conclusion_text[:200],
            session_key = session_key,
        )
```

---

## context_builder.py — Use Librarian for Layer 2

```python
# In ContextBuilder.__init__:
from jagabot.core.librarian import Librarian
self.librarian = Librarian(workspace)

# In build(), add after Layer 1:
negative = self.librarian.get_constraints(topic)
if negative:
    parts.insert(1, negative)
    tokens += self._estimate_tokens(negative)
```

---

## What each phase fixes

```
Phase 1 — Trajectory Monitor:
  ✅ Fixes "narration instead of execution" bug
  ✅ Kills runs when agent spins > 5 steps without tool
  ✅ Provides thought:action ratio metric

Phase 2 — Brier Scorer:
  ✅ Tracks actual prediction accuracy per perspective
  ✅ Adjusts displayed confidence based on track record
  ✅ Shows honest calibration in /status command
  ✅ Grows more valuable with every verdict given

Phase 3 — Librarian:
  ✅ Prevents repeating known wrong conclusions
  ✅ Injects CVaR timing failure as hard constraint
  ✅ Blocks SSB hypothesis from being presented as confirmed
  ✅ Auto-updates as new failures are recorded

Phase 4 — Strategic Interceptor:
  ✅ Catches overconfident responses before user sees them
  ✅ Forces perspective pivot when trust < 50%
  ✅ Adjusts confidence numbers throughout response
  ✅ Re-runs with better perspective automatically
```

---

## Build order (lowest risk first)

```
Week 1:
  1. Phase 3 (Librarian) — 15 mins, already 80% done
     Just wire into context_builder.py
     Already have bridge_log.json with CVaR + SSB failures
     
  2. Phase 1 (Trajectory Monitor) — 30 mins
     Wire into _run_agent_loop
     Fixes narration bug immediately
     
Week 2:
  3. Phase 2 (Brier Scorer) — 45 mins
     Wire into outcome_tracker.py
     Needs more verdicts to become useful
     Gets better over time
     
  4. Phase 4 (Interceptor) — 1 hour
     Depends on Phase 2 having data
     Most powerful but least urgent
     Build after 10+ outcomes recorded
```

---

## Checking it works

After wiring Phase 1 — look for in logs:
```
WARNING | TrajectoryMonitor: SPIN DETECTED — steps_without_tool=5
```
That means it's working.

After wiring Phase 3 — check system prompt includes:
```
## ⚠️ VERIFIED FAILURES — Do NOT repeat these:
❌ DO NOT claim: "CVaR-based warning signaled margin risk 2 days before..."
```

After wiring Phase 2 + giving 3 more verdicts:
```
jagabot /status
→ shows Brier calibration table with real scores
```

After wiring Phase 4 — look for:
```
INFO | StrategicInterceptor: PIVOT triggered — bear/financial trust=0.40
```

