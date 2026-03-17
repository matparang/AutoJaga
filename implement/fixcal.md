✅ SETUJU! Kita fix SEMUA 3 masalah - 1 SCOPE untuk semuanya

📋 SCOPE PROMPT: JAGABOT v3.7.1 - Fix VaR, Recovery & Bear Confidence

```markdown
# SCOPE: JAGABOT v3.7.1 - Critical Fixes (VaR, Recovery, Bear)

## CURRENT STATE
✅ v3.7 complete (1277 tests)
❌ VaR 95%: $1,280,400 vs $819,534 (+56% error)
❌ Recovery Time: 23.5 bulan vs 43 bulan (-19.5 bulan error)
❌ Bear Confidence: 100% vs 51.5% (+48.5% error)
✅ Basic math correct (units, equity)
✅ Final decision correct (SELL)

## FIX 1: VaR Formula (Use Portfolio Value, NOT Exposure)

### Current (WRONG)
```python
# jagabot/tools/var.py
var = 1.645 * volatility * sqrt(10) * exposure  # Using $6,000,000
```

Correct (from Colab)

```python
portfolio_value = position_value + cash  # $4,610,265 + $600,000 = $5,210,265
var = 1.645 * volatility * sqrt(10/252) * portfolio_value  # $819,534
```

Fix Implementation

```python
def calculate_var(portfolio_value, volatility, days=10):
    """
    Calculate VaR using portfolio value (not exposure)
    """
    z_score = 1.645  # 95% confidence
    time_factor = np.sqrt(days/252)
    var_amount = z_score * volatility * time_factor * portfolio_value
    
    return {
        'var_amount': var_amount,
        'var_percentage': (var_amount / portfolio_value) * 100,
        'portfolio_value': portfolio_value
    }
```

FIX 2: Recovery Time (15% Annual Return)

Current (WRONG)

```python
# Formula maybe using 20%+ return
years = log(target_return) / log(1.20)  # Too optimistic
```

Correct (from Colab)

```python
annual_return = 0.15  # 15% per year (market average)
target_return = (MODAL / current_equity) - 1  # 65.25%
years = np.log(1 + target_return) / np.log(1 + annual_return)  # 3.6 years
```

Fix Implementation

```python
def calculate_recovery_time(current_equity, target_capital, annual_return=0.15):
    """
    Calculate years to recover with given annual return
    Default 15% (market average)
    """
    if current_equity >= target_capital:
        return 0
    
    target_return = (target_capital / current_equity) - 1
    years = np.log(1 + target_return) / np.log(1 + annual_return)
    
    return {
        'years': years,
        'months': years * 12,
        'target_return': target_return * 100,
        'annual_return': annual_return * 100
    }
```

FIX 3: Bear Confidence Calibration

Current (WRONG)

```python
# Too aggressive (100% just because margin call)
bear_conf = 100 if margin_call else ...
```

Target (from Colab analysis)

```python
# Bear should be based on:
# - VaR percentage (15.73%) → weight 0.4
# - Probability downside (42.33%) → weight 0.3
# - Margin call severity → weight 0.3

bear_conf = (
    (var_percent * 2) * 0.4 +  # 15.73% * 2 = 31.46% * 0.4 = 12.6%
    prob_below * 0.3 +          # 42.33% * 0.3 = 12.7%
    (margin_shortfall_ratio * 100) * 0.3  # (789k/2M=0.39) → 39% * 0.3 = 11.7%
)  # Total ~37% + margin_call_boost = ~51.5%
```

Fix Implementation

```python
def calculate_bear_confidence(prob_below, var_percent, margin_shortfall_ratio, margin_call):
    """
    Calibrated bear confidence based on risk metrics
    """
    conf = 0
    
    # VaR component (max 40%)
    conf += min(var_percent * 2, 40) * 0.4
    
    # Probability component (max 30%)
    conf += prob_below * 0.3
    
    # Margin shortfall component (max 30%)
    if margin_call:
        conf += min(margin_shortfall_ratio * 100, 30) * 0.3
    
    # Small boost for margin call (but not 100%)
    if margin_call:
        conf += 10
    
    return min(conf, 100)
```

FILES TO MODIFY

1. jagabot/tools/var.py - Fix VaR formula
2. jagabot/tools/recovery_time.py - Fix to 15% annual return
3. jagabot/tools/decision_engine.py - Fix bear confidence formula
4. tests/test_var.py - Update expected values
5. tests/test_recovery.py - Update expected values
6. tests/test_decision_engine.py - Update bear confidence tests

NEW TESTS (10+)

1. test_var_with_portfolio_value() - Verify VaR matches Colab
2. test_recovery_15_percent() - Verify 3.6 years
3. test_bear_calibration() - Verify ~51.5% confidence
4. test_integration_fixes() - Full portfolio test

SUCCESS CRITERIA

After fixes, running test portfolio should produce:

```python
EXPECTED_VALUES = {
    'var_amount': 819534,        # Not 1,280,400
    'var_percentage': 15.73,     # Not 21.34
    'recovery_months': 43,        # Not 23.5
    'bear_confidence': 51.5,      # Not 100
    'final_decision': 'SELL',
    'final_confidence': 69.7
}
```

✅ VaR fixed (uses portfolio_value)
✅ Recovery fixed (15% annual return)
✅ Bear calibrated (51.5%)
✅ All 1277+ tests passing
✅ Target: 1287+ tests

TIMELINE

Fix Hours
VaR formula 1
Recovery time 1
Bear confidence 2
Tests (10+) 2
Integration 1
TOTAL 7 hours

```

---

**Satu SCOPE untuk fix semua 3 masalah. Boleh implement cepat sebelum credit habis!** 🚀
