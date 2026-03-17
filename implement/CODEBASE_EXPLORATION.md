# JAGABOT CODEBASE EXPLORATION REPORT

## 1. EXISTING MCP CLIENT & SERVER INFRASTRUCTURE

### A. MCP Server: deepseek-mcp-server (TypeScript/Node.js)
**Location:** `/root/nanojaga/deepseek-mcp-server/`

**Type:** Standalone MCP server for DeepSeek API endpoints

**Architecture:**
- **Framework:** Model Context Protocol (MCP) SDK v1.26.0
- **Transports:** 
  - Stdio (local, self-hosted)
  - Streamable HTTP (remote hosted endpoint)
- **Version:** 0.4.0 (as of Mar 9, 2025)

**Key Files:**
- `src/mcp-server.ts` (150+ LOC) - Main server with tool registration
- `src/index.ts` - Startup & configuration
- `src/deepseek/client.ts` - DeepSeek API client
- `server.json` - MCP registry manifest

**Registered Tools (via ENDPOINT_MATRIX):**
```
- chat_completion        (POST /chat/completions)
- completion             (POST /completions)
- list_models            (GET /models)
- get_user_balance       (GET /user/balance)
- vision_upload          (POST /v4/vision/upload) [experimental]
- image_generation       (POST /v4/image/generate) [experimental]
- video_upload           (POST /v4/video/upload) [experimental]
- video_generation       (POST /v4/video/generate) [experimental]
```

**Server Features:**
- Resources: deepseek-api-endpoints, deepseek-runtime
- Conversation state management via ConversationStore
- Retry logic for transient errors (408, 409, 429, 500-504)
- Schema validation with Zod

---

### B. MCP Client Implementation (Nanobot)
**Location:** `/root/nanojaga/nanobot/nanobot/agent/tools/mcp.py`

**Purpose:** Connects to MCP servers and wraps their tools as native agent tools

**Key Classes:**

```python
class MCPToolWrapper(Tool):
    """Wraps MCP server tool as nanobot Tool"""
    - Converts MCP tool_def → native Tool interface
    - Translates MCP textContent blocks → string result
    - Renames tools as: mcp_{server_name}_{original_name}
```

**Function:**
```python
async def connect_mcp_servers(
    mcp_servers: dict,          # Config dict {server_name: {command|url, args, headers}}
    registry: ToolRegistry,     # Target registry
    stack: AsyncExitStack
) -> None
```

**Supported Transports:**
1. **Stdio:** Command-based servers (StdioServerParameters)
2. **Streamable HTTP:** Remote servers with optional headers (httpx.AsyncClient)

**Flow:**
1. Spawn/connect to MCP server (stdio or HTTP)
2. Initialize ClientSession
3. List tools via session.list_tools()
4. Wrap each tool_def in MCPToolWrapper
5. Register wrapper in target ToolRegistry
6. Execute: wrapper.execute(**kwargs) → session.call_tool()

---

### C. MCP Test Infrastructure
**Location:** `/root/nanojaga/nanobot/tests/test_v2_mcp.py`

Example: Chess MCP wrapper validation testing

---

## 2. EXISTING TOOL REGISTRY IMPLEMENTATIONS

### A. Swarm Tool Registry (Simpler, Read-Only)
**File:** `/root/nanojaga/jagabot/swarm/tool_registry.py` (40 LOC)

**Design:** Lazy-loading, static mapping

**API:**
```python
def get_tool_class(name: str) -> type | None        # Get class by name
def get_all_tool_names() -> list[str]               # List all names
def get_tool_count() -> int                         # Count total tools
```

**Implementation:** 
- `_TOOL_MAP` dict populated lazily from `jagabot.guardian.tools.ALL_TOOLS`
- Each tool instantiated once to extract `instance.name`
- Maps tool name → tool class

**Used for:** Swarm worker instantiation

---

### B. Agent Tool Registry (Full-Featured)
**File:** `/root/nanojaga/jagabot/agent/tools/registry.py` (74 LOC)

**Design:** Instance-based registry with lifecycle management

