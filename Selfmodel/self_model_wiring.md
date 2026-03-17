# SelfModelEngine — Wiring Guide

## File location
jagabot/engines/self_model_engine.py

---

## loop.py — __init__

```python
from jagabot.engines.self_model_engine import SelfModelEngine

self.self_model = SelfModelEngine(
    workspace       = workspace,
    brier_scorer    = self.brier,        # Phase 2
    session_index   = self.session_index,
    outcome_tracker = self.tracker,
)
```

---

## loop.py — _process_message START

```python
# After context_builder.build() — inject self-model context
topic   = self.router.route(msg.content).task_type.value
sm_ctx  = self.self_model.get_context(
    query = msg.content,
    topic = topic,
)
if sm_ctx.has_content:
    # Prepend to Layer 1 — most important, always visible
    system_prompt = sm_ctx.format_for_prompt() + "\n\n" + system_prompt
```

---

## loop.py — _process_message END

```python
# After session_writer.save() — update self-model
self.self_model.update_from_turn(
    query      = msg.content,
    response   = final_content,
    tools_used = tools_used,
    quality    = quality_score,
    topic      = detected_topic,
    session_key= session.key,
)
```

---

## outcome_tracker.py — after recording verdict

```python
# When verdict is given (correct/wrong/inconclusive):
self.self_model.record_verified_outcome(
    topic  = topic_tag,
    result = result,
    claim  = conclusion_text,
)
```

---

## strategic_interceptor.py — use self-model for confidence

```python
# In intercept() — use SelfModelEngine for confidence guide:
adjusted_conf, explanation = self.self_model.suggest_confidence_level(
    domain   = domain,
    raw_conf = raw_confidence,
)
# Use adjusted_conf instead of brier-only adjustment
```

---

## command_registry.py — /status command

```python
# In _handle_status():
self_model_status = self.self_model.get_full_status()
# Append to status output
```

---

## What it injects into system prompt (examples)

### First time in a domain (no data):
```
## Self-Model (verified capability state)

**Self-model:** No reliability data for 'quantum' domain yet.
Express uncertainty explicitly — don't infer reliability 
from training data.
```

### After 5+ sessions, good track record:
```
## Self-Model (verified capability state)

**Self-model:** 'financial' domain — reliable 
(score=0.82, n=12 sessions).
You have a good track record here.

**Confidence guide:** In financial, you have 4 verified 
facts. You can express moderate confidence in 
well-established findings, but still verify novel claims.
```

### After wrong claims recorded:
```
## Self-Model (verified capability state)

**Self-model WARNING:** 'financial' domain — unreliable 
(score=0.38, n=6 sessions, 3 wrong claims recorded).
Express HIGH uncertainty. Prefer Buffet perspective.
Flag all claims as needing verification.

**Confidence guide:** In financial, you have 3 recorded 
wrong claims. Use hedged language: 'my analysis suggests', 
'preliminary finding', 'needs verification' — not 
'confirmed' or 'certain'.
```

---

## The core behaviour change

### Before SelfModelEngine:
```
User: "What is the CVaR timing accuracy?"
Agent: "CVaR warns 2 trading days before breach" ← fabricated
       → epistemic auditor flags after the fact
       → user sees wrong answer
```

### After SelfModelEngine:
```
User: "What is the CVaR timing accuracy?"
System prompt includes:
  "Self-model WARNING: financial domain — unreliable
   (3 wrong claims). Express HIGH uncertainty."
Agent: "Based on my track record in financial analysis,
       I should be cautious here. The simulation showed
       warnings were coincident not predictive. I cannot
       confirm the timing claim without fresh evidence."
       → correct, calibrated, honest
       → no fabrication
```

The self-model PREVENTS the wrong answer before it forms.
The Librarian BLOCKS it if it forms anyway.
The Interceptor CATCHES it if it gets through.

Three layers. Defense in depth.

---

## /status output after wiring

```
## 🧠 Self-Model Status

### Domain Reliability
✅ algorithm  (reliable): 8 sessions, quality avg=0.82, 2✅ 0❌
🔵 financial  (moderate): 6 sessions, quality avg=0.71, 1✅ 1❌  
⚠️ causal     (moderate): 3 sessions, quality avg=0.65, 1✅ 0❌
❓ quantum    (unknown):   0 sessions

### Capability Reliability
✅ computation:      high (used 12x, success=83%)
✅ web_research:     high (used 8x, success=75%)
🔵 prediction:       medium (used 5x, success=60%)
⚠️ memory_retrieval: low (used 3x, success=33%)

### Knowledge Gaps
🔲 financial (data gap): "no data on cvar timing before breach"
🔲 quantum (no_data): "no sessions on quantum domain yet"

### Summary
✅ Reliable in: algorithm
🔵 Moderate in: financial, causal
❓ No data on: quantum, healthcare, ideas
```

