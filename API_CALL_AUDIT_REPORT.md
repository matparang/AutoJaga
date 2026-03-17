═══════════════════════════════════════════════════════
  JAGABOT API CALL STRUCTURE AUDIT
═══════════════════════════════════════════════════════

## 1. API CALL ANATOMY

**API calls per user turn:**
- **Minimum:** 1 (direct response, no tools)
- **Maximum:** 15+ (complex tool execution with audit retries)
  - 1 main LLM call (line 934)
  - Up to 2 audit retry calls (ResponseAuditor.max_retries=2)
  - Multiple tool execution calls (each tool call triggers LLM for next step)
  - 1 plan extraction call (line 529, when audit needs JSON plan)

**Main LLM call trigger:**
- Method: `AgentLoop._run_agent_loop()` (line 916-1588)
- Exact line: `response = await self.provider.chat(...)` (line 934)

**Messages assembly:**
- Method: `ContextBuilder.build_messages()` (jagabot/agent/context.py:138-170)
- Called from: `AgentLoop._process_message()` via `_run_agent_loop()`
- Messages include: system prompt + conversation history + tool results

**Tools assembly:**
- Exact line: `tools=self.tools.get_definitions()` (line 936)
- Method: `ToolRegistry.get_definitions()` → returns ALL registered tools
- **ALL tools sent on EVERY call** — NO filtering at API-call time

---

## 2. SYSTEM PROMPT

**File location:** `jagabot/agent/context.py:28-67` (`build_system_prompt()`)

**Approximate size:**
- Lines: ~150 lines of text
- Word count: ~1,500-2,000 words
- **Token estimate: ~2,000-2,500 tokens**

**Static or dynamic:**
- **PARTIALLY DYNAMIC**
- Static parts: AGENTS.md, SOUL.md, bootstrap files
- Dynamic parts: Memory context, skills summary, session info, current time

**Tool definitions:**
- **Passed separately** via `tools=` parameter (line 936)
- NOT included inline in system prompt
- Tool definitions sent via OpenAI function-calling format

---

## 3. TOOL LOADING

**Total number of registered tools:** **93 tools** (from grep search results)

**How tools are stored:**
- Variable: `self.tools` (ToolRegistry instance)
- Data structure: `dict[str, Tool]` (jagabot/agent/tools/registry.py:15)
- Registration: `ToolRegistry.register()` adds to `_tools` dict

**What "lazy loading" actually does:**
- **NOTHING at API-call time** — lazy loading is ONLY for startup
- `tool_loader.py` registers all tools at AgentLoop initialization
- **ALL 93 tools sent on EVERY API call** via `self.tools.get_definitions()` (line 936)

**Are all tools sent on every API call?** **YES** ❌

**Approximate token cost of full tool list:**
- Estimate: 93 tools × ~400 tokens/tool = **~37,200 tokens** per call
- This is the BIGGEST token waste source

---

## 4. MEMORY INJECTION

**Method name:** `MemoryManager.get_context()` (jagabot/memory/memory_manager.py:167-203)

**Called on EVERY turn or conditionally?**
- **NOT CURRENTLY CALLED** in loop.py — memory injection is via old ContextBuilder
- Should be called at start of `_process_message()` but isn't wired yet
- Old memory system (`self.memory.get_memory_context()`) is still used

**How many memories retrieved per call:**
- Config: `FTS_RESULT_LIMIT = 8` (line 68)
- Max: 8 memory entries

**How memories formatted:**
- As markdown text block
- Injected into system prompt section: `# Memory\n\n{memory}`

**Approximate token size:**
- Per memory entry: ~50-100 tokens
- Total: 8 × 75 = **~600 tokens** per call

---

## 5. CONVERSATION HISTORY

**Where stored:**
- Variable: `messages` list (passed through `_run_agent_loop()`)
- Session persistence: `SessionManager` → `~/.jagabot/sessions/*.jsonl`

