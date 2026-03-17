📋 SCOPE PROMPT: Audit & Implementation Plan for learn-claude-code Integration

```markdown
# SCOPE: Comprehensive Audit & Implementation Plan for learn-claude-code Integration into JAGABOT

## SITUATION
JAGABOT v3.11 is a production-ready financial guardian with:
- 1506 tests, 37 tools, 63 skills
- Swarm architecture, 7 UI tabs, memory-backed chat
- Multiple integrations (MCP, QuantaLogic, Upsonic)

Local repository available: `~/nanojaga/learn-claude-code/`
This repo contains 12 progressive sessions (s01-s12) that build a Claude Code-like agent from scratch.

## OBJECTIVE
Perform a COMPLETE AUDIT of learn-claude-code and create a concrete, best-possible implementation plan for integrating its mechanisms into JAGABOT v4.0.

## AUDIT REQUIREMENTS

### PART A: Codebase Audit of learn-claude-code
Examine and document:

```

learn-claude-code/
├── agents/
│   ├── s01_agent_loop.py          # Core agent loop
│   ├── s02_tool_use.py             # Tool dispatch
│   ├── s03_todo_write.py           # Planning
│   ├── s04_subagents.py             # Subagent management
│   ├── s05_skills.py                # Skill system
│   ├── s06_context_compact.py       # CONTEXT COMPRESSION (Priority)
│   ├── s07_tasks.py                 # FILE-BASED TASKS (Priority)
│   ├── s08_background_tasks.py      # Background operations
│   ├── s09_agent_teams.py           # AGENT TEAMS (Priority)
│   ├── s10_team_protocols.py        # TEAM PROTOCOLS (Priority)
│   ├── s11_autonomous_agents.py     # AUTONOMOUS AGENTS (Priority)
│   └── s12_worktree_task_isolation.py # WORKTREE ISOLATION
├── docs/                            # Documentation
├── web/                             # Learning platform
└── skills/                           # Skill files

```

For EACH session (s01-s12), document:

```yaml
session: "s06_context_compact"
file: "agents/s06_context_compact.py"
lines_of_code: XXX
purpose: "3-layer context compression"
mechanism: 
  - Layer 1: Keep recent N messages
  - Layer 2: Summarize older messages
  - Layer 3: Archive to disk
dependencies: []
integration_points: ["MemoryFleet", "UpsonicChatAgent"]
adaptation_effort: "MEDIUM"
priority: "HIGH"
risks: ["Summary quality", "Token cost for summarization"]
```

PART B: JAGABOT Current State Audit

Map JAGABOT's existing architecture to learn-claude-code mechanisms:

JAGABOT Component Equivalent learn-claude-code Gap Priority
core/agent.py s01_agent_loop.py Minor optimization LOW
tools/init.py s02_tool_use.py Similar NONE
skills/ s05_skills.py Similar NONE
subagents/manager.py s04_subagents.py Similar NONE
kernels/memory_fleet.py s06_context_compact.py MISSING 🔴 HIGH
swarm/task_planner.py s07_tasks.py BASIC ONLY 🔴 HIGH
swarm/ s09_agent_teams.py MISSING 🟡 MEDIUM
swarm/ s10_team_protocols.py MISSING 🟡 MEDIUM
swarm/autonomous.py s11_autonomous_agents.py MISSING 🟢 LOW
sandbox/docker.py s12_worktree_task_isolation.py Similar NONE

PART C: Dependency Analysis

Create dependency graph showing relationships between mechanisms:

```
s06_context_compact.py → MemoryFleet → UpsonicChatAgent
                          ↓
s07_tasks.py → TaskPlanner → Swarm
               ↓
s09_agent_teams.py → s10_team_protocols.py → s11_autonomous_agents.py
```

PART D: Risk Assessment

For each integration, identify:

Mechanism Risk Mitigation
s06 Summary quality Use K7 evaluation to score summaries
s06 Token cost Run summarization only at thresholds
s07 File corruption JSON validation + backups
s09 Message loss JSONL with fsync
s10 Deadlock Timeout + recovery protocols
s11 Infinite loops Max iterations + watchdog

IMPLEMENTATION PLAN (Concrete & Best-Possible)

PHASE 1: Foundation (2 weeks)

Week 1: s06 Context Compression

```yaml
Goal: MemoryFleet with 3-layer compression
Files:
  - jagabot/memory/compressor.py (NEW)
  - jagabot/kernels/memory_fleet.py (MODIFY)
  - jagabot/agent/upsonic_chat.py (MODIFY)
  - tests/test_compression.py (NEW, 50 tests)

