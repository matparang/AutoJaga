# AutoJagaMAS — Level 4 Multi-Agent System

**AutoJaga's cognitive BDI engine × MASFactory's visual graph orchestration**

---

## What This Demonstrates Architecturally

AutoJagaMAS is a **portfolio-grade integration project** that bridges two independent
AI frameworks into a coherent multi-agent research system:

| Framework | Role |
|-----------|------|
| **AutoJaga** (`legacy/jagabot/`) | BDI cognitive stack — fluid dispatching, two-tier model routing, calibrated belief scoring |
| **MASFactory** (`matparang/MASFactory`) | Visual graph orchestration — node editing, websocket state broadcasting, graph topology |

The integration demonstrates:

1. **Adapter pattern** — wrapping AutoJaga's async cognitive stack as MASFactory's synchronous Model/ContextProvider interfaces
2. **Two-tier model routing** — local Qwen 3B for routine specialist tasks, cloud Claude Sonnet for synthesis and orchestration
3. **BDI state propagation** — cognitive metadata (complexity, confidence, escalation) flowing through graph edges
4. **Graceful degradation** — all components work without MASFactory installed (stub implementations), without API keys (local-only mode), and without GPU

---

## DeepMind AGI Levels Positioning

```
Level 0  ──  JagaChatbot (chat only)
Level 0  ──  JagaRAG (retrieval + chat)
Level 1  ──  AutoJaga (tool-using agent with memory)
Level 1→2 ─  AutoJagaMAS (multi-agent swarm)    ← THIS PROJECT
Level 2  ──  (requires closed self-improvement loop — see docs/AGI_LEVELS.md)
```

AutoJagaMAS is a **Level 1→2 bridge**: it demonstrates multi-agent orchestration,
cross-agent belief sharing, and calibrated confidence — the foundations for Level 2
Competent AGI, but without yet closing the self-improvement loop.

See [`docs/AGI_LEVELS.md`](docs/AGI_LEVELS.md) for the full analysis.

---

## The Mangliwood Demo

The demo investigates **Styrax sumatrana** (Mangliwood), a Malaysian timber species
with three unresolved research paradoxes:

1. **Density anomaly** — 25–35% denser than expected for its family
2. **Resin composition** — inverted cinnamic/benzoic acid ester ratio vs. Sumatra standard
3. **Pathogen resistance** — unusual resistance to Phytophthora root rot

A 5-agent swarm attacks all three simultaneously:

```
entry → conductor → [botanist, chemist, pathologist] → synthesiser → exit
```

The synthesiser proposes a unifying hypothesis connecting all three paradoxes.

See [`docs/MANGLIWOOD_RESEARCH.md`](docs/MANGLIWOOD_RESEARCH.md) for the full research brief.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          AutoJagaMAS                                │
│                                                                     │
│  AutoJaga Layer              MASFactory Layer                       │
│  ──────────────              ──────────────────                     │
│  FluidDispatcher    ──────▶  JagaBDIContextProvider                 │
│  CognitiveStack     ──────▶  JagaBDIModel                           │
│  ModelSwitchboard   ──────▶  JagaModelRouter                        │
│                                                                     │
│  Model Tier 1: ollama/qwen2.5:3b      (local, CPU, free)            │
│  Model Tier 2: anthropic/claude-sonnet-4-6  (cloud, reasoning)      │
│                                                                     │
│  Graph: conductor → [botanist | chemist | pathologist] → synthesiser│
└─────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
AutoJagaMAS/
├── core/
│   ├── jaga_bdi_context_provider.py   # FluidDispatcher → ContextProvider
│   ├── jaga_bdi_model.py              # CognitiveStack → Model adapter
│   └── jaga_model_router.py           # ModelSwitchboard → routing
├── agents/
│   └── jaga_bdi_agent.py              # MASFactory Agent + BDI
├── personas/
│   ├── conductor.yaml                 # Research orchestrator
│   ├── botanist.yaml                  # Morphology/ecology specialist
│   ├── chemist.yaml                   # Resin chemistry specialist
│   ├── pathologist.yaml               # Disease/resistance specialist
│   └── synthesiser.yaml               # Synthesis and brief-writing
├── graphs/
│   ├── mangliwood_swarm.py            # 5-agent Mangliwood demo
│   └── base_mas_template.py           # Reusable graph factory
├── contracts/
│   └── jagashell_contract.py          # Intent/result schemas
├── config/
│   └── ajm_config.json                # Model routing config
├── docs/
│   ├── ARCHITECTURE.md                # Component diagrams + data flow
│   ├── AGI_LEVELS.md                  # DeepMind levels positioning
│   ├── EXPLAIN_SIMPLY.md              # Plain English with MY analogies
│   └── MANGLIWOOD_RESEARCH.md         # The specimen story + 3 paradoxes
├── tests/
│   └── test_smoke.py                  # 15 smoke tests, no GPU, no API keys
├── LEGACY_NOTES.md                    # Bugs found but not fixed (audit notes)
├── requirements.txt
├── .env.example
└── README.md                          # (this file)
```

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/matparang/AutoJaga.git
cd AutoJaga/AutoJagaMAS
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY for cloud model
# For local-only mode, start Ollama: ollama run qwen2.5:3b
```

