# CuriosityEngine + ConfidenceEngine — Wiring Guide

---

## File locations
jagabot/engines/curiosity_engine.py
jagabot/engines/confidence_engine.py

---

## loop.py — __init__

```python
from jagabot.engines.curiosity_engine  import CuriosityEngine
from jagabot.engines.confidence_engine import ConfidenceEngine

self.curiosity = CuriosityEngine(
    workspace       = workspace,
    self_model      = self.self_model,
    session_index   = self.session_index,
    connection_det  = self.connector,
    outcome_tracker = self.tracker,
)

self.confidence_engine = ConfidenceEngine(
    workspace    = workspace,
    brier_scorer = self.brier,
    self_model   = self.self_model,
)
```

---

## loop.py — _process_message START (first message)

```python
if self._first_message:
    # Curiosity suggestions
    suggestions = self.curiosity.get_session_suggestions(
        current_query = msg.content,
        session_key   = session.key,
    )
    if suggestions.has_suggestions:
        # Inject into agent context
        self._inject_system_note(
            suggestions.format_for_agent()
        )
        # Show user-facing suggestions
        # (only if score >= 0.6 — format_for_user handles this)
        user_note = suggestions.format_for_user()
        if user_note:
            # Prepend to response or show as system message
            self._pending_curiosity_note = user_note
    self._first_message = False
```

---

## loop.py — _process_message END

```python
# Annotate response with confidence structure
final_content = self.confidence_engine.annotate_response(
    response   = final_content,
    topic      = detected_topic,
    tools_used = tools_used,
    exec_output= exec_outputs_this_turn,
)

# Record exploration for curiosity engine
self.curiosity.record_exploration(
    topic    = detected_topic,
    query    = msg.content,
    quality  = quality_score,
    findings = len(extracted_facts),
)
```

---

## outcome_tracker.py — after verdict recorded

```python
# Feed confidence engine with claim outcome
self.confidence_engine.record_claim_outcome(
    claim         = conclusion_text,
    topic         = topic_tag,
    correct       = (result == "correct"),
    level_at_time = ConfidenceLevel.MODERATE,  # or actual level
)

# Feed curiosity engine — gap resolved if correct
if result == "correct":
    # Mark any pending gap for this topic as explored
    self.curiosity.record_exploration(
        topic    = topic_tag,
        query    = conclusion_text[:100],
        quality  = 1.0,
        findings = 1,
    )
```

---

## session_writer.py — feed CuriosityEngine from SelfModelEngine

```python
# When SelfModelEngine detects a knowledge gap:
# (in update_from_turn)
for gap in detected_gaps:
    self.curiosity.add_gap(
        topic       = gap.topic,
        description = gap.description,
        gap_type    = gap.gap_type,
        priority    = gap.priority,
    )
```

---

## command_registry.py — /status additions

```python
curiosity_status = self.curiosity.format_status()
confidence_status = self.confidence_engine.format_status()
```

---

## What the user sees after wiring

### Session start (CuriosityEngine):
```
💡 Research opportunities I noticed:

→ Cross-domain link: Quantum simulation could 
  accelerate drug discovery
  You've researched both sides — want me to connect them?

→ Open question: CVaR timing accuracy (unverified, 3 days old)
  This came up in a past session and wasn't resolved.

*Say 'explore this' to investigate any of these.*
```

### Response annotation (ConfidenceEngine):
```
[agent response about CVaR timing]

*⚠️ Confidence note: Low calibration in financial domain
(trust=0.38). Treat claims as preliminary until verified
by real outcomes.*

*🔬 Epistemic uncertainty present — this gap is reducible
with more data. Consider: run more simulations to verify.*
```

### /status output:

```
**CuriosityEngine**

Knowledge gaps: 7
Explored:       2 (29%)
Unexplored:     5
Top targets: quantum+healthcare, CVaR timing, causal+financial

**ConfidenceEngine**

✅ verified    actual=96%  target=95%  gap=+1%
✅ high        actual=82%  target=80%  gap=+2%
⚠️ moderate    actual=58%  target=65%  gap=-7%
⚠️ low         actual=30%  target=40%  gap=-10%

Uncertainty types tracked:
  Aleatory:   inherent randomness — use ranges
  Epistemic:  knowledge gaps — get more data
```

---

## How the three engines work together

```
SelfModelEngine detects gap:
  "No data on quantum domain"
        ↓
CuriosityEngine scores it:
  curiosity_score = 0.72 (high — bridges to healthcare)
        ↓
Next session start:
  "💡 You've researched healthcare but not quantum —
   quantum simulation could accelerate drug discovery"
        ↓
User says "explore this"
        ↓
Agent researches, makes claims
        ↓
ConfidenceEngine annotates:
  "Epistemic uncertainty — no verified outcomes yet
   in quantum domain. Flag as preliminary."
        ↓
User gives verdict later
        ↓
CuriosityEngine marks gap as explored
SelfModelEngine updates quantum domain reliability
ConfidenceEngine records claim outcome
BrierScorer updates trust score
        ↓
Loop complete — three engines fed one outcome
```

