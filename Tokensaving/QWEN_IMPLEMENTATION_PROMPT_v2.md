# JAGABOT TOKEN REDUCTION — TAILORED IMPLEMENTATION PLAN
# Based on API_CALL_AUDIT_REPORT.md findings

You are implementing targeted token reduction fixes for jagabot.
The audit has already been completed. You have exact file names, line numbers,
and variable names. Follow each fix precisely. Read each file before editing it.

**Estimated savings: ~55,000 tokens/call → ~8,000 tokens/call (87% reduction)**

---

## CRITICAL CONTEXT FROM AUDIT

Before touching any file, understand these facts:

| Finding | Detail |
|---|---|
| Tools sent per call | **93 tools on EVERY call** via `self.tools.get_definitions()` (loop.py:936) |
| Tool token cost | 93 × ~400 = **~37,200 tokens/call** — 60% of total waste |
| Tool filtering code | Already EXISTS in `jagabot/agent/context_builder.py` lines 42–77 — just NOT wired |
| History | Grows **unbounded**, no compression anywhere |
| History token cost | **~20,000 tokens** after 50 turns (33% of total waste) |
| Main API call | `response = await self.provider.chat(...)` — loop.py line 934 |
| Tools line | `tools=self.tools.get_definitions()` — loop.py line 936 |
| Two context files | `context.py` = OLD (currently used), `context_builder.py` = NEW (NOT wired) |
| Memory wiring | `MemoryManager.get_context()` exists but NOT called in loop.py |

---

## PHASE 1 — Wire the Existing Tool Filtering (Highest ROI, ~30 min)

**THE BIGGEST WIN: `context_builder.py` already has the TOOL_RELEVANCE map
at lines 42–77. You just need to use it at the API call site.**

### Step 1a — Read these files first

```
jagabot/agent/loop.py              (focus: lines 916–960, the _run_agent_loop method)
jagabot/agent/context_builder.py   (focus: lines 42–77, the TOOL_RELEVANCE map)
jagabot/agent/tools/registry.py    (understand ToolRegistry.get_definitions())
```

### Step 1b — Create `jagabot/core/tool_filter.py` (new file)

