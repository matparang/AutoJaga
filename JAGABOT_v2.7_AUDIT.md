# JAGABOT v2.7 AUDIT REPORT

> Generated: 2026-03-09 | Tests: 608 passing | Tools: 22 | LOC: 20,271

---

## Executive Summary

Jagabot v2.7 is a **fully functional financial risk management AI assistant** with 22
registered analysis tools, an 8-worker swarm architecture, Docker sandboxing, 10 messaging
channels, and 608 passing tests across 13 test files. The codebase is 20,271 lines of
Python (3,587 core agent lines) built on the Tool ABC → ToolRegistry → AgentLoop pipeline.

**Strengths**: Modular tool system, resilient 4-subagent Guardian pipeline, bilingual
EN/Malay support, comprehensive test coverage, swarm parallel execution.

**Gaps for v3.0**: No learning from outcomes, no knowledge graph, no persistent cross-session
memory, no formal evaluation kernel, no tool evolution/creation at runtime.

---

## 1. Codebase Structure

### Directory Map with LOC

| Module | Files | LOC | Purpose |
|--------|------:|----:|---------|
| `jagabot/agent/tools/` | 32 | 6,129 | 22 financial tools + base/registry/models |
| `jagabot/channels/` | 12 | 3,375 | 10 messaging platforms + manager |
| `jagabot/cli/` | 3 | 1,715 | CLI commands, daemon, sandbox CLI |
| `jagabot/swarm/` | 13 | 2,244 | Parallel execution engine |
| `jagabot/guardian/` | 10 | 2,191 | 4-subagent pipeline + guardian tools |
| `jagabot/agent/` (core) | 5 | 1,062 | Loop, context, memory, skills, subagent |
| `jagabot/providers/` | 5 | 717 | LLM providers (litellm, transcription) |
| `jagabot/sandbox/` | 5 | 642 | Docker sandbox + verifier + tracker |
| `jagabot/gateway/` | 2 | 565 | WebSocket API server |
| `jagabot/config/` | 3 | 421 | Pydantic schemas + YAML/JSON loader |
| `jagabot/cron/` | 3 | 411 | Cron scheduling service |
| `jagabot/session/` | 2 | 207 | Session management |
| `jagabot/heartbeat/` | 2 | 135 | Periodic heartbeat service |
| `jagabot/bus/` | 3 | 124 | Event bus + message queue |
| `jagabot/utils/` | 2 | 85 | Helpers |
| **TOTAL** | **114** | **20,271** | |

### Non-Python Assets

| Path | Type | Purpose |
|------|------|---------|
| `jagabot/skills/financial/SKILL.md` | Markdown | 15-step analysis protocol, 22 tools |
| `jagabot/skills/skill-creator/SKILL.md` | Markdown | Dynamic skill creation instructions |
| `jagabot/skills/{cron,github,memory,summarize,tmux,weather}/SKILL.md` | Markdown | Auxiliary skill packs |
| `jagabot/guardian/README.md` | Markdown | Guardian architecture docs |
| `jagabot/skills/tmux/scripts/*.sh` | Shell | tmux session helpers |

---

## 2. Tool Inventory (22 Tools)

All tools inherit from `Tool` ABC, implement `name`, `description`, `parameters`, `execute()`.
Registered in 3 places: `loop.py`, `agent/tools/__init__.py`, `guardian/tools/__init__.py`.

### Risk & Portfolio Analysis (8 tools)

| # | Tool Name | Class | Methods | LOC | Deps |
|---|-----------|-------|---------|----:|------|
| 1 | `financial_cv` | FinancialCVTool | calculate_cv, calculate_cv_ratios, calculate_equity, calculate_leveraged_equity, check_margin_call | 233 | — |
| 2 | `monte_carlo` | MonteCarloTool | __direct__ (flat params dispatch) | 224 | numpy, scipy |
| 3 | `var` | VaRTool | parametric_var, historical_var, monte_carlo_var | 169 | numpy, scipy |
| 4 | `cvar` | CVaRTool | calculate_cvar, compare_var_cvar | 138 | numpy |
| 5 | `stress_test` | StressTestTool | run_stress_test, historical_stress | 215 | — |
| 6 | `correlation` | CorrelationTool | pairwise_correlation, correlation_matrix, rolling_correlation | 211 | numpy |
| 7 | `portfolio_analyzer` | PortfolioAnalyzerTool | analyze, stress_test, probability | 319 | numpy, scipy |
| 8 | `recovery_time` | RecoveryTimeTool | estimate_recovery, recovery_probability | 200 | numpy |

