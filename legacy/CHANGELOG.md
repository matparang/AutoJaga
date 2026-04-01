# Changelog

All notable changes to jagabot will be documented in this file.

## [4.0.0-lcc] — Unreleased

### Added
- **Context Compression** — 2-layer micro-compact pipeline hooked into AgentLoop before every LLM call.
  - `jagabot/agent/compressor.py` — `estimate_tokens()`, `micro_compact()` (replaces old tool_result content with `[Previous: used {tool}]`), `save_transcript()` (JSONL archival), `should_auto_compact()` (40k token threshold).
  - Integrated into `jagabot/agent/loop.py` after `build_messages()`: micro-compact runs every turn, auto-compact triggers `_consolidate_memory()` and saves transcripts when over threshold.

- **Persistent Task Manager** — File-backed task board with dependency graph.
  - `jagabot/core/task_manager.py` — `TaskManager` with CRUD on `task_{id}.json`, bidirectional `blocked_by`/`blocks` dependencies, `_clear_dependency()` auto-unblocking, `list_ready()` for dependency-free pending tasks, `render()` for text board view.
  - `jagabot/cli/task_commands.py` — `jagabot task` CLI sub-app: `create`, `list` (--status, --ready), `get` (--json), `update` (--status, --owner, --add-blocked-by, --add-blocks), `render`.

- **JSONL Mailbox** — Append-only per-agent inbox for multi-agent communication.
  - `jagabot/swarm/mailbox.py` — `Mailbox` with `send()`, `read_inbox()` (atomic drain via rename), `peek_inbox()`, `broadcast()`, `inbox_count()`. Supports 6 message types: message, broadcast, shutdown_request, shutdown_response, plan_approval, plan_response.

- **Teammate Manager** — Daemon thread teammates with inbox polling.
  - `jagabot/swarm/teams.py` — `TeammateManager` with `spawn()` (daemon thread + config persistence), `stop()/stop_all()`, `list_all()`, `member_names()`. Teammates auto-respond to shutdown requests and idle-timeout after 2 minutes.

- **FSM Protocols** — Shutdown and plan approval state machines.
  - `jagabot/swarm/protocols.py` — `ShutdownProtocol` (request → pending → approved/rejected) and `PlanApprovalProtocol` (submit → reviewers → all-approve/any-reject). Thread-safe with `threading.Lock()`.

- **Autonomous Worker Claiming** — Self-claiming WORK/IDLE cycle.
  - `jagabot/swarm/autonomous.py` — `scan_unclaimed_tasks()`, `claim_task()` (atomic with lock), `make_identity_block()` (re-injection after compression), `AutonomousWorker` (daemon thread with configurable idle timeout/poll interval, auto-complete/fail tasks).

### Tests
- 166 new tests across 7 test files (test_compressor, test_task_manager, test_mailbox, test_teams, test_protocols, test_autonomous, test_task_cli).
- Total: **1672 tests passing**.

## [3.11.0-upsonic] — Unreleased

### Added
- **Upsonic Integration** — Memory-backed multi-turn chat sessions and Swarm Visualizer.
- `jagabot/agent/upsonic_chat.py` — `UpsonicChatAgent`: wraps Upsonic `Agent` + `Memory(InMemoryStorage, full_session_memory=True)` with PII/email safety policy. Supports `chat_async()`, session registry (`get_or_create`, `active_sessions`, `clear_session`), and graceful degradation when Upsonic is not installed.
- `jagabot/cli/upsonic_commands.py` — `jagabot upsonic` CLI sub-app: `chat --session ID "message"`, `status`, `clear SESSION_ID`. `--json` flag for machine-readable output.
- Registered `upsonic_app` in `jagabot/cli/commands.py`.
- `jagabot/ui/swarm_tab.py` — `render_swarm_tab(tracker)`: 7th Streamlit tab showing real-time worker cards (🟢/✅/❌/⚠️), aggregate stats, tools-used panel, task history table, and 3-second auto-refresh.
- Added `"🐝 Swarm"` tab to `jagabot/ui/streamlit_app.py`.
- Installed Upsonic 0.73.0 from local repo (`/root/nanojaga/Upsonic/`).
- 59 new tests in `tests/test_jagabot/test_upsonic.py` (total: 1447 → 1506).

