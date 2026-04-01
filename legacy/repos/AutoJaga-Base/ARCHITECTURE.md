# AutoJaga-Base Architecture

## Component Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INPUT                                │
│                     (CLI / Channel)                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FluidDispatcher                               │
│  • Classify intent (RESEARCH, ACTION, ANALYSIS, CHAT)           │
│  • Select relevant tools                                         │
│  • Runs in <5ms — no LLM calls                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       AgentLoop                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    LLM Call                              │    │
│  │  • Send messages with tool definitions                   │    │
│  │  • Receive response (text + tool calls)                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 Tool Execution Loop                      │    │
│  │  • Execute each tool call                                │    │
│  │  • Track in ToolHarness                                  │    │
│  │  • Return results to LLM                                 │    │
│  │  • Repeat until no more tool calls                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 Anti-Fabrication Check                   │    │
│  │  • Scan response for file creation claims                │    │
│  │  • Verify against harness records                        │    │
│  │  • Add warnings if fabrication detected                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    BDI Scoring                           │    │
│  │  • Score belief (verified assumptions?)                  │    │
│  │  • Score desire (persisted through failures?)            │    │
│  │  • Score intention (effective tool use?)                 │    │
│  │  • Score anomaly (clean execution?)                      │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT RESPONSE                              │
│                  (with tool results + BDI score)                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### AgentLoop (`agent/loop.py`)
The main orchestrator. Manages the tool execution loop:
1. Build messages with system prompt
2. Call LLM with tool definitions
3. Execute any requested tools
4. Return tool results to LLM
5. Repeat until done
6. Run fabrication check
7. Score with BDI scorecard

### ToolRegistry (`agent/tools.py`)
Manages available tools:
- Register tools as objects (not strings)
- Provide OpenAI-format tool definitions
- Execute tools by name

### Built-in Tools (`agent/builtin_tools.py`)
- **web_search**: DuckDuckGo search
- **read_file**: Read file contents (sandboxed)
- **write_file**: Write to file (sandboxed)
- **exec**: Execute shell commands (sandboxed)

### ToolHarness (`core/tool_harness.py`)
Tracks every tool invocation:
- Records start/complete/fail
- Tracks files created
- Detects fabricated claims

### BDIScorecardTracker (`core/bdi_scorecard.py`)
Scores each turn on 4 dimensions:
- **Belief**: Did agent verify assumptions?
- **Desire**: Did agent persist through failures?
- **Intention**: Did agent use tools effectively?
- **Anomaly**: Did agent avoid chaotic behavior?

### FluidDispatcher (`core/fluid_dispatcher.py`)
Intent classification without LLM calls:
- Pattern matching on user input
- Returns relevant tools for intent
- Runs in <5ms

## Swarm Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       CONDUCTOR                                  │
│  • Receives high-level query                                     │
│  • Dispatches to specialists                                     │
│  • Synthesizes outputs                                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  SPECIALIST 1  │   │  SPECIALIST 2  │   │  SPECIALIST N  │
│  (Botanist)    │   │  (Chemist)     │   │  (...)         │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       SYNTHESIS                                  │
│  • Integrate specialist perspectives                             │
│  • Resolve contradictions                                        │
│  • Produce unified response                                      │
└─────────────────────────────────────────────────────────────────┘
```

## File Locations

```
~/.autojaga/
├── config.json              # User configuration
├── workspace/
│   └── memory/
│       ├── MEMORY.md        # Long-term facts
│       ├── HISTORY.md       # Conversation log
│       └── bdi_scores.json  # BDI score history
└── .env                     # Environment variables
```

## Tool Binding Design

Tools are bound as **objects**, not strings:

```python
# ✅ Correct: Tool passed as object
agent.tools.register(WebSearchTool(api_key=key))

# ❌ Wrong: Tool described in prompt
"You have access to a tool called web_search..."
```

This ensures:
1. Tools are real, executable code
2. No hallucinated tool capabilities
3. Proper sandboxing and security
4. Consistent tool behavior