### Dynamics & Scenarios (3 tools)

| # | Tool Name | Class | Methods | LOC | Deps |
|---|-----------|-------|---------|----:|------|
| 9 | `dynamics_oracle` | DynamicsTool | simulate, forecast_convergence | 170 | — |
| 10 | `counterfactual_sim` | CounterfactualTool | simulate_counterfactual, compare_scenarios | 178 | — |
| 11 | `sensitivity_analyzer` | SensitivityTool | analyze_sensitivity, tornado_analysis | 168 | — |

### Statistics & Probability (4 tools)

| # | Tool Name | Class | Methods | LOC | Deps |
|---|-----------|-------|---------|----:|------|
| 12 | `statistical_engine` | StatisticalTool | confidence_interval, hypothesis_test, distribution_analysis | 171 | — |
| 13 | `bayesian_reasoner` | BayesianTool | update_belief, sequential_update, bayesian_network_inference | 191 | — |
| 14 | `early_warning` | EarlyWarningTool | detect_warning_signals, classify_risk_level | 241 | — |
| 15 | `pareto_optimizer` | ParetoTool | find_pareto_optimal, rank_strategies, optimize_portfolio_allocation | 236 | — |

### Decision & Visualization (2 tools)

| # | Tool Name | Class | Methods | LOC | Deps |
|---|-----------|-------|---------|----:|------|
| 16 | `decision_engine` | DecisionTool | bull_perspective, bear_perspective, buffet_perspective, collapse_perspectives | 408 | — |
| 17 | `visualization` | VisualizationTool | (dispatch via execute) | 377 | matplotlib, numpy |

### Education & Accountability (2 tools)

| # | Tool Name | Class | Methods | LOC | Deps |
|---|-----------|-------|---------|----:|------|
| 18 | `education` | EducationTool | explain_concept, get_glossary, explain_result | 358 | — |
| 19 | `accountability` | AccountabilityTool | generate_questions, detect_red_flags, generate_report_card | 299 | — |

### Research & Content (3 tools)

| # | Tool Name | Class | Methods | LOC | Deps |
|---|-----------|-------|---------|----:|------|
| 20 | `researcher` | ResearcherTool | (dispatch via execute) | 160 | — |
| 21 | `copywriter` | CopywriterTool | (dispatch via execute) | 168 | — |
| 22 | `self_improver` | SelfImproverTool | (dispatch via execute) | 196 | — |

### Utility Tools (registered but not in 22 financial tools)

| Tool | Class | File | LOC | Purpose |
|------|-------|------|----:|---------|
| `read_file` / `write_file` | FileTool | filesystem.py | 211 | File system operations |
| `shell` | ShellTool | shell.py | 144 | Command execution |
| `web_search` | WebSearchTool | web.py | 163 | Web search |
| `web_fetch` | WebFetchTool | web.py | 163 | URL fetching |
| `send_message` | MessageTool | message.py | 86 | Cross-channel messaging |
| `spawn` | SpawnTool | spawn.py | 65 | Subagent spawning |
| `cron` | CronTool | cron.py | 127 | Cron scheduling |

---

## 3. Skill System

### Current State

| Aspect | Detail |
|--------|--------|
| **Location** | `jagabot/skills/` — 8 skill packs |
| **Format** | Markdown SKILL.md per directory |
| **Loader** | `jagabot/agent/skills.py` (228 LOC) |
| **Loading** | Progressive: always-loaded (financial) + on-demand |
| **Creation** | `skill-creator/SKILL.md` instructs LLM to create new packs |

