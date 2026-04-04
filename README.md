## What is AutoJaga?

AutoJaga is not a single project — it is a **deliberate progression**.

Each sub-project represents a distinct level of AI architecture complexity,
mapped to the DeepMind AGI performance framework. The goal is to show not 
just that AI systems can be built, but that the *architecture decisions* 
behind them matter — and that those decisions can be reasoned about clearly.

---

## The Four Levels

### 🟢 Level 1 — [JagaChatbot](./JagaChatbot/)
**DeepMind Classification: Emerging AGI**

A clean, minimal conversational agent with multi-provider LLM routing,
conversation memory, and history compression.

```
User → CLI/Telegram → LLM Provider (OpenAI / Anthropic / DeepSeek) → Response
                            ↑
                     Memory + Compression
```

**Key concepts demonstrated:**
- Multi-provider LLM abstraction
- Conversation history compression
- Stateful memory across turns
- Clean channel separation (CLI vs Telegram)

---

### 🔵 Level 2 — [JagaRAG](./JagaRAG/)
**DeepMind Classification: Competent AGI**

JagaChatbot extended with a full retrieval-augmented generation pipeline.
Agents retrieve from a vector store before responding — grounding outputs
in real documents rather than model priors.

```
User Query → Vector Search → Retrieved Chunks → LLM → Grounded Response
                  ↑
          Ingested Document Store
```

**Key concepts demonstrated:**
- Document ingestion pipeline
- Vector similarity search
- Retrieval-grounded response generation
- Hallucination reduction via context injection

**Demo dataset:** Field notes and research data from the Mangliwood specimen — 
an unidentified resinous wood recovered in Kedah, Malaysia, with anomalous 
physical properties. JagaRAG answers questions grounded in real field observations.

---

### 🔴 Level 3 — [AutoJaga](./AutoJaga/)
**DeepMind Classification: Expert AGI**

A fully autonomous multi-agent system with a custom BDI reasoning harness,
subagent spawning, swarm orchestration, and live MCP tool binding.

```
         CoPaw Conductor
        /       |        \
  Agent A    Agent B    Agent C
  [tools]    [tools]    [tools]
     ↓           ↓          ↓
  websearch  websearch  websearch
        \       |        /
         Synthesis Layer
               ↓
         Final Report
```

**Key concepts demonstrated:**
- BDI reasoning harness (Belief / Desire / Intention)
- Subagent spawning with tools bound at spawn time
- JagaSwarm multi-persona orchestration
- FluidDispatcher — structured output parsing and tool routing
- Confidence scoring and REVERSE WHEN logic
- MCP websearch as a live, callable bound tool

**Demo config:** Mangliwood elimination swarm — 5 specialist agents
(botanist, materials scientist, resin chemist, pathologist, synthesiser)
autonomously research an unidentified wood specimen across public botanical
and materials science databases, eliminating candidate species until a
convergence point is reached.

---

### 🟣 Level 4 — [AutoJagaMAS](./AutoJagaMAS/)
**DeepMind Classification: Virtuoso AGI**

A portfolio-grade integration bridging AutoJaga's cognitive BDI engine with 
MASFactory's visual graph orchestration — demonstrating multi-agent swarm 
coordination with two-tier model routing, cross-agent belief sharing, and 
calibrated confidence scoring.

```
         entry
           │
           ▼
       conductor (cloud tier)
     /     |     \
    ▼      ▼      ▼
 botanist chemist pathologist (local tier)
    \      |      /
     ▼     ▼     ▼
      synthesiser (cloud tier)
           │
           ▼
         exit
```

**Key concepts demonstrated:**
- Two-tier model routing (local Qwen 3B for specialists, cloud Claude for orchestration)
- BDI state propagation through graph edges
- Cross-agent belief sharing and confidence weighting
- Adapter pattern bridging autonomous BDI stack with graph orchestration
- Graceful degradation (works without GPU, without cloud API, without MASFactory)

**Demo dataset:** The same Mangliwood specimen from Level 2/3, but now attacked 
by a 5-agent swarm investigating three simultaneous research paradoxes:
density anomaly, inverted resin composition, and pathogen resistance.
The synthesiser produces a unified hypothesis connecting all three.

---

## Why This Architecture Progression?

