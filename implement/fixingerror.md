📋 SCOPE PROMPT: Fix Jagabot Risk Metrics Volatility Calculation

```markdown
# SCOPE: Fix Jagabot Risk Metrics - Volatility Scaling Error

## SITUATION
Jagabot v2.3 has been tested against Google Colab ground truth. Results show:

✅ **BASIC MATH IS PERFECT** (0.00% error)
- Equity: $546,942 (vs $546,942)
- P&L: -$203,057 (vs -$203,058)
- Margin Requirement: $750,000 (vs $750,000)

❌ **RISK METRICS HAVE SYSTEMATIC ERROR** (All ~2.2x too high)
- Probability <$75: 45.77% vs 24.41% (+87.5% error)
- VaR 95%: $260,398 vs $117,179 (+122% error)
- CV: 50.0% vs 22.25% (+124% error)
- Stress Test $60: $400,000 vs $183,468 (+118% error)

## ROOT CAUSE IDENTIFIED
The agent is using **percentage values (e.g., 22.25)** instead of **decimal values (0.2225)** in risk calculations:

```python
# WRONG (what agent does):
vol_pct = 22.25  # percentage
var = 1.645 * vol_pct * sqrt(10) * exposure  # $260,398 (2.2x too high)

# CORRECT (what should happen):
vol_decimal = 0.2225  # decimal (22.25% / 100)
var = 1.645 * vol_decimal * sqrt(10) * exposure  # $117,179
```

AFFECTED COMPONENTS

1. Monte Carlo probability - uses vol in GBM formula
2. VaR/CVaR calculations - uses vol in parametric VaR
3. CV Analysis - CV should be 0.2225, not 22.25%
4. Stress Test scenarios - indirectly affected by wrong vol
5. 3 Perspectives confidence scores - based on risk metrics

OBJECTIVE

Fix ALL risk calculations to use decimal volatility (0.XX) not percentage (XX%).

REQUIRED FIXES

FIX 1: Monte Carlo Worker (jagabot/workers/monte_carlo.py)

```python
# CURRENT (WRONG - using percentage):
vol = np.std(returns) * 100  # Returns 22.25
# ...
price *= np.exp((mu - 0.5 * vol**2) + vol * np.random.normal())  # vol=22.25 (WRONG!)

# CORRECT (use decimal):
vol_decimal = np.std(returns)  # Returns 0.2225 (22.25% / 100)
# ...
price *= np.exp((mu - 0.5 * vol_decimal**2) + vol_decimal * np.random.normal())
```

FIX 2: VaR/CVaR Calculations

```python
# CURRENT (WRONG):
var = 1.645 * (vol_pct) * np.sqrt(10) * exposure  # Using 22.25

# CORRECT:
vol_decimal = vol_pct / 100 if vol_pct > 1 else vol_pct  # Handle both cases
var = 1.645 * vol_decimal * np.sqrt(10) * exposure
```

FIX 3: CV Analysis (jagabot/tools/cv_analysis.py)

```python
# CURRENT (returns percentage):
cv = (np.std(returns) / np.mean(returns)) * 100  # Returns 22.25

# CORRECT (return decimal, let formatter handle display):
cv = np.std(returns) / np.mean(returns)  # Returns 0.2225

# Display layer can add % symbol, but calculations use decimal
```

FIX 4: Stress Test Worker

```python
# Stress test doesn't directly use vol, but ensure units are correct
# All equity calculations already verified ✅
```

FIX 5: Update System Prompts

```python
SUBAGENT_RISK_PROMPT = """
You are a RISK ANALYSIS expert.

🚫 CRITICAL RULE - VOLATILITY UNITS:
- ALWAYS use DECIMAL values (0.XX) for volatility in calculations
- NEVER use percentage values (XX%) in formulas
- Convert: 22.25% → 0.2225 before using in math

✅ CORRECT:
vol = 0.2225
var = 1.645 * vol * sqrt(10) * exposure

❌ INCORRECT:
vol = 22.25
var = 1.645 * vol * sqrt(10) * exposure  # This gives WRONG results!

Always verify units before calculations.
"""
```

TESTING REQUIREMENTS

Test Case 1: Volatility Conversion

```python
# Input
returns = [0.032, 0.045, 0.058, 0.062, 0.059, 0.068]
vol_decimal = np.std(returns)  # Should be ~0.2225
vol_pct = vol_decimal * 100  # Should be ~22.25%