### 8 Skill Packs

| Skill | LOC | Always? | Purpose |
|-------|----:|---------|---------|
| `financial` | 241 | ✅ | 15-step analysis protocol with 22 tools |
| `skill-creator` | 371 | ❌ | Dynamic skill creation instructions |
| `tmux` | 121 | ❌ | Terminal multiplexer management |
| `summarize` | 67 | ❌ | Text summarization |
| `weather` | 49 | ❌ | Weather API integration |
| `github` | 48 | ❌ | GitHub integration |
| `cron` | 47 | ❌ | Cron job management |
| `memory` | 31 | ❌ | Memory operations |

### Limitations
- ❌ Skills are static markdown — no runtime composition
- ❌ No skill versioning or evolution
- ❌ No skill performance metrics (which skill works best?)
- ❌ No skill dependency resolution
- ❌ skill-creator creates files but doesn't register tools

---

## 4. Memory System

### Current Implementation

| Component | Detail |
|-----------|--------|
| **MemoryStore** | `jagabot/agent/memory.py` (30 LOC) — two flat files |
| **Long-term** | `workspace/memory/MEMORY.md` — facts, preferences |
| **History** | `workspace/memory/HISTORY.md` — timestamped entries |
| **Sessions** | `jagabot/session/manager.py` (202 LOC) — JSONL per channel:chat_id |
| **Consolidation** | AgentLoop auto-consolidates when session > 50 messages |
| **Swarm DB** | `~/.jagabot/swarm.db` — SQLite task/result persistence |
| **Cost DB** | `~/.jagabot/swarm_costs.db` — execution cost tracking |
| **Sandbox DB** | `~/.jagabot/sandbox.db` — sandbox execution audit log |

### Runtime Databases

| Database | Engine | Tables | Purpose |
|----------|--------|--------|---------|
| `swarm.db` | SQLite | runs, tasks, results | Swarm execution history |
| `swarm_costs.db` | SQLite | costs | Per-task cost tracking |
| `sandbox.db` | SQLite | executions | Sandbox audit trail |

### Limitations
- ❌ **No cross-session learning** — each session starts from scratch (only MEMORY.md persists)
- ❌ **No structured knowledge** — memory is unstructured markdown
- ❌ **No relationships** — no graph, no entity linking
- ❌ **No retrieval by similarity** — only grep-searchable
- ❌ **No outcome tracking** — doesn't store prediction accuracy
- ❌ **No vector store** — no embeddings, no semantic search
- ❌ Memory consolidation is LLM-dependent (lossy)

---

## 5. Swarm Architecture

### Current Implementation

| Component | File | LOC | Purpose |
|-----------|------|----:|---------|
| **TaskPlanner** | `planner.py` | 465 | Query → category → param extraction → TaskSpec groups |
| **WorkerPool** | `worker_pool.py` | 148 | ProcessPoolExecutor, max_workers=min(cpu_count, 8) |
| **SwarmOrchestrator** | `memory_owner.py` | 228 | Central coordinator with SQLite persistence |
| **ResultStitcher** | `stitcher.py` | 232 | Markdown dashboard assembly |
| **WorkerTracker** | `status.py` | 128 | Worker heartbeat and stall detection |
| **Watchdog** | `watchdog.py` | 180 | Task monitoring with configurable timeout |
| **CostTracker** | `costs.py` | 208 | Per-task execution cost tracking |
| **Dashboard** | `dashboard.py` | 99 | MISSION CONTROL terminal display |
| **QueueBackend** | `queue_backend.py` | 210 | Persistent task queue (dict-based) |
| **BaseWorker** | `base_worker.py` | 134 | Sync tool wrapper for ProcessPool |
| **ToolRegistry** | `tool_registry.py` | 39 | Lazy-loaded tool name → class mapping |
| **Scheduler** | `scheduler.py` | 89 | Cron-based workflow scheduling |
| **Workflows** | `workflows.py` | 52 | Workflow definitions |

### Execution Flow

