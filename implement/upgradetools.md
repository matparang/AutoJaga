✅ SCOPE PROMPT: Fix Jagabot to Call ALL 8 Tools

```markdown
# SCOPE: Fix Jagabot Tool Calling - Ensure ALL 8 Financial Tools Are Used

## SITUATION
Jagabot has 8 financial tools, but testing shows only 3 are being called:
- ✅ Monte Carlo (working)
- ✅ Visualization (working)  
- ✅ Bayesian (partial)

The remaining 5 tools are **NOT being called**:
- ❌ Financial CV (manual observation instead)
- ❌ Statistical (CI from Monte Carlo only)
- ❌ Early Warning (manual data reading)
- ❌ Counterfactual (no scenarios)
- ❌ Sensitivity (no parameter analysis)
- ❌ Pareto (manual EV calculation)

Agent provides excellent manual analysis, but tools exist to AUTOMATE this.

## CURRENT STATE

### What Agent Does NOW (Manual)
```python
# Agent's current approach - GOOD but manual
def analyze_crisis():
    # 1. Monte Carlo (TOOL CALLED ✓)
    prob = monte_carlo(52.80, 58, 45)
    
    # 2. Everything else is MANUAL (✗)
    cv_pattern = "Volatility meningkat + momentum negatif"  # Should use CV tool
    warnings = "Stok↑, USD↑, VIX↑"  # Should use Early Warning tool
    ev = "Exit > Hold"  # Should use Pareto tool
    ci = f"${prob['p5']} - ${prob['p95']}"  # Should use Statistical tool
    scenarios = None  # Should use Counterfactual tool
    sensitivity = None  # Should use Sensitivity tool
```

What Agent SHOULD Do (Using Tools)

```python
# Agent's TARGET approach - ALL tools called
def analyze_crisis():
    # 1. Monte Carlo
    mc = call_tool('monte_carlo', price=52.80, vix=58, target=45)
    
    # 2. Financial CV
    cv = call_tool('financial_cv', changes=wti_changes, asset="WTI")
    
    # 3. Early Warning
    warnings = call_tool('early_warning', 
                         current=market_data['current'],
                         historical=market_data['historical'])
    
    # 4. Statistical (for CI)
    stats = call_tool('confidence_interval', data=mc['prices'])
    
    # 5. Bayesian update
    bayes = call_tool('bayesian_update', 
                      prior=0.29, 
                      likelihood=0.8, 
                      evidence=0.7)
    
    # 6. Counterfactual scenarios
    scenarios = call_tool('counterfactual',
                         base_price=52.80,
                         scenarios=['opec_cut', 'fed_pivot', 'recession'])
    
    # 7. Sensitivity analysis
    sensitivity = call_tool('sensitivity',
                           base_params={'vol':0.58, 'drift':-0.001})
    
    # 8. Pareto optimization
    strategies = call_tool('pareto_optimize',
                          strategies=['exit', 'hedge', 'hold', 'add_margin'])
    
    # 9. Visualization
    viz = call_tool('visualize', data=mc, cv=cv, warnings=warnings)
