# JAGABOT QUICK REFERENCE GUIDE

## 🔍 QUICK FACTS

| Item | Value |
|------|-------|
| **Jagabot Version** | 0.1.0 |
| **Config Location** | `~/.jagabot/config.json` |
| **Workspace Dir** | `~/.jagabot/workspace/` |
| **History File** | `~/.jagabot/history/cli_history` |
| **Evolution State** | `~/.jagabot/workspace/evolution_state.json` |

---

## 🛠️ TOOL REGISTRY QUICK COMPARISON

### Swarm Registry (`jagabot/swarm/tool_registry.py`)
```python
# Read-only, class mapping
get_tool_class(name)      # → type | None
get_all_tool_names()      # → list[str]
get_tool_count()          # → int
```
- **Use:** Swarm worker instantiation
- **Size:** 40 LOC

### Agent Registry (`jagabot/agent/tools/registry.py`)
```python
# Full lifecycle, instance-based
registry.register(tool)
registry.unregister(name)
registry.get(name)              # → Tool | None
registry.has(name)              # → bool
await registry.execute(name, params)  # Async!
registry.get_definitions()      # → OpenAI schema
```
- **Use:** Agent tool management
- **Size:** 74 LOC

---

## 🧪 32 BUILT-IN TOOLS

**Location:** `jagabot/guardian/tools/` → `jagabot/agent/tools/__init__.py` (ALL_TOOLS list)

**Categories:**
- **Financial:** FinancialCVTool, VaRTool, CVaRTool, PortfolioAnalyzerTool
- **Analysis:** MonteCarloTool, StressTestTool, CorrelationTool, RecoveryTimeTool
- **ML/AI:** BayesianTool, DynamicsTool, StatisticalTool, EarlyWarningTool
- **Meta:** MetaLearningTool, K1BayesianTool, K3PerspectiveTool
- **Knowledge:** KnowledgeGraphTool, MemoryFleetTool, EvaluationTool
- **Other:** DecisionTool, EducationTool, CopywriterTool, SelfImproverTool, ReviewTool, SkillTriggerTool, EvolutionTool, etc.

**Registration:**
```python
from jagabot.guardian.tools import register_jagabot_tools
register_jagabot_tools(registry)  # Register all 32 tools
```

---

## 🚀 MCP INTEGRATION

### Existing MCP Server (TypeScript)
**Path:** `/root/nanojaga/deepseek-mcp-server/`
- **Version:** 0.4.0
- **Tools:** 8 (chat, completion, models, balance, vision, image, video)
- **Transports:** Stdio, Streamable HTTP

### Existing MCP Client (Python)
**Path:** `/root/nanojaga/nanobot/nanobot/agent/tools/mcp.py`
```python
await connect_mcp_servers(
    mcp_servers={"deepseek": {url: "...", headers: {...}}},
    registry=registry,
    stack=stack
)
```
- Wraps MCP tools as native Tools
- Supports: Stdio + Streamable HTTP
- Names tools: `mcp_{server}_{tool_name}`

---

## 🧬 EVOLUTION ENGINE

**File:** `jagabot/evolution/engine.py` (499 LOC)

### 4-Layer Safety:
1. **Mutation Clamping:** ×0.90–×1.10 only
2. **Sandbox:** 50-cycle test period
3. **Fitness Check:** Accept only if fitness improves
4. **Auto-Rollback:** Revert on rejection

### Key Methods:
```python
engine = EvolutionEngine(storage_path, parameter_values)

engine.cycle()              # → {cycle, fitness, action, mutation}
engine.get_status()         # → {cycle, fitness, params, ...}
engine.get_mutations(20)    # → Recent mutations with results
engine.get_targets()        # → Tunable targets with descriptions
engine.force_mutation(target, factor)  # Bypass governor
engine.cancel_sandbox()     # Rollback active mutation
```

### Tunable Targets:
```python
RISK_THRESHOLD = 0.95              # VaR confidence (0.90–0.99)
VOLATILITY_WEIGHT = 0.30           # CV pattern weight
CORRELATION_THRESHOLD = 0.60       # Alert trigger
PERSPECTIVE_WEIGHT = 0.35          # K3 bear/buffet balance
LEARNING_RATE = 0.40               # MetaLearning threshold
```

### Fitness Formula:
```
Fitness = 0.40 × param_balance + 0.30 × accepted_ratio + 0.30 × stability
```

---

## ⚙️ CONFIG SYSTEM

**File:** `jagabot/config/schema.py` (310 LOC)

### Main Sections:
```python
config.agents.defaults       # Model, max_tokens, temperature, etc.
config.channels             # WhatsApp, Telegram, Discord, Slack, Email, etc.
config.providers            # 14 LLM providers (Anthropic, OpenAI, DeepSeek, etc.)
config.gateway              # Host/port for API gateway
config.tools                # Web search, exec timeout, sandbox limits, visualization
```

