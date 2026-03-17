---
name: portfolio_rebalancing
description: Portfolio rebalancing workflow — verify → present options → execute → update
metadata: {"jagabot":{"emoji":"⚖️","trigger":"rebalancing"}}
---

# Portfolio Rebalancing Skill

## TRIGGER
- Risk metrics exceed thresholds (VaR > limit, concentration > 40%)
- User requests: rebalance, adjust allocation, trim, rotate sectors
- Skill trigger detects: overweight, underweight, sector rotation

## PURPOSE
Systematically rebalance a portfolio by comparing current allocation to targets, presenting actionable options with risk/tax implications, and tracking the outcome.

## WORKFLOW

### Step 1: VERIFY Current Allocation
- `portfolio_analyzer` → Get current positions, weights, and exposure
- Compare with target allocation (from MemoryFleet or user-defined)
- Flag overweights (> +5% drift) and underweights (> -5% drift)

### Step 2: PRESENT Options
Generate 3 rebalancing options:
- **Option A: Sell Overweights** — Reduce largest drifts first
- **Option B: Buy Underweights** — Deploy cash to fill gaps
- **Option C: Hedge with Options** — Use puts/calls instead of selling
- Each option shows: trades needed, estimated cost, tax impact

### Step 3: SIMULATE
- `sensitivity` → Sensitivity of each option to market moves
- `monte_carlo` → Forward simulation of rebalanced portfolio
- `review` → Quality gate on simulation results

### Step 4: EXECUTE (after user approval)
- Generate trade list with exact quantities
- Verify with user before any execution
- Log rationale for each trade

### Step 5: UPDATE Memory
- `memory_fleet` → Save new allocation snapshot
- `knowledge_graph` → Record rebalancing event with rationale
- `meta_learning` → Track performance of rebalancing decision

## TOOLS USED
- portfolio_analyzer, sensitivity, monte_carlo, var, cvar
- review (two-stage), memory_fleet, knowledge_graph, meta_learning

## COMPOSABLE
- Called by: crisis_management (Step 5), risk_validation (REFACTOR step)
- Calls: risk_validation (to verify post-rebalance risk)
