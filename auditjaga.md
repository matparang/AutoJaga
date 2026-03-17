📋 SCOPE PROMPT: Audit JAGABOT Current State for v3.0 Planning

```markdown
# SCOPE: Audit JAGABOT v2.7 Current State for v3.0 Planning

## SITUATION
JAGABOT v2.7 is functional with:
- ✅ 608 tests passing
- ✅ 22 tools registered
- ✅ Swarm architecture (8 parallel workers)
- ✅ Docker sandbox for secure execution
- ✅ Skill creation ability (`skill-creator` tool)

However, for v3.0 we need to add 7 URGENT components:
1. EvolutionEngine - tool creation
2. MetaLearningEngine - learning from outcomes
3. K3 Multi-Perspective - formal Bull/Bear/Buffet kernel
4. K1 Bayesian - uncertainty quantification
5. K7 Evaluation - result assessment
6. MemoryFleet V2 - long-term memory
7. KnowledgeGraph - relationship storage

Before we can integrate these, we need a COMPLETE AUDIT of current JAGABOT to understand:
- What exists already
- What's missing
- Dependencies between components
- Integration points

## AUDIT OBJECTIVES

### 1. CODEBASE STRUCTURE AUDIT
Map ALL current files and their purposes:

```

jagabot/
├── core/ - Main orchestrator
├── tools/ - 22 financial tools
├── swarm/ - Parallel execution
├── sandbox/ - Docker execution
├── cli/ - Command line interface
├── memory/ - Current memory system
└── tests/ - 608 tests

```

For EACH directory, document:
- Files present
- Lines of code
- Key functions/classes
- Dependencies
- What it does

### 2. TOOL INVENTORY (22 tools)

For EACH of the 22 existing tools, document:

```yaml
tool_name: "monte_carlo"
file: "jagabot/tools/monte_carlo.py"
lines: ~300
purpose: "Probability forecasting with VIX"
inputs:
  - current_price
  - vix
  - target_price
  - days (default 30)
  - simulations (default 10000)
outputs:
  - probability
  - confidence_interval
  - full_distribution (optional)
dependencies:
  - numpy
  - scipy
integration:
  - called_by: swarm workers
  - used_in: risk_analysis
tests: 15 tests passing
status: ✅ WORKING
```

List ALL 22 tools with same detail:

1. portfolio_analyzer
2. monte_carlo
3. var
4. cvar
5. stress_test
6. financial_cv
7. correlation
8. recovery_time
9. early_warning
10. sensitivity_analyzer
11. counterfactual_sim
12. bayesian_reasoner
13. statistical_engine
14. dynamics_oracle
15. pareto_optimizer
16. researcher
17. copywriter
18. self_improver
19. education
20. accountability
21. visualization
22. decision_engine

3. SKILL SYSTEM AUDIT

Document current skill system:

· Where skills are stored (path)
· Format (markdown)
· How skills are created (skill-creator tool)
· How skills are executed (subagent spawning)
· Example skill (oil_analysis.md)
· Limitations
· What's working vs what's missing

4. MEMORY SYSTEM AUDIT

Document current memory:

· Storage mechanism (SQLite? Files?)
· What is stored (analyses, results, history?)
· How it's organized
· Retrieval methods
· Relationships (if any)
· Limitations for v3.0 requirements

Current memory components:

· MEMORY.md
· HISTORY.md
· Session logs
· Swarm database (/root/.jagabot/swarm.db)

5. SWARM ARCHITECTURE AUDIT

Document swarm implementation:

· Max workers (8)
· How tasks are distributed
· How results are collected
· Error handling
· Current limitations
· Integration with tools

6. LEARNING CAPABILITIES AUDIT

Document what learning exists NOW:

· Does JAGABOT learn from outcomes?
· Are past analyses used?
· Is there any pattern recognition?
· Self-improver tool (what it does)
· MetaLearningEngine (not yet implemented)
· EvolutionEngine (not yet implemented)

7. REASONING CAPABILITIES AUDIT

Document current reasoning:

· decision_engine (3 perspectives)
· How confidence is calculated
· Uncertainty quantification
· K1/K2/K3/K7 kernels (none yet)
· What's missing for v3.0

8. DEPENDENCY MAPPING

Create dependency graph showing:

```
skill_creator → creates → skill_file
skill_file → defines → subagents
subagents → call → tools
tools → produce → results
results → stored in → memory
memory → used for → future analyses
```

9. GAP ANALYSIS

For each of the 7 URGENT v3.0 components, identify:

```yaml
component: "EvolutionEngine"
purpose: "Tool creation"
currently_exists: false
dependencies:
  - Need access to tool templates
  - Need sandbox for testing
  - Need registry for new tools
integration_points:
  - Should be callable from JAGABOT core
  - Should output to tools directory
  - Should register new tools
risks:
  - Security (creating arbitrary code)
  - Stability (new tools might break)
  - Testing (need validation)
```

Do this for ALL 7:

1. EvolutionEngine
2. MetaLearningEngine
3. K3 Multi-Perspective
4. K1 Bayesian
5. K7 Evaluation
6. MemoryFleet V2
7. KnowledgeGraph

10. RECOMMENDATIONS

Based on audit, provide:

· What can be reused from current code
· What needs to be built from scratch
· Integration order (dependencies)
· Potential risks
· Estimated effort per component
· Testing strategy

OUTPUT FORMAT

Provide audit results as:

```markdown
# JAGABOT v2.7 AUDIT REPORT

## Executive Summary
[1 page overview]

## Detailed Findings
### Codebase Structure
[tree + descriptions]

### Tool Inventory
[table with all 22 tools]

### Skill System
[current state + limitations]

### Memory System
[current state + limitations]

### Swarm Architecture
[current state + capabilities]

### Learning Capabilities
[current state + gaps]

### Reasoning Capabilities
[current state + gaps]

### Dependency Map
[visual + description]

### Gap Analysis
[for each of 7 urgent components]

### Recommendations
[clear next steps]
```

SUCCESS CRITERIA

Audit is complete when:

· Every file in codebase is documented
· All 22 tools have complete inventory
· Skill system fully understood
· Memory system mapped
· Swarm architecture documented
· Current learning capabilities known
· Current reasoning capabilities known
· Dependency graph created
· Gap analysis for 7 urgent components done
· Clear recommendations provided

DELIVERABLES

1. JAGABOT_v2.7_AUDIT.md - Complete audit report
2. dependency_graph.md - Visual/text representation
3. gap_analysis.md - Detailed per-component gaps
4. recommendations.md - Implementation order + effort estimates

TIMELINE ESTIMATE

· Codebase audit: 2 hours
· Tool inventory: 3 hours
· Skill/Memory/Swarm: 2 hours
· Gap analysis: 2 hours
· Report writing: 1 hour
· TOTAL: ~10 hours

```

---

This SCOPE prompt gives Copilot everything needed to:
1. **Audit current JAGABOT completely**
2. **Document all 22 tools**
3. **Map dependencies**
4. **Analyze gaps for 7 urgent components**
5. **Provide clear recommendations for v3.0**

**Once we have this audit, we can plan EXACTLY how to integrate the 7 urgent components.** 🚀