```
User Query
  → TaskPlanner._classify_query() → category (8 types)
  → TaskPlanner._detect_params() → 11 extractors (price, vix, target, ...)
  → _category_tasks() builder → list[list[TaskSpec]]
  → WorkerPool.run_task_groups()
      → Group 0: parallel (ProcessPoolExecutor)
      → Group 1: parallel (after Group 0 completes)
      → ...
  → ResultStitcher.stitch() → Markdown dashboard
```

### 8 Query Categories
crisis, stock, risk, portfolio, education, accountability, research, content, general

### Limitations
- ❌ **No inter-task communication** — groups are isolated
- ❌ **No adaptive planning** — planner uses static regex, not learned patterns
- ❌ **No result feedback** — Group 1 doesn't receive Group 0 results
- ❌ **No priority queue** — all tasks within a group have equal priority
- ❌ **No dynamic re-planning** — if a tool fails, plan doesn't adapt

---

## 6. Guardian Subagent Pipeline

### Architecture

```
WebSearch → Support → Billing → Supervisor
  (news)    (CV/risk)  (MC/equity)  (report)
```

| Stage | File | LOC | Purpose | Retry |
|-------|------|----:|---------|-------|
| WebSearch | `websearch.py` | 58 | Fetches news/market data | 2x |
| Support | `support.py` | 63 | Structures data, CV analysis | 2x |
| Billing | `billing.py` | 130 | Monte Carlo, equity, margin | 2x |
| Supervisor | `supervisor.py` | 171 | Final report + Bayesian analysis | 2x |
| Resilience | `resilience.py` | 120 | Retry + fallback orchestration | — |
| Core | `core.py` | 186 | Guardian pipeline coordinator | — |

### Limitations
- ❌ **Sequential only** — each stage waits for the previous
- ❌ **No parallel sub-pipelines** — can't run billing + support simultaneously
- ❌ **No evaluation** — no scoring of output quality

---

## 7. Learning Capabilities

### Current State: **MINIMAL**

| Capability | Exists? | Detail |
|------------|---------|--------|
| Learn from outcomes | ❌ | No prediction tracking |
| Pattern recognition | ❌ | No historical pattern analysis |
| Self-improvement | ⚠️ | `self_improver` tool suggests improvements but doesn't implement |
| Calibration | ❌ | No probability calibration tracking |
| Memory-based learning | ❌ | MEMORY.md is manual, not learned |
| Outcome storage | ❌ | Predictions not tracked against actuals |

### What `self_improver` Actually Does
- Analyzes analysis results for potential biases
- Suggests calibration improvements
- **Does NOT** persist suggestions or learn from them

---

## 8. Reasoning Capabilities

### Current State: **BASIC**

| Capability | Exists? | Implementation |
|------------|---------|----------------|
| Multi-perspective | ✅ | `decision_engine` — Bull/Bear/Buffet |
| Bayesian updating | ✅ | `bayesian_reasoner` — belief updates |
| Uncertainty quantification | ⚠️ | VaR/CVaR for portfolio, MC confidence intervals |
| Formal K1/K2/K3/K7 kernels | ❌ | Not implemented |
| Counterfactual reasoning | ✅ | `counterfactual_sim` — what-if scenarios |
| Sensitivity analysis | ✅ | `sensitivity_analyzer` — tornado charts |

### What's Missing for v3.0

| Kernel | Purpose | Current Proxy | Gap |
|--------|---------|---------------|-----|
| **K1 Bayesian** | Formal uncertainty engine | `bayesian_reasoner` tool | Tool exists but is not a persistent kernel — no state accumulation |
| **K3 Multi-Perspective** | Formal Bull/Bear/Buffet kernel | `decision_engine` tool | Tool exists but perspectives are one-shot — no historical calibration |
| **K7 Evaluation** | Result quality assessment | None | No evaluation of output quality, accuracy, or usefulness |

---

## 9. Dependency Map