```

PROBLEM ANALYSIS

Why Tools Aren't Being Called

1. Tool Registration Issues
   · Tools may not be properly registered in registry
   · Agent doesn't know they exist
   · Check jagabot/agent/tools/__init__.py
2. Tool Descriptions Unclear
   · LLM doesn't understand WHEN to call them
   · Need better descriptions in tool registry
3. Prompt Engineering Gap
   · System prompt doesn't instruct agent to use financial tools
   · Agent defaults to manual reasoning
4. Tool Dependencies
   · Some tools need output from others
   · Agent doesn't chain them correctly

OBJECTIVE

Fix Jagabot so ALL 8 tools are called automatically for financial queries, with ZERO manual calculations.

REQUIRED FIXES

FIX 1: Verify Tool Registration

```python
# jagabot/agent/tools/__init__.py
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
    """Register ALL 8 financial tools with clear descriptions"""
    
    registry.register(
        name="financial_cv",
        function=financial_cv,
        description="Calculate Coefficient of Variation and pattern classification for price changes. Use this to detect whether price movement is STABLE, EXPONENTIAL, or UNSTABLE.",
        schema={
            "changes": {"type": "array", "items": {"type": "number"}, 
                       "description": "List of price changes over time", 
                       "required": True},
            "asset_name": {"type": "string", 
                          "description": "Name of asset (e.g., 'WTI')",
                          "required": False}
        }
    )
    
    registry.register(
        name="early_warning",
        function=detect_warnings,
        description="Detect RED/YELLOW/GREEN warning signals from market data. Checks VIX, CV values, USD Index, and inventory levels.",
        schema={
            "current": {"type": "object", 
                       "description": "Current market data (VIX, USD Index, etc.)",
                       "required": True},
            "historical": {"type": "object",
                          "description": "Historical changes for CV calculation",
                          "required": True}
        }
    )
    
    registry.register(
        name="confidence_interval",
        function=confidence_interval,
        description="Calculate statistical confidence intervals for any data array.",
        schema={
            "data": {"type": "array", "items": {"type": "number"},
                    "description": "Array of values to calculate CI for",
                    "required": True},
            "confidence": {"type": "number",
                          "description": "Confidence level (0.95 for 95%)",
                          "default": 0.95}
        }
    )
    
    registry.register(
        name="counterfactual",
        function=simulate_scenario,
        description="Run what-if scenarios to see impact of different events (OPEC cut, Fed pivot, recession, etc.)",
        schema={
            "base_price": {"type": "number",
                          "description": "Current price to base scenarios on",
                          "required": True},
            "scenarios": {"type": "array",
                         "description": "List of scenario names to simulate",
                         "required": True}
        }
    )
    
    registry.register(
        name="sensitivity",
        function=analyze_sensitivity,
        description="Analyze which parameters have most impact on results.",
        schema={
            "base_params": {"type": "object",
                           "description": "Base parameters to analyze",
                           "required": True},
            "variations": {"type": "number",
                          "description": "Percentage to vary parameters by",
                          "default": 0.1}
        }
    )
    
    registry.register(
        name="pareto_optimize",
        function=optimize_strategies,
        description="Find optimal strategies using Pareto frontier (risk vs return).",
        schema={
            "strategies": {"type": "array",
                          "description": "List of strategy names to evaluate",
                          "required": True}
        }
    )
    
    # Already registered tools (verify descriptions)
    registry.register(
        name="monte_carlo",
        function=monte_carlo,
        description="Run Monte Carlo simulation for price probability. ALWAYS use this for probability questions.",
        schema={...}
    )
    
    registry.register(
        name="bayesian_update",
        function=bayesian_update,
        description="Update probability using Bayes theorem with new evidence.",
        schema={...}
    )
    
    registry.register(
        name="visualize",
        function=generate_chart,
        description="Generate visualization of analysis results. Call AFTER all other tools.",
        schema={...}
    )
```

FIX 2: Update System Prompt

```python
# jagabot/agent/prompts/financial.py

FINANCIAL_SYSTEM_PROMPT = """
Anda adalah Jagabot, pakar analisis kewangan dengan 8 tools khusus.

WAJIB GUNAKAN TOOLS INI UNTUK SEMUA ANALISIS:

📊 TOOLS YANG TERSEDIA:
1. monte_carlo - Untuk probability dan ramalan harga (WAJIB guna)
2. financial_cv - Untuk pattern detection (CV, stabil/tidak stabil)
3. early_warning - Untuk detect RED/YELLOW/GREEN signals
4. bayesian_update - Untuk update probability dengan evidence baru
5. confidence_interval - Untuk statistical confidence
6. counterfactual - Untuk what-if scenarios
7. sensitivity - Untuk parameter importance analysis
8. pareto_optimize - Untuk banding strategi (EV ranking)
9. visualize - Untuk hasilkan dashboard

📋 PROTOCOL:
1. PERTAMA: panggil monte_carlo untuk probability asas
2. KEDUA: panggil financial_cv untuk pattern harga
3. KETIGA: panggil early_warning untuk signal bahaya
4. KEEMPAT: guna bayesian_update jika ada evidence baru
5. KELIMA: panggil confidence_interval untuk semua angka
6. KEENAM: guna counterfactual untuk scenario analysis
7. KETUJUH: panggil sensitivity untuk parameter penting
8. KELAPAN: guna pareto_optimize untuk banding strategi
9. AKHIR: panggil visualize untuk dashboard

JANGAN GUNA MANUAL CALCULATION. SETIAP ANALISIS MESTI GUNA TOOLS.
"""
```

FIX 3: Add Tool Chaining Logic

```python
# jagabot/agent/core.py - Modified agent loop

