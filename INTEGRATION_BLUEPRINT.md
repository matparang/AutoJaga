# 🏗️ NEW INTEGRATION BLUEPRINT: AutoJaga + Jagabot + CoPaw CLI

**Date:** March 15, 2026  
**Status:** Ready for Implementation  
**Based on:** Full Audit (FULL_AUDIT_AUTOJAGA_COPAW.md)

---

## 🎯 PROBLEM STATEMENT

**Current Issue:** AutoJaga API creates AgentLoop but never actually uses it. It makes direct LLM calls instead of triggering the full Jagabot agent runtime.

**Result:**
- ❌ No tool execution
- ❌ No memory access
- ❌ No subagent spawning
- ❌ No Guardian pipeline
- ❌ Just simple LLM responses

---

## 🏗️ NEW ARCHITECTURE

### Overview

```
┌──────────────────────────────────────────────────────────────┐
│                      CoPaw CLI                                │
│                                                               │
│  Commands:                                                    │
│  • talk <service> <message>  → Chat with agent               │
│  • plan <prompt>             → Create experiment blueprint   │
│  • execute <tool> <params>   → Execute specific tool         │
│  • memory <query>            → Query memory system           │
│  • subagent <type> <task>    → Spawn subagent                │
└─────────────────────┬────────────────────────────────────────┘
                      │ HTTP/REST API
                      ↓
┌──────────────────────────────────────────────────────────────┐
│                   AutoJaga API Gateway                        │
│                                                               │
│  Endpoints:                                                   │
│  • POST /execute      → Execute agent task                   │
│  • POST /plan         → Create blueprint                     │
│  • GET  /memory       → Query memory                         │
│  • POST /subagent     → Spawn subagent                       │
│  • GET  /session/<id> → Get session state                    │
│                                                               │
│  Role: HTTP ↔ MessageBus bridge                              │
└─────────────────────┬────────────────────────────────────────┘
                      │ MessageBus (async)
                      ↓
┌──────────────────────────────────────────────────────────────┐
│                  Jagabot AgentLoop (Background)               │
│                                                               │
│  Components:                                                  │
│  • AgentLoop - Core processing engine                        │
│  • ToolRegistry - 45+ tools                                  │
│  • ToolHarness - Execution verification                      │
│  • Memory System - Fractal memory                            │
│  • Providers - Qwen Plus, etc.                               │
│                                                               │
│  Flow:                                                        │
│  1. Receive message via bus                                  │
│  2. Build context (history, memory, tools)                   │
│  3. Call LLM with tools                                      │
│  4. Execute tool calls                                       │
│  5. Verify results                                           │
│  6. Send response via bus                                    │
└──────────────────────────────────────────────────────────────┘
```

---

## 📋 COMPONENT SPECIFICATIONS

### 1. AutoJaga API Gateway

**File:** `jagabot/api/server.py`

**New Role:** HTTP ↔ MessageBus Bridge

**Key Changes:**

```python
# OLD (Broken):
@app.post("/plan")
async def create_plan(request: PlanRequest):
    agent = AgentLoop(...)  # Created but never used!
    response = await provider.chat(messages, tools=[])  # Direct LLM call
    return response

# NEW (Working):
@app.post("/execute")
async def execute_task(request: ExecuteRequest):
    # Create session
    session_id = create_session(request.prompt)
    
    # Create message bus
    bus = MessageBus()
    
    # Start agent loop in background
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        model=model,
    )
    asyncio.create_task(agent.run())
    
    # Send message via bus
    msg = InboundMessage(
        channel="api",
        chat_id=session_id,
        content=request.prompt,
        sender_id="copaw_cli"
    )
    await bus.publish_inbound(msg)
    
    # Wait for agent response
    response = await bus.consume_outbound(timeout=300)
    
    # Return formatted result
    return format_response(response)
```

**New Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/execute` | POST | Execute full agent task with tools |
| `/plan` | POST | Create experiment blueprint (existing) |
| `/memory` | GET | Query memory system |
| `/subagent` | POST | Spawn subagent |
| `/session/<id>` | GET | Get session state |
| `/tools` | GET | List available tools |
| `/tools/<name>/execute` | POST | Execute specific tool |

---

### 2. CoPaw CLI

**File:** `copaw_manager.py`

**New Commands:**

```python
# Execute full agent task
copaw> execute Improve model accuracy with ensemble methods
📤 Sending to AutoJaga agent...
⏳ Agent is thinking...
🔧 Executing tools:
   • financial_cv - Analyzing CV ratios
   • monte_carlo - Running simulation
   • decision_engine - Multi-perspective analysis
✅ Task complete!
Result: XGBoost selected with 87% confidence

# Query memory
copaw> memory What did we learn about VIX?
📤 Querying memory...
✅ Found 3 relevant memories:
   1. [2026-03-15] VIX measures volatility...
   2. [2026-03-14] High VIX indicates fear...
   3. [2026-03-13] VIX calculation uses...

# Spawn subagent
copaw> subagent tri_agent Analyze AAPL risk
📤 Spawning Tri-Agent...
⏳ Running debate...
✅ Tri-Agent complete:
   Bull: Buy opportunity
   Bear: High risk
   Buffett: Wait for better entry
   Consensus: HOLD

# Execute specific tool
copaw> tool monte_carlo current_price=150 target_price=180 vix=25
📤 Executing monte_carlo tool...
✅ Result: 65% probability of reaching target
```

**Enhanced Existing Commands:**

```python
# talk command - now uses full agent
copaw> talk autojaga "What is VIX?"
📤 Sending to AutoJaga agent...
⏳ Agent is thinking...
🔧 Agent executed: web_search
✅ Response: VIX is the CBOE Volatility Index...