```python
"""
jagabot/core/tool_filter.py
────────────────────────────
Wraps the existing TOOL_RELEVANCE map from context_builder.py and exposes
a single function: get_tools_for_query(query, all_tools) → filtered list.

This fixes loop.py:936 where ALL 93 tools are sent on every call.
"""

from __future__ import annotations
import os
from loguru import logger

# Pull in the existing relevance map from context_builder
# (it was built but never connected to the API call)
try:
    from jagabot.agent.context_builder import TOOL_RELEVANCE
    _HAS_RELEVANCE_MAP = True
except ImportError:
    TOOL_RELEVANCE = {}
    _HAS_RELEVANCE_MAP = False
    logger.warning("tool_filter: TOOL_RELEVANCE not found in context_builder — sending all tools")

# ── Always-on tools (sent regardless of topic) ───────────────────────────────
# Keep this list ≤ 3. These are tools the agent needs for basic orientation.
ALWAYS_SEND: set[str] = {
    "memory_fleet",
    "read_file",
    "self_model_awareness",
}

# ── Debug override ────────────────────────────────────────────────────────────
# Set JAGABOT_FULL_TOOLS=1 to bypass filtering (useful when debugging tool issues)
_FULL_TOOLS = os.getenv("JAGABOT_FULL_TOOLS", "0") == "1"

# ── Max tools to send per call ────────────────────────────────────────────────
MAX_TOOLS = int(os.getenv("JAGABOT_MAX_TOOLS", "8"))


def get_tools_for_query(query: str, all_tools: dict) -> list:
    """
    Return a filtered list of tool definitions for this query.

    Priority:
    1. JAGABOT_FULL_TOOLS=1  → send everything (debug)
    2. TOOL_RELEVANCE map    → send relevant tools + always-on
    3. Fallback              → send only ALWAYS_SEND tools
    """
    if _FULL_TOOLS:
        logger.warning(f"JAGABOT_FULL_TOOLS=1 — sending all {len(all_tools)} tools")
        return list(all_tools.values()) if hasattr(list(all_tools.values())[:1][0], '__iter__') \
               else all_tools.get_definitions() if hasattr(all_tools, 'get_definitions') \
               else list(all_tools)

    # Determine relevant tool names from the existing TOOL_RELEVANCE map
    relevant_names: set[str] = set(ALWAYS_SEND)

    if _HAS_RELEVANCE_MAP and TOOL_RELEVANCE:
        query_lower = query.lower()
        for keyword, tool_names in TOOL_RELEVANCE.items():
            if keyword in query_lower:
                relevant_names.update(tool_names)
                logger.debug(f"tool_filter: keyword='{keyword}' matched → adding {tool_names}")

    # Get definitions — handle both dict and ToolRegistry
    if hasattr(all_tools, 'get_definitions'):
        all_defs = {t['function']['name']: t for t in all_tools.get_definitions()}
    elif isinstance(all_tools, dict):
        all_defs = all_tools
    else:
        logger.warning("tool_filter: unrecognised tools type — sending all")
        return list(all_tools)

    # Filter to relevant names
    filtered = [
        tool_def for name, tool_def in all_defs.items()
        if name in relevant_names
    ]

    # Cap at MAX_TOOLS
    if len(filtered) > MAX_TOOLS:
        # Prioritise always-send, then take up to MAX_TOOLS
        always = [t for t in filtered if _tool_name(t) in ALWAYS_SEND]
        rest   = [t for t in filtered if _tool_name(t) not in ALWAYS_SEND]
        filtered = (always + rest)[:MAX_TOOLS]

    logger.debug(
        f"tool_filter: {len(filtered)}/{len(all_defs)} tools selected "
        f"for query='{query[:60]}...'" if len(query) > 60 else
        f"tool_filter: {len(filtered)}/{len(all_defs)} tools selected "
        f"for query='{query}'"
    )

    # Warn if relevant_names referenced tools not registered
    registered = set(all_defs.keys())
    missing = relevant_names - registered
    if missing:
        logger.debug(f"tool_filter: {len(missing)} configured tools not registered: {missing}")

    return filtered


def _tool_name(tool_def: dict) -> str:
    """Extract name from an OpenAI function-calling tool definition."""
    try:
        return tool_def['function']['name']
    except (KeyError, TypeError):
        return tool_def.get('name', '')
```

### Step 1c — Modify `jagabot/agent/loop.py` line 936

**READ loop.py lines 930–940 first. Then make this change:**

Find the exact line:
```python
tools=self.tools.get_definitions()
```

Replace with:
```python
tools=get_tools_for_query(user_input, self.tools)
```

Also add at the top of loop.py with the other imports:
```python
from jagabot.core.tool_filter import get_tools_for_query
```

**Add one debug log immediately after the API call (line ~937):**
```python
logger.debug(f"API call: {len(tools_payload)} tools sent, model={model}")
```

---

## PHASE 2 — Wire context_builder.py (the NEW context system)

The audit found `context_builder.py` was built but never integrated into loop.py.
It has dynamic layers and is designed to replace the static `context.py`.

### Step 2a — Read these files

```
jagabot/agent/context.py           (current system — understand what it does)
jagabot/agent/context_builder.py   (new system — understand its interface)
jagabot/agent/loop.py              (find where build_messages() is called)
```

### Step 2b — Replace context.py usage with context_builder.py

In loop.py, find the import of context.py:
```python
from jagabot.agent.context import ContextBuilder
# or: from jagabot.agent.context import build_messages
```

**Do NOT delete context.py.** Instead, update the import to use the new one:
```python
from jagabot.agent.context_builder import ContextBuilder as ContextBuilder
```