**Core API:**
```python
class ToolRegistry:
    def register(tool: Tool) -> None              # Register instance
    def unregister(name: str) -> None             # Remove by name
    def get(name: str) -> Tool | None             # Retrieve instance
    def has(name: str) -> bool                    # Check existence
    
    # Execution
    async def execute(name: str, params: dict) -> str
        ├─ Validates params via tool.validate_params()
        └─ Returns: string result or error message
    
    # Introspection
    def get_definitions() -> list[dict]           # OpenAI schema format
    @property tool_names -> list[str]             # List all names
    def __len__() -> int                          # Tool count
    def __contains__(name: str) -> bool           # Membership test
```

**Validation:** 
- Calls `tool.validate_params(params)` before execution
- Returns error list (empty if valid)
- Comprehensive schema checking: required fields, types, enum values, min/max, length constraints

---

### C. Base Tool Class
**File:** `/root/nanojaga/jagabot/agent/tools/base.py` (103 LOC)

**Abstract Interface:**
```python
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str                # Unique identifier
    
    @property
    @abstractmethod
    def description(self) -> str         # User-facing docs
    
    @property
    @abstractmethod
    def parameters(self) -> dict         # JSON Schema
    
    @abstractmethod
    async def execute(self, **kwargs) -> str  # Execute logic
    
    # Validation & Conversion
    def validate_params(params: dict) -> list[str]     # Schema validation
    def to_schema() -> dict                # OpenAI function schema
```

**Type Mapping:** string, integer, number, boolean, array, object

---

## 3. EVOLUTION ENGINE

**File:** `/root/nanojaga/jagabot/evolution/engine.py` (499 LOC)

**Purpose:** Safe self-evolution with 4-layer safety protocol for financial parameter tuning

### Safety Layers:
1. **Factor Clamping:** Mutations constrained to ×0.90–×1.10
2. **Sandbox Testing:** 50 evaluation cycles before acceptance
3. **Fitness Validation:** Accept only if fitness improves
4. **Auto-Rollback:** Revert on rejection

### Governor:
- Minimum 100 cycles between mutations (cooldown)

### Core Classes:

```python
@dataclass
class Mutation:
    id, target, old_value, new_value, created_at, description
    factor() -> float              # Ratio of new/old value

@dataclass
class MutationResult:
    mutation_id, success, fitness_before, fitness_after,
    improvement, test_cycles, accepted_at

class MutationSandbox:
    active_mutation, fitness_before, start_cycle, test_cycles_remaining
    start_test(mutation, fitness_before, current_cycle)
    tick() -> bool                 # True when sandbox period complete
    cancel()

class EvolutionEngine:
    __init__(storage_path, parameter_values)
    params: dict[MutationTarget, float]
    cycle_count: int
    last_mutation_cycle: int
    mutations: dict[str, Mutation]
    results: list[MutationResult]
    sandbox: MutationSandbox
```

### Main Methods:

```python
def cycle() -> dict[str, Any]:
    """Run one evolution cycle, return {cycle, fitness, action, mutation}"""
    
def get_status() -> dict:
    """Return current state with params, fitness, cooldown, etc."""
    
def get_mutations(limit=20) -> list[dict]:
    """List recent mutations with acceptance status"""
    
def get_targets() -> list[dict]:
    """List all tunable targets with descriptions"""
    
def force_mutation(target: str, factor: float) -> dict | None:
    """Bypass governor, keep Layer 1 safety"""
    
def cancel_sandbox() -> bool:
    """Rollback active mutation"""
```

### Fitness Function:
Weighted score (0.0–1.0) combining:
- **param_balance** (40%): Penalize drift from defaults
- **accepted_ratio** (30%): Fraction of accepted mutations
- **stability** (30%): 1.0 if no active sandbox, 0.5 if testing

### Storage:
- Default: `~/.jagabot/workspace/evolution_state.json`
- Persists: cycle_count, mutations, results, params, sandbox state
- Lazy loading on init

### Mutation Targets:
**File:** `/root/nanojaga/jagabot/evolution/targets.py`

