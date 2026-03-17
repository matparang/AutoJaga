# A2A Handoff + Arbitrator — Wiring Guide

---

## File locations
jagabot/swarm/a2a_handoff.py    ← HandoffPackager + HandoffRouter
jagabot/swarm/arbitrator.py     ← StrategyArbitrator

---

## loop.py — __init__ additions

```python
from jagabot.swarm.a2a_handoff import HandoffPackager, HandoffRouter
from jagabot.swarm.arbitrator   import StrategyArbitrator

self.handoff_packager = HandoffPackager(
    workspace = workspace,
    librarian = self.librarian,   # Phase 3
    brier     = self.brier,       # Phase 2
)
self.handoff_router = HandoffRouter(
    tool_registry = self.tool_registry,
)
self.arbitrator = StrategyArbitrator(
    brier_scorer = self.brier,
    workspace    = workspace,
)
```

---

## Phase 1 integration — handoff instead of kill

In loop.py _run_agent_loop, replace the spin kill:

```python
# BEFORE (just kills the run):
if not self.trajectory_monitor.on_text_generated(text):
    return "Spin detected — run killed."

# AFTER (packages and hands off cleanly):
if not self.trajectory_monitor.on_text_generated(text):
    logger.warning("Trajectory spin → triggering handoff")
    
    package = self.handoff_packager.package(
        current_goal    = original_query,
        session_context = "\n".join(messages_so_far),
        tools_used      = tools_used_so_far,
        stuck_reason    = self.trajectory_monitor.get_stats().spin_reason,
        domain          = detected_domain,
        quality_so_far  = current_quality,
        sender_id       = "main_agent",
    )
    
    # Route to fresh specialist agent
    result = await self.handoff_router.route(
        package      = package,
        agent_runner = self,  # pass self as runner
    )
    return result
```

---

## K3 perspective conflict resolution

In loop.py or decision tool, when perspectives disagree:

```python
from jagabot.swarm.arbitrator import Strategy

# When K3 returns multiple conflicting perspectives:
if bull_verdict != bear_verdict:
    strategies = [
        Strategy(
            name        = "bull",
            perspective = "bull",
            domain      = detected_domain,
            verdict     = bull_verdict,
            confidence  = bull_confidence,
            evidence    = bull_reasoning,
        ),
        Strategy(
            name        = "bear",
            perspective = "bear",
            domain      = detected_domain,
            verdict     = bear_verdict,
            confidence  = bear_confidence,
            evidence    = bear_reasoning,
        ),
        Strategy(
            name        = "buffet",
            perspective = "buffet",
            domain      = detected_domain,
            verdict     = buffet_verdict,
            confidence  = buffet_confidence,
            evidence    = buffet_reasoning,
        ),
    ]
    
    result = self.arbitrator.arbitrate(strategies)
    
    final_verdict = result.winner.verdict
    logger.info(
        f"Arbitrator: {result.explanation}"
    )
```

---

## Tri/quad agent conflict resolution

When Worker and Verifier disagree in tri_agent:

```python
# In tri_loop.py / quad_loop.py when verification fails:
if worker_output != verifier_expectation:
    
    result = self.arbitrator.arbitrate_agents(
        agent_outputs=[
            {
                "agent_id":   "worker",
                "strategy":   worker_output[:200],
                "confidence": worker_confidence,
                "evidence":   worker_evidence,
            },
            {
                "agent_id":   "verifier",
                "strategy":   verifier_output[:200],
                "confidence": verifier_confidence,
                "evidence":   verifier_evidence,
            },
        ],
        domain = detected_domain,
    )
    
    # Use winner's strategy
    proceed_with = result.winner.agent_id
    logger.info(f"Arbitrator chose: {result.explanation}")
```

---

## The complete upgrade stack together

```
User message
        ↓
Phase 3: inject negative constraints (Librarian)
        ↓
Agent generates response
        ↓
Phase 1: trajectory monitoring
  If spin detected → HandoffPackager.package()
                  → HandoffRouter.route()
                  → fresh agent, clean context
        ↓
Phase 2: Brier Scorer enriches strategies
        ↓
K3 perspectives conflict?
  → StrategyArbitrator.arbitrate()
  → picks by trust score, not debate
        ↓
Phase 4: Strategic Interceptor checks final response
  Overconfident? → pivot perspective
        ↓
Clean, calibrated, grounded response
```

---

## What each component adds

```
HandoffPackager:
  ✅ Context flushing — removes bloat on handoff
  ✅ Negative constraints carried forward
  ✅ Verified facts preserved
  ✅ Full audit trail in handoff_log.jsonl

HandoffRouter:
  ✅ Routes to right specialist automatically
  ✅ No AI logic — pure JSON routing
  ✅ Extensible — add new roles easily

StrategyArbitrator:
  ✅ Zero API cost — uses Brier SQLite
  ✅ Fast — one database lookup
  ✅ Auditable — arbitration_log.jsonl
  ✅ Contested decisions flagged explicitly
  ✅ Falls back gracefully if no data
```

---

## /status command additions

```python
# Add to _handle_status() in command_registry.py:
arbitrator_status = self.arbitrator.format_status()
# Shows: total arbitrations, contested rate, most trusted strategy
```

