# JagaChatbot Architecture

## Component Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INPUT                                │
│                     (CLI / Channel)                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       ChatLoop                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    ContextBuilder                        │    │
│  │  • Loads system prompt                                   │    │
│  │  • Injects memory context                                │    │
│  │  • Assembles message history                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    LLMProvider                           │    │
│  │  • Routes to correct API (OpenAI/Anthropic/DeepSeek)     │    │
│  │  • Handles authentication                                │    │
│  │  • Parses response                                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    MemoryStore                           │    │
│  │  • Appends to HISTORY.md (grep-searchable)               │    │
│  │  • Updates MEMORY.md (long-term facts)                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Compressor                            │    │
│  │  • Estimates token count                                 │    │
│  │  • Shrinks old tool results                              │    │
│  │  • Keeps recent context intact                           │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RESPONSE OUTPUT                             │
│                     (CLI / Channel)                              │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### ChatLoop (`agent/loop.py`)
The main orchestrator. Receives user messages, builds context, calls the LLM, updates history, and returns responses.

### ContextBuilder (`agent/context.py`)
Assembles the system prompt by combining:
- Core identity (who the bot is)
- Current time and environment
- Long-term memory facts
- Conversation history

### MemoryStore (`agent/memory.py`)
Two-layer persistent memory:
- `MEMORY.md` — Long-term facts (manually written by the agent)
- `HISTORY.md` — Grep-searchable conversation log (auto-appended)

### Compressor (`agent/compressor.py`)
Prevents token overflow in long conversations:
- Estimates token count (~4 chars per token)
- Replaces old tool results with placeholders
- Preserves recent messages intact

### LiteLLMProvider (`providers/litellm_provider.py`)
Unified interface to multiple LLM providers:
- Auto-detects provider from model name
- Sets correct API keys and base URLs
- Handles response parsing

## Data Flow

1. **Input**: User types message in CLI
2. **Context**: ContextBuilder loads memory and builds prompt
3. **LLM Call**: Provider sends request to API
4. **Response**: LLM returns text
5. **Memory**: MemoryStore logs the exchange
6. **Compression**: If history too long, older messages compressed
7. **Output**: Response displayed to user

## File Locations

```
~/.jagachatbot/
├── config.json          # User configuration
├── workspace/
│   └── memory/
│       ├── MEMORY.md    # Long-term facts
│       └── HISTORY.md   # Conversation log
└── .env                 # Environment variables
```

## Extension Points

- **New providers**: Implement `LLMProvider` interface
- **New channels**: Implement `Channel` interface  
- **Custom memory**: Extend `MemoryStore` class