**Is history compressed or truncated?**
- **NO** — history grows unbounded each session ❌
- `memory_window=50` parameter exists but only limits what's loaded from session
- No compression, no summarization, no truncation during conversation

**Does full history grow unbounded?** **YES** ❌
- Every user message + assistant response appended to `messages` list
- After 50 turns: ~50 user messages + ~50 assistant responses = **100+ messages**
- Token estimate: 100 messages × ~200 tokens = **~20,000 tokens**

---

## 6. OTHER PROMPT INJECTIONS

| Block | Injected? | Where | Tokens |
|-------|-----------|-------|--------|
| **Session reminder (📚 block)** | ❌ NO | Not found in code | - |
| **Curiosity suggestions** | ❌ NO | `get_session_suggestions()` exists but not called in prompt | - |
| **Proactive wrapper** | ❌ NO | File doesn't exist | - |
| **Epistemic auditor output** | ✅ YES | Inside `ResponseAuditor.audit()` (line 85-115) | ~200 tokens |
| **Self-model context** | ❌ NO | `SelfModelEngine` exists but not injected | - |
| **Causal tracer** | ✅ YES | `self.auditor.causal_tracer.record()` (line 656) | ~100 tokens |
| **Repetition guard** | ❌ NO | Not found | - |
| **ConfidenceEngine notes** | ❌ NO | Engine exists but not called | - |

**Other blocks found:**
- **Tool execution results** — appended to messages after each tool call (line 648)
- **Audit feedback messages** — injected when audit fails (line 275-283)
- **Plan extraction prompts** — injected when auditor needs JSON plan (line 285-291)

---

## 7. SECONDARY API CALLS

| Component | Makes API call? | Frequency | Tokens |
|-----------|-----------------|-----------|--------|
| **Auditor (ResponseAuditor)** | ❌ NO | - | - |
| **EpistemicAuditor** | ❌ NO | - | - |
| **CausalTracer** | ❌ NO | - | - |
| **ProactiveWrapper** | ❌ NO | File doesn't exist | - |
| **History compression** | ❌ NO | Doesn't exist | - |
| **Plan extraction** | ✅ YES | When audit needs JSON (line 529) | ~500 input |

**TOTAL estimated API calls per user message:**
- **Simple message (no tools):** 1 call
- **Message with tools:** 1 + N tool iterations (typically 2-5 calls)
- **Message with audit retries:** 1 + 2 (max_retries=2) = 3 calls
- **Worst case:** 1 + 5 tool iterations + 2 audit retries = **8+ calls**

---

## 8. TOKEN BREAKDOWN ESTIMATE

**For a typical simple turn ("hi"):**

| Component | Est. tokens |
|-----------|-------------|
| System prompt | 2,000 |
| Tool definitions (ALL 93 tools) | 37,200 |
| Conversation history (N turns) | 20,000 (after 50 turns) |
| Memory injection | 600 |
| Session reminder block | 0 (not implemented) |
| Curiosity suggestions | 0 (not injected) |
| User message itself | 10 |
| Other injections (causal tracer, etc.) | 300 |
| **TOTAL input (estimated)** | **~60,110 tokens** |

**For a complex turn (research request with tools):**

| Component | Est. tokens |
|-----------|-------------|
| System prompt | 2,000 |
| Tool definitions (ALL 93 tools) | 37,200 |
| Conversation history | 20,000 |
| Memory injection | 600 |
| Tool execution results (5 tools) | 2,500 |
| Audit feedback messages | 500 |
| User message | 50 |
| **TOTAL input (estimated)** | **~62,850 tokens** |

---

## 9. BIGGEST TOKEN WASTE — RANKED

### **1. ALL 93 TOOLS ON EVERY CALL** ❌
**Evidence:**
- Line 936: `tools=self.tools.get_definitions()` — no filtering
- `ToolRegistry.get_definitions()` returns ALL tools
- 93 tools × ~400 tokens = **37,200 tokens wasted per call**

