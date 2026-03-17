---
name: risk_validation
description: TDD-style risk validation — RED (define expected) → GREEN (calculate actual) → REFACTOR (adjust if mismatch)
metadata: {"jagabot":{"emoji":"🧪","trigger":"risk_validation"}}
---

# Risk Validation Skill (TDD-Style)

## TRIGGER
- Before any major investment decision
- User requests: validate, check risk, verify, backtest
- After portfolio changes (auto-triggered by rebalancing skill)

## PURPOSE
Apply Test-Driven Development principles to financial risk assessment. Define expectations FIRST, then calculate actuals, then adjust parameters if there's a mismatch. This ensures disciplined, evidence-based risk management.

## WORKFLOW

### Step 1: RED — Define Expectations
Before running any calculations, state expected values:
```
Expected VaR (95%):    $X
Expected CVaR (95%):   $Y
Expected max drawdown: Z%
Expected correlation:  W
Margin status:         Safe / Warning / Critical
```
Source expectations from: previous analyses (MemoryFleet), market consensus, user input.

### Step 2: GREEN — Calculate Actuals
Run the full risk toolkit:
- `var` → Calculate actual Value-at-Risk
- `cvar` → Calculate actual Conditional VaR
- `stress_test` → Run stress scenarios
- `correlation` → Calculate correlation matrix
- `monte_carlo` → Forward simulation

### Step 3: COMPARE — Test Pass/Fail
For each metric, compare expected vs actual:
- **PASS** (< 20% deviation): Metric is within tolerance
- **WARN** (20-50% deviation): Flag for review
- **FAIL** (> 50% deviation): Critical mismatch requiring action

### Step 4: REFACTOR — Adjust on Mismatch
If any test FAILS:
1. Log discrepancy to MetaLearningEngine
2. Use `evolution` tool to check if parameter adjustment helps
3. Update KnowledgeGraph with the lesson learned
4. Re-run failed tests with adjusted parameters

### Step 5: COMMIT — Only if Tests Pass
- `review` → Two-stage review (spec + quality)
- `memory_fleet` → Store validated risk snapshot
- `meta_learning` → Record validation outcome for calibration

## TOOLS USED
- var, cvar, stress_test, correlation, monte_carlo
- evolution (for parameter tuning), review, memory_fleet, meta_learning, knowledge_graph

## COMPOSABLE
- Called by: crisis_management, portfolio_rebalancing, investment_thesis
- Calls: (leaf skill — does not call other workflows)