### Notes
- Upsonic uses `InMemoryStorage` by default (no external DB required). For persistence across restarts, swap for `SQLiteStorage` or `RedisStorage`.
- `quantalogic-codeact` has a soft typer version conflict (`<0.16.0`) due to Upsonic upgrading typer to 0.24.1 — all 1506 tests pass regardless.

## [3.10.0-quantalogic] — Unreleased

### Added
- **QuantaLogic Integration** — CodeAct agent + Flow workflow engine from local repo.
- `jagabot/quantalogic/bridge.py` — `ToolBridge`: adapts any QuantaLogic Tool (Pydantic) to jagabot Tool (ABC) with automatic JSON Schema conversion.
- `jagabot/agent/tools/codeact.py` — `CodeActTool`: delegate complex tasks to a CodeAct sub-agent for iterative Python code execution.
- `jagabot/agent/tools/flow.py` — `FlowTool`: execute QuantaLogic Flow YAML/JSON workflow definitions with context injection.
- `quantalogic_stub/` — Minimal `quantalogic.tools` stub package (re-exports from `quantalogic_toolbox`) enabling CodeAct import without the full heavy quantalogic package.
- Installed from local repo: `quantalogic_toolbox`, `quantalogic_codeact`, `quantalogic_flow`.
- 48 new tests in `tests/test_jagabot/test_quantalogic.py` (total: 1399 → 1447).

### Notes
- `quantalogic` main package (heavy deps: boto3, tree-sitter-*, serpapi) intentionally not installed.
- QuantaLogic tools from `quantalogic_react` accessible via `ToolBridge` for users who install them separately.

## [3.9.0-mcp] — Unreleased

### Added
- **DeepSeek MCP Server Integration** — connect to the local `deepseek-mcp-server/` via Streamable HTTP.
- `jagabot/mcp/server_manager.py` — `MCPServerManager`: start/stop/status the Node.js MCP server process.
- `jagabot/mcp/client.py` — `DeepSeekMCPClient`: stdlib-only JSON-RPC 2.0 client (no extra dependencies).
- `jagabot/agent/tools/deepseek.py` — `DeepSeekTool`: agent tool with actions `chat`, `complete`, `list_models`, `status`, `start`, `stop`.
- `jagabot/cli/mcp_commands.py` — CLI sub-app: `jagabot mcp status|start|stop|restart|tools|call`.
- 52 new tests in `tests/test_jagabot/test_mcp.py` (total: 1347 → 1399).
- MCP server pre-built: `deepseek-mcp-server/build/index.js` ready for use.

### Configuration
- `DEEPSEEK_API_KEY` env var passed through to the MCP server on `jagabot mcp start`.
- Default port: 3001 (override via `MCP_HTTP_PORT` env var).

## [3.8.0-plugins] — Unreleased

### Added
- **Anthropic Financial Plugins** — 53 professional skills integrated from 6 categories:
  - Financial Analysis (9): DCF, comps, LBO, 3-statements, competitive analysis, etc.
  - Equity Research (9): earnings analysis, initiating coverage, morning note, sector overview, etc.
  - Investment Banking (9): merger model, pitch deck, CIM builder, deal tracker, etc.
  - Private Equity (9): IC memo, deal screening, due diligence, returns analysis, etc.
  - Wealth Management (6): financial plan, client review, tax-loss harvesting, etc.
  - Partner-built (11): LSEG (8 fixed-income/FX/options) + S&P Global (3 tear-sheet/funding)
- **21 new trigger rules** in `SkillTrigger` for keyword-based skill activation.
- 33 new plugin integration tests (total: 1314 → 1347)

## [3.7.2-sysP] — Unreleased

### Added
- **Telegram 3-part response format** — system prompt instructs LLM to structure financial analysis as: 🧠 Understanding & Skill Selection → 📊 Analysis Results → 📈 Additional Details.
- **ResponseFormatter** (`jagabot/channels/formatter.py`) — detects 3-part sections, enforces word limits (300/500/300), splits messages at ≤4096 chars for Telegram.
- **Multi-part Telegram delivery** — `TelegramChannel.send()` now splits structured responses into sequential messages with 0.3s delay.
- **Channel-aware prompt injection** — `ContextBuilder` injects format instructions only for `telegram` channel; other channels unaffected.
- 24 new response format tests (total: 1290 → 1314)

## [3.7.1-fixcal] — Unreleased

