---
name: systematic_debugging
description: 4-phase debugging for financial analysis errors — Observe → Hypothesize → Test → Verify
metadata: {"jagabot":{"emoji":"🔍","trigger":"systematic_debugging"}}
---

# Systematic Debugging Skill

## TRIGGER
- Analysis produces unexpected results
- Risk metrics diverge from historical patterns
- User reports: "this doesn't look right", "unexpected result", "error"
- Anomaly detected by EvaluationTool (z-score > 2)

## PURPOSE
Apply systematic debugging methodology to financial analysis errors. Instead of ad-hoc fixes, follow a structured 4-phase process to identify root causes, test hypotheses, and prevent regression.

## WORKFLOW

### Phase 1: OBSERVE — Gather Facts
1. **What was expected?** Query MemoryFleet for previous similar analyses
2. **What actually happened?** Document the anomalous output
3. **What changed?** Check:
   - Input data differences
   - Parameter values (EvolutionEngine current params)
   - Market regime shifts (VIX level, correlation changes)
4. Collect all relevant data points

### Phase 2: HYPOTHESIZE — Generate Causes
Generate exactly 3 hypotheses ranked by probability:
- **H1** (most likely): Use Bayesian reasoning with available evidence
- **H2** (alternative): Consider data quality issues
- **H3** (edge case): Consider model assumptions broken
- Use `bayesian` tool to assign prior probabilities to each

### Phase 3: TEST — Controlled Experiments
For each hypothesis (starting with highest probability):
1. Design a test that would confirm or reject the hypothesis
2. Run the test using relevant tools:
   - `financial_cv` → Check if volatility regime changed
   - `correlation` → Check if correlations broke down
   - `stress_test` → Check if scenario was outside tested range
   - `evaluate_result` → Compare expected vs actual numerically
3. Record result: CONFIRMED or REJECTED
4. Stop at first CONFIRMED hypothesis

### Phase 4: VERIFY — Fix and Prevent
1. Apply the fix (adjust parameters, update data, recalculate)
2. Re-run the original analysis to confirm fix works
3. `review` → Two-stage review on corrected output
4. `knowledge_graph` → Add lesson: "cause → fix → prevention"
5. `meta_learning` → Record debugging outcome for pattern learning
6. Document regression test for future detection

## TOOLS USED
- bayesian, financial_cv, correlation, stress_test, evaluate_result
- review, knowledge_graph, meta_learning, evolution (for param checks)

## COMPOSABLE
- Called by: Any skill when review fails or anomaly detected
- Calls: risk_validation (Phase 4 — re-verify after fix)
