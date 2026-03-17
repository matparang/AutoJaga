📋 SCOPE PROMPT: Fix JAGABOT v3.2.1 - Tool Calibration

```markdown
# SCOPE: JAGABOT v3.2.1 - Tool Calibration (Monte Carlo, VaR, Stress Test)

## SITUATION
JAGABOT v3.2 (1068 tests) shows discrepancies vs Colab ground truth:

❌ Probability <$70: 40.26% vs 34.24% (+6.02% error)
❌ VaR 95%: 1-day default vs industry standard 10-day
❌ Stress Test @$65: $688,515 vs $864,064 (-$175,549 error)
❌ Bear confidence: 50.3% vs 25.0% (due to tool errors)
❌ Final decision: REDUCE vs SELL (due to tool errors)

✅ Basic math correct: Units, Equity, Margin ✓

## ROOT CAUSES

### 1. Monte Carlo Probability Error
```python
# CURRENT (WRONG)
volatility = VIX  # Using 52 instead of 0.52
# or wrong time scaling

# CORRECT (from Colab)
volatility = VIX / 100  # 52 → 0.52
dt = days / 252  # 30/252 = 0.119
prices = current * exp((-0.5 * vol**2) * dt + vol * sqrt(dt) * Z)
```

2. VaR Default Period

```python
# CURRENT (WRONG)
def var(portfolio, days=1):  # 1-day not standard

# CORRECT (Industry Standard)
def var(portfolio, days=10, confidence=0.95):
    """Value at Risk - default 10-day (Basel standard)"""
```

3. Stress Test Formula

```python
# CURRENT (WRONG)
stress_equity = current_equity - (loss_per_unit * units)

# CORRECT (from Colab)
stress_loss = (stress_price - current_price) * units
stress_equity = current_equity + stress_loss  # loss is negative
```

OBJECTIVE

Fix these 3 tools to match Colab ground truth:

1. monte_carlo - correct volatility scaling (VIX/100)
2. var - default to 10-day (industry standard)
3. stress_test - correct equity calculation formula

DELIVERABLES

FIX 1: monte_carlo.py

```python
# jagabot/tools/monte_carlo.py (updated)

def monte_carlo(current_price, vix, target, days=30, simulations=100000):
    """
    Correct GBM Monte Carlo with VIX scaling
    
    Args:
        current_price: Current asset price
        vix: VIX value (e.g., 52 for 52% annual volatility)
        target: Target price threshold
        days: Forecast horizon (default 30)
        simulations: Number of paths (default 100000)
    """
    # CORRECT: Convert VIX to decimal
    volatility = vix / 100  # 52 → 0.52
    
    # Time in years (trading days)
    dt = days / 252
    
    # GBM simulation
    np.random.seed(42)  # reproducibility
    Z = np.random.standard_normal(simulations)
    prices = current_price * np.exp(
        (-0.5 * volatility**2) * dt + 
        volatility * np.sqrt(dt) * Z
    )
    
    # Probability
    prob_below = np.mean(prices < target) * 100
    
    # Confidence interval
    n_below = np.sum(prices < target)
    ci_lower, ci_upper = stats.beta.interval(
        0.95, n_below + 1, simulations - n_below + 1
    )
    
    return {
        'probability': prob_below,
        'ci_95': [ci_lower*100, ci_upper*100],
        'mean': np.mean(prices),
        'median': np.median(prices),
        'p5': np.percentile(prices, 5),
        'p95': np.percentile(prices, 95)
    }
```

FIX 2: var.py

```python
# jagabot/tools/var.py (updated)

def var(portfolio, days=10, confidence=0.95):
    """
    Value at Risk - default 10-day (Basel standard)
    
    Args:
        portfolio: Portfolio value or exposure
        days: Holding period (default 10 days)
        confidence: Confidence level (default 0.95)
    """
    # Use Monte Carlo or parametric method
    # Scale to requested days
    var_1day = calculate_var_1day(portfolio)
    var_ndays = var_1day * np.sqrt(days)
    
    return {
        'var_amount': var_ndays,
        'var_percentage': (var_ndays / portfolio) * 100,
        'days': days,
        'confidence': confidence,
        'method': 'parametric'
    }
```

FIX 3: stress_test.py

```python
# jagabot/tools/stress_test.py (updated)

def stress_test(current_equity, current_price, stress_price, units):
    """
    Calculate equity under stressed price
    
    Args:
        current_equity: Current equity value
        current_price: Current asset price
        stress_price: Stressed price scenario
        units: Number of units held
    """
    # CORRECT formula
    stress_loss = (stress_price - current_price) * units
    stress_equity = current_equity + stress_loss  # loss is negative
    
    return {
        'stress_price': stress_price,
        'additional_loss': abs(stress_loss),
        'stress_equity': stress_equity,
        'change_percent': (stress_equity / current_equity - 1) * 100
    }
```

TESTING REQUIREMENTS

Test 1: Monte Carlo

```python
def test_monte_carlo():
    result = monte_carlo(76.50, 52, 70, days=30, simulations=100000)
    assert 33.0 < result['probability'] < 35.0  # Should be ~34.24%
    assert result['ci_95'][0] < result['probability'] < result['ci_95'][1]
```

Test 2: VaR Default

```python
def test_var_default():
    result = var(3_750_000)  # No days specified
    assert result['days'] == 10  # Default to 10
    assert 400_000 < result['var_amount'] < 430_000  # ~$419,384
```

Test 3: Stress Test

```python
def test_stress_test():
    result = stress_test(1_109_092, 76.50, 65, 21_307)
    assert abs(result['stress_equity'] - 864_064) < 1000
    assert abs(result['change_percent'] + 22.09) < 0.1
```

Test 4: Full Integration

```python
def test_full_analysis():
    # Run complete portfolio analysis
    results = analyze_portfolio(test_data)
    
    # Should now match Colab
    assert abs(results['probability'] - 34.24) < 0.5
    assert abs(results['var_amount'] - 419_384) < 5000
    assert abs(results['stress_equity'] - 864_064) < 5000
```

FILES TO MODIFY

1. jagabot/tools/monte_carlo.py - Fix probability
2. jagabot/tools/var.py - Set default to 10 days
3. jagabot/tools/cvar.py - Update to match var
4. jagabot/tools/stress_test.py - Fix formula
5. tests/test_monte_carlo.py - Update expected values
6. tests/test_var.py - Update expected values
7. tests/test_stress_test.py - Update expected values
8. tests/test_integration.py - Update full analysis test

SUCCESS CRITERIA

After fixes, running the test portfolio should produce:

```python
EXPECTED_VALUES = {
    'probability': 34.24,  # Not 40.26
    'var_amount': 419384,   # 10-day, not 1-day
    'stress_equity': 864064, # Not 688515
    'bull_confidence': 65.8,
    'bear_confidence': 25.0,
    'buffet_confidence': 100.0,
    'final_decision': 'SELL',
    'final_confidence': 63.1
}
```

✅ All 3 tools fixed
✅ 1088+ tests passing
✅ No regression in existing features
✅ All 32 tools still working
✅ UI still functional

TIMELINE

Fix Hours
Monte Carlo 2
VaR default 1
Stress test 1
Update tests (15+) 3
Integration testing 2
Documentation 1
TOTAL 10 hours

```

---

**This SCOPE will fix the 3 critical tools and make JAGABOT match Colab 100%.** 🚀
