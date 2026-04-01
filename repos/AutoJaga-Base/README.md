# AutoJaga-Base

> **DeepMind AGI Level 3 — Autonomous Multi-Agent System**

A full agentic framework with tool binding, BDI reasoning, and multi-agent swarm orchestration.

![Level 3](https://img.shields.io/badge/DeepMind%20AGI-Level%203%20Agent-red)
![Python](https://img.shields.io/badge/Python-3.11+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## What is AutoJaga-Base?

AutoJaga-Base is the **kernel** of the AutoJaga autonomous research agent. It extends [JagaRAG](https://github.com/matparang/JagaRAG) (Level 2) with:

- **Tool binding** — Agents execute real tools (web search, file operations, shell commands)
- **BDI Scorecard** — Belief-Desire-Intention scoring for autonomous behavior
- **Anti-fabrication harness** — Catches hallucinated tool results
- **Fluid Dispatcher** — Intent classification and tool routing
- **Swarm orchestration** — Multiple specialist agents working in parallel

This is **Level 3** in the [DeepMind AGI Levels framework](DEEPMIND_AGI_LEVELS.md): an agent that can use tools and take actions in the world.

---

## 5-Minute Quickstart

### 1. Install

```bash
git clone https://github.com/matparang/AutoJaga-Base.git
cd AutoJaga-Base
pip install -e .
```

### 2. Configure

```bash
# Option A: Environment variable
export OPENAI_API_KEY="sk-..."

# Option B: Config file
cp .env.example ~/.autojaga/.env
```

### 3. Run

```bash
python -m autojaga
```

### 4. Use Tools

```bash
> Research the antimicrobial properties of Styrax benzoin

🐈 AutoJaga:
I'll search for information about this...

[tool] web_search: "Styrax benzoin antimicrobial properties"
[tool] web_search: "benzoin compound antibacterial studies"

Based on my research, Styrax benzoin shows significant antimicrobial activity...
```

### 5. Try Swarm Mode

```bash
> /swarm What are the therapeutic applications of Mangliwood compounds?

Starting Mangliwood research swarm...

[Botanist] Mangliwood (Styrax) trees are native to...
[Chemist] The primary active compounds include...
[Pharmacologist] Therapeutic applications include...

[Synthesis]
Combining these perspectives, Mangliwood compounds show promise for...
```

---

## Architecture

```
autojaga/
├── __main__.py              # Entry point
├── agent/
│   ├── loop.py              # Main agent loop with tool execution
│   ├── tools.py             # Tool interface and registry
│   └── builtin_tools.py     # Web search, file ops, exec
├── core/
│   ├── bdi_scorecard.py     # Belief-Desire-Intention scoring
│   ├── tool_harness.py      # Anti-fabrication checks
│   └── fluid_dispatcher.py  # Intent classification
├── swarm/
│   └── conductor.py         # Multi-agent orchestration
├── providers/
│   └── litellm_provider.py  # Multi-provider LLM routing
├── config/
│   └── schema.py            # Configuration
└── cli/
    └── interactive.py       # Rich terminal interface
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed component flow.

---

## Key Features

### Tool Binding

Tools are passed as objects at agent spawn, not described in system prompts:

```python
from autojaga.agent import AgentLoop, WebSearchTool

agent = AgentLoop(provider=provider, workspace=workspace)
# Tools are already registered: web_search, read_file, write_file, exec
```

### BDI Scorecard

Every turn is scored on 4 dimensions:

| Dimension | What it measures |
|-----------|------------------|
| **Belief** | Did the agent verify assumptions? |
| **Desire** | Did it persist through failures? |
| **Intention** | Did it use tools effectively? |
| **Anomaly** | Did it avoid chaotic behavior? |

Target score: **6+/10** = Autonomous Strategist

### Anti-Fabrication Harness

The harness catches hallucinated tool results:

```python
# If agent claims "I created file.txt" but no write_file was called:
⚠️ Fabrication detected: claims to have created 'file.txt' 
   but no write_file tool was called and file doesn't exist.
```

### Swarm Orchestration

Multiple specialist agents work in parallel:

```
Conductor
    │
    ├── Botanist (plant biology)
    ├── Chemist (compound analysis)
    ├── Pharmacologist (drug applications)
    └── Synthesizer (integration)
           │
           ▼
    [Unified Response]
```

---

## Demo: Mangliwood Research Swarm

AutoJaga-Base includes a demo swarm for botanical research:

```bash
python -m autojaga

> /swarm What compounds in Styrax benzoin have antimicrobial activity?

# 5 specialist agents analyze the question:
# - Botanist: Styrax taxonomy and ecology
# - Materials Scientist: Resin properties
# - Chemist: Compound identification
# - Pathologist: Antimicrobial mechanisms
# - Synthesizer: Cross-disciplinary integration
```

---

## Configuration

Configuration at `~/.autojaga/config.json`:

```json
{
  "providers": {
    "openai": {"api_key": "sk-..."}
  },
  "defaults": {
    "model": "openai/gpt-4o",
    "max_tool_iterations": 10
  }
}
```

---

## Smoke Test

```bash
python -m pytest tests/test_smoke.py -v
```

---

## Related Projects

| Repo | Level | Description |
|------|-------|-------------|
| [JagaChatbot](https://github.com/matparang/JagaChatbot) | Level 1 | Conversational chatbot |
| [JagaRAG](https://github.com/matparang/JagaRAG) | Level 2 | Retrieval-augmented reasoning |
| **AutoJaga-Base** (this) | Level 3 | Autonomous multi-agent system |

---

## License

MIT — see [LICENSE](LICENSE)

---

## Author

Built by [@matparang](https://github.com/matparang)

> *"Most agents answer questions. AutoJaga tries to get better at answering them."*
