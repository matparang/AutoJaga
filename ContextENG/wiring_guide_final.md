# Complete Wiring Guide
# All files from today's session + where they go

---

## File Map

```
jagabot/
├── agent/
│   ├── context_builder.py    ← NEW: dynamic context assembly
│   ├── session_index.py      ← NEW: session discovery
│   ├── session_writer.py     ← UPGRADE: v2 with quality scoring
│   ├── outcome_tracker.py    ← NEW: loop closure
│   ├── task_router.py        ← NEW: compute/idea/verify routing
│   ├── idea_tracker.py       ← NEW: idea outcome tracking
│   └── prompts/
│       └── ideation.py       ← NEW: tri/quad ideation prompts
├── core/
│   ├── epistemic_auditor.py  ← PATCH: fix false positives
│   └── behavior_monitor.py   ← PATCH: suppress explicit tool warnings
├── engines/
│   └── engine_improver.py    ← NEW: cross-kernel improvement
├── cli/
│   └── tui.py                ← NEW: full terminal UI
└── /root/.jagabot/
    ├── AGENTS.md              ← SINGLE SOURCE OF TRUTH
    └── core_identity.md       ← NEW: 300-token Layer 1 context
```

---

## loop.py — Complete Wiring Summary

Add to __init__:
```python
from jagabot.agent.context_builder import ContextBuilder
from jagabot.agent.session_index   import SessionIndex
from jagabot.agent.session_writer  import SessionWriter
from jagabot.agent.outcome_tracker import OutcomeTracker
from jagabot.agent.task_router     import TaskRouter
from jagabot.engines.engine_improver import EngineImprover

self.ctx_builder    = ContextBuilder(workspace, agents_md_path)
self.session_index  = SessionIndex(workspace)
self.writer         = SessionWriter(workspace, tool_registry)
self.tracker        = OutcomeTracker(workspace)
self.router         = TaskRouter()
self.engine_improver= EngineImprover(workspace, tool_registry)
self._first_message = True
self._session_count = 0
```

Add to _process_message START:
```python
# Session startup reminder (first message only)
if self._first_message:
    reminder = self.session_index.get_startup_reminder()
    if reminder:
        self._inject_system_note(reminder)
    # Check pending outcomes
    pending = self.tracker.get_session_reminder()
    if pending:
        self._inject_system_note(pending)
    self._first_message = False

# Dynamic context (replaces static system prompt)
system_prompt = self.ctx_builder.build(
    query=msg.content,
    session_key=session.key,
    tools_available=list(self.tool_registry.keys()),
)

# Task routing
decision = self.router.route(msg.content)
```

Add to _process_message END (after session_writer.save):
```python
# Extract conclusions for loop closure
self.tracker.extract_and_save(
    content=final_content,
    query=msg.content,
    session_key=session.key,
)

# Update session index
self.session_index.update(
    session_key=session.key,
    query=msg.content,
    content=final_content,
    quality=quality_score,
    tools_used=tools_used,
    pending_outcomes=self.tracker.get_pending_count(),
)

# Run improvement cycle every 10 sessions
self._session_count += 1
if self._session_count % 10 == 0:
    self.engine_improver.run_improvement_cycle()
```

---

## Apply Order (lowest risk first)

1. core_identity.md        → copy to /root/.jagabot/
2. epistemic_auditor patch → fix false rejections immediately
3. session_writer v2       → already partially wired
4. session_index           → wire into loop.py
5. context_builder         → replace static system prompt
6. outcome_tracker         → wire into session_writer
7. engine_improver         → wire into loop.py
8. task_router             → wire into loop.py
9. tui.py                  → wire _call_agent() to real agent

---

## What Each File Fixes

| File | Fixes |
|---|---|
| core_identity.md | Bloated system prompt, ignored instructions |
| context_builder.py | Context fills too fast, irrelevant memory |
| session_index.py | Can't find which session to continue |
| session_writer v2 | Outputs not saved, MetaLearning not fed |
| outcome_tracker.py | Self-improvement loop never closes |
| task_router.py | tri/quad used for wrong task types |
| epistemic_auditor v2 | False rejections on legal/illustrative numbers |
| engine_improver.py | K1/K3 islands, MetaLearning no patterns |
| tui.py | Basic CLI, no visibility into agent state |

