# JagaChatbot

> **DeepMind AGI Level 1 — Conversational Agent**

A clean, minimal chatbot with multi-provider LLM routing, conversation memory, and compression.

![Level 1](https://img.shields.io/badge/DeepMind%20AGI-Level%201%20Chatbot-blue)
![Python](https://img.shields.io/badge/Python-3.11+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## What is JagaChatbot?

JagaChatbot is the foundation layer of the Jaga AI agent stack. It demonstrates:

- **Multi-provider LLM routing** — Switch between OpenAI, Anthropic, DeepSeek, Gemini
- **Conversation memory** — Persistent storage with grep-searchable history
- **Automatic compression** — Token-aware context management for long sessions
- **Clean architecture** — Minimal dependencies, easy to extend

This is **Level 1** in the [DeepMind AGI Levels framework](DEEPMIND_AGI_LEVELS.md): a chatbot that can have natural conversations but doesn't yet reason over external knowledge or use tools.

---

## 5-Minute Quickstart

### 1. Install

```bash
git clone https://github.com/matparang/JagaChatbot.git
cd JagaChatbot
pip install -e .
```

### 2. Configure

```bash
# Option A: Environment variable
export OPENAI_API_KEY="sk-..."

# Option B: Config file
cp .env.example ~/.jagachatbot/.env
# Edit with your API key
```

### 3. Run

```bash
python -m jagachatbot
```

You'll see:
```
🐈 JagaChatbot DeepMind Level 1 · openai/gpt-4o-mini
Type your message · /clear to reset · Ctrl+C to exit

> Hello!
```

---

## Architecture

```
jagachatbot/
├── __main__.py          # Entry point
├── agent/
│   ├── loop.py          # Main chat loop
│   ├── context.py       # System prompt builder
│   ├── memory.py        # Long-term memory store
│   └── compressor.py    # Token-aware compression
├── providers/
│   ├── base.py          # Abstract LLM interface
│   └── litellm_provider.py  # Multi-provider via LiteLLM
├── config/
│   ├── schema.py        # Configuration schema
│   └── loader.py        # Config file loading
├── cli/
│   └── interactive.py   # Rich terminal interface
└── channels/
    └── base.py          # Abstract channel interface
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed component flow.

---

## Configuration

JagaChatbot reads configuration from `~/.jagachatbot/config.json`:

```json
{
  "providers": {
    "openai": {"api_key": "sk-..."},
    "anthropic": {"api_key": "sk-ant-..."},
    "deepseek": {"api_key": "sk-..."}
  },
  "defaults": {
    "model": "openai/gpt-4o-mini",
    "temperature": 0.7,
    "memory_window": 50
  }
}
```

Environment variables take precedence:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `DEEPSEEK_API_KEY`
- `GEMINI_API_KEY`

---

## Smoke Test

Verify installation:

```bash
python -m pytest tests/test_smoke.py -v
```

Or manually:
```bash
python -m jagachatbot
# Type: "What is 2+2?"
# Expect: A response mentioning "4"
# Check: ~/.jagachatbot/workspace/memory/HISTORY.md exists
```

---

## Related Projects

This is part of a 3-repo portfolio demonstrating progressive AI capability:

| Repo | Level | Description |
|------|-------|-------------|
| **JagaChatbot** (this) | Level 1 | Conversational chatbot |
| [JagaRAG](https://github.com/matparang/JagaRAG) | Level 2 | Retrieval-augmented reasoning |
| [AutoJaga-Base](https://github.com/matparang/AutoJaga-Base) | Level 3 | Autonomous multi-agent system |

---

## License

MIT — see [LICENSE](LICENSE)

---

## Author

Built by [@matparang](https://github.com/matparang)