class JagabotAgent:
    async def process_financial_query(self, query, market_data):
        """Process financial query using ALL tools in sequence"""
        
        # Step 1: Monte Carlo (always first)
        mc_result = await self.call_tool('monte_carlo', {
            'price': market_data['current']['WTI'],
            'vix': market_data['current']['VIX'],
            'target': 45
        })
        
        # Step 2: Financial CV
        cv_result = await self.call_tool('financial_cv', {
            'changes': market_data['historical_changes']['WTI'],
            'asset_name': 'WTI'
        })
        
        # Step 3: Early Warning
        warning_result = await self.call_tool('early_warning', {
            'current': market_data['current'],
            'historical': market_data['historical_changes']
        })
        
        # Step 4: Bayesian Update (if applicable)
        bayes_result = None
        if 'evidence' in query.lower():
            bayes_result = await self.call_tool('bayesian_update', {
                'prior': mc_result['probability'] / 100,
                'likelihood': 0.8,
                'evidence': 0.7
            })
        
        # Step 5: Confidence Intervals
        ci_result = await self.call_tool('confidence_interval', {
            'data': mc_result.get('prices', []),
            'confidence': 0.95
        })
        
        # Step 6: Counterfactual Scenarios
        scenario_result = await self.call_tool('counterfactual', {
            'base_price': market_data['current']['WTI'],
            'scenarios': ['opec_cut', 'fed_pivot', 'recession', 'recovery']
        })
        
        # Step 7: Sensitivity Analysis
        sensitivity_result = await self.call_tool('sensitivity', {
            'base_params': {
                'volatility': market_data['current']['VIX'] / 100,
                'drift': -0.001,
                'days': 30
            }
        })
        
        # Step 8: Pareto Optimization
        strategies = ['exit_now', 'partial_cut', 'hedge_only', 'add_margin', 'do_nothing']
        pareto_result = await self.call_tool('pareto_optimize', {
            'strategies': strategies
        })
        
        # Step 9: Visualization (with ALL results)
        viz_result = await self.call_tool('visualize', {
            'monte_carlo': mc_result,
            'cv_analysis': cv_result,
            'warnings': warning_result,
            'bayesian': bayes_result,
            'confidence': ci_result,
            'scenarios': scenario_result,
            'sensitivity': sensitivity_result,
            'pareto': pareto_result
        })
        
        # Combine ALL results into final answer
        return self.synthesize_answer(
            mc_result, cv_result, warning_result, bayes_result,
            ci_result, scenario_result, sensitivity_result,
            pareto_result, viz_result
        )
```

FIX 4: Add Test Script

```python
# tests/test_tool_calling.py

def test_all_tools_are_called():
    """Verify that ALL 8 tools are called for financial query"""
    
    query = "Saya ada portfolio minyak. Kira probability jatuh bawah USD 45."
    market_data = {...}  # test data
    
    # Mock tool calls
    called_tools = []
    
    agent = JagabotAgent()
    agent.call_tool = lambda name, _: called_tools.append(name)
    
    agent.process_financial_query(query, market_data)
    
    expected_tools = [
        'monte_carlo',
        'financial_cv', 
        'early_warning',
        'bayesian_update',
        'confidence_interval',
        'counterfactual',
        'sensitivity',
        'pareto_optimize',
        'visualize'
    ]
    
    for tool in expected_tools:
        assert tool in called_tools, f"{tool} was not called!"
    
    print("✅ ALL 8 tools were called correctly")
```

FIX 5: Update Tool Descriptions for LLM

```python
# jagabot/agent/tools/descriptions.py