If `context_builder.py` has a different class/function name than context.py,
create a thin adapter — do NOT rewrite context_builder.py.

### Step 2c — Wire MemoryManager.get_context()

The audit confirmed `MemoryManager.get_context()` exists but is NOT called.
The old `self.memory.get_memory_context()` is still used instead.

In loop.py, find:
```python
self.memory.get_memory_context()
# or any call that fetches memory for prompt injection
```

Replace with gated call:
```python
# GATED MEMORY — skip retrieval for trivial/short inputs
_mem_query = user_input.strip()
if len(_mem_query.split()) >= 4 or any(
    kw in _mem_query.lower() for kw in
    ("remember", "engine", "status", "check", "solidif", "show", "recall")
):
    memory_context = await self.memory_manager.get_context(_mem_query)
else:
    memory_context = []
    logger.debug("MemoryManager: skipped (input too short)")
```

---

## PHASE 3 — History Compression (second biggest waste)

The audit confirmed history grows unbounded. After 50 turns = ~20,000 tokens.

### Step 3a — Create `jagabot/core/history_compressor.py` (new file)

```python
"""
jagabot/core/history_compressor.py
────────────────────────────────────
Compresses old conversation turns into a summary block.
Prevents linear token growth over long sessions.

Configuration via env vars:
  JAGABOT_COMPRESS_AFTER=6   turns before compression triggers (default: 6)
  JAGABOT_KEEP_RECENT=3      recent turns always kept raw (default: 3)
  JAGABOT_COMPRESS_MODEL=gpt-4o-mini  (default)
  JAGABOT_HISTORY_COMPRESS=0 to disable
"""

from __future__ import annotations
import os
from loguru import logger

_ENABLED       = os.getenv("JAGABOT_HISTORY_COMPRESS", "1") == "1"
COMPRESS_AFTER = int(os.getenv("JAGABOT_COMPRESS_AFTER", "6"))
KEEP_RECENT    = int(os.getenv("JAGABOT_KEEP_RECENT", "3"))
COMPRESS_MODEL = os.getenv("JAGABOT_COMPRESS_MODEL", "gpt-4o-mini")

_client = None

def _get_client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI()
    return _client


async def compress_history(messages: list[dict]) -> list[dict]:
    """
    Compress old messages into a summary block, keep recent turns raw.

    Parameters
    ----------
    messages : list of {"role": ..., "content": ...}
               The full messages list passed to the LLM (excluding system prompt).

    Returns
    -------
    Compressed messages list. Returns original if compression not needed.
    """
    if not _ENABLED:
        return messages

    # Only non-system messages count toward the threshold
    non_system = [m for m in messages if m.get("role") != "system"]
    threshold  = COMPRESS_AFTER * 2  # each turn = user + assistant

    if len(non_system) <= threshold:
        return messages

    keep_n   = KEEP_RECENT * 2
    old_msgs = non_system[:-keep_n]
    new_msgs = non_system[-keep_n:]

    system_msgs = [m for m in messages if m.get("role") == "system"]

    est_saved = sum(len(m.get("content","")) // 4 for m in old_msgs)
    logger.info(
        f"history_compressor: compressing {len(old_msgs)} messages "
        f"(~{est_saved:,} tokens) → summary block"
    )

    summary = await _summarise(old_msgs)

    summary_block = {
        "role": "system",
        "content": (
            "[Earlier conversation — summarised to save context]\n" + summary
        )
    }

    result = system_msgs + [summary_block] + new_msgs
    est_new = sum(len(m.get("content","")) // 4 for m in result)
    logger.info(
        f"history_compressor: {est_saved:,} → {est_new:,} tokens "
        f"(~{max(0,est_saved-est_new):,} saved)"
    )
    return result


async def _summarise(messages: list[dict]) -> str:
    text = "\n".join(
        f"{m['role'].upper()}: {m.get('content','')}" for m in messages
    )
    prompt = (
        "Summarise the following conversation in ≤8 bullet points.\n"
        "Keep ONLY: decisions made, facts confirmed, tasks pending, errors, "
        "tool outputs used.\n"
        "Omit greetings, filler, and back-and-forth.\n\n" + text
    )
    try:
        client = _get_client()
        resp = await client.chat.completions.create(
            model=COMPRESS_MODEL,
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning(f"history_compressor: summarisation failed ({exc}) — using truncation")
        lines = [f"• [{m['role']}] {m.get('content','')[:200]}" for m in messages]
        return "\n".join(lines)
```

