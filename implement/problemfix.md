📋 SCOPE PROMPT: Fix Jagabot Equity Calculation Inconsistency

```markdown
# SCOPE: Fix Jagabot Equity Calculation - Multiple Definitions Causing Inconsistent Outputs

## SITUATION
Jagabot v2.6 produces TWO DIFFERENT equity values for the SAME portfolio:

### OUTPUT 1 (Using Wrong Formula):
```

Equity: $3,284,935
Margin Status: ✅ TIADA MARGIN CALL
VaR 95%: $915,709 (30.52%)
CVaR: $1,099,273 (36.64%)

```

### OUTPUT 2 (Using Correct Formula):
```

Equity: $684,935
Margin Status: 🚨 MARGIN CALL TRIGGERED
VaR 95%: $229,772
CVaR: $283,052

```

### COLAB GROUND TRUTH (Correct):
```

Equity: $684,935
Margin Status: 🚨 MARGIN CALL TRIGGERED
VaR 95%: $229,772
CVaR: $283,052
Probability <$80: 42.26%
CV Score: 0.1726

```

## ROOT CAUSE IDENTIFIED
Jagabot has **TWO DIFFERENT DEFINITIONS** of equity:

```python
# DEFINITION A (WRONG - used by some subagents):
equity_A = current_value + cash  
# = $2,084,936 + $200,000 = $2,284,936
# (Output shows $3,284,935 - even larger! Maybe exposure + cash?)

# DEFINITION B (CORRECT - used by other subagents):
equity_B = capital + total_pnl
# = $1,000,000 - $315,064 = $684,935 ✅

# COLAB GROUND TRUTH (CORRECT):
equity_colab = capital + total_pnl = $684,935 ✅
```

IMPACT ANALYSIS

Component Using Wrong Equity Using Correct Equity Status
Margin Call ✅ TIADA 🚨 TRIGGERED ❌ KRITIKAL
VaR 95% $915,709 (4x) $229,772 ❌ SALAH
CVaR $1,099,273 (4x) $283,052 ❌ SALAH
Stress Test $476,611 $554,672 ❌ SALAH
Decision SELL (by chance) SELL (correct) ✅ OK

OBJECTIVE

Fix Jagabot to use ONE consistent, correct equity formula across ALL subagents:

```
equity = capital + total_pnl
OR equivalently:
equity = (current_value - loan) + cash
where:
- capital = initial capital (1,000,000)
- total_pnl = sum of all position P&L (-315,064)
- loan = exposure - capital (2,000,000)
- current_value = sum of position values (2,084,936)
- cash = cash allocation (200,000)
```

GROUND TRUTH REFERENCE (COLAB CODE)

```python
# ==========================================
# COLAB GROUND TRUTH - CORRECT CALCULATIONS
# ==========================================
import numpy as np

# Portfolio parameters
MODAL = 1_000_000
LEVERAJ = 3
EXPOSURE = MODAL * LEVERAJ  # 3,000,000

wti_alloc, brent_alloc, cash_alloc = 0.55, 0.25, 0.20
wti_buy, wti_now = 95.0, 82.50
brent_buy, brent_now = 98.0, 85.20

# Calculate units
wti_exposure = EXPOSURE * wti_alloc
brent_exposure = EXPOSURE * brent_alloc
wti_units = wti_exposure / wti_buy      # 17,368.42
brent_units = brent_exposure / brent_buy # 7,653.06

# Calculate P&L
wti_pnl = (wti_now - wti_buy) * wti_units      # -217,105
brent_pnl = (brent_now - brent_buy) * brent_units  # -97,959
total_pnl = wti_pnl + brent_pnl                 # -315,064

# CORRECT EQUITY FORMULA
current_equity = MODAL + total_pnl              # 684,935 ✅

# Current value (for reference)
current_value = (wti_now * wti_units) + (brent_now * brent_units)  # 2,084,936

# Margin check
margin_requirement = EXPOSURE / LEVERAJ         # 1,000,000
margin_call = current_equity < margin_requirement  # TRUE 🚨