TOOL_DESCRIPTIONS = {
    'financial_cv': """
    Gunakan tool ini untuk analisis pattern pergerakan harga.
    Ia akan berikan:
    - CV (Coefficient of Variation) - nilai >0.40 bermaksud TIDAK STABIL
    - Pattern classification (STABIL/EKSPONEN/LEMAH)
    - Ratios antara perubahan harga
    
    Contoh bila guna:
    - "Apakah pattern harga WTI?"
    - "Adakah pergerakan harga stabil?"
    - "CV analysis untuk minyak mentah"
    """,
    
    'early_warning': """
    Gunakan tool ini untuk detect early warning signals:
    - VIX >40 → 🔴 RED (panic)
    - CV >0.40 → 🔴 RED (unstable)
    - USD Index >108 → 🟡 YELLOW (pressure on commodities)
    - Inventory increasing → 🟡 YELLOW (supply pressure)
    
    Contoh bila guna:
    - "Adakah tanda-tanda bahaya?"
    - "Early warning signals untuk pasaran?"
    - "Apa kata VIX dan inventory?"
    """,
    
    'confidence_interval': """
    Gunakan tool ini untuk dapatkan statistical confidence:
    - 95% CI untuk semua ramalan
    - Standard error of mean
    - Distribution statistics
    
    Contoh bila guna:
    - "Berapa confidence interval untuk ramalan ini?"
    - "Statistical significance?"
    - "Range yang realistik?"
    """,
    
    'counterfactual': """
    Gunakan tool ini untuk what-if scenarios:
    - OPEC cut (harga naik 15%)
    - Fed pivot (harga naik 8%)
    - China stimulus (harga naik 10%)
    - Recession deepens (harga turun 20%)
    
    Contoh bila guna:
    - "Apa jadi jika OPEC potong pengeluaran?"
    - "Scenario analysis untuk Fed pivot?"
    - "Jika recession berlaku, apa impact?"
    """,
    
    'sensitivity': """
    Gunakan tool ini untuk tahu parameter apa paling penting:
    - Volatility sensitivity
    - Drift sensitivity
    - Target price sensitivity
    
    Contoh bila guna:
    - "Parameter apa paling penting?"
    - "Sensitivity analysis untuk ramalan ini?"
    - "Apa yang paling mempengaruhi hasil?"
    """,
    
    'pareto_optimize': """
    Gunakan tool ini untuk bandingkan strategi:
    - Exit now (EV known, risk low)
    - Partial cut (EV medium, risk medium)
    - Hedge only (EV negative, risk medium)
    - Add margin (EV uncertain, risk high)
    - Do nothing (EV worst, risk extreme)
    
    Contoh bila guna:
    - "Strategi mana paling optimum?"
    - "Bandingkan EV untuk semua pilihan"
    - "Risk vs return analysis"
    """
}
```

SUCCESS CRITERIA

After fixes, run this query:

```
Saya ada portfolio minyak. Harga WTI $52.80, VIX 58. 
Perubahan harga: [0.7, 2.4, 4.2, 6.7, 8.3, 7.4]
Stok meningkat, USD kuat. 
Analisis lengkap dengan semua tools.
```

Expected:

1. ✅ Monte Carlo called → 29% probability
2. ✅ Financial CV called → CV=0.55, "TIDAK STABIL"
3. ✅ Early Warning called → 🔴 RED for VIX, 🟡 YELLOW for USD
4. ✅ Bayesian called → updated probability
5. ✅ Confidence Interval called → CI for all numbers
6. ✅ Counterfactual called → scenario impacts
7. ✅ Sensitivity called → most important parameters
8. ✅ Pareto called → strategy ranking with EV
9. ✅ Visualization called → dashboard with ALL results

OUTPUT FILES TO MODIFY

1. jagabot/agent/tools/__init__.py - Update registrations
2. jagabot/agent/prompts/financial.py - Add system prompt
3. jagabot/agent/core.py - Modify agent loop for tool chaining
4. jagabot/agent/tools/descriptions.py - NEW file with tool descriptions
5. tests/test_tool_calling.py - NEW test file
6. jagabot/agent/tools/registry.py - Verify registration logic

TEST AFTER FIXES

Run the Malay test query and verify:

· ALL 8 tools appear in logs
· NO manual calculations in response
· Dashboard includes data from ALL tools
· Response matches expected numbers

TIMELINE

· Fix 1 (Registration): 1 hour
· Fix 2 (Prompts): 1 hour
· Fix 3 (Tool chaining): 2 hours
· Fix 4 (Tests): 1 hour
· Fix 5 (Descriptions): 1 hour
· Total: ~6 hours

```

---

This SCOPE prompt gives Copilot everything needed to:
1. **Fix tool registration** so agent knows they exist
2. **Update prompts** so agent knows WHEN to call them
3. **Add tool chaining** so tools are called in correct order
4. **Create tests** to verify all 8 tools are used
5. **Add descriptions** so LLM understands each tool's purpose
