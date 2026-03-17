# MemoryManager — Wiring Guide
# Drop-in upgrade over current grep-based memory

---

## File location
jagabot/memory/memory_manager.py

---

## loop.py — __init__

```python
from jagabot.memory.memory_manager import MemoryManager

self.memory_mgr = MemoryManager(workspace)
```

---

## loop.py — _process_message START

```python
# Replace current memory loading with MemoryManager
# (remove old grep-based memory loading)

memory_context = self.memory_mgr.get_context(
    query       = msg.content,
    session_key = session.key,
)
# Inject into system prompt via context_builder
```

---

## loop.py — _process_message END

```python
# After session_writer.save():
self.memory_mgr.store_turn(
    query      = msg.content,
    response   = final_content,
    tools_used = tools_used,
    quality    = quality_score,
    topic      = decision.task_type.value,
)
```

---

## context_builder.py — replace _load_relevant_memory()

```python
# In ContextBuilder.__init__:
from jagabot.memory.memory_manager import MemoryManager
self.memory_mgr = MemoryManager(workspace)

# Replace _load_relevant_memory() with:
def _load_relevant_memory(self, topic: str, query: str) -> str:
    return self.memory_mgr.get_context(
        query      = query,
        max_tokens = 250,
    )
```

---

## loop.py — context window near limit trigger

```python
# In ContextCompressor.should_auto_compact():
# When returning True, also flush important context:
self.memory_mgr.pre_compaction_flush(
    session_content = self._get_full_session_text(),
    session_key     = session.key,
)
```

---

## yolo.py — auto-generate skill after successful run

```python
# In YOLORunner.run() after session completes:
if session.total_elapsed > 0:
    quality = sum(
        1 for s in session.steps 
        if s.status == "done"
    ) / len(session.steps)
    
    self.memory_mgr.auto_generate_skill(
        task        = session.goal,
        steps       = [s.__dict__ for s in session.steps],
        quality     = quality,
        topic       = self._detect_topic(session.goal),
        session_key = session.session_id,
    )
```

---

## What improves immediately

| Before | After |
|---|---|
| grep MEMORY.md | FTS5 ranked search |
| All memory equally weighted | Recent memories rank higher |
| Redundant results | MMR deduplication |
| Context window fills → lose context | Pre-compaction flush saves it |
| Skills only in static SKILL.md | Auto-generated from YOLO runs |
| ALS.json manually maintained | Auto-updated from usage |

---

## Memory file structure after wiring

```
~/.jagabot/workspace/memory/
    MEMORY.md               ← unchanged (curated facts)
    HISTORY.md              ← unchanged (event log)
    memory_fts.db           ← NEW: FTS5 search index
    ALS.json                ← UPGRADED: user model auto-updated
    2026-03-15.md           ← NEW: today's daily note
    2026-03-14.md           ← NEW: yesterday's daily note
    session_index.json      ← existing (session discovery)
    pending_outcomes.json   ← existing (loop closure)
    bridge_log.json         ← existing (outcome verification)

~/.jagabot/workspace/skills/auto_generated/
    research_quantum_drug_discovery.md  ← NEW: auto-skill
    mental_health_llm_strategies.md     ← NEW: auto-skill
```

---

## Checking it works

```python
# In jagabot chat, type:
/status

# Agent should now call:
stats = self.memory_mgr.get_stats()
# Returns:
# {
#   "indexed_entries": 847,
#   "skill_documents": 3,
#   "daily_notes": 7,
#   "user_sessions": 24,
#   "top_topics": {"healthcare": 8, "research": 6, ...},
#   "db_size_kb": 124
# }
```