# Monte Carlo (30 day)
np.random.seed(42)
simulations = 100000
volatility = 35 / 100  # 0.35 from VIX
dt_30 = 30 / 252
Z_30 = np.random.standard_normal(simulations)
wti_30_days = wti_now * np.exp((-0.5 * volatility**2) * dt_30 + 
                                volatility * np.sqrt(dt_30) * Z_30)
prob_below_80 = np.mean(wti_30_days < 80) * 100  # 42.26%

# VaR 95% (10 day)
dt_10 = 10 / 252
Z_10 = np.random.standard_normal(simulations)
wti_10_days = wti_now * np.exp((-0.5 * volatility**2) * dt_10 + 
                                volatility * np.sqrt(dt_10) * Z_10)
brent_10_days = brent_now * np.exp((-0.5 * volatility**2) * dt_10 + 
                                    volatility * np.sqrt(dt_10) * Z_10)

port_10_days = (wti_10_days * wti_units) + (brent_10_days * brent_units) + (EXPOSURE * cash_alloc)
port_now = (wti_now * wti_units) + (brent_now * brent_units) + (EXPOSURE * cash_alloc)
port_returns_10d = port_10_days - port_now

var_95 = np.percentile(port_returns_10d, 5)        # -229,772
cvar_95 = port_returns_10d[port_returns_10d <= var_95].mean()  # -283,052

# CV Analysis
changes = np.array([4.2, 5.1, 6.3, 6.8, 6.5, 7.2])
cv_value = np.std(changes) / np.mean(changes)      # 0.1726

# Stress Test
stress_prices = [75, 70, 65]
for price in stress_prices:
    stress_loss = (price - wti_now) * wti_units
    stress_equity = current_equity + stress_loss
    # stress_equity values: 554,672; 467,830; 380,988
```

AFFECTED COMPONENTS

Subagents Using WRONG Equity Formula:

1. portfolio_analyzer (primary offender)
2. var (uses equity for scaling?)
3. cvar (uses equity for scaling?)
4. stress_test (uses equity as base)
5. recovery_time (uses equity)
6. margin_check (uses equity)
7. decision_engine (indirectly via other tools)

Subagents Using CORRECT Equity Formula:

1. monte_carlo (independent)
2. financial_cv (independent)
3. correlation (independent)

REQUIRED FIXES

FIX 1: Standardize Equity Formula Across ALL Subagents

```python
# jagabot/tools/portfolio_analyzer.py
def calculate_equity(capital, total_pnl):
    """
    CORRECT equity formula: capital + total_pnl
    NOT: current_value + cash
    NOT: exposure + cash
    """
    return capital + total_pnl

def calculate_margin_status(equity, exposure, leverage):
    margin_requirement = exposure / leverage
    return {
        'equity': equity,
        'margin_requirement': margin_requirement,
        'margin_call': equity < margin_requirement,
        'excess_equity': max(0, equity - margin_requirement)
    }
```

FIX 2: Update All Risk Tools to Use Correct Equity

```python
# jagabot/tools/var.py
def calculate_var(portfolio, equity, ...):
    """
    Use correct equity for scaling if needed
    But VaR should be based on exposure/portfolio value, NOT equity
    """
    # VaR should be based on portfolio value, not equity
    portfolio_value = current_position_value + cash
    var = 1.645 * volatility * sqrt(10) * portfolio_value
    return var
```

FIX 3: Add Validation Layer

```python
# jagabot/sandbox/verifier.py
def verify_equity_consistency(analysis_results):
    """
    Check that all subagents use same equity value
    """
    equity_values = []
    for tool, result in analysis_results.items():
        if 'equity' in result:
            equity_values.append(result['equity'])
    
    if len(set(equity_values)) > 1:
        return {
            'consistent': False,
            'values': equity_values,
            'error': f"Multiple equity definitions: {equity_values}"
        }
    return {'consistent': True, 'equity': equity_values[0]}
```

FIX 4: Update System Prompts

```python
# SKILL.md - Add Equity Definition Rule

## EQUITY DEFINITION - CRITICAL RULE

**ALWAYS use this formula:**
```

equity = initial_capital + total_unrealized_pnl

```

**NEVER use these formulas:**
- `equity = current_position_value + cash` ❌ (forgets loan)
- `equity = exposure + cash` ❌ (double counts)
- `equity = portfolio_value` ❌ (confuses with NAV)