```
┌─────────────────────────────────────────────────┐
│                    USER QUERY                     │
└──────────────────────┬──────────────────────────┘
                       │
          ┌────────────▼────────────┐
          │   AgentLoop (loop.py)   │
          │  ┌──────────────────┐   │
          │  │  ToolRegistry    │   │
          │  │  (22 tools)      │   │
          │  └──────────────────┘   │
          │  ┌──────────────────┐   │
          │  │  SkillsLoader    │   │
          │  │  (8 skill packs) │   │
          │  └──────────────────┘   │
          │  ┌──────────────────┐   │
          │  │  MemoryStore     │   │
          │  │  (MD files)      │   │
          │  └──────────────────┘   │
          └────────────┬────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  SwarmOrchestrator (swarm/) │
        │  ┌────────────────────────┐ │
        │  │ TaskPlanner            │ │
        │  │  → _classify_query()   │ │
        │  │  → _detect_params()    │ │
        │  │  → _builder()          │ │
        │  └────────────────────────┘ │
        │  ┌────────────────────────┐ │
        │  │ WorkerPool (8 proc)   │ │
        │  │  → ProcessPoolExecutor │ │
        │  └────────────────────────┘ │
        │  ┌────────────────────────┐ │
        │  │ ResultStitcher        │ │
        │  │  → Markdown dashboard  │ │
        │  └────────────────────────┘ │
        └──────────────┬──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  Guardian Pipeline          │
        │  Web → Support → Billing    │
        │  → Supervisor               │
        └──────────────┬──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  Sandbox (Docker/Subprocess)│
        │  ┌────────────────────────┐ │
        │  │ Executor + Tracker     │ │
        │  │ Verifier + SelfCorrect │ │
        │  └────────────────────────┘ │
        └──────────────┬──────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  Persistence                │
        │  ├── MEMORY.md (facts)      │
        │  ├── HISTORY.md (log)       │
        │  ├── swarm.db (runs)        │
        │  ├── swarm_costs.db (costs) │
        │  └── sandbox.db (audit)     │
        └─────────────────────────────┘
```

---

## 10. Gap Analysis for v3.0 Components

### 10.1 EvolutionEngine — Tool Creation

| Aspect | Detail |
|--------|--------|
| **Purpose** | Create new tools at runtime based on analysis needs |
| **Currently exists** | ❌ No |
| **Closest proxy** | `skill-creator` creates SKILL.md files but not Tool classes |
| **Dependencies** | Tool ABC template, sandbox for validation, ToolRegistry for registration |
| **Integration points** | Should create `.py` files → test in sandbox → register in ToolRegistry |
| **What can be reused** | Tool ABC, ToolRegistry.register(), sandbox executor, skill-creator patterns |
| **Risks** | Security (arbitrary code), stability (untested tools), import conflicts |
| **Effort** | **HIGH** — needs code generation, validation, hot-reload |

### 10.2 MetaLearningEngine — Learning from Outcomes

| Aspect | Detail |
|--------|--------|
| **Purpose** | Track predictions vs actuals, learn from errors, improve over time |
| **Currently exists** | ❌ No |
| **Closest proxy** | `self_improver` suggests improvements but doesn't persist or learn |
| **Dependencies** | Outcome storage (new DB), prediction registry, calibration metrics |
| **Integration points** | Hook into Guardian pipeline output → store predictions → compare with actuals |
| **What can be reused** | SQLite pattern from swarm.db, self_improver analysis logic |
| **Risks** | Data quality (bad actuals), overfitting, cold start |
| **Effort** | **MEDIUM** — needs new DB schema + prediction tracking + calibration loop |

### 10.3 K3 Multi-Perspective — Formal Bull/Bear/Buffet Kernel

| Aspect | Detail |
|--------|--------|
| **Purpose** | Persistent multi-perspective reasoning with historical calibration |
| **Currently exists** | ⚠️ Partial — `decision_engine` has Bull/Bear/Buffet but one-shot |
| **Closest proxy** | `decision_engine` tool (408 LOC, 4 methods) |
| **Dependencies** | MetaLearningEngine (for calibration), MemoryFleet (for history) |
| **Integration points** | Wrap decision_engine with state accumulation + calibration scoring |
| **What can be reused** | All 4 decision_engine methods, collapse_perspectives logic |
| **Risks** | Low — mostly enhancement of existing tool |
| **Effort** | **LOW** — wrap existing tool + add persistent state |