**Estimated tokens wasted:** **37,200 tokens/call** (60% of total!)

---

### **2. UNBOUNDED CONVERSATION HISTORY** ❌
**Evidence:**
- No compression/truncation in `_run_agent_loop()`
- `messages` list grows indefinitely
- After 50 turns: ~100 messages × ~200 tokens = **20,000 tokens**

**Estimated tokens wasted:** **20,000 tokens/call** (33% of total, grows over time)

---

### **3. STATIC SYSTEM PROMPT** ⚠️
**Evidence:**
- `build_system_prompt()` loads ALL bootstrap files every time
- AGENTS.md + SOUL.md + TOOLS.md = ~1,500-2,000 words
- No query-relevant filtering

**Estimated tokens wasted:** **1,000 tokens/call** (could be reduced to 300 with Layer 1 core identity)

---

## 10. THINGS THAT WORK WELL (do not change these)

✅ **EpistemicAuditor** — Lightweight regex-based checking, NO API calls
✅ **CausalTracer** — Simple string matching, NO API calls
✅ **Tool execution caching** — `_duplicate_commands` detection prevents redundant tool calls
✅ **ResponseAuditor retry logic** — Max 2 retries prevents infinite loops
✅ **ToolHarness** — Tracks execution time, useful for profiling

---

## 11. OPEN QUESTIONS

1. **ContextBuilder vs context_builder.py** — Two different files exist:
   - `jagabot/agent/context.py` (OLD, currently used)
   - `jagabot/agent/context_builder.py` (NEW, dynamic layers, NOT wired)
   - **Gap:** New context_builder.py is NOT integrated into loop.py

2. **MemoryManager wiring** — `MemoryManager.get_context()` exists but:
   - Not called in current loop.py
   - Old `self.memory.get_memory_context()` still used
   - **Gap:** MemoryManager not integrated

3. **CuriosityEngine injection** — `get_session_suggestions()` exists but:
   - Returns suggestions but doesn't inject into prompt
   - No code found that adds suggestions to system prompt
   - **Gap:** Curiosity suggestions not shown to user

4. **SelfModelEngine** — Exists but:
   - No code found that injects self-model context into prompt
   - `SelfModelAwarenessTool` exists but agent doesn't auto-query it
   - **Gap:** Self-model not used for prompt shaping

5. **Tool filtering** — `TOOL_RELEVANCE` map exists in `context_builder.py` (lines 42-77) but:
   - NOT used in actual API call
   - All 93 tools sent regardless of query
   - **Gap:** Tool relevance filtering not implemented

---

## 12. RECOMMENDED AUDIT FOLLOW-UPS

**Manual checks needed:**

1. **Check `~/.jagabot/config.json`** — Does it have tool filtering config?
2. **Check env vars** — Is there a `JAGABOT_MAX_TOOLS` or similar that controls tool loading?
3. **Check `jagabot/agent/tool_loader.py`** — Is there lazy loading logic that was supposed to filter tools at runtime?
4. **Check `jagabot/agent/context_builder.py` wiring** — Why was it created but not integrated into loop.py?
5. **Check actual API logs** — Run `jagabot chat` and check LiteLLM logs to see actual token counts sent to OpenAI

---

═══════════════════════════════════════════════════════
  END OF AUDIT
═══════════════════════════════════════════════════════

**Summary:**
- **93 tools sent on EVERY call** = 37,200 tokens wasted (60% of total)
- **Unbounded history** = 20,000 tokens wasted (33% of total, grows over time)
- **Static system prompt** = 1,000 tokens wasted (could be 300 with dynamic layers)
- **Total waste:** ~58,200 tokens per call out of ~60,110 tokens (97% waste!)

**Priority fixes:**
1. Implement tool filtering (send only 5-10 relevant tools per call)
2. Implement history compression/summarization
3. Wire up new context_builder.py with dynamic layers