assert 0.22 < vol_decimal < 0.23  # Pass
assert 22.0 < vol_pct < 23.0  # Pass
```

Test Case 2: Monte Carlo Probability

```python
# With correct decimal volatility
prob = monte_carlo(price=78.50, vol=0.2225, target=75)
assert 23.0 < prob < 26.0  # Should be ~24.41%

# With wrong percentage volatility
prob_wrong = monte_carlo(price=78.50, vol=22.25, target=75)
assert prob_wrong > 40  # Would be ~45.77% (WRONG!)
```

Test Case 3: VaR Calculation

```python
exposure = 1_875_000
vol_decimal = 0.2225
var_correct = 1.645 * vol_decimal * np.sqrt(10) * exposure  # ~$117,179
var_wrong = 1.645 * 22.25 * np.sqrt(10) * exposure  # ~$260,398 (2.2x too high)

assert 110_000 < var_correct < 120_000
```

Test Case 4: CV Analysis

```python
returns = [0.032, 0.045, 0.058, 0.062, 0.059, 0.068]
cv_decimal = np.std(returns) / np.mean(returns)  # Should be ~0.2225
cv_pct = cv_decimal * 100  # Should be ~22.25%

assert 0.22 < cv_decimal < 0.23
assert 22.0 < cv_pct < 23.0
```

VERIFICATION WITH COLAB

After fixes, run against Google Colab ground truth:

```python
EXPECTED_VALUES = {
    "prob_below_75": 24.41,  # Not 45.77
    "var_95": 117179,         # Not 260398
    "cv": 22.25,              # Not 50.0
    "stress_70": 354671,       # Not 600000
    "stress_65": 269069,       # Not 500000
    "stress_60": 183468        # Not 400000
}

# All should be within 1% error after fix
```

FILES TO MODIFY

1. jagabot/workers/monte_carlo.py
2. jagabot/tools/var.py (if exists)
3. jagabot/tools/cvar.py (if exists)
4. jagabot/tools/cv_analysis.py
5. jagabot/workers/risk_worker.py (if exists)
6. jagabot/guardian/subagents/risk.py (prompts)
7. SKILL.md (update system prompts)

NEW TESTS TO ADD

Add 15 new tests to tests/test_jagabot/test_risk_metrics.py:

· Test volatility decimal conversion
· Test Monte Carlo with correct vol scaling
· Test VaR with decimal vs percentage
· Test CV analysis returns decimal
· Test stress test integration
· Test all risk metrics against Colab ground truth
· Test edge cases (zero vol, negative returns)

SUCCESS CRITERIA

After fixes, run the Colab comparison again:

```
Metric          Ground Truth    Jagabot (Fixed)    Error
──────────────  ──────────────  ─────────────────  ──────
Prob <$75       24.41%          24.41%             ±0.1%
VaR 95%         $117,179        $117,179           ±$100
CV              22.25%          22.25%             ±0.1%
Stress $60      $183,468        $183,468           ±$500
```

All errors should be <1% (rounding only).

TIMELINE

Task Est. Time
Fix Monte Carlo worker 2 hours
Fix VaR/CVaR tools 1 hour
Fix CV analysis 1 hour
Update system prompts 1 hour
Add tests (15 new) 3 hours
Verify with Colab 1 hour
TOTAL 9 hours

```

---

This SCOPE prompt gives Copilot everything needed to:
1. **Understand the exact problem** (volatility scaling error)
2. **See the pattern** (all risk metrics 2.2x too high)
3. **Fix each affected component** with correct code
4. **Test thoroughly** with before/after comparisons
5. **Verify against Colab ground truth**

**Ready to fix Jagabot's risk metrics!** 🎯