### Step 3b — Wire compression into loop.py

In `_run_agent_loop()`, find where the `messages` list is built/assembled
before the API call (around line 916–934).

Insert BEFORE the `await self.provider.chat(...)` call:

```python
# HISTORY COMPRESSION — prevent unbounded token growth
from jagabot.core.history_compressor import compress_history
messages = await compress_history(messages)
```

---

## PHASE 4 — Token Budget Tracker

### Step 4a — Create `jagabot/core/token_budget.py` (new file)

```python
"""
jagabot/core/token_budget.py
────────────────────────────
Tracks token usage per-session and per-day.
Enforces limits and prints a report at session end.

Usage:
    from jagabot.core.token_budget import budget
    budget.record(input_tokens, output_tokens, model)
    budget.record_skip()   # when LLM call avoided
    budget.report()        # at session end

Config via env vars:
    JAGABOT_SESSION_LIMIT=50000    hard stop per session
    JAGABOT_CALL_LIMIT=10000       alert if single call exceeds this
    JAGABOT_DAILY_LIMIT=500000     soft daily cap
"""

from __future__ import annotations
import os
import json
from pathlib import Path
from datetime import date
from dataclasses import dataclass, field
from loguru import logger

SESSION_LIMIT = int(os.getenv("JAGABOT_SESSION_LIMIT", "50000"))
CALL_LIMIT    = int(os.getenv("JAGABOT_CALL_LIMIT",   "10000"))
DAILY_LIMIT   = int(os.getenv("JAGABOT_DAILY_LIMIT", "500000"))
STATE_PATH    = Path(os.getenv("JAGABOT_BUDGET_STATE",
                    str(Path.home() / ".jagabot" / "token_budget.json")))


def _load_daily():
    today = str(date.today())
    if STATE_PATH.exists():
        try:
            s = json.loads(STATE_PATH.read_text())
            if s.get("date") == today:
                return s
        except Exception:
            pass
    return {"date": today, "total": 0, "calls": 0}

def _save_daily(s: dict):
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(s, indent=2))
    except Exception as e:
        logger.warning(f"token_budget: could not save state — {e}")


@dataclass
class TokenBudget:
    session_limit: int = SESSION_LIMIT
    call_limit:    int = CALL_LIMIT
    daily_limit:   int = DAILY_LIMIT

    _in:     int  = field(default=0, init=False)
    _out:    int  = field(default=0, init=False)
    _calls:  int  = field(default=0, init=False)
    _skips:  int  = field(default=0, init=False)
    _models: dict = field(default_factory=dict, init=False)
    _daily:  dict = field(default_factory=_load_daily, init=False)

    def record(self, input_tokens: int, output_tokens: int, model: str):
        self._in    += input_tokens
        self._out   += output_tokens
        self._calls += 1
        self._models[model] = self._models.get(model, 0) + 1
        total = input_tokens + output_tokens
        self._daily["total"] += total
        self._daily["calls"] += 1
        _save_daily(self._daily)

        logger.info(
            f"💰 tokens | call={total:,} (in={input_tokens:,} out={output_tokens:,}) "
            f"| session={self._in+self._out:,} | daily={self._daily['total']:,} | {model}"
        )
        if input_tokens > self.call_limit:
            logger.warning(f"⚠️  High input: {input_tokens:,} tokens — check tool payload")
        if self._in + self._out > self.session_limit:
            raise RuntimeError(
                f"🛑 Session budget exceeded: {self._in+self._out:,} > {self.session_limit:,}"
            )
        if self._daily["total"] > self.daily_limit:
            logger.warning(f"📊 Daily budget exceeded: {self._daily['total']:,}")

    def record_skip(self):
        self._skips += 1
        logger.info(f"⏭️  LLM skipped (trivial) — {self._skips} skips this session")

    def remaining(self) -> int:
        return max(0, self.session_limit - (self._in + self._out))

    def report(self):
        models = ", ".join(f"{m}×{n}" for m, n in self._models.items()) or "none"
        skip_pct = self._skips / max(1, self._calls + self._skips) * 100
        logger.info(
            "\n" + "═"*50 + "\n"
            "  🐈 JAGABOT TOKEN REPORT\n" + "═"*50 + "\n"
            f"  Session input   : {self._in:>10,}\n"
            f"  Session output  : {self._out:>10,}\n"
            f"  Session total   : {self._in+self._out:>10,}\n"
            f"  Budget remaining: {self.remaining():>10,}\n"
            f"  LLM calls made  : {self._calls:>10}\n"
            f"  Calls skipped   : {self._skips:>10}  ({skip_pct:.0f}% avoided)\n"
            f"  Models          : {models}\n"
            f"  Daily total     : {self._daily['total']:>10,}\n"
            + "═"*50
        )

budget = TokenBudget()
```

