✅ SCOPE PROMPT: Fix Jagabot's Financial Tools

---

```markdown
# SCOPE: Debug and Fix Jagabot's Financial Tools

## SITUATION
Jagabot has 8 financial tools, but testing shows:
1. ✅ **Monte Carlo tool** - WORKING (23.94% probability)
2. ❌ **Financial CV tool** - ERROR with parameters
3. ❌ **Visualization tool** - ERROR with data format
4. ⚠️ **Other 5 tools** - UNTESTED (bayesian, statistical, early_warning, counterfactual, sensitivity, pareto)

## CURRENT STATE

### What Works
```python
# Monte Carlo produces correct results
probability = 23.94%  # matches VIX=58 expectation
CI = [40.05, 68.32]   # reasonable range
```

What Fails

```
1. Financial CV tool - parameter error when called
2. Visualization tool - cannot process Monte Carlo output format
3. Other tools - never called by agent (possibly registration issue)
```

Agent's Workaround

Despite failures, agent manually calculated:

· Equity: -$170,000 ✓
· Loss scenarios: $883k at $45, $1.58M at $40 ✓
· Created ASCII dashboard with tables ✓

OBJECTIVE

Fix ALL 8 tools so they:

1. Register correctly in tool registry
2. Accept proper parameters
3. Return consistent data formats
4. Can be called by agent automatically
5. Pass unit tests

TOOL-BY-TOOL DEBUGGING

TOOL 1: Financial CV Engine ❌

Current Error: Parameter mismatch

Expected Input:

```python
{
    "changes": [0.7, 2.4, 4.2, 6.7, 8.3, 7.4],  # List of price changes
    "asset_name": "WTI"  # Optional
}
```

Expected Output:

```python
{
    "cv": 0.55,
    "mean_ratio": 1.78,
    "pattern": "TIDAK STABIL",
    "ratios": [3.43, 1.75, 1.6, 1.24, 0.89]
}
```

Fix Checklist:

· Check tool registration in jagabot/agent/tools/registry.py
· Verify function signature matches schema
· Add input validation
· Test with sample data

---

TOOL 2: Visualization Engine ❌

Current Error: Cannot process Monte Carlo output format

Expected Input:

```python
{
    "prices": [23.4, 45.6, 51.2, ...],  # List of simulated prices
    "current_price": 52.80,
    "target_price": 45,
    "probability": 23.94,
    "ci_lower": 40.05,
    "ci_upper": 68.32
}
```

Expected Output (Base64 PNG):

```python
{
    "chart_base64": "iVBORw0KGgoAAAANS...",  # Base64 encoded PNG
    "format": "png",
    "width": 800,
    "height": 600
}
```

Fix Checklist:

· Ensure matplotlib is installed (pip install matplotlib)
· Fix data format conversion
· Add error handling for missing data
· Test with Monte Carlo output

---

TOOL 3: Bayesian Engine ⚠️ (Untested)

Expected Function:

```python
def bayesian_update(prior, likelihood, evidence):
    """Update probability using Bayes theorem"""
    posterior = (likelihood * prior) / evidence
    return {
        "prior": prior,
        "likelihood": likelihood,
        "evidence": evidence,
        "posterior": posterior
    }
```

Test Case:

```python
prior = 0.45  # 45% recession probability
likelihood = 0.8
evidence = 0.7
# Expected posterior = 0.514 (51.4%)
```

---

TOOL 4: Statistical Engine ⚠️ (Untested)

Expected Functions:

```python
def confidence_interval(data, confidence=0.95):
    """Calculate confidence interval"""
    
def t_test(sample1, sample2):
    """Run t-test between two samples"""
```

---

TOOL 5: Early Warning Engine ⚠️ (Untested)

Expected Function:

```python
def detect_warnings(current_data, historical_data):
    """Generate RED/YELLOW/GREEN warnings"""
    # VIX > 40 → RED
    # CV > 0.40 → RED
    # USD Index > 108 → YELLOW
```

---

TOOL 6: Counterfactual Engine ⚠️ (Untested)

Expected Function:

```python
def simulate_scenario(base_price, scenario_params):
    """Run what-if scenarios"""