**Verification:**
- Initial capital: 1,000,000
- Total P&L: -315,064
- Correct equity: 684,936
```

FIX 5: Add Comprehensive Tests

```python
# tests/test_equity_consistency.py

def test_equity_calculation():
    """Test equity formula against ground truth"""
    capital = 1_000_000
    total_pnl = -315_064
    expected_equity = 684_936
    
    equity = calculate_equity(capital, total_pnl)
    assert abs(equity - expected_equity) < 100

def test_margin_status():
    """Test margin call detection"""
    equity = 684_936
    exposure = 3_000_000
    leverage = 3
    margin_req = exposure / leverage  # 1,000,000
    
    assert equity < margin_req  # Should be TRUE
    assert margin_call_detected(equity, exposure, leverage) == True

def test_all_subagents_same_equity():
    """Run full analysis and verify all tools use same equity"""
    results = run_complete_analysis(test_query)
    
    # Check all tools that return equity
    for tool in ['portfolio_analyzer', 'var', 'stress_test']:
        assert abs(results[tool]['equity'] - 684_936) < 100

def test_regression_wrong_equity():
    """Ensure wrong equity values never appear"""
    results = run_complete_analysis(test_query)
    
    # These wrong values should NEVER appear
    forbidden_values = [3_284_935, 2_284_936, 5_284_936]
    for value in forbidden_values:
        assert value not in str(results)
```

TESTING REQUIREMENTS

Test Case 1: Basic Equity

```python
query = """
MODAL: 1,000,000
LEVERAJ: 3
WTI: 55% (BUY=95, NOW=82.50)
BRENT: 25% (BUY=98, NOW=85.20)
CASH: 20%
"""
expected_equity = 684_935
```

Test Case 2: Margin Call Detection

```python
# With equity 684,935 and margin req 1,000,000
expected_margin_call = True
```

Test Case 3: Stress Test Consistency

```python
# Stress test at $75 should use SAME equity as portfolio_analyzer
stress_equity = 554,672  # Based on correct equity 684,935
```

Test Case 4: VaR/CVaR Scaling

```python
# VaR should NOT scale with wrong equity
correct_var = 229,772
wrong_var = 915,709  # 4x larger
```

FILES TO MODIFY

1. jagabot/tools/portfolio_analyzer.py
2. jagabot/tools/var.py
3. jagabot/tools/cvar.py
4. jagabot/tools/stress_test.py
5. jagabot/tools/recovery_time.py
6. jagabot/swarm/planner.py (equity extraction)
7. jagabot/sandbox/verifier.py (add consistency check)
8. SKILL.md (add equity definition rule)
9. tests/test_equity_consistency.py (new file)

SUCCESS CRITERIA

After fixes:

✅ ALL subagents return SAME equity value:

```
portfolio_analyzer.equity = 684,935
var.equity (if used) = 684,935
stress_test.base_equity = 684,935
recovery_time.equity = 684,935
```

✅ Margin call correctly detected:

```
margin_call = TRUE (equity 684,935 < 1,000,000)
```

✅ VaR/CVaR match ground truth:

```
var_95 = 229,772 (not 915,709)
cvar = 283,052 (not 1,099,273)
```

✅ Stress test values match:

```
stress @75: 554,672
stress @70: 467,830  
stress @65: 380,988
```

✅ No inconsistent outputs in any analysis

TIMELINE

Task Est. Time
Fix portfolio_analyzer equity formula 1 hour
Update var/cvar to use correct equity 1 hour
Fix stress_test base equity 1 hour
Add verifier consistency check 1 hour
Update system prompts 1 hour
Add 15 new tests 2 hours
Verify against Colab 1 hour
TOTAL 8 hours

```

---

This SCOPE prompt gives Copilot everything needed to:
1. **Understand the problem** (two different equity definitions)
2. **See the ground truth** (Colab code with correct calculations)
3. **Fix all affected subagents** to use ONE consistent formula
4. **Add validation** to prevent future inconsistencies
5. **Test thoroughly** against ground truth values

**Ready to fix Jagabot's equity calculation once and for all!** 🎯