```python
enum MutationTarget:
    RISK_THRESHOLD = 0.95              # VaR confidence level
    VOLATILITY_WEIGHT = 0.30           # CV pattern weight
    CORRELATION_THRESHOLD = 0.60       # Alert trigger level
    PERSPECTIVE_WEIGHT = 0.35          # K3 bear/buffet balance
    LEARNING_RATE = 0.40               # MetaLearning threshold
```

---

## 4. CLI STRUCTURE

**Main File:** `/root/nanojaga/jagabot/cli/commands.py` (46+ LOC shown)

### Framework: Typer (async-enabled CLI)

**Root App:**
```python
app = typer.Typer(
    name="jagabot",
    help="🐈 jagabot - Personal AI Assistant"
)

# Sub-command groups
app.add_typer(lab_app, name="lab", help="Lab — tool execution & parallel workflows")
```

### Key Features (from commands.py):
1. **Prompt Toolkit Integration:**
   - FileHistory (persistent ~/.jagabot/history/cli_history)
   - Terminal state management (save/restore)
   - Input buffering/flushing

2. **EXIT_COMMANDS:** exit, quit, /exit, /quit, :q

### Sub-Commands (Lab Module):
**File:** `/root/nanojaga/jagabot/cli/lab_commands.py` (7.6 KB)
- Tool execution workflows
- Parallel task management

### Other CLI File:
**File:** `/root/nanojaga/jagabot/cli/daemon.py`
- Daemon process management

---

## 5. JAGABOT INITIALIZATION

**File:** `/root/nanojaga/jagabot/__init__.py` (7 LOC)

```python
__version__ = "0.1.0"
__logo__ = "��"
```

Minimal initialization — version and branding only.

---

## 6. AGENT TOOLS LOADING

**File:** `/root/nanojaga/jagabot/agent/tools/__init__.py` (74 LOC)

### Imports & Registration:
```python
# Imports all tool classes
from jagabot.agent.tools.base import Tool
from jagabot.agent.tools.registry import ToolRegistry
from jagabot.agent.tools.financial_cv import FinancialCVTool
# ... 35 more tool imports ...

__all__ = [
    "Tool", "ToolRegistry", "FinancialCVTool", "MonteCarloTool", ...
    # 37 exports total
]

def register_jagabot_tools(registry: ToolRegistry) -> None:
    """Register all Jagabot engine tools into a ToolRegistry."""
    for tool_cls in ALL_TOOLS:
        registry.register(tool_cls())
```

### ALL_TOOLS List (from /root/nanojaga/jagabot/guardian/tools/__init__.py):
32 financial/ML tools:
- FinancialCVTool, MonteCarloTool, DynamicsTool, StatisticalTool
- EarlyWarningTool, BayesianTool, CounterfactualTool, SensitivityTool
- ParetoTool, VisualizationTool, VaRTool, CVaRTool, StressTestTool
- CorrelationTool, RecoveryTimeTool, DecisionTool, EducationTool
- AccountabilityTool, ResearcherTool, CopywriterTool, SelfImproverTool
- PortfolioAnalyzerTool, MemoryFleetTool, KnowledgeGraphTool
- EvaluationTool, K1BayesianTool, K3PerspectiveTool, MetaLearningTool
- SubagentTool, EvolutionTool, SkillTriggerTool, ReviewTool

---

## 7. CONFIGURATION SYSTEM

**Module:** `/root/nanojaga/jagabot/config/`

### Key Functions:

```python
def load_config(config_path: Path | None = None) -> Config:
    """Load from ~/.jagabot/config.json or use defaults"""

def save_config(config: Config, config_path: Path | None = None) -> None:
    """Save to file with camelCase conversion"""

def get_config_path() -> Path:
    """Return ~/.jagabot/config.json"""

def get_data_dir() -> Path:
    """Return jagabot data directory"""
```

### Configuration Schema (Pydantic):
**File:** `/root/nanojaga/jagabot/config/schema.py` (310 LOC)