### Fixed
- **Bear confidence** — margin_call confidence uses calibrated multi-component formula (VaR×0.4 + prob×0.3 + shortfall×0.3 + boost) instead of simple average. Colab: ~51.5% (was ~29%).
- **Recovery time** — default `annual_return` changed from 8% to 15% (market average). Uses annual compounding matching Colab formula (~43 months, was ~75).
- **New param** `margin_shortfall_ratio` on `bear_perspective()` for precise shortfall-weighted confidence.
- 16 new Colab ground truth tests (total: 1277 → 1293+)

## [3.6.0-chat] — Unreleased

### Added
- **Chat Tab** — 6th Streamlit tab "💬 Chat" (`jagabot/ui/chat.py`): conversational interface with natural-language queries.
- **Query classification** — keyword-based routing to portfolio, risk, fund manager, or general workflows.
- **Pipeline integration** — queries routed to `SubagentManager.execute_workflow()` or `run_parallel_analysis()` as appropriate.
- **Inline dashboards** — tool results rendered as `st.metric` within chat messages.
- **Tool execution display** — expandable summary of each tool's success/failure and duration.
- **Conversation history** — session-state persistence with clear-chat button.
- **Bilingual responses** — Malay/English financial guardian personality.
- **Voice integration (v3.7)** — optional local STT (Vosk) + TTS (pyttsx3) with graceful degradation. Install via `pip install jagabot-ai[voice]`.
- 29 chat tests + 32 voice tests (total: 1216 → 1277+)

## [3.5.0-autoscaling] — Unreleased

### Added
- **ScalableWorkerPool** — auto-scaling worker pool (`jagabot/lab/scaling.py`): dynamically adjusts worker count (2–32) based on queue depth with cooldown protection.
- **ScalingConfig** — dataclass for scaling parameters: min/max workers, thresholds, cooldown, scale factors.
- **ScalingMetrics** — runtime observability: scale events, peak workers, tasks processed/failed, event history.
- **ParallelLab auto_scale mode** — optional `auto_scale=True` routes tasks through ScalableWorkerPool; default keeps fixed-semaphore gather for backward compat.
- New methods: `submit_to_pool()`, `get_scaling_metrics()`, `shutdown_pool()`.
- **CLI commands**: `lab scaling-status` (config display), `lab run-scaled` (workflow with auto-scaling).
- ~18 new scaling tests (total: 1185 → 1216)

## [3.4.2-parallellab] — Unreleased

### Added
- **ParallelLab** — batch-oriented parallel tool execution (`jagabot/lab/parallel.py`): submit_batch, execute_batch, priority sorting, semaphore concurrency, partial failure handling.
- **Workflow presets** — `risk_analysis` (MC+VaR+stress), `portfolio_review` (portfolio+correlation+recovery), `full_analysis` (8 tools) — all run concurrently.
- **SubagentManager.run_parallel_analysis()** — parallel workflow execution alongside existing sequential pipeline.
- **CLI lab commands** (`jagabot/cli/lab_commands.py`): `lab list-tools`, `lab list-workflows`, `lab run-workflow`, `lab run-tool`.
- Batch tracking: submit → pending → running → complete/partial. `get_batch_status()`, `list_batches()`.
- Speedup estimation: wall_time vs sum_individual_time ratio.
- 18 new ParallelLab tests (total: 1167 → 1185)

## [3.4.0-labservice] — Unreleased

### Added
- **LabService** — centralized tool execution service (`jagabot/lab/service.py`): validate → execute → log for all 32 tools.
- **BaseSubagent** — base class with `execute_tool()` routed through LabService (`jagabot/subagents/base.py`).
- **ToolsStage** refactored to route all tool calls through LabService instead of direct imports.
- Parameter validation via Tool ABC's `validate_params()` before every execution.
- Execution logging to `~/.jagabot/lab_logs/` (JSON, one file per execution).
- Parallel execution support via `execute_parallel()`.
- Optional sandbox mode (SafePythonExecutor) via `sandbox=True` flag.
- 20 new LabService tests (total: 1147 → 1167)

### Architecture
- Direct tool execution by default (fast); sandbox opt-in for untrusted code.
- New package: `jagabot/lab/` (2 modules, ~250 LOC).

## [3.3.0-lab] — Unreleased