### 10.4 K1 Bayesian — Uncertainty Quantification

| Aspect | Detail |
|--------|--------|
| **Purpose** | Formal uncertainty engine that accumulates evidence across sessions |
| **Currently exists** | ⚠️ Partial — `bayesian_reasoner` tool exists but stateless |
| **Closest proxy** | `bayesian_reasoner` (191 LOC, 3 methods) |
| **Dependencies** | MemoryFleet (for prior persistence), MetaLearning (for calibration) |
| **Integration points** | Persist priors across sessions, update with new evidence, feed into K3 |
| **What can be reused** | All bayesian_reasoner methods (update_belief, sequential_update, bayesian_network_inference) |
| **Risks** | Prior drift, numerical stability, cold start |
| **Effort** | **LOW-MEDIUM** — add persistence layer around existing tool |

### 10.5 K7 Evaluation — Result Assessment

| Aspect | Detail |
|--------|--------|
| **Purpose** | Score analysis quality, accuracy, usefulness |
| **Currently exists** | ❌ No |
| **Closest proxy** | `sandbox/verifier.py` checks sandbox coverage (not output quality) |
| **Dependencies** | Ground truth data, MetaLearningEngine, scoring rubrics |
| **Integration points** | Post-analysis hook → score results → feed back into MetaLearning |
| **What can be reused** | Verifier pattern, self_improver bias detection |
| **Risks** | Subjective scoring, need for ground truth |
| **Effort** | **MEDIUM** — needs scoring framework + ground truth pipeline |

### 10.6 MemoryFleet V2 — Long-term Memory

| Aspect | Detail |
|--------|--------|
| **Purpose** | Persistent, structured, searchable cross-session memory |
| **Currently exists** | ⚠️ Minimal — flat MEMORY.md + HISTORY.md |
| **Closest proxy** | MemoryStore (30 LOC) + session JSONL files |
| **Dependencies** | Vector store (embeddings), SQLite for structured data |
| **Integration points** | Replace MemoryStore with MemoryFleet, integrate with all components |
| **What can be reused** | SQLite pattern from swarm.db, session manager, consolidation logic |
| **Risks** | Migration of existing memory, embedding model dependency, storage growth |
| **Effort** | **HIGH** — needs vector store, entity extraction, relationship storage |

### 10.7 KnowledgeGraph — Relationship Storage

| Aspect | Detail |
|--------|--------|
| **Purpose** | Store entities and relationships (assets, events, correlations, predictions) |
| **Currently exists** | ❌ No |
| **Closest proxy** | Correlation tool stores pairwise relationships (but not persisted) |
| **Dependencies** | MemoryFleet V2 (storage layer), entity extraction |
| **Integration points** | Populate from analysis results, query for context enrichment |
| **What can be reused** | SQLite for graph storage, correlation tool relationship patterns |
| **Risks** | Schema design, query complexity, stale relationships |
| **Effort** | **MEDIUM-HIGH** — needs graph schema + entity extraction + query layer |

---

## 11. Test Coverage

### 608 Tests across 13 Files

| File | Tests | LOC | Coverage Area |
|------|------:|----:|---------------|
| `test_tools.py` | 73 | 703 | 8 core engine tools |
| `test_v21.py` | 55 | 552 | Swarm infrastructure (tracker, dashboard, scheduler, costs, watchdog) |
| `test_swarm.py` | 45 | 383 | Workers, pool, planner, stitcher, orchestrator |
| `test_query_parsing.py` | 44 | 283 | v2.6 param extraction + builders |
| `test_v2.py` | 33 | 300 | Decision engine, education, accountability |
| `test_fixagain.py` | 30 | 329 | v2.4 portfolio analyzer + Pydantic models |
| `test_frm.py` | 28 | 318 | VaR, CVaR, stress test, correlation, recovery |
| `test_sandbox.py` | 26 | 388 | Sandbox tracker, config, CLI, verifier |
| `test_equity.py` | 24 | 396 | v2.7 equity consistency (Colab ground truth) |
| `test_risk_metrics.py` | 23 | 207 | v2.5 volatility scaling guards |
| `test_fixswarm.py` | 18 | 490 | v2.2 sandbox + self-correction + resilience |
| `test_tool_chaining.py` | ~200 | 219 | 22-tool registry, schemas, descriptions |
| `test_integration.py` | 9 | 251 | Subagent integration (support, billing, supervisor) |
| **TOTAL** | **608** | **4,819** | |

