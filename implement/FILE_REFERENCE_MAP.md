# JAGABOT FILE REFERENCE MAP

## Core Files Referenced in Exploration

| File | Location | Size | Purpose | Key Methods/Classes |
|------|----------|------|---------|---------------------|
| **jagabot/__init__.py** | `/root/nanojaga/jagabot/` | 7 LOC | Version & branding | `__version__`, `__logo__` |
| **agent/tools/base.py** | `jagabot/agent/tools/` | 103 LOC | Tool interface | `Tool` (ABC) with `execute()`, `validate_params()`, `to_schema()` |
| **agent/tools/registry.py** | `jagabot/agent/tools/` | 74 LOC | Full-featured registry | `ToolRegistry.register()`, `execute()`, `get_definitions()` |
| **swarm/tool_registry.py** | `jagabot/swarm/` | 40 LOC | Lightweight registry | `get_tool_class()`, `get_all_tool_names()`, `get_tool_count()` |
| **evolution/engine.py** | `jagabot/evolution/` | 499 LOC | Self-evolution engine | `EvolutionEngine.cycle()`, `get_status()`, `force_mutation()` |
| **evolution/targets.py** | `jagabot/evolution/` | 38 LOC | Tunable parameters | `MutationTarget` enum, `DEFAULT_VALUES`, `TARGET_DESCRIPTIONS` |
| **config/schema.py** | `jagabot/config/` | 310 LOC | Configuration schema | `Config`, `AgentsConfig`, `ChannelsConfig`, `ProvidersConfig` |
| **config/loader.py** | `jagabot/config/` | 107 LOC | Config I/O | `load_config()`, `save_config()`, `get_config_path()` |
| **config/__init__.py** | `jagabot/config/` | 7 LOC | Config exports | Exports `Config`, `load_config`, `get_config_path` |
| **cli/commands.py** | `jagabot/cli/` | 46+ LOC (excerpt) | CLI main | Typer app, prompt toolkit, exit handlers |
| **cli/lab_commands.py** | `jagabot/cli/` | 7.6 KB | Lab sub-commands | Tool execution, parallel workflows |
| **cli/__init__.py** | `jagabot/cli/` | 2 LOC | CLI module marker | Empty module marker |
| **agent/tools/__init__.py** | `jagabot/agent/tools/` | 74 LOC | Tool exports | 32 tool imports, `register_jagabot_tools()` |
| **guardian/tools/__init__.py** | `jagabot/guardian/tools/` | 78 LOC | Master tool list | `ALL_TOOLS` list, `register_jagabot_tools()` |

---

## Tool Files (32 Total)

### Location: `/root/nanojaga/jagabot/agent/tools/`

**Financial/Portfolio Tools:**
- `financial_cv.py` - Financial cross-validation
- `portfolio_analyzer.py` - Portfolio analysis
- `var.py` - Value at Risk
- `cvar.py` - Conditional VaR
- `correlation.py` - Correlation analysis
- `recovery_time.py` - Recovery time metrics

**Analysis & Testing:**
- `monte_carlo.py` - Monte Carlo simulation
- `stress_test.py` - Stress testing
- `bayesian.py` - Bayesian analysis
- `statistical.py` - Statistical methods
- `early_warning.py` - Early warning indicators
- `dynamics.py` - Dynamics analysis

**Optimization & Decision Making:**
- `pareto.py` - Pareto analysis
- `counterfactual.py` - Counterfactual reasoning
- `sensitivity.py` - Sensitivity analysis
- `decision.py` - Decision making
- `evaluation.py` - Evaluation framework

**Knowledge & Learning:**
- `knowledge_graph.py` - Knowledge graph
- `memory_fleet.py` - Memory fleet management
- `meta_learning.py` - Meta-learning
- `k1_bayesian.py` - K1 Bayesian perspective
- `k3_perspective.py` - K3 perspective (bear/buffet)

**Visualization & Communication:**
- `visualization.py` - Chart/graph generation
- `education.py` - Educational content
- `researcher.py` - Research tasks
- `copywriter.py` - Content writing

**Meta & System Tools:**
- `accountability.py` - Accountability tracking
- `skill_trigger.py` - Skill triggering
- `subagent.py` - Sub-agent management
- `evolution.py` - Evolution tool wrapper
- `review.py` - Review functionality
- `self_improver.py` - Self-improvement tool

---

## MCP-Related Files

| File | Language | Location | Purpose |
|------|----------|----------|---------|
| **mcp-server.ts** | TypeScript | `deepseek-mcp-server/src/` | Main MCP server (150+ LOC) |
| **index.ts** | TypeScript | `deepseek-mcp-server/src/` | Server startup & config |
| **client.ts** | TypeScript | `deepseek-mcp-server/src/deepseek/` | DeepSeek API client |
| **schemas.ts** | TypeScript | `deepseek-mcp-server/src/deepseek/` | Request/response schemas |
| **conversation-store.ts** | TypeScript | `deepseek-mcp-server/src/` | Session state management |
| **server.json** | JSON | `deepseek-mcp-server/` | MCP registry manifest |
| **mcp.py** | Python | `nanobot/nanobot/agent/tools/` | MCP client wrapper (92 LOC) |
| **test_v2_mcp.py** | Python | `nanobot/tests/` | MCP test suite |

---

## Configuration Files

| File | Location | Format | Purpose |
|------|----------|--------|---------|
| **config.json** | `~/.jagabot/` | JSON | Main configuration file |
| **.env** | `deepseek-mcp-server/` | Shell | DeepSeek server env vars |
| **smithery.yaml** | `deepseek-mcp-server/` | YAML | Smithery MCP registry |
| **tsconfig.json** | `deepseek-mcp-server/` | JSON | TypeScript config |

