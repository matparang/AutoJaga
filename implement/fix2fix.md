📋 SCOPE PROMPT: Fix Jagabot Query Parsing & Tool Coverage

```markdown
# SCOPE: Fix Jagabot Query Parsing and Ensure All 13 Tools Execute

## SITUATION
Jagabot v2.5 runs but has critical issues:

✅ **WORKING (7 tools):**
- monte_carlo (price parsing fixed: 52.80 ✓)
- var (working)
- decision_engine (3 perspectives working)

❌ **FAILING (6 tools):**
- financial_cv → "No data" (changes array not reaching tool)
- cvar → missing
- stress_test → missing (3 scenarios not executed)
- correlation → missing (USD Index 110.5 not used)
- recovery_time → missing
- portfolio_analyzer → missing (equity not calculated)

⚠️ **PARSING ISSUES:**
- Target price: Query says "TARGET: 80" but agent uses 44.88
- Only 7/13 workers spawned (54% coverage)

## ROOT CAUSES IDENTIFIED

### 1. Target Price Parsing Error
```python
# QUERY: "TARGET: 80"
# CURRENT OUTPUT: target_price = 44.88 (WRONG!)
# EXPECTED: target_price = 80.00

# Agent is applying some transformation instead of direct extraction
```

2. Financial CV Data Not Reaching Tool

```python
# QUERY: "CHANGES: [4.2, 5.1, 6.3, 6.8, 6.5, 7.2]"
# OUTPUT: financial_cv → "No data"

# Changes array is being lost in pipeline
```

3. 6 Tools Never Spawned

Only 7/13 workers executed. Missing:

· cvar (depends on var)
· stress_test (needs target prices [75,70,65])
· correlation (needs USD Index 110.5)
· recovery_time (needs equity)
· portfolio_analyzer (needs position data)
· financial_cv (data reaching but failing)

OBJECTIVE

Fix ALL issues to achieve:

1. ✅ Correct target price parsing (80, not 44.88)
2. ✅ Financial CV receives and processes changes array
3. ✅ ALL 13 tools execute successfully
4. ✅ No "No data" errors
5. ✅ All metrics from query used (VIX=35, USD=110.5, Stress=[75,70,65])

REQUIRED FIXES

FIX 1: Planner Query Parsing (jagabot/swarm/planner.py)

```python
# CURRENT (WRONG):
def extract_target_price(query):
    # Some transformation happening
    return transformed_value  # Returns 44.88

# CORRECT:
def extract_target_price(query):
    """Extract target price directly from query"""
    import re
    match = re.search(r'TARGET:\s*(\d+(?:\.\d+)?)', query)
    if match:
        return float(match.group(1))  # Returns 80.00
    return None

# Also extract:
# - CHANGES: [4.2, 5.1, ...] → list of floats
# - STRESS: [75,70,65] → list of prices
# - USD Index: 110.5 → float
```

FIX 2: Financial CV Data Pipeline (jagabot/workers/financial_cv.py)

```python
# CURRENT: Changes array lost
def run(self):
    task = self.get_task()
    # task missing 'changes' key

# FIX: Ensure changes passed through
def run(self):
    task = self.get_task()
    changes = task.get('params', {}).get('changes', [])
    if not changes:
        # Try to extract from original query
        changes = self.extract_changes_from_query(task.get('original_query', ''))
    
    result = calculate_cv(changes)
    return result

def extract_changes_from_query(self, query):
    """Extract [4.2, 5.1, ...] from query string"""
    import re
    match = re.search(r'CHANGES:\s*\[(.*?)\]', query)
    if match:
        return [float(x.strip()) for x in match.group(1).split(',')]
    return []
```

FIX 3: Ensure All 13 Workers Spawned

```python
# jagabot/swarm/planner.py - TASK GENERATION

def plan_tasks(query):
    """Generate ALL 13 tasks from query"""
    tasks = []
    
    # 1. Portfolio Analyzer (equity, margin)
    tasks.append({
        'type': 'portfolio_analyzer',
        'params': extract_portfolio_params(query)
    })
    
    # 2. Financial CV
    tasks.append({
        'type': 'financial_cv',
        'params': {'changes': extract_changes(query)}
    })
    
    # 3. Monte Carlo
    tasks.append({
        'type': 'monte_carlo',
        'params': {
            'price': extract_current_price(query),
            'vix': extract_vix(query),
            'target': extract_target_price(query)
        }
    })
    
    # 4. VaR
    tasks.append({
        'type': 'var',
        'params': {
            'price': extract_current_price(query),
            'vix': extract_vix(query),
            'exposure': calculate_exposure(query)
        }
    })
    
    # 5. CVaR (depends on VaR)
    tasks.append({
        'type': 'cvar',
        'depends_on': ['var'],
        'params': {}  # Will use var results
    })
    
    # 6-8. Stress Tests (3 scenarios)
    stress_prices = extract_stress_prices(query)  # [75,70,65]
    for price in stress_prices:
        tasks.append({
            'type': 'stress_test',
            'params': {'target_price': price}
        })
    
    # 9. Correlation
    tasks.append({
        'type': 'correlation',
        'params': {'usd_index': extract_usd_index(query)}
    })
    
    # 10. Recovery Time
    tasks.append({
        'type': 'recovery_time',
        'depends_on': ['portfolio_analyzer'],
        'params': {}
    })
    
    # 11-13. Decision Engine (3 perspectives)
    tasks.append({'type': 'decision_engine_bull', 'depends_on': ['monte_carlo']})
    tasks.append({'type': 'decision_engine_bear', 'depends_on': ['var', 'cvar']})
    tasks.append({'type': 'decision_engine_buffet', 'depends_on': ['portfolio_analyzer']})
    
    return tasks  # 13 tasks total