# plan command - now executes full analysis
copaw> plan Improve accuracy
📤 Sending to AutoJaga agent...
⏳ Agent is thinking...
🔧 Agent executed: financial_cv, monte_carlo, decision_engine
✅ Blueprint created with full analysis
```

---

### 3. Session Manager

**File:** `jagabot/api/session_manager.py` (NEW)

**Purpose:** Persist sessions to disk

**Implementation:**

```python
class SessionManager:
    def __init__(self, workspace: Path):
        self.sessions_dir = workspace / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
    
    def create_session(self, prompt: str) -> str:
        session_id = f"session_{datetime.now():%Y%m%d_%H%M%S}"
        session = {
            "id": session_id,
            "prompt": prompt,
            "created_at": datetime.now().isoformat(),
            "status": "active",
            "messages": [],
            "tools_used": []
        }
        self.save(session)
        return session_id
    
    def save(self, session: dict):
        session_file = self.sessions_dir / f"{session['id']}.json"
        with open(session_file, 'w') as f:
            json.dump(session, f, indent=2)
    
    def load(self, session_id: str) -> dict:
        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            return json.loads(session_file.read_text())
        return None
    
    def add_message(self, session_id: str, role: str, content: str, tools: list = None):
        session = self.load(session_id)
        if session:
            session["messages"].append({
                "role": role,
                "content": content,
                "tools": tools or []
            })
            self.save(session)
```

---

## 🔧 IMPLEMENTATION STEPS

### Step 1: Create Session Manager (30 min)

**File:** `jagabot/api/session_manager.py`

```python
# Create session manager class
# Add save/load methods
# Test session persistence
```

### Step 2: Update AutoJaga API (1 hour)

**File:** `jagabot/api/server.py`

```python
# Add /execute endpoint
# Use MessageBus to communicate with AgentLoop
# Start AgentLoop as background task
# Wait for response via bus
# Return formatted result
```

### Step 3: Update CoPaw CLI (1 hour)

**File:** `copaw_manager.py`

```python
# Add execute command
# Add memory command
# Add subagent command
# Add tool command
# Enhance talk and plan commands
```

### Step 4: Test Integration (1 hour)

```bash
# Test full agent execution
copaw> execute Improve model accuracy

# Test memory queries
copaw> memory What did we learn?

# Test subagent spawning
copaw> subagent tri_agent Analyze risk

# Test tool execution
copaw> tool monte_carlo current_price=150
```

---

## 📊 EXPECTED RESULTS

### Before (Current)

```bash
copaw> talk autojaga "What is VIX?"
✅ Response: {
  "status": "success",
  "blueprint": "...",
  "agent_selected": "GENERAL_QUESTION"
}
```

**Issues:**
- ❌ No tool execution
- ❌ No web search
- ❌ Just LLM response
- ❌ No real analysis

### After (New)

```bash
copaw> talk autojaga "What is VIX?"
📤 Sending to AutoJaga agent...
⏳ Agent is thinking...
🔧 Executing tools:
   • web_search - Searching for VIX definition
   • read_file - Reading financial glossary
✅ Response:

VIX (Volatility Index)
======================

The VIX is a real-time market index representing market expectations 
for 30-day forward-looking volatility...

Sources:
• CBOE VIX documentation
• Investopedia definition

Session: session_20260315_041500
```

**Benefits:**
- ✅ Real tool execution
- ✅ Web search performed
- ✅ Files read
- ✅ Comprehensive answer
- ✅ Sources cited

---

## 🎯 SUCCESS CRITERIA

### Phase 1: Core Integration

- [ ] `/execute` endpoint working
- [ ] AgentLoop receives messages via bus
- [ ] AgentLoop executes tools
- [ ] Responses returned via bus
- [ ] Sessions persisted to disk

### Phase 2: CoPaw Commands

- [ ] `execute` command working
- [ ] `memory` command working
- [ ] `subagent` command working
- [ ] `tool` command working
- [ ] Formatted output

### Phase 3: Full Integration

- [ ] All 45+ tools accessible
- [ ] Memory system queries working
- [ ] Subagent spawning working
- [ ] Multi-turn conversations
- [ ] Session history loaded

---

## 📁 FILE CHANGES

### New Files

| File | Purpose | Lines |
|------|---------|-------|
| `jagabot/api/session_manager.py` | Session persistence | ~150 |
| `jagabot/api/tool_executor.py` | Tool execution helper | ~100 |

### Modified Files

| File | Changes | Lines |
|------|---------|-------|
| `jagabot/api/server.py` | Add /execute endpoint, use MessageBus | ~300 |
| `copaw_manager.py` | Add new commands | ~400 |

---

## 🏁 CONCLUSION

**Current State:** AutoJaga API creates AgentLoop but doesn't use it

**New State:** AutoJaga API bridges HTTP to MessageBus, triggering full AgentLoop

**Impact:**
- ✅ Full tool execution (45+ tools)
- ✅ Memory system access
- ✅ Subagent spawning
- ✅ Guardian pipeline
- ✅ All Jagabot features

**Implementation Time:** ~3.5 hours  
**Risk:** LOW (uses existing Jagabot components)  
**Benefit:** HIGH (full agent capabilities)

---

**Blueprint Created:** March 15, 2026  
**Status:** ✅ **READY FOR IMPLEMENTATION**  
**Next Step:** Start Phase 1 - Session Manager
