# Wiring: MemoryOutcomeBridge + ConnectionDetector
# Add these to loop.py and outcome_tracker.py

---

## loop.py — __init__ additions

```python
from jagabot.agent.memory_outcome_bridge import MemoryOutcomeBridge
from jagabot.agent.connection_detector   import ConnectionDetector

self.mem_bridge = MemoryOutcomeBridge(workspace, tool_registry)
self.connector  = ConnectionDetector(workspace, tool_registry)
```

---

## loop.py — _process_message (FIRST message)

```python
# After session startup reminder, add connection detection:
if self._first_message:
    connections = self.connector.detect(
        current_query=msg.content,
        session_key=session.key,
    )
    if connections.has_insights:
        # Inject as system note — agent sees connections
        self._inject_system_note(
            connections.format_for_context()
        )
        # Also show user-facing message
        chat_log.add_system(
            connections.format_for_user()
        )
    self._first_message = False
```

---

## outcome_tracker.py — after recording verified outcome

```python
# Add to record_outcome() after meta_learning call:
from jagabot.agent.memory_outcome_bridge import MemoryOutcomeBridge

# Wire bridge at __init__:
self.bridge = MemoryOutcomeBridge(workspace, tool_registry)

# In record_outcome() after result determined:
self.bridge.on_outcome_verified(
    conclusion  = conclusion_text,
    result      = result,          # "correct"|"wrong"|"partial"
    session_key = session_key,
    topic_tag   = topic_tag,
    evidence    = evidence,
)
```

---

## context_builder.py — inject wrong conclusions guard

```python
# In build() after Layer 1:
wrong_guard = self.mem_bridge.inject_wrong_conclusions_guard()
if wrong_guard:
    parts.insert(1, wrong_guard)  # inject after core identity
    tokens += self._estimate_tokens(wrong_guard)
```

---

## What happens after wiring

Session flow with both components active:

```
New session starts
        ↓
ConnectionDetector.detect(query)
        ↓
[if past research found]
"💡 You researched healthcare 3 days ago.
 Link: Causal inference is critical for 
 clinical trial analysis.
 Want me to build on those findings?"
        ↓
Agent answers query
        ↓
OutcomeTracker extracts conclusion
        ↓
[later session — user verifies]
"that quantum finding was correct"
        ↓
MemoryOutcomeBridge.on_outcome_verified()
        ↓
MEMORY.md: "quantum reduces drug discovery [✅ VERIFIED CORRECT]"
Fractal node: confidence +0.20
HISTORY.md: OUTCOME_VERIFIED | ✅ VERIFIED CORRECT
K1 Bayesian: record_outcome(actual=True)
        ↓
Next session on quantum topic:
ConnectionDetector finds this verified finding
Surfaces it with "(verified correct)" label
Agent builds on trusted knowledge
```

---

## Memory health check (call anytime)

```python
# Ask agent: "show memory health"
# Agent calls:
summary = self.mem_bridge.get_verification_summary()
# Returns honest: {"total": 5, "correct": 3, "wrong": 1, ...}
# NOT fabricated numbers
```