Most AI agent tutorials jump straight to complex orchestration.
AutoJaga takes the opposite approach — each level adds exactly one
layer of architectural complexity, making the design decisions visible:

| What gets added | Why it matters |
|---|---|
| L1 → L2: Vector retrieval | Grounds agent in real knowledge, reduces hallucination |
| L2 → L3: Tool binding at spawn | Eliminates fabricated tool calls — agents do real work |
| L2 → L3: BDI harness | Makes agent reasoning inspectable and structured |
| L2 → L3: Subagent spawning | Parallelises research across specialist personas |
| L2 → L3: Confidence + REVERSE WHEN | Agents know when to stop and escalate |
| L3 → L4: Two-tier model routing | Optimizes cost/performance by matching model to task complexity |
| L3 → L4: Graph orchestration | Visual multi-agent coordination with state broadcasting |
| L3 → L4: Cross-agent belief sharing | Specialists share confidence metadata for synthesis weighting |
| L3 → L4: Adapter pattern integration | Bridges autonomous BDI stack with graph frameworks |

This mirrors how production AI systems actually scale — not by making
one agent smarter, but by composing multiple grounded, bounded agents
with clear responsibilities.

---

## DeepMind AGI Levels Reference

| Level | Name | Description | AutoJaga equivalent |
|---|---|---|---|
| 0 | No AI | Rule-based systems | — |
| 1 | Emerging | Matches unskilled human on some tasks | JagaChatbot |
| 2 | Competent | Outperforms 50% of skilled adults on a range of tasks | JagaRAG |
| 3 | Expert | Outperforms 90% of skilled adults | AutoJaga |
| 4 | Virtuoso | Outperforms 99% of skilled adults | AutoJagaMAS |
| 5 | Superhuman | Outperforms all humans | — |

AutoJaga targets architectural progression through Levels 1-4, not by claiming 
model performance — but by demonstrating the **architectural patterns** at each level:

- **Level 1:** Conversational memory and multi-provider routing
- **Level 2:** Retrieval-grounded response generation  
- **Level 3:** Autonomous reasoning, multi-agent coordination, grounded tool use
- **Level 4:** Multi-agent swarm orchestration with cross-agent belief sharing and two-tier model routing

---

## Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| LLM Providers | Anthropic, OpenAI, DeepSeek |
| Vector Store | Local vector memory |
| Tool Protocol | MCP (Model Context Protocol) |
| Agent Reasoning | Custom BDI harness |
| Interfaces | CLI, Telegram, FastAPI |
| Deployment | CPU-only (aarch64 Hetzner Ubuntu) |

---

## Repository Structure

```
AutoJaga/
├── JagaChatbot/        # Level 1 — Conversational agent
├── JagaRAG/            # Level 2 — Retrieval-augmented agent  
├── AutoJaga/           # Level 3 — Autonomous multi-agent system
├── AutoJagaMAS/        # Level 4 — Multi-agent swarm with graph orchestration
└── legacy/             # Original AutoJaga codebase (archived)
```

Each sub-project has its own `README.md`, `ARCHITECTURE.md`,
and a runnable smoke test.

---

## Getting Started

Each level is independently runnable. Start at Level 1:

```bash
cd JagaChatbot
cp .env.example .env
# Add your LLM provider key to .env
pip install -r requirements.txt
python test_smoke.py
```

Then move up:

```bash
cd ../JagaRAG
cd ../AutoJaga
cd ../AutoJagaMAS
```

---

## Project Status

| Sub-project | Status |
|---|---|
| JagaChatbot | ✅ Stable |
| JagaRAG | ✅ Stable |
| AutoJaga | 🔧 Active development |
| AutoJagaMAS | 🔬 Experimental |

---

## Background

AutoJaga started as a financial research agent and evolved into a 
general-purpose multi-agent framework through iterative development
on constrained hardware. The architecture decisions — BDI harness,
fluid dispatching, spawn-time tool binding — emerged from real debugging
sessions, not textbook design.

The Mangliwood demo is a real ongoing project: an attempt to use AI 
agent swarms to identify an unclassified wood specimen recovered in 
Kedah, Malaysia, through public botanical and materials science databases —
without access to a lab.

---

## License

MIT — see [LICENSE](./LICENSE)

---

*Built in Malaysia. Running on a CPU. Figuring it out one agent at a time.*