```

---

TOOL 7: Sensitivity Engine ⚠️ (Untested)

Expected Function:

```python
def analyze_sensitivity(base_params, variations=0.1):
    """Analyze parameter sensitivity"""
```

---

TOOL 8: Pareto Engine ⚠️ (Untested)

Expected Function:

```python
def optimize_strategies(strategies):
    """Find optimal strategies using Pareto frontier"""
```

REGISTRATION CHECK

Verify all tools are registered in jagabot/agent/tools/__init__.py:

```python
from .financial_cv import financial_cv
from .monte_carlo import monte_carlo
from .bayesian import bayesian_update
from .statistical import confidence_interval, t_test
from .early_warning import detect_warnings
from .counterfactual import simulate_scenario
from .sensitivity import analyze_sensitivity
from .pareto import optimize_strategies
from .visualization import generate_chart

def register_all_tools(registry):
    registry.register(
        name="financial_cv",
        function=financial_cv,
        description="Calculate Coefficient of Variation and pattern classification",
        schema={
            "changes": {"type": "array", "items": {"type": "number"}, "required": True},
            "asset_name": {"type": "string", "required": False}
        }
    )
    # ... register all 8 tools
```

TEST SCRIPT

Create a test script to verify all tools:

```python
# tests/test_financial_tools.py
import pytest
from jagabot.agent.tools import *

def test_monte_carlo():
    result = monte_carlo(52.80, 58, 45)
    assert 15 < result['probability'] < 30
    assert 'ci_lower' in result

def test_financial_cv():
    changes = [0.7, 2.4, 4.2, 6.7, 8.3, 7.4]
    result = financial_cv(changes, "WTI")
    assert abs(result['cv'] - 0.55) < 0.1
    assert result['pattern'] == "TIDAK STABIL"

def test_visualization():
    prices = [23.4, 45.6, 51.2] * 1000  # Mock data
    result = generate_chart(prices, 52.80, 45, 23.94)
    assert 'chart_base64' in result
    assert len(result['chart_base64']) > 100

# Add tests for all 8 tools
```

AGENT INTEGRATION CHECK

Ensure agent knows to call tools:

```python
# jagabot/agent/core.py
class JagabotAgent:
    def process_query(self, query):
        # Check if query needs financial tools
        if any(word in query.lower() for word in ['wti', 'minyak', 'oil', 'portfolio']):
            # Call Monte Carlo
            mc_result = self.call_tool('monte_carlo', {
                'price': 52.80,
                'vix': 58,
                'target': 45
            })
            
            # Call CV if needed
            if 'pattern' in query or 'trend' in query:
                cv_result = self.call_tool('financial_cv', {
                    'changes': market_data['historical_changes']['WTI']
                })
            
            # Generate visualization
            chart = self.call_tool('visualize', {
                'prices': mc_result['all_prices'],
                'probability': mc_result['probability']
            })
```

SUCCESS CRITERIA

After fixes, all these should work:

1. ✅ financial_cv runs without parameter errors
2. ✅ visualize generates base64 PNG from Monte Carlo data
3. ✅ All 8 tools pass unit tests
4. ✅ Agent automatically calls tools for financial queries
5. ✅ No manual calculations needed (agent uses tools)

OUTPUT FILES TO MODIFY

1. jagabot/agent/tools/financial_cv.py - Fix parameter handling
2. jagabot/agent/tools/visualization.py - Fix data format
3. jagabot/agent/tools/__init__.py - Verify registrations
4. jagabot/agent/core.py - Ensure tool calling logic
5. tests/test_financial_tools.py - Create test suite
6. requirements.txt - Add matplotlib if missing

TEST AFTER FIXES

Run this query:

```
"Saya ada portfolio minyak mentah dengan modal USD 2.5M, leveraj 3:1. 
Harga WTI sekarang USD 52.80, VIX 58. Kira probability jatuh bawah USD 45 
dan tunjuk visualization."
```

Expected:

· Monte Carlo runs (23-25% probability)
· CV calculates pattern (TIDAK STABIL)
· Chart generates and displays
· All tools called automatically

```

---

This SCOPE prompt gives Copilot everything needed to:
1. **Debug the 2 broken tools** (CV and visualization)
2. **Test the 6 untested tools**
3. **Fix registration issues**
4. **Create test suite**
5. **Verify agent integration**
