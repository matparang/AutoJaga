# AutoJaga

> A self-improving AI research agent with calibrated reasoning, belief tracking, and knowledge solidification.

![AutoJaga Architecture](nanobot_arch.png)

---

## What is AutoJaga?

AutoJaga is a solo indie project — an AI agent designed to get *better over time*, not just answer questions.

Most AI agents forget everything after each session. AutoJaga is built around the opposite idea: every research run, every prediction, every outcome gets tracked, scored, and fed back into the agent's knowledge base. Over time it builds a calibrated model of what it knows, what it doesn't know, and where it's been wrong before.

**The core loop:**
```
Research → Predict → Act → Observe Outcome → Score → Solidify → Repeat
```

---

## Architecture

AutoJaga is built on the `jagabot` core — a modular agent framework with the following layers:

### Agent Core (`jagabot/`)
| Module | Purpose |
|--------|---------|
| `agent/loop.py` | Main agent loop — orchestrates all components |
| `kernels/brier_scorer.py` | Calibration scoring — tracks prediction accuracy over time |
| `core/cognitive_stack.py` | Adjusts reasoning depth based on domain confidence |
| `core/token_budget.py` | Token-aware execution — prevents runaway loops |
| `core/fluid_dispatcher.py` | Routes tasks to the right model dynamically |
| `core/librarian.py` | Knowledge retrieval and context management |
| `core/strategic_interceptor.py` | Catches and redirects low-quality reasoning paths |
| `engines/confidence_engine.py` | Tracks confidence per domain |
| `engines/curiosity_engine.py` | Drives autonomous exploration |

### Soul Layer (`jagabot/`)
| Module | Purpose |
|--------|---------|
| `guardian/` | Behavioral guardrails and safety checks |
| `evolution/` | Self-improvement mechanisms |
| `heartbeat/` | Health monitoring and uptime |
| `swarm/` | Multi-agent coordination via A2A protocol |

### Supporting Systems
| Directory | Purpose |
|-----------|---------|
| `frontend/` | PinchChat — React/TypeScript UI |
| `autoresearch/` | Automated research pipeline |
| `data/solidified/` | Knowledge graph — chess reasoning as a test domain |
| `deepseek-mcp-server/` | MCP server integration |
| `bridge/` | WebSocket bridge for external connections |

---

## Quickstart

### Requirements
- Python 3.12+
- Node.js 18+ (for frontend)

### Install
```bash
git clone https://github.com/matparang/AutoJaga.git
cd AutoJaga
pip install -e .
```

### Configure
```bash
cp .env.example .env
# Add your API keys to .env
```

### Run
```bash
python jagabot_direct.py
```

---

## Skills

AutoJaga comes with a large library of built-in skills across domains:

- **Research** — autonomous web research with lesson extraction
- **Financial Analysis** — DCF, LBO, comps, earnings analysis
- **Equity Research** — initiating coverage, morning notes, thesis tracking
- **Investment Banking** — CIM builder, pitch decks, deal tracking
- **Private Equity** — deal screening, IC memos, portfolio monitoring

Skills live in `jagabot/skills/` and follow the SKILL.md format.

---

## Roadmap

### Phase 1 — Wire existing components (in progress)
- [ ] Activate CognitiveStack dynamic reasoning adjustment
- [ ] Connect BrierScorer to live prediction data
- [ ] Automate Solidification after each research run

### Phase 2 — Build missing components
- [ ] BeliefEngine — downstream of BrierScorer
- [ ] ChallengeProblems — synthetic calibration data generator
- [ ] YOLO auto-lesson extraction

### Phase 3 — Close the loop
- [ ] MetaLearning reads from real calibration data
- [ ] Self-optimization based on Brier scores
- [ ] Multi-modal research inputs

---

## Project Structure
```
AutoJaga/
├── jagabot/              # Core agent
│   ├── agent/            # Loop, memory, tools
│   ├── core/             # CognitiveStack, TokenBudget, etc.
│   ├── engines/          # Confidence, Curiosity
│   ├── kernels/          # BrierScorer
│   ├── skills/           # Domain skill library
│   ├── swarm/            # A2A multi-agent
│   └── guardian/         # Behavioral safety
├── frontend/             # PinchChat React UI
├── autoresearch/         # Research automation
├── data/solidified/      # Knowledge graphs
├── deepseek-mcp-server/  # MCP integration
└── bridge/               # WebSocket bridge
```

---

## Built With

- [LiteLLM](https://github.com/BerriAI/litellm) — multi-model routing
- [Pydantic](https://docs.pydantic.dev/) — data validation
- [Rich](https://github.com/Textualize/rich) — terminal UI
- [python-telegram-bot](https://python-telegram-bot.org/) — Telegram channel
- React + Vite + TypeScript — frontend

---

## License

MIT — see [LICENSE](LICENSE)

---

## Author

Built by [@matparang](https://github.com/matparang) — solo indie project.

> *"Most agents answer questions. AutoJaga tries to get better at answering them."*