### 3. Run the smoke tests (no GPU, no API keys needed)

```bash
cd AutoJagaMAS
python -m pytest tests/test_smoke.py -v
```

Expected: **15 passed**.

### 4. Run the Mangliwood swarm

```python
import sys
sys.path.insert(0, ".")  # from AutoJagaMAS/ directory

from graphs.mangliwood_swarm import build_mangliwood_swarm
from contracts.jagashell_contract import JagaShellIntent, JagaShellResult

# Build the 5-agent swarm
graph = build_mangliwood_swarm()

# Create a research intent
intent = JagaShellIntent(
    query="Styrax sumatrana density records Malaysia — what explains the density anomaly?",
    source_node="user",
    target_node="conductor",
    profile="RESEARCH",
)

# Run the swarm
raw_output = graph.run(intent.query)

# Wrap in a structured result
result = JagaShellResult.from_graph_output(raw_output, intent=intent)
print(result.to_json())
```

### 5. Use as a template for new swarms

```python
from graphs.base_mas_template import build_mas_graph

graph = build_mas_graph(
    name="climate_swarm",
    persona_configs=[
        {"node_name": "lead",      "persona": "conductor"},
        {"node_name": "physicist", "persona": "chemist"},    # reuse chemist persona
        {"node_name": "summary",   "persona": "synthesiser"},
    ],
    edges=[
        ("entry",     "lead"),
        ("lead",      "physicist"),
        ("physicist", "summary"),
        ("summary",   "exit"),
    ],
)
result = graph.run("What explains the 2024 SST anomaly in the Straits of Malacca?")
```

---

## Legacy Fixes Applied

Three surgical fixes were applied to `legacy/jagabot/` as part of this integration:

| Fix | File | Description |
|-----|------|-------------|
| Fix 1 | `agent/loop.py` | Wire `CognitiveStack.process()` into `_process_message` |
| Fix 2 | `providers/registry.py` | Add Ollama `ProviderSpec` (local model routing) |
| Fix 3 | `core/model_switchboard.py` | Support `model_presets` key + fix `get_tool_definition` schema |

See [`LEGACY_NOTES.md`](LEGACY_NOTES.md) for additional bugs found but not fixed (audit notes only).

---

## Documentation

| Document | Audience | Description |
|----------|----------|-------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Technical | Component diagrams, data flow, BDI state propagation |
| [`docs/AGI_LEVELS.md`](docs/AGI_LEVELS.md) | Technical/Assessment | DeepMind framework positioning, what's missing for Level 2 |
| [`docs/EXPLAIN_SIMPLY.md`](docs/EXPLAIN_SIMPLY.md) | Non-technical | Plain English with Malaysian business analogies |
| [`docs/MANGLIWOOD_RESEARCH.md`](docs/MANGLIWOOD_RESEARCH.md) | Research | The specimen, 3 paradoxes, swarm approach, priority questions |

---

## Requirements

```
masfactory>=0.1.0   # Graph orchestration framework
pyyaml>=6.0         # Persona YAML loading
loguru>=0.7.0       # Logging
litellm>=1.0.0      # LLM provider routing (Ollama + Anthropic)
```

**Optional for async nesting:**
```
nest_asyncio>=1.5.0  # Required if running inside Jupyter or FastAPI
```

---

## Roadmap

- [ ] NemoClaw integration — `JagaShellResult` → NemoClaw reasoning pipeline (`# TODO: wire to NemoClaw when v0.3 stable`)
- [ ] MASFactory VSCode visualizer hooks — websocket state broadcasting per node
- [ ] Persistent swarm memory — cross-session vector store for specialist findings
- [ ] Closed self-improvement loop — BrierScorer feedback into CognitiveStack tier thresholds
- [ ] Parallel specialist execution — async fan-out in MASFactory graph (currently sequential in stub mode)