---

## Build & Package Files

| File | Location | Format | Purpose |
|------|----------|--------|---------|
| **pyproject.toml** | `/root/nanojaga/` | TOML | Python project config |
| **package.json** | `deepseek-mcp-server/` | JSON | Node.js dependencies |
| **Dockerfile** | `deepseek-mcp-server/` | Dockerfile | Docker container |
| **.dockerignore** | `deepseek-mcp-server/` | Text | Docker build exclusions |

---

## Directory Tree (Key Paths)

```
/root/nanojaga/
├── jagabot/                          # Main framework
│   ├── __init__.py                  # Version 0.1.0
│   ├── agent/                       # Agent logic
│   │   ├── context.py
│   │   ├── loop.py
│   │   ├── skills.py
│   │   ├── subagent.py
│   │   └── tools/                  # Tool registry & base
│   │       ├── base.py             # Tool ABC
│   │       ├── registry.py         # Agent registry
│   │       ├── __init__.py         # Tool exports
│   │       └── [32 tool files]
│   ├── evolution/                  # Self-evolution
│   │   ├── engine.py               # EvolutionEngine (499 LOC)
│   │   ├── targets.py              # MutationTarget enum
│   │   └── __init__.py
│   ├── swarm/                      # Swarm workers
│   │   └── tool_registry.py        # Swarm registry (40 LOC)
│   ├── config/                     # Configuration
│   │   ├── schema.py               # Pydantic schemas (310 LOC)
│   │   ├── loader.py               # Config I/O
│   │   └── __init__.py
│   ├── cli/                        # CLI interface
│   │   ├── commands.py             # Main CLI
│   │   ├── lab_commands.py         # Lab sub-commands
│   │   ├── daemon.py               # Daemon process
│   │   └── __init__.py
│   ├── guardian/                   # Tool definitions
│   │   ├── __init__.py             # ALL_TOOLS list
│   │   └── tools/                  # 32+ tool files
│   ├── channels/                   # Communication
│   ├── memory/                     # Memory systems
│   ├── kernels/                    # Computation kernels
│   ├── ui/                         # User interface
│   ├── voice/                      # Voice/audio
│   └── [other modules]
│
├── deepseek-mcp-server/             # MCP Server (TypeScript)
│   ├── src/
│   │   ├── mcp-server.ts           # Main server
│   │   ├── index.ts                # Startup
│   │   ├── deepseek/               # DeepSeek client
│   │   │   ├── client.ts
│   │   │   ├── schemas.ts
│   │   │   └── types.ts
│   │   ├── conversation-store.ts
│   │   └── transports/             # Transport layer
│   ├── server.json                 # MCP registry
│   ├── package.json
│   ├── Dockerfile
│   └── [tests, config, etc]
│
├── nanobot/                        # Legacy nanobot
│   ├── nanobot/
│   │   └── agent/
│   │       └── tools/
│   │           └── mcp.py          # MCP client wrapper
│   └── tests/
│       └── test_v2_mcp.py
│
├── implement/                      # This exploration output
│   ├── CODEBASE_EXPLORATION.md    # Detailed analysis
│   ├── QUICK_REFERENCE.md         # Quick lookup
│   └── FILE_REFERENCE_MAP.md      # This file
│
└── [pyproject.toml, README.md, etc]
```

---

## Quick Navigation

**Want to understand:**
- **Tool system?** → Start with `agent/tools/base.py` → `registry.py`
- **All tools?** → `guardian/tools/__init__.py` (ALL_TOOLS list)
- **Configuration?** → `config/schema.py` (Pydantic models)
- **Evolution?** → `evolution/engine.py` (499 LOC, well-commented)
- **CLI?** → `cli/commands.py` + `cli/lab_commands.py`
- **MCP?** → `deepseek-mcp-server/src/mcp-server.ts` + `nanobot/agent/tools/mcp.py`

---

## File Statistics

| Category | Count | Total LOC |
|----------|-------|-----------|
| Python Core (9 files) | 9 | ~1,067 |
| Tool Files (32) | 32 | Multiple |
| Config Files | 4 | 417 |
| CLI Files | 3 | ~55+ |
| MCP Server (TypeScript) | 6 | ~500+ |
| MCP Client (Python) | 2 | ~92 |
| Tests | 2 | Multiple |
| Documentation | 40+ | Multiple |

---

## Import Paths (Common)

```python
# Configuration
from jagabot.config import Config, load_config, get_config_path

# Tools
from jagabot.agent.tools import Tool, ToolRegistry
from jagabot.guardian.tools import register_jagabot_tools, ALL_TOOLS

# Evolution
from jagabot.evolution.engine import EvolutionEngine
from jagabot.evolution.targets import MutationTarget, DEFAULT_VALUES

# CLI
from jagabot.cli import app  # Typer app

# MCP (Nanobot)
from nanobot.agent.tools.mcp import connect_mcp_servers, MCPToolWrapper
```

---

## Key Constants

| Constant | Value | Location |
|----------|-------|----------|
| `__version__` | "0.1.0" | `jagabot/__init__.py` |
| `__logo__` | "🐈" | `jagabot/__init__.py` |
| `MIN_MUTATION_FACTOR` | 0.90 | `evolution/engine.py` |
| `MAX_MUTATION_FACTOR` | 1.10 | `evolution/engine.py` |
| `SANDBOX_CYCLES` | 50 | `evolution/engine.py` |
| `MIN_CYCLES_BETWEEN` | 100 | `evolution/engine.py` |
| `SERVER_VERSION` | "0.4.0" | `deepseek-mcp-server/src/mcp-server.ts` |