```python
class Config(BaseSettings):
    agents: AgentsConfig
    channels: ChannelsConfig
    providers: ProvidersConfig
    gateway: GatewayConfig
    tools: ToolsConfig
```

### Sub-Schemas:

1. **AgentsConfig:**
   - workspace: ~/.jagabot/workspace
   - model: anthropic/claude-opus-4-5
   - max_tokens: 8192
   - temperature: 0.7
   - max_tool_iterations: 20
   - memory_window: 50

2. **ChannelsConfig:** (Multi-channel support)
   - WhatsAppConfig, TelegramConfig, DiscordConfig, SlackConfig
   - FeishuConfig, DingTalkConfig, EmailConfig, MochatConfig, QQConfig

3. **ProvidersConfig:** (14 LLM providers)
   - anthropic, openai, deepseek, openrouter, groq, gemini, etc.
   - Each with: api_key, api_base, extra_headers

4. **ToolsConfig:**
   - web: WebSearchConfig (Brave Search API)
   - exec: ExecToolConfig (timeout: 60s)
   - sandbox: SandboxToolConfig (Docker container limits)
   - visualization: VisualizationConfig (markdown/base64/ascii/none)
   - restrict_to_workspace: bool

5. **GatewayConfig:**
   - host: 0.0.0.0
   - port: 18790

### Key Methods:
```python
config.workspace_path -> Path          # Expanded workspace path
config.get_provider(model) -> ProviderConfig | None
config.get_api_key(model) -> str | None
config.get_api_base(model) -> str | None
config.get_provider_name(model) -> str | None  # e.g., "deepseek"
```

### Storage:
- **Default:** `~/.jagabot/config.json` (JSON format)
- **ENV vars:** Prefix `JAGABOT_` with nested delimiter `__`
  - Example: `JAGABOT_AGENTS__DEFAULTS__MODEL=deepseek/r1`

### Key-Case Conversion:
- Disk: camelCase (standard JSON)
- Python: snake_case (Pydantic convention)
- Auto-conversion on load/save

---

## SUMMARY TABLE

| Component | Location | Type | Lines | Purpose |
|-----------|----------|------|-------|---------|
| **MCP Server** | deepseek-mcp-server/ | TypeScript | ~500 | DeepSeek API endpoint wrapper |
| **MCP Client** | nanobot/agent/tools/mcp.py | Python | ~92 | Connect to MCP servers, wrap tools |
| **Swarm Registry** | jagabot/swarm/tool_registry.py | Python | 40 | Lazy-loading, class mapping |
| **Agent Registry** | jagabot/agent/tools/registry.py | Python | 74 | Full lifecycle, async execution |
| **Tool Base** | jagabot/agent/tools/base.py | Python | 103 | Abstract interface, validation |
| **EvolutionEngine** | jagabot/evolution/engine.py | Python | 499 | Self-evolution with 4-layer safety |
| **CLI** | jagabot/cli/commands.py | Python | 46+ | Typer-based interactive CLI |
| **Config** | jagabot/config/ | Python | 310+ | Pydantic schema, JSON persistence |
| **Tools** | jagabot/agent/tools/ | Python | Multiple | 32 financial/ML tools |

---

## KEY ARCHITECTURE INSIGHTS

1. **Dual Registry Pattern:**
   - Swarm: class-based, read-only, lightweight
   - Agent: instance-based, full lifecycle, async-capable

2. **MCP Integration:**
   - Existing: Standalone deepseek-mcp-server (TypeScript)
   - Existing: Generic MCP client wrapper (nanobot)
   - **Gap:** No MCP server built into jagabot itself

3. **Tool Loading:**
   - All tools defined in guardian/tools/__init__.py (central registry)
   - Imported in agent/tools/__init__.py
   - Registered via `register_jagabot_tools(registry)`

4. **Safety Philosophy:**
   - EvolutionEngine: 4-layer mutation safety
   - Config: environment-based with type checking
   - Tools: parameter validation before execution

5. **Config Management:**
   - Single source of truth: ~/.jagabot/config.json
   - Schema-driven with Pydantic
   - Environment override support
   - Multiple LLM providers (14 configured)