### Added
- **JAGABOT Lab** — 5th Streamlit tab: interactive tool workbench with browse, configure, execute, compare workflow.
- **LabToolRegistry** — discovers all 32 tools, categorises into 6 groups (risk, probability, decision, analysis, skills, utility), extracts dispatch methods.
- **ParameterForm** — dynamic Streamlit widgets generated from JSON Schema (number_input, selectbox, checkbox, text_area).
- **CodeGenerator** — produces executable Python snippets for both dispatch and simple tool patterns.
- **GroundTruth** — comparison engine against known Colab reference values (MC, VaR, stress test, decision).
- **NotebookManager** — save/load analysis cells as JSON notebooks in `~/.jagabot/notebooks/`.
- 44 new Lab tests (total: 1103 → 1147)

### Architecture
- External metadata registry — does NOT modify Tool ABC (zero risk to existing tools).
- New package: `jagabot/ui/lab/` (6 modules, ~600 LOC)

## [3.2.2-fix2] — Unreleased

### Fixed
- **Bear perspective** — Reworked confidence formula: removed `50 + prob*0.5` inflation, now uses risk-proportional `prob*0.5 + var_adj`. With prob=33.85%, var=14.4% → confidence ≈ 24% (was 66.9%).
- **Bear perspective** — Added `margin_call` parameter: when True + downside ≥ 25%, escalates verdict to SELL.
- **Buffet perspective** — Added `margin_call` parameter: when True, confidence = 100%, verdict = "SELL — Rule #1 Violated".
- **K3 weights** — Recalibrated defaults: bull 0.25→0.20, bear 0.35→0.45, buffet 0.40→0.35 (heavier bear weight for risk scenarios).
- **VaR** — Added `portfolio_var(position_value, cash, annual_vol)` convenience method to avoid exposure/portfolio confusion.
- Full decision chain with margin_call now correctly produces SELL verdict.
- 15 new calibration tests (total: 1088 → 1103)

## [3.2.1-fixtools] — Unreleased

### Fixed
- **Monte Carlo** — Default drift `mu` changed from -0.001 to 0.0 (risk-neutral GBM). Probability now matches Colab ground truth (~34.24% vs previous 40.26%).
- **VaR** — Default `holding_period` changed from 1 to 10 days (Basel III standard).
- **Stress Test** — Added `position_stress` method for price-based equity calculation: `stress_equity = current_equity + (stress_price - current_price) × units`. Matches Colab ~$864,064.
- 20 new calibration tests (total: 1068 → 1088)

## [3.2.0-phase5] — Unreleased