```

FIX 4: Update System Prompt for Planner

```python
# SKILL.md - Add parsing rules

## QUERY PARSING RULES

When extracting numbers from queries:

1. **Target Price**: Direct extraction, NO transformation
   - Query: "TARGET: 80" → target = 80.00
   - NOT: 52.80 × 0.85 = 44.88

2. **Changes Array**: Pass through exactly
   - Query: "CHANGES: [4.2, 5.1, 6.3, 6.8, 6.5, 7.2]"
   → changes = [4.2, 5.1, 6.3, 6.8, 6.5, 7.2]

3. **Stress Scenarios**: Create separate task for EACH price
   - Query: "STRESS: [75,70,65]" → 3 tasks: stress@75, stress@70, stress@65

4. **USD Index**: Store for correlation
   - Query: "USD Index: 110.5" → usd_index = 110.5

5. **VIX**: Use directly in decimal form
   - Query: "VIX: 35" → annual_vol = 0.35 (NOT 35.0)
```

FIX 5: Add Missing Tools to Registry

```python
# jagabot/swarm/__init__.py - Ensure ALL tools registered

REGISTERED_TOOLS = [
    'portfolio_analyzer',  # New
    'financial_cv',
    'monte_carlo',
    'var',
    'cvar',                # New
    'stress_test',         # New (will spawn 3 instances)
    'correlation',         # New
    'recovery_time',       # New
    'decision_engine_bull',
    'decision_engine_bear',
    'decision_engine_buffet',
    # ... total 13
]
```

TESTING REQUIREMENTS

Test Case 1: Target Price Parsing

```python
query = "TARGET: 80"
target = extract_target_price(query)
assert target == 80.00  # NOT 44.88
```

Test Case 2: Changes Extraction

```python
query = "CHANGES: [4.2, 5.1, 6.3, 6.8, 6.5, 7.2]"
changes = extract_changes(query)
assert changes == [4.2, 5.1, 6.3, 6.8, 6.5, 7.2]
assert len(changes) == 6
```

Test Case 3: Stress Scenarios

```python
query = "STRESS: [75,70,65]"
stress_prices = extract_stress_prices(query)
assert stress_prices == [75, 70, 65]
assert len(stress_prices) == 3
```

Test Case 4: Full Pipeline

```python
# Run with test query
result = jagabot.swarm.analyze(test_query)

# Verify ALL 13 tools executed
assert len(result.tasks) == 13
assert result.tasks['financial_cv'].success
assert result.tasks['cvar'].success
assert len(result.tasks['stress_test']) == 3  # Three scenarios
assert result.tasks['correlation'].success
assert result.tasks['recovery_time'].success
```

VERIFICATION WITH COLAB

After fixes, run against Google Colab ground truth:

Metric Expected Jagabot Error
Target Price 80.00 80.00 0%
CV ~0.12 ~0.12 <1%
Stress @75 (calculate) (match) <1%
Stress @70 (calculate) (match) <1%
Stress @65 (calculate) (match) <1%
VaR 95% ~$187,000 ~$187,000 <1%
CVaR ~$210,000 ~$210,000 <1%

FILES TO MODIFY

1. jagabot/swarm/planner.py - Query parsing logic
2. jagabot/workers/financial_cv.py - Changes extraction
3. jagabot/workers/stress_test.py - New worker
4. jagabot/workers/cvar.py - New worker
5. jagabot/workers/correlation.py - New worker
6. jagabot/workers/recovery_time.py - New worker
7. jagabot/workers/portfolio_analyzer.py - New worker
8. jagabot/swarm/__init__.py - Tool registry
9. SKILL.md - Update parsing rules
10. tests/test_parsing.py - New tests

SUCCESS CRITERIA

After fixes:

✅ Target price = 80.00 (NOT 44.88)
✅ Financial CV returns CV value (not "No data")
✅ ALL 13 tools execute (not just 7)
✅ Stress test runs for 3 scenarios
✅ Correlation uses USD Index 110.5
✅ Recovery time calculated from equity
✅ VaR and CVaR both present
✅ 3 decision perspectives with correct confidences
✅ No "No data" errors in output
✅ All 13 tasks show in swarm status

TIMELINE

Task Est. Time
Fix planner parsing 2 hours
Fix financial_cv data pipeline 1 hour
Add missing workers (5 new) 5 hours
Update tool registry 1 hour
Add tests (20 new) 3 hours
Verify with Colab 1 hour
TOTAL 13 hours

```

---

This SCOPE prompt gives Copilot everything needed to:
1. **Fix target price parsing** (80, not 44.88)
2. **Fix financial_cv "No data" error**
3. **Add all 6 missing workers**
4. **Ensure ALL 13 tools execute**
5. **Test against ground truth**

**Ready to fix Jagabot's query parsing!** 🎯