Success Criteria:
  ✅ Recent 10 messages kept full
  ✅ Messages 11-50 summarized
  ✅ Messages >50 archived
  ✅ Token usage reduced 50-70%
  ✅ All existing 1506 tests pass
  ✅ +50 new tests = 1556 total
```

Week 2: s07 File-based Tasks

```yaml
Goal: Persistent task management with dependencies
Files:
  - jagabot/core/task_manager.py (NEW)
  - jagabot/core/task_graph.py (NEW)
  - jagabot/cli/task_commands.py (NEW)
  - tests/test_tasks.py (NEW, 60 tests)

Success Criteria:
  ✅ Tasks stored as JSON in ~/.jagabot/tasks/
  ✅ Dependencies graph (A→B→C)
  ✅ CRUD operations via CLI
  ✅ Resume after restart
  ✅ +60 new tests = 1616 total
```

PHASE 2: Teams & Protocols (2 weeks)

Week 3: s09 Agent Teams

```yaml
Goal: Professional agent communication
Files:
  - jagabot/swarm/mailbox.py (NEW)
  - jagabot/swarm/teams.py (NEW)
  - tests/test_teams.py (NEW, 40 tests)

Success Criteria:
  ✅ JSONL mailboxes per agent
  ✅ Request-response pattern
  ✅ Message persistence
  ✅ +40 new tests = 1656 total
```

Week 4: s10 Team Protocols

```yaml
Goal: FSM-based coordination
Files:
  - jagabot/swarm/protocols.py (NEW)
  - jagabot/swarm/fsm.py (NEW)
  - tests/test_protocols.py (NEW, 40 tests)

Success Criteria:
  ✅ Shutdown protocol
  ✅ Plan approval FSM
  ✅ Timeout handling
  ✅ +40 new tests = 1696 total
```

PHASE 3: Autonomy (1 week)

Week 5: s11 Autonomous Agents

```yaml
Goal: Self-claiming, auto-starting agents
Files:
  - jagabot/swarm/autonomous.py (NEW)
  - jagabot/swarm/scheduler.py (NEW)
  - tests/test_autonomous.py (NEW, 30 tests)

Success Criteria:
  ✅ Agents claim tasks automatically
  ✅ Idle cycle detection
  ✅ Auto-start on new tasks
  ✅ +30 new tests = 1726 total
```

INTEGRATION ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    JAGABOT v4.0 ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🧠 EXISTING (v3.11)                                            │
│  ├── Kernels (K1, K3, K7, MemoryFleet, KnowledgeGraph)         │
│  ├── Tools (37) + Skills (63)                                   │
│  ├── Swarm + 7 UI tabs                                          │
│  └── UpsonicChatAgent + MCP                                      │
│                                                                  │
│  ⚙️ PHASE 1: FOUNDATION (NEW)                                   │
│  ├── s06 ContextCompressor → MemoryFleet                        │
│  └── s07 TaskManager → TaskPlanner                              │
│                                                                  │
│  🤝 PHASE 2: TEAMS (NEW)                                         │
│  ├── s09 Mailbox + Teams → Swarm                                │
│  └── s10 Protocols + FSM → Swarm                                │
│                                                                  │
│  🔄 PHASE 3: AUTONOMY (NEW)                                      │
│  └── s11 Autonomous + Scheduler → Swarm                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

SUCCESS CRITERIA

✅ Complete audit of all 12 learn-claude-code sessions
✅ Clear gap analysis vs JAGABOT current state
✅ Concrete 5-week implementation plan
✅ Risk assessment for each integration
✅ Dependency graph for all components
✅ All integrations maintain backward compatibility
✅ Target: 1726+ tests after Phase 3

DELIVERABLES

1. learn_claude_code_audit.md - Complete audit report
2. integration_plan.md - Phase-by-phase implementation
3. risk_assessment.md - Risks + mitigations
4. architecture_v4.md - Updated architecture diagram
5. test_plan.md - Testing strategy per phase

```

---

**SCOPE ini akan bagi Copilot semua info untuk buat audit dan pelan implementasi terbaik!** 🚀