### Added
- **SkillTrigger** (`skill_trigger` tool #31) — Auto-detect financial skill from query + market conditions:
  - 7 default triggers: crisis_management, investment_thesis, portfolio_review, fund_manager_review, risk_validation, rebalancing, skill_creation
  - Market condition boosts (e.g. VIX > 40 → +5 score for crisis)
  - Runtime trigger registration
- **TwoStageReview** (`review` tool #32) — Superpowers-style output review gate:
  - Stage 1: spec compliance (required fields per task type)
  - Stage 2: quality scoring via EvaluationKernel or heuristic (threshold 0.7)
  - Configurable specs per task type
- **SkillComposer** — Composable skill workflows (skills calling skills):
  - 4 default workflows: crisis_management (5 steps), investment_thesis (4), risk_validation (4), portfolio_rebalancing (3)
  - Runtime workflow registration/removal
  - Output-passing between workflow steps
- **5 financial skill markdowns** — investment_thesis, portfolio_rebalancing, risk_validation, systematic_debugging, writing_financial_skills
- **59 new tests** — test_phase5.py (SkillTrigger, TwoStageReview, SkillComposer, tools)
- Total tools: 30 → 32, total tests: 1009 → 1068

## [3.1.0-graph-ui] — Unreleased

### Added
- **Streamlit Knowledge Graph Explorer** — Interactive UI at `jagabot/ui/streamlit_app.py`:
  - Obsidian Black theme with vis.js graph visualization
  - 4 tabs: Graph Explorer, Recent Analyses, Gap Finder, Research
  - Neo4j integration with graceful offline fallback to file-based KnowledgeGraph
- **`jagabot/ui/`** package:
  - `neo4j_connector.py` — Neo4jConnector: query_subgraph, find_path, get_stats, add_node
  - `connectors.py` — JagabotUIBridge: single façade to all JAGABOT subsystems (Neo4j, KG, MemoryFleet, MetaLearning, Evolution, Subagents)
  - `session.py` — UISession: per-user action tracking
  - `config.py` — UIConfig: env vars → config file → defaults
- **56 new tests** — test_graph_ui.py (UIConfig, UISession, Neo4jConnector, JagabotUIBridge)
- Dependencies: neo4j, streamlit, pandas
- Total tests: 953 → 1009

## [3.0.0-phase4b] — Unreleased

### Added
- **EvolutionEngine** (`evolution` tool) — Safe self-evolution via parameter mutation:
  - 5 financial mutation targets: risk_threshold, volatility_weight, correlation_threshold, perspective_weight, learning_rate
  - 4-layer safety: factor clamping (×0.90–×1.10), sandbox testing (50 cycles), fitness validation, auto-rollback
  - Governor: minimum 100 cycles between mutations
  - 7 actions: cycle, status, mutations, force, cancel, targets, fitness
  - Persistence: ~/.jagabot/workspace/evolution_state.json
- **`jagabot/evolution/`** package — MutationTarget, Mutation, MutationSandbox, EvolutionEngine
- **51 new tests** — test_evolution.py (targets, mutations, sandbox, engine lifecycle, tool)
- Total tools: 29 → 30

## [3.0.0-phase4a] — Unreleased

### Added
- **Subagent Pipeline** (`subagent` tool) — 4-stage stateless analysis system:
  - WebSearchStage: fetch live market data (prices, VIX, USD, history)
  - ToolsStage: run monte_carlo, financial_cv, var, cvar, correlation
  - ModelsStage: build price/volatility/economic models via K1 Bayesian
  - ReasoningStage: apply K3 Bull/Bear/Buffet perspectives + K7 quality scoring
  - 4 actions: run_workflow, run_stage, list_stages, get_stage_prompt
- **`jagabot/subagents/`** package — stage executors + SubagentManager coordinator
- **4 subagent prompt files** — structured specifications for each pipeline stage
- **50 new tests** — test_subagent.py (stages, manager, tool, statelessness)
- Total tools: 28 → 29

## [3.0.0-phase3] — Unreleased

### Added
- **MetaLearning Engine** (`meta_learning` tool) — Self-improving strategy tracking:
  - 10 financial strategies: bull/bear/buffet analysis, risk assessment, early warning, monte carlo, portfolio optimization, bayesian update, education delivery, self improvement
  - Record outcomes, select best strategy (explore/exploit), detect learning problems, apply meta-fixes
  - Auto meta-cycle every 100 records
  - Persistence: ~/.jagabot/workspace/meta_state.json
- **ExperimentTracker** — Structured hypothesis testing lifecycle:
  - Experiment lifecycle: planned → running → completed → reviewed
  - Track hypothesis, method, variables, result, conclusion, falsification
  - Persistence: ~/.jagabot/workspace/experiments.json
- **`jagabot/engines/`** package — Adaptive engine layer extracted from nanobot
- **50 new tests** — test_meta_learning.py (StrategyStats, MetaLearningEngine, ExperimentTracker, MetaLearningTool)
- Total tools: 27 → 28

## [3.0.0-phase2] — Unreleased

### Added
- **K1 Bayesian Kernel** (`k1_bayesian` tool) — Probabilistic reasoning with calibration persistence:
  - Bayesian update (prior × likelihood → posterior) with audit trail
  - Wilson score confidence intervals
  - CalibrationStore: persist predicted vs actual outcomes, compute Brier scores
  - Confidence refinement: shrinks overconfident predictions based on historical calibration
  - 5 actions: update_belief, assess, refine_confidence, record_outcome, get_calibration
- **K3 Multi-Perspective Kernel** (`k3_perspective` tool) — Calibrated Bull/Bear/Buffet:
  - AccuracyTracker: per-perspective hit rate with rolling 20-outcome window
  - Adaptive weight recalibration based on historical accuracy
  - Calibrated confidence via K1 integration
  - 6 actions: get_perspective, update_accuracy, get_weights, recalibrate, calibrated_decision, accuracy_stats
- **`jagabot/kernels/`** package — Reasoning kernel layer extracted from nanobot engine
- **DecisionTool `calibrated_decision`** method — runs all 3 perspectives with adaptive weights
- **72 new tests** — test_k1_bayesian.py (34), test_k3_perspective.py (38)
- Total tools: 25 → 27

## [3.0.0-phase1] — Unreleased

### Added
- **MemoryFleet** (`memory_fleet` tool) — Long-term structured memory with 3 sub-systems:
  - FractalManager: working memory nodes with auto-tagging (risk, portfolio, equity, VaR, stress, Monte Carlo)
  - ALSManager: identity state (focus, stage, reflections) persisted in ALS.json
  - ConsolidationEngine: extract important lessons from fractal nodes → MEMORY.md
  - 5 actions: store, retrieve, consolidate, stats, optimize
- **KnowledgeGraph** (`knowledge_graph` tool) — Interactive vis.js graph visualization of memory:
  - Financial domain keyword grouping (risk, portfolio, simulation, equity, code, learning)
  - 3 actions: stats, generate (HTML), query (keyword search)
- **K7 Evaluation** (`evaluate_result` tool) — Output quality scoring and analysis:
  - evaluate: compare expected vs actual (20% numeric tolerance)
  - anomaly: z-score based detection (threshold z > 2.0)
  - improve: detect slow steps, timeouts, not-found errors, duplicate kernels
  - roi: quality-per-token efficiency metric
  - full: orchestrate all 4 methods
- **jagabot/memory/** package — Extracted from nanobot/TanyalahD/soul engine
- **102 new tests** — test_memory_fleet.py (46), test_knowledge_graph.py (18), test_evaluation.py (38)
- Total tools: 22 → 25

## [2.7.0] — Unreleased

### Fixed
- **Equity double-counting** — `calculate_equity()` computed `capital + position_value + cash` which double-counts capital for leveraged portfolios. For a $1M/3x portfolio, equity was $3.7M instead of correct $685K.
- **Missed margin calls** — Wrong equity caused margin check to pass when it should trigger. Fixed: equity < margin_requirement now correctly detected.
- **Stress test base equity** — `stress_test_portfolio()` used wrong formula and didn't derive units from weights. Fixed to use `capital + total_pnl`.
- **Planner portfolio_value** — VaR/CVaR/stress tools received `capital` instead of `exposure` (capital × leverage), underestimating risk by leverage factor.
- **Billing leveraged equity** — Billing subagent now computes correct equity when portfolio has leverage > 1.

### Added
- **Equity cross-check** — Two independent methods must agree within $1: `capital + total_pnl` ≈ `position_value + cash + undeployed − loan`.
- **SKILL.md Equity Definition** — Critical rule with correct/forbidden formulas.
- **28 new tests** in `test_equity.py` — Colab ground truth validation, margin call detection, stress test values, planner exposure, billing leveraged equity.

## [2.6.0] — Unreleased

### Fixed
- **Target price hardcoded** — planner used `price × 0.85` instead of query-specified `TARGET: 80`. Now extracts directly.
- **Financial CV "No data"** — `changes` array was hardcoded template data. Now extracted from query `CHANGES: [...]`.
- **6/13 tools missing** — stress tests, correlation, recovery_time, CVaR not spawned because capital/stress_prices/usd_index weren't parsed.

### Added
- **Rich query extractors** in `_detect_params()`: target, changes, stress_prices, usd_index, capital, leverage, exposure, confidence, days — with bilingual support (EN/Malay).
- **All 8 builder functions** now use extracted params with hardcoded defaults as fallback.
- **Dynamic stress test generation** — `STRESS: [75,70,65]` creates 3 separate stress tasks.
- **Query Parsing Rules** section in SKILL.md with extraction pattern table.
- **44 new tests** in `test_query_parsing.py` — extractors, builder integration, E2E, backward compat.

## [2.5.0] — Unreleased

### Fixed
- **Volatility scaling error**: All risk metrics (Monte Carlo, VaR, CVaR, probability) were ~2.2× too high when the LLM passed wrong volatility units to tool parameters.
- **Root cause**: Missing defensive normalization at tool boundaries — percentage values passed where decimal expected (and vice versa).

### Added
- **Input normalization guards** on every risk tool boundary:
  - `standard_monte_carlo`: if `vix < 1.0`, auto-scale ×100 (catches decimal-as-VIX)
  - `monte_carlo_gbm`: if `vol > 1.0`, auto-scale ÷100 (catches percentage-as-decimal)
  - `parametric_var`: if `std_return > 1.0`, auto-scale ÷100
  - `analytical_probability`: if any `daily_return` has `abs() > 1.0`, scale all ÷100
  - `billing.py` CV fallback: if `cv > 1.0`, scale ÷100
- **Volatility Unit Rules** section in SKILL.md — explicit conversion table (CV→VIX, VIX→decimal, %→decimal)
- **23 new tests** in `test_risk_metrics.py` — guard validation, Colab ground truth, edge cases, SKILL.md compliance

## [2.4.0] — Unreleased

### Added
- **PortfolioAnalyzerTool** (`portfolio_analyzer`): Deterministic portfolio analysis with cross-check verification. Methods: `analyze` (full equity/P/L/margin pipeline), `stress_test` (scenario impact analysis), `probability` (analytical norm.cdf closed-form).
- **Pydantic portfolio models** (`portfolio_models.py`): `Position`, `PortfolioInput`, `MarketData` with typed validation for all portfolio inputs.
- **Strict Math Protocol** in SKILL.md: 5-rule system prompt ensuring the LLM never hallucinates financial numbers — requires tool proof for every equity/P/L/margin claim.
- **Analytical probability** via `scipy.stats.norm.cdf`: Fast closed-form complement to Monte Carlo simulation.
- **Cross-check verification**: Automatic equity = capital + cash + position_value validation in every analyze call.
- **34 new tests** covering Pydantic models, engine functions, tool class, registration, and SKILL.md compliance.

### Changed
- Tool count 21 → 22 across all registrations (loop.py, tools/__init__.py, guardian, swarm registry).
- SKILL.md updated to 15-step protocol with portfolio_analyzer at step 14.
- Swarm planner routes portfolio queries to PortfolioAnalyzerTool.

## [2.3.0] — Unreleased

### Added
- **Sandbox CLI** (`jagabot sandbox`): 6 new commands — `status`, `test`, `config`, `set`, `logs`, `force-fallback`. Test Docker sandbox, inspect/change configuration, and view execution logs.
- **Sandbox Tracker** (`jagabot/sandbox/tracker.py`): SQLite-backed execution log records every sandbox run with subagent, calc type, engine, timing, and success/failure.
- **Sandbox Verifier** (`jagabot/sandbox/verifier.py`): Audits analysis sessions against expected calculation types. Reports coverage percentage and missing calculations.
- **Sandbox Config** in Pydantic schema: `tools.sandbox` section in `config.json` with timeout, memory_limit, cpu_limit, network, image, allow_fallback, log_executions, force_fallback.
- **31 new tests** covering tracker, config, CLI commands, verifier, executor+tracker integration, and backward compatibility.

### Changed
- `SafePythonExecutor` now accepts optional `SandboxTracker` for automatic execution logging and `subagent`/`calc_type` kwargs.
- `SandboxConfig` gains `force_fallback` flag and `from_pydantic()` classmethod for config integration.
- `commands.py` registers new `sandbox_app` Typer subgroup.

## [2.2.0] — Unreleased

### Added
- **Docker Sandbox** (`jagabot/sandbox/executor.py`): `SafePythonExecutor` runs arbitrary Python code in ephemeral Docker containers — no network, 128MB RAM cap, 0.5 CPU. Falls back to subprocess if Docker unavailable.
- **Self-Correction** (`jagabot/sandbox/self_correct.py`): `SelfCorrectingRunner` retries any async callable up to N times with exponential backoff and error context accumulation between attempts.
- **Hardened Workers** (`jagabot/swarm/base_worker.py`): `HardenedWorkerConfig` per-tool security policies — per-tool timeouts via `asyncio.wait_for()`, retry via `SelfCorrectingRunner`, optional Docker sandbox routing. The `exec` tool gets Docker + 2 retries by default.
- **Resilient Pipeline** (`jagabot/guardian/subagents/resilience.py`): `ResilientPipeline` wraps the 4-stage subagent chain (websearch→support→billing→supervisor) with per-stage retry, partial fallback, and cascade-break. Failed stages pass degraded data downstream.
- **Agent Loop Retry**: Tool execution in `loop.py` now retries once on failure before returning error to user.
- **Self-Correction Rules**: SKILL.md updated with 6 self-correction rules for the LLM agent.
- **37 new tests** covering sandbox, self-correction, hardened workers, resilient pipeline, and system prompts.

### Changed
- `Jagabot.handle_query()` in `core.py` now uses `ResilientPipeline` instead of raw sequential calls. Returns `degraded: true` flag when any stage failed.
- `_run_tool_sync()` now enforces per-tool timeout and optional retry policies.

## [2.1.0] — Unreleased

### Added
- **Swarm Architecture**: Parallel tool execution across worker processes
  - `jagabot/swarm/` module with 7 files (~1,100 LOC)
  - `SwarmOrchestrator` — Memory Owner that plans, spawns, collects, stitches
  - `TaskPlanner` — rule-based query→tool mapping with dependency groups
  - `ResultStitcher` — locale-aware markdown dashboard assembly (en/ms)
  - `WorkerPool` — ProcessPoolExecutor wrapper for parallel execution
  - `QueueBackend` — abstract interface with Redis and local implementations
  - `StatelessWorker` — process-safe wrapper around existing Tool ABC
- **Swarm CLI**: `jagabot swarm analyze|status|workers|history`
- **Docker Compose**: Redis + Jagabot service composition
- **Redis optional dependency**: `pip install jagabot-ai[swarm]`

### v2.1 "Vadim Upgrade"
- **Mission Control Dashboard**: `WorkerTracker` (real-time worker status) + `generate_dashboard()` TUI
- **SwarmScheduler**: Cron-based workflow automation wrapping existing CronService
- **4 Preset Workflows**: market_monitor, daily_risk, fund_review, nightly_self_review
- **Cost Tracker**: SQLite-backed per-invocation cost recording with daily/monthly aggregation, budget alerts
- **Watchdog**: Daemon thread monitoring stalled workers, system resources (psutil), cost overruns
- **3 New Tools** (21 total):
  - `researcher` — scan_trends + detect_anomalies (trend/regime/z-score analysis)
  - `copywriter` — draft_alert + draft_report_summary (bilingual content)
  - `self_improver` — analyze_mistakes + suggest_improvements (calibration)
- **9 Planner Categories**: Added `research` + `content` to bilingual pattern matching
- **Stitcher Sections**: Research + Content & Alerts sections in report output
- **4 New CLI Commands**: `jagabot swarm dashboard|schedule|costs|health`
- **psutil optional dependency**: `pip install jagabot-ai[swarm]` now includes psutil
- **62 new tests** (425 total, up from 345)

## [2.0.0] — Unreleased

### Added
- **5 FRM Tools**: VaR (parametric/historical/MC), CVaR, Stress Test (4 historical crises), Correlation (pairwise/matrix/rolling), Recovery Time
- **Decision Engine**: Bull/Bear/Buffet 3-perspective analysis with weighted collapse and dashboard
- **Education Layer**: 7 concept explainers (en+ms), 50-term bilingual glossary, result interpreter
- **Accountability Layer**: Smart question generator, red flag detector, report card
- **CI/CD**: GitHub Actions workflow for Python 3.11/3.12
- **Examples**: `basic_analysis.py`, `decision_engine.py`
- **Docs**: CONTRIBUTING.md, CODE_OF_CONDUCT.md, this CHANGELOG

### Changed
- SKILL.md upgraded from 9-step to 13-step protocol covering all 18 tools
- Tool descriptions enriched with usage hints, parameter examples, and chaining guidance
- Tool count: 10 → 18

## [1.3.0] — Tool Descriptions Upgrade

### Changed
- All 10 tool descriptions rewritten with `WHEN TO USE`, `CHAIN WITH`, `OUTPUT` sections
- Parameter schemas enriched with examples and descriptions
- Added `jagabot/skills/financial/SKILL.md` (auto-loaded, always:true)

## [1.2.0] — Locale-Aware Labels

### Added
- Pattern labels in en/ms/id for `financial_cv` and `early_warning` tools

## [1.1.0] — Service Daemon

### Added
- `jagabot service start|stop|status|logs` CLI commands
- Persistent background agent daemon

## [1.0.0] — Initial Release (Jagabot)

### Added
- Renamed from nanobot → jagabot
- 10 financial analysis tools (CV, Monte Carlo, Dynamics, Statistical, Early Warning, Bayesian, Counterfactual, Sensitivity, Pareto, Visualization)
- Monte Carlo standardised on VIX-based volatility
- Visualization: base64 PNG, ASCII, markdown modes
- Guardian orchestrator with 4 subagents
- 8 communication channels