### Step 4b — Wire budget into loop.py

Find the response line in `_run_agent_loop()` (line ~934):
```python
response = await self.provider.chat(...)
```

Immediately after, add:
```python
# BUDGET TRACKING
from jagabot.core.token_budget import budget
_u = response.usage
if _u:
    budget.record(
        input_tokens=_u.prompt_tokens,
        output_tokens=_u.completion_tokens,
        model=getattr(response, 'model', 'unknown'),
    )
```

Find the session end / CLI exit handler. Add:
```python
from jagabot.core.token_budget import budget
budget.report()
```

---

## PHASE 5 — Trivial Input Guard

### Step 5a — Create `jagabot/core/trivial_guard.py` (new file)

```python
"""
jagabot/core/trivial_guard.py
──────────────────────────────
Skip the LLM entirely for inputs like "hi", "ok", "thanks", "exit".
A "hi" was costing ~37,200+ tokens with 93 tool definitions attached.

Usage:
    from jagabot.core.trivial_guard import is_trivial, trivial_response

    if is_trivial(user_input):
        return trivial_response(user_input)
"""

from __future__ import annotations
import os
import random

_ENABLED = os.getenv("JAGABOT_TRIVIAL_GUARD", "1") == "1"

TRIVIAL: set[str] = {
    "hi","hello","hey","hiya","howdy","sup","yo",
    "ok","okay","k","sure","yep","yeah","yes","no","nope","nah",
    "got it","understood","noted","cool","great","nice",
    "thanks","thank you","ty","thx","cheers",
    "exit","quit","bye","goodbye","later","cya","done",
    "hmm","hm","um","uh","ah",
}

CANNED: dict[str, list[str]] = {
    "hi":        ["Hey! What would you like to work on?", "Hi — what's on your mind?"],
    "hello":     ["Hello! Ready when you are."],
    "hey":       ["Hey! What's up?"],
    "thanks":    ["You're welcome!", "Happy to help!"],
    "thank you": ["Of course!", "Any time."],
    "ok":        ["Got it. What's next?"],
    "yes":       ["Noted. What would you like to do?"],
    "no":        ["No problem. Anything else?"],
    "bye":       ["See you! Session saved. 🐈"],
    "exit":      ["Session ended. 🐈"],
    "done":      ["All done! 🐈"],
}

_DEFAULT = ["What would you like to work on?", "How can I help?", "Go ahead — I'm listening."]

def is_trivial(text: str) -> bool:
    if not _ENABLED:
        return False
    n = text.strip().lower()
    return len(n.split()) <= 5 and n in TRIVIAL

def trivial_response(text: str) -> str:
    n = text.strip().lower()
    return random.choice(CANNED.get(n, _DEFAULT))
```