### Coverage Gaps
- ❌ No tests for channels (telegram, slack, etc.)
- ❌ No tests for CLI commands
- ❌ No tests for gateway/WebSocket server
- ❌ No tests for session manager
- ❌ No tests for cron service
- ❌ No E2E tests with actual LLM calls

---

## 12. Recommendations

### Integration Order (dependency-aware)

```
Phase 1 (Foundation):
  MemoryFleet V2 ──────────────→ replaces MemoryStore
  K7 Evaluation ───────────────→ standalone scoring

Phase 2 (Learning):
  MetaLearningEngine ──────────→ depends on MemoryFleet + K7
  KnowledgeGraph ──────────────→ depends on MemoryFleet

Phase 3 (Reasoning):
  K1 Bayesian ─────────────────→ depends on MemoryFleet + MetaLearning
  K3 Multi-Perspective ────────→ depends on MetaLearning + K1

Phase 4 (Evolution):
  EvolutionEngine ─────────────→ depends on all above
```

### What Can Be Reused

| Existing | Reuse For |
|----------|-----------|
| `bayesian_reasoner` tool | K1 Bayesian kernel core |
| `decision_engine` tool | K3 Multi-Perspective kernel core |
| `self_improver` tool | MetaLearningEngine analysis logic |
| `sandbox/verifier.py` | K7 Evaluation pattern |
| `swarm.db` SQLite pattern | MemoryFleet storage |
| `Tool` ABC + `ToolRegistry` | EvolutionEngine tool creation |
| `skill-creator` SKILL.md | EvolutionEngine skill patterns |

### Effort Estimates

| Component | Effort | New LOC (est.) | Risk |
|-----------|--------|---------------:|------|
| MemoryFleet V2 | HIGH | ~800 | Migration, embeddings |
| K7 Evaluation | MEDIUM | ~400 | Ground truth availability |
| MetaLearningEngine | MEDIUM | ~600 | Data quality, cold start |
| KnowledgeGraph | MEDIUM-HIGH | ~700 | Schema design, staleness |
| K1 Bayesian | LOW-MEDIUM | ~300 | Prior drift |
| K3 Multi-Perspective | LOW | ~200 | Minimal (wrapper) |
| EvolutionEngine | HIGH | ~1000 | Security, stability |
| **TOTAL** | | **~4,000** | |

### Testing Strategy
- Each component gets its own test file (`test_memory_fleet.py`, `test_k7_eval.py`, etc.)
- Integration tests between components (MetaLearning + MemoryFleet)
- Colab ground truth regression suite maintained for all financial calculations
- Target: 750+ tests after v3.0

---

## Appendix: Project Configuration

| Setting | Value |
|---------|-------|
| Package | `jagabot-ai` 0.1.3.post7 |
| Python | ≥3.11 |
| License | MIT |
| Build | hatchling |
| Entry point | `jagabot` → `jagabot.cli.commands:app` |
| Core deps | typer, litellm, pydantic, numpy, scipy, matplotlib, rich, httpx |
| Optional | pytest, pytest-asyncio, ruff (dev); redis, psutil (swarm) |
| CI | GitHub Actions — pytest on Python 3.11 + 3.12 |
| Gateway port | 18790 |
| Channels | Telegram, Slack, Discord, WhatsApp, Email, Feishu, DingTalk, Mochat, QQ |
