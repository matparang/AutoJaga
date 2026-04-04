# AutoJagaMAS Architecture

## Overview

AutoJagaMAS is a **Level 4 Multi-Agent System** that integrates AutoJaga's cognitive BDI engine
with MASFactory's visual graph orchestration. It bridges two frameworks:

- **AutoJaga** — BDI cognitive stack with fluid dispatching, two-tier model routing, and calibrated belief scoring
- **MASFactory** — graph-based multi-agent orchestration with visual node editing and websocket state broadcasting

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          AutoJagaMAS                                │
│                                                                     │
│  ┌──────────────────────┐     ┌──────────────────────────────────┐  │
│  │   AutoJaga Layer     │     │      MASFactory Layer            │  │
│  │                      │     │                                  │  │
│  │  FluidDispatcher     │────▶│  JagaBDIContextProvider          │  │
│  │  (BDI Router)        │     │  (ContextProvider adapter)       │  │
│  │                      │     │                                  │  │
│  │  CognitiveStack      │────▶│  JagaBDIModel                    │  │
│  │  (Two-tier LLM)      │     │  (Model adapter)                 │  │
│  │                      │     │                                  │  │
│  │  ModelSwitchboard    │────▶│  JagaModelRouter                 │  │
│  │  (Model Selector)    │     │  (Node-level routing)            │  │
│  │                      │     │                                  │  │
│  │  BrierScorer         │     │  JagaBDIAgent                    │  │
│  │  (Trust Calibration) │     │  (Agent subclass)                │  │
│  │                      │     │                                  │  │
│  │  BeliefEngine        │     │  MAS Graph                       │  │
│  │  (Belief States)     │     │  (conductor→specialists→synth)   │  │
│  └──────────────────────┘     └──────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Model Tier                               │    │
│  │                                                             │    │
│  │  Tier 1: ollama/qwen2.5:3b    (local, CPU, no API key)     │    │
│  │  Tier 2: anthropic/claude-sonnet-4-6  (cloud, reasoning)   │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. User Query Arrives

```
User query
    │
    ▼
FluidDispatcher.dispatch(query)
    │
    ├── Classifies intent: RESEARCH / SIMPLE / CALIBRATION / ...
    ├── Loads relevant context strings
    ├── Selects active tool set
    └── Returns: DispatchPackage
```

### 2. BDI State → MASFactory Context

```
DispatchPackage
    │
    ▼
JagaBDIContextProvider.get_blocks(query)
    │
    ├── Block 1: context text (system prompt preamble)
    └── Block 2: BDI state metadata (profile, engines, tools, k1_assisted)
```

### 3. Routing Decision

```
DispatchPackage.profile
    │
    ▼
JagaModelRouter.route(package)
    │
    ├── SIMPLE / MAINTENANCE / ACTION / SAFE_DEFAULT → ollama/qwen2.5:3b
    └── RESEARCH / VERIFICATION / CALIBRATION / AUTONOMOUS → anthropic/claude-sonnet-4-6
```

### 4. Cognitive Processing

```
Query + Profile + Context + Tools
    │
    ▼
CognitiveStack.process()
    │
    ├── Classifier: SIMPLE → Model 1 direct (1 LLM call)
    ├── Classifier: COMPLEX → Model 2 plans + Model 1 executes (2+ LLM calls)
    └── Classifier: CRITICAL → Model 2 handles entirely (calibration writes)
    │
    ▼
StackResult { output, complexity, model1_calls, model2_calls, elapsed_ms }
```

### 5. Graph Orchestration (Mangliwood Swarm)

```
entry
  │
  ▼
conductor (JagaBDIAgent, cloud tier)
  │         Decomposes query, assigns subtasks
  ├──────────────────────┬──────────────────────┐
  ▼                      ▼                      ▼
botanist               chemist            pathologist
(local tier)           (local tier)        (local tier)
  │                      │                      │
  └──────────────────────┴──────────────────────┘
                          │
                          ▼
                    synthesiser (JagaBDIAgent, cloud tier)
                    │   Combines findings → research brief
                    ▼
                   exit
```

---

## BDI State Flow Through Graph Edges

BDI state is carried as metadata through graph edges via `response["bdi_metadata"]`.
Each JagaBDIAgent's `think()` return dict contains:

```python
{
    "type": "content",
    "content": "...",          # Primary output
    "persona": "botanist",     # Which persona produced this
    "bdi_metadata": {
        "complexity": "simple",
        "model1_calls": 1,
        "model2_calls": 0,
        "escalated": False,
        "elapsed_ms": 120.5,
        "profile": "RESEARCH",
        "engines_active": ["web_search", "researcher"],
    }
}
```

The synthesiser node reads `node_results` from all specialist nodes, extracts
BDI metadata, and uses it to weight confidence in the final synthesis brief.

---

## File Structure

```
AutoJagaMAS/
├── core/                          # AutoJaga → MASFactory adapters
│   ├── jaga_bdi_context_provider.py  # FluidDispatcher → ContextProvider
│   ├── jaga_bdi_model.py             # CognitiveStack → Model adapter
│   └── jaga_model_router.py          # ModelSwitchboard → routing
├── agents/
│   └── jaga_bdi_agent.py             # MASFactory Agent + BDI
├── personas/                      # YAML persona definitions
│   ├── conductor.yaml
│   ├── botanist.yaml
│   ├── chemist.yaml
│   ├── pathologist.yaml
│   └── synthesiser.yaml
├── graphs/
│   ├── mangliwood_swarm.py           # 5-agent demo graph
│   └── base_mas_template.py          # Reusable graph factory
├── contracts/
│   └── jagashell_contract.py         # Intent/result schemas
├── config/
│   └── ajm_config.json               # Model routing config
├── docs/                          # Documentation
├── tests/
│   └── test_smoke.py                 # Smoke tests (no GPU, no API keys)
├── requirements.txt
├── .env.example
└── README.md
```