### Step 5b — Wire into loop.py `_process_message()`

Find the start of `_process_message()`, just after the entry log line. Insert:

```python
# TRIVIAL GUARD — skip LLM for greetings/acks
from jagabot.core.trivial_guard import is_trivial, trivial_response
from jagabot.core.token_budget import budget

if is_trivial(user_input):
    reply = trivial_response(user_input)
    budget.record_skip()
    logger.info(f"Trivial guard fired — LLM call skipped for: '{user_input}'")
    return reply
```

---

## VERIFICATION — After All Phases Complete

Run the agent and confirm each fix in the logs:

```
PHASE 1 ✅  "tool_filter: 5/93 tools selected for query='check status'"
PHASE 2 ✅  "MemoryManager: skipped (input too short)"  ← for "hi"
PHASE 3 ✅  "history_compressor: compressing 14 messages (~3,200 tokens) → summary block"
PHASE 4 ✅  "💰 tokens | call=2,840 (in=2,580 out=260)"  ← way down from ~60,000
PHASE 4 ✅  "🐈 JAGABOT TOKEN REPORT" printed at session end
PHASE 5 ✅  "Trivial guard fired — LLM call skipped for: 'hi'"
```

**If tool count in logs is still 93:** JAGABOT_FULL_TOOLS env var may be set, or
the import failed. Check `jagabot/agent/context_builder.py` lines 42–77 to confirm
TOOL_RELEVANCE is exported correctly.

---

## ENV VAR CONTROL PANEL

Add these to your `.env` or shell config to tune behaviour at runtime:

```bash
# Budget limits
JAGABOT_SESSION_LIMIT=50000     # hard stop per session (default 50k)
JAGABOT_CALL_LIMIT=10000        # alert if single call > this
JAGABOT_DAILY_LIMIT=500000      # soft daily warning

# Tool filtering
JAGABOT_MAX_TOOLS=8             # max tools per call (default 8)
JAGABOT_FULL_TOOLS=0            # set to 1 to disable filtering (debug)

# Memory gating
JAGABOT_MIN_WORDS_MEMORY=4      # min words before memory retrieval fires

# History compression
JAGABOT_HISTORY_COMPRESS=1      # set to 0 to disable
JAGABOT_COMPRESS_AFTER=6        # turns before compression triggers
JAGABOT_KEEP_RECENT=3           # recent turns kept raw

# Trivial guard
JAGABOT_TRIVIAL_GUARD=1         # set to 0 to disable
```

---

## OPEN QUESTIONS TO CHECK FIRST

The audit flagged these — resolve before starting:

1. **`context_builder.py` lines 42–77** — Read the `TOOL_RELEVANCE` map carefully.
   Confirm it is a `dict[str, list[str]]` mapping keyword → tool names.
   If the structure is different, adapt `tool_filter.py` accordingly.

2. **`tool_loader.py`** — Does it have any runtime filtering logic?
   If yes, understand it before adding `tool_filter.py` to avoid conflicts.

3. **`self.provider.chat()`** — Does this go through LiteLLM or direct OpenAI?
   Check if `response.usage` is available on the response object.
   If not, find where token counts are logged and hook `budget.record()` there.

4. **async vs sync** — `_run_agent_loop` is async. Ensure `compress_history` is
   awaited properly. If `history_compressor.py` needs to be sync, remove `async`/`await`.

5. **`self.tools` type** — Confirm `self.tools` is a `ToolRegistry` instance.
   In `tool_filter.py`, adjust the `get_definitions()` call to match the actual interface.