### LLM Providers (14):
- anthropic, openai, deepseek, openrouter, groq, zhipu, dashscope
- vllm, gemini, moonshot, minimax, aihubmix, custom

### Loading:
```python
from jagabot.config import load_config, save_config
cfg = load_config()  # ~/.jagabot/config.json or default
cfg.get_api_key(model)     # → API key for model
cfg.get_provider_name(model)  # → Provider name (e.g., "deepseek")
```

### Environment Overrides:
```bash
export JAGABOT_AGENTS__DEFAULTS__MODEL=deepseek/r1
export JAGABOT_PROVIDERS__DEEPSEEK__API_KEY=sk-...
```

---

## 📍 CLI STRUCTURE

**Framework:** Typer (async-capable)

**Main File:** `jagabot/cli/commands.py`

**Features:**
- Prompt toolkit with persistent history
- Multi-line input support
- Terminal state management

**Sub-commands:**
```
jagabot --help
jagabot lab --help     # Lab: tool execution & parallel workflows
```

**Exit Commands:** exit, quit, /exit, /quit, :q

---

## 📦 KEY DIRECTORY STRUCTURE

```
/root/nanojaga/jagabot/
├── agent/
│   ├── __init__.py
│   ├── context.py
│   ├── loop.py
│   ├── skills.py
│   ├── subagent.py
│   └── tools/
│       ├── base.py           ← Tool abstract class
│       ├── registry.py        ← Agent registry (full-featured)
│       ├── __init__.py        ← ALL tool imports
│       └── [32 tool files]
├── evolution/
│   ├── engine.py             ← 4-layer safety evolution
│   └── targets.py            ← Tunable parameters
├── swarm/
│   └── tool_registry.py       ← Swarm registry (lightweight)
├── config/
│   ├── loader.py
│   └── schema.py             ← Pydantic Config
├── cli/
│   ├── commands.py           ← Main CLI
│   ├── lab_commands.py       ← Lab sub-commands
│   └── daemon.py
├── guardian/
│   ├── __init__.py
│   └── tools/
│       ├── __init__.py       ← ALL_TOOLS export
│       └── [32 tool files]
├── channels/
├── memory/
├── kernels/
├── ui/
├── voice/
└── __init__.py              ← Version 0.1.0, logo 🐈

/root/nanojaga/deepseek-mcp-server/       ← MCP Server (TypeScript)
/root/nanojaga/nanobot/nanobot/agent/tools/mcp.py  ← MCP Client
```

---

## 🔗 DATA FLOW EXAMPLES

### Example 1: Register & Execute a Tool
```python
from jagabot.agent.tools import ToolRegistry, FinancialCVTool

registry = ToolRegistry()
tool = FinancialCVTool()
registry.register(tool)

# Execute
result = await registry.execute("financial_cv", {"param": "value"})
```

### Example 2: Load All Jagabot Tools
```python
from jagabot.agent.tools import ToolRegistry
from jagabot.guardian.tools import register_jagabot_tools

registry = ToolRegistry()
register_jagabot_tools(registry)  # Register all 32
print(registry.tool_names)  # → ['financial_cv', 'monte_carlo', ...]
```

### Example 3: Connect MCP Server
```python
from contextlib import AsyncExitStack
from jagabot.agent.tools import ToolRegistry
from nanobot.agent.tools.mcp import connect_mcp_servers

async with AsyncExitStack() as stack:
    registry = ToolRegistry()
    await connect_mcp_servers(
        {"deepseek": {"url": "https://...", "headers": {...}}},
        registry,
        stack
    )
    # Now registry has mcp_deepseek_* tools
```

### Example 4: Evolution Cycle
```python
from jagabot.evolution.engine import EvolutionEngine

engine = EvolutionEngine()
for _ in range(1000):
    result = engine.cycle()
    print(f"Cycle {result['cycle']}: {result['action']}")
    if result.get('mutation'):
        print(f"  Target: {result['mutation']['target']}")
```

---

## 🎯 KEY INSIGHTS FOR IMPLEMENTATION

1. **Tool Registration is Dual-Pattern:**
   - Swarm: class-based (lightweight, read-only)
   - Agent: instance-based (full lifecycle, async)

2. **MCP Already Integrated at Nanobot Level:**
   - Use `connect_mcp_servers()` to attach MCP servers to any ToolRegistry
   - Tools are wrapped and renamed: `mcp_{server}_{tool}`

3. **Config is Schema-Driven:**
   - Pydantic + JSON file
   - Environment overrides via `JAGABOT_` prefix
   - Multiple providers auto-selected by keyword matching

4. **Evolution is Conservative:**
   - 4-layer safety prevents drift
   - Governor ensures minimum 100 cycles between mutations
   - All state persisted to JSON

5. **All Tools Are Async:**
   - `async def execute(**kwargs) -> str`
   - Registry.execute() is async
   - Validation happens before execution

