---
name: financial
description: Financial crisis analysis protocol — 13-step tool-calling workflow
metadata: {"jagabot":{"emoji":"📊","always":false}}
---

# Financial Analysis Protocol

You have 32 specialised financial analysis tools. **ALWAYS use these tools — NEVER calculate manually.**

> **UI Available:** Run `streamlit run jagabot/ui/streamlit_app.py` for the Knowledge Graph Explorer (Neo4j + vis.js).
> **Auto-Trigger:** Use `skill_trigger` tool to auto-detect the best workflow for a query. Use `review` tool for two-stage quality gating.

## Tool Calling Order (15-Step Protocol)

When a user asks about stocks, risk, crisis, margin calls, portfolios, or financial analysis:

### Step 1: CV Analysis (`financial_cv`)
Calculate Coefficient of Variation to assess volatility regime.
```
→ call financial_cv(method="calculate_cv", params={"mean": price_mean, "stddev": price_stddev})
→ call financial_cv(method="calculate_cv_ratios", params={"cv_values": {"ASSET": cv}})
```

### Step 2: Equity Position (`financial_cv`)
```
→ call financial_cv(method="calculate_equity", params={"assets": total_assets, "liabilities": total_liabilities})
→ call financial_cv(method="check_margin_call", params={"equity": equity, "margin_requirement": required})
```

### Step 3: Early Warning (`early_warning`)
Feed CV + equity into warning signals.
```
→ call early_warning(method="detect_warning_signals", params={"cv": cv_value, "equity_ratio": ratio, "trend": "declining"})
→ call early_warning(method="classify_risk_level", params={"signals": [list_from_step_3]})
```

### Step 4: Monte Carlo Simulation (`monte_carlo`)
Price probability with VIX-based volatility.
```
→ call monte_carlo(current_price=150, target_price=120, vix=58)
```

### Step 5: System Dynamics (`dynamics_oracle`)
Model crisis momentum.
```
→ call dynamics_oracle(method="simulate", params={"initial_energy": 100, "decay_rate": 0.05, "feedback_strength": 0.02, "steps": 50})
```

### Step 6: Statistical Validation (`statistical_engine`)
```
→ call statistical_engine(method="confidence_interval", params={"data": price_history, "confidence": 0.95})
```

### Step 7: Bayesian Update (`bayesian_reasoner`)
Update crisis probability with evidence.
```
→ call bayesian_reasoner(method="update_belief", params={"prior": base_probability, "likelihood": evidence_strength, "evidence_probability": p_evidence})
```

### Step 8: VaR & CVaR (`var`, `cvar`)
Quantify downside risk at specified confidence levels.
```
→ call var(method="parametric_var", params={"portfolio_value": 100000, "mean_return": 0.001, "std_return": 0.02, "confidence": 0.95, "horizon_days": 10})
→ call cvar(method="calculate_cvar", params={"portfolio_value": 100000, "returns": [...], "confidence": 0.95})
```

### Step 9: Stress Test & Correlation (`stress_test`, `correlation`)
```
→ call stress_test(method="historical_stress", params={"portfolio_value": 100000, "crisis": "gfc_2008"})
→ call correlation(method="pairwise_correlation", params={"series_a": [...], "series_b": [...], "labels": ["A", "B"]})
```

### Step 10: Recovery Time (`recovery_time`)
```
→ call recovery_time(method="estimate_recovery", params={"current_value": 70000, "target_value": 100000, "monthly_return": 0.02})
```

### Step 11: Decision Engine (`decision_engine`)
Run Bull/Bear/Buffet perspectives and collapse.
```
→ call decision_engine(method="bull_perspective", params={...})
→ call decision_engine(method="bear_perspective", params={...})
→ call decision_engine(method="buffet_perspective", params={...})
→ call decision_engine(method="collapse_perspectives", params={"bull": ..., "bear": ..., "buffet": ...})
→ call decision_engine(method="decision_dashboard", params={"bull": ..., "bear": ..., "buffet": ..., "collapsed": ...})
```

### Step 12: Education (`education`)
Explain concepts and results in plain language.
```
→ call education(method="explain_concept", params={"concept": "var", "locale": "en"})
→ call education(method="explain_result", params={"tool_name": "monte_carlo", "result": {...}})
→ call education(method="get_glossary", params={"locale": "ms"})
```

### Step 13: Accountability & Counterfactual + Sensitivity + Optimise + Visualise (`accountability`, `counterfactual_sim`, `sensitivity_analyzer`, `pareto_optimizer`, `visualization`)
```
→ call accountability(method="generate_questions", params={"analysis_results": {...}})
→ call accountability(method="detect_red_flags", params={"fund_manager_claims": [...]})
→ call accountability(method="generate_report_card", params={"decisions": [...]})
→ call counterfactual_sim(method="compare_scenarios", params={...scenarios...})
→ call sensitivity_analyzer(method="tornado_analysis", params={...param_ranges...})
→ call pareto_optimizer(method="rank_strategies", params={...strategies...})
→ call visualization(mode="markdown", prices=[...from_MC...], current_price=X, target_price=Y, probability=Z)
```

### Step 14: Portfolio Analysis (`portfolio_analyzer`)
```
→ call portfolio_analyzer(method="analyze", params={"capital": 500000, "leverage": 2, "positions": [{"symbol": "WTI", "entry_price": 85, "current_price": 72.5, "quantity": 7058, "weight": 0.6}], "cash": 0})
→ call portfolio_analyzer(method="stress_test", params={"capital": 500000, "leverage": 2, "positions": [...], "target_prices": {"WTI": 60}})
→ call portfolio_analyzer(method="probability", params={"current_price": 72.5, "target_price": 60, "daily_returns": [...], "days": 30})
```

### Step 15: Research & Content (`researcher`, `copywriter`, `self_improver`)
```
→ call researcher(method="scan_trends", params={"data_points": [100, 102, 98, ...]})
→ call researcher(method="detect_anomalies", params={"values": [...], "z_threshold": 2.0})
→ call copywriter(method="draft_alert", params={"risk_level": "high", "tool_name": "var", "key_metric": "VaR", "value": 5000})
→ call copywriter(method="draft_report_summary", params={"analysis_results": {...}, "query": "..."})
→ call self_improver(method="analyze_mistakes", params={"predictions": [{"predicted": X, "actual": Y}, ...]})
→ call self_improver(method="suggest_improvements", params={"analysis_results": {...}})
```

## Critical Rules

1. **NEVER skip tools** — every financial query should use at least steps 1, 3, 4, 8, 11, and 13
2. **NEVER calculate CV, equity, VaR, or probability manually** — the tools do it correctly
3. **Pass tool outputs forward** — Monte Carlo prices → VaR, CV → Early Warning, all → Decision Engine
4. **Use locale** — if the user writes in Malay/Indonesian, pass locale="ms" or locale="id"
5. **Visualization is ALWAYS the last step** — present results to the user visually
6. **For simple questions** (e.g. "what is CV?"), use `education` tool
7. **For fund manager review**, use `accountability` tool
8. **For trend analysis**, use `researcher` tool; **for alerts**, use `copywriter` tool
9. **For portfolio P/L, equity, margin**, use `portfolio_analyzer` tool — it cross-checks automatically

## Trigger Phrases

Call financial tools when the user mentions ANY of:
- stock, saham, portfolio, pelaburan, risiko, risk
- margin call, equity, leverage, hutang
- volatility, VIX, turun naik
- crisis, krisis, warning, amaran
- Monte Carlo, simulation, simulasi
- probability, kebarangkalian
- "what if", "bagaimana kalau"
- forecast, ramalan, prediction
- VaR, CVaR, stress test, correlation, recovery
- decision, buy, sell, hold, keputusan
- explain, glossary, education, penerangan
- accountability, red flag, report card, pengurus dana
- trend, anomaly, scan, pattern, regime
- alert, report summary, draft, improve, calibrate
- portfolio analyzer, stress test, units, P/L, cross-check

## Equity Definition — Critical Rule (v2.7)

**ALWAYS use this formula:**
```
equity = capital + total_pnl
```

Where:
- `capital` = initial investment (e.g. 1,000,000)
- `total_pnl` = sum of all position P&L = Σ(qty × (current_price − entry_price))

**NEVER use these formulas:**
- `equity = capital + position_value + cash` ❌ (double-counts capital for leveraged)
- `equity = exposure + cash` ❌ (ignores loan)
- `equity = portfolio_value` ❌ (confuses with NAV)

**Cross-check (must agree within $1):**
```
loan = capital × (leverage − 1)
deployed = Σ(qty × entry_price) + cash
undeployed = max(0, exposure − deployed)
equity_alt = position_value + cash + undeployed − loan
```

**VaR/CVaR/Stress portfolio_value = exposure (capital × leverage), NOT just capital.**

## Query Parsing Rules (v2.6)

When the user provides structured data in queries, **extract and pass through exactly**:

| Pattern | Example | Extracted As |
|---------|---------|-------------|
| `TARGET: 80` | Target/threshold/sasaran + number | `target = 80.0` |
| `CHANGES: [4.2, 5.1, ...]` | Changes + JSON array | `changes = [4.2, 5.1, ...]` |
| `STRESS: [75,70,65]` | Stress prices/scenarios + array | `stress_prices = [75, 70, 65]` |
| `USD Index: 110.5` | USD Index/DXY + number | `usd_index = 110.5` |
| `capital: 500000` | Capital/modal + number | `capital = 500000` |
| `leverage: 2` | Leverage/leveraj + number | `leverage = 2.0` |
| `VIX: 35` | VIX + number | `vix = 35.0` |
| `USD 78.50` | RM/USD/$ + number | `price = 78.50` |

**Rules:**
1. **Target price**: Direct extraction, NO transformation — `TARGET: 80` → 80.00, NOT `price × 0.85`
2. **Changes array**: Pass through exactly — `CHANGES: [4.2, 5.1]` → `[4.2, 5.1]`
3. **Stress scenarios**: Create separate stress test per price — `STRESS: [75,70,65]` → 3 tasks
4. **USD Index**: Store for correlation analysis
5. **Capital/leverage**: Use for portfolio_analyzer and VaR portfolio_value

## Strict Math Protocol (v2.4)

🚫 **NO EXCEPTIONS — follow every step for any financial calculation:**

1. **IDENTIFY VARIABLES**: List all inputs (capital, prices, weights, leverage) before calling any tool.
2. **UNIT DERIVATION**: You MUST calculate the number of units owned before calculating P/L. Use `portfolio_analyzer(method="analyze")` — it derives units from weight × exposure ÷ entry_price.
3. **SANDBOX MANDATE**: You are PROHIBITED from stating a final equity, P/L, or margin figure without first receiving it from a tool call. Never write "Equity = $X" without tool output proof.
4. **CROSS-CHECK**: The `portfolio_analyzer` automatically verifies equity = capital + total_pnl + cash. If `cross_check.passed` is False, call the tool again with corrected inputs.
5. **OUTPUT TEMPLATE**: Always present portfolio results using this structure:
   - Position table (symbol, units, entry, current, P/L, P/L%)
   - Total equity with cross-check confirmation
   - Margin status with required vs actual equity
   - Stress test scenarios (if applicable)

## Volatility Unit Rules (v2.5)

⚠️ **CRITICAL — wrong units cause 2.2× errors in ALL risk metrics:**

| Parameter | Expected Unit | Example | Tool |
|-----------|---------------|---------|------|
| `vix` | Percentage index | `vix=22.25` (means 22.25%) | `monte_carlo` |
| `vol` | Decimal (0-1) | `vol=0.2225` | `monte_carlo_gbm` |
| `std_return` | Decimal daily σ | `std_return=0.025` | `var` (parametric) |
| `daily_returns` | Decimal list | `[-0.02, 0.01, ...]` | `portfolio_analyzer` probability |
| CV ratio | Decimal | `cv=0.2225` (= 22.25%) | `financial_cv` output |

**Conversion rules:**
- **CV → VIX**: multiply by 100 (`cv=0.2225` → `vix=22.25`)
- **VIX → decimal vol**: divide by 100 (`vix=22.25` → `vol=0.2225`)
- **Percentage returns → decimal**: divide by 100 (`-2.5%` → `-0.025`)

**Defensive guards are active** — tools auto-correct wrong units, but you MUST still pass correct units to avoid ambiguity.

## Self-Correction Rules (v2.2)

1. **If a tool execution fails**, read the error message carefully and retry with corrected parameters.
2. **Never guess numbers** — always use a calculation tool (Monte Carlo, Stats, Bayesian) to produce them.
3. **Use vectorised numpy** for all Monte Carlo simulations — the `monte_carlo` tool already does this.
4. **If 3 consecutive retries fail**, report the failure honestly to the user with the error context.
5. **Sandbox policy**: code execution via `exec` tool runs inside Docker isolation (no network, 128MB RAM, 0.5 CPU).
6. **Pipeline resilience**: if any subagent stage fails, downstream stages receive degraded fallback data and continue.


## Source Hierarchy & Verification (Adversarial Guardrail Rule 1)

When using ANY data source for financial analysis:
1. **Source Hierarchy**: Primary sources > Verified APIs > Web scraping > User claims
2. **Minimum Verification**: Two independent sources required for financial claims
3. **Quality Disclosure**: Must flag and disclose when using unverified/scraped data
4. **Timestamp Check**: News >24h old must be labeled "stale"
5. **Confidence Capping**: 
   - Verified API + 3+ sources → max 90% confidence
   - Web scraping + 2 sources → max 60% confidence  
   - User claim + 1 source → max 30% confidence
   - Unverified + multiple failures → max 10% confidence

**Enforcement**: 
- Automatic trigger for all financial recommendations
- Required disclosure: "Source quality: [level], Verification: [X sources]"
- Failure to verify → "HIGH RISK - UNVERIFIED" warning in output

**Integration**:
- Apply BEFORE Step 1 (CV Analysis) of financial protocol
- Apply BEFORE Monte Carlo simulation inputs
- Apply BEFORE Decision Engine perspectives


## Engine Tools (v3.0)

### Memory Fleet (`memory_fleet`)
Long-term structured memory system.
```
→ call memory_fleet(action="store", content="...", source="user")         # Store interaction
→ call memory_fleet(action="retrieve", query="...", k=5)                  # Retrieve relevant memories
→ call memory_fleet(action="consolidate")                                  # Extract lessons → MEMORY.md
→ call memory_fleet(action="stats")                                        # Node counts, ages, tags
→ call memory_fleet(action="optimize", dry_run=true)                       # Prune/merge weak nodes
```

### Knowledge Graph (`knowledge_graph`)
Interactive visualization of memory relationships.
```
→ call knowledge_graph(action="stats")                                     # Node/edge counts, groups
→ call knowledge_graph(action="generate")                                  # Generate vis.js HTML graph
→ call knowledge_graph(action="query", keyword="risk", limit=10)           # Find nodes by keyword
```

### K7 Evaluation (`evaluate_result`)
Output quality scoring and anomaly detection.
```
→ call evaluate_result(action="evaluate", expected={...}, actual={...})    # Score: 0-1, gap, reasons
→ call evaluate_result(action="anomaly", result=X, history=[...])          # Z-score anomaly detection
→ call evaluate_result(action="improve", execution_log=[...])              # Suggest optimizations
→ call evaluate_result(action="roi", plan_tokens=N, score=S, total=T)     # Quality per token
→ call evaluate_result(action="full", expected={...}, actual={...}, ...)   # All-in-one evaluation
```

### K1 Bayesian (`k1_bayesian`)
Probabilistic reasoning with calibration persistence.
```
→ call k1_bayesian(action="update_belief", topic="crisis", evidence={...})     # Prior → posterior
→ call k1_bayesian(action="assess", problem="market crash")                     # Uncertainty + CI
→ call k1_bayesian(action="refine_confidence", raw_confidence=75, perspective="bull")  # Calibrate
→ call k1_bayesian(action="record_outcome", perspective="bull", predicted_prob=0.8, actual=true)
→ call k1_bayesian(action="get_calibration", perspective="bull")                # Brier score
```

### K3 Multi-Perspective (`k3_perspective`)
Calibrated Bull/Bear/Buffet with adaptive weights.
```
→ call k3_perspective(action="get_perspective", ptype="bull", data={...})       # Calibrated confidence
→ call k3_perspective(action="update_accuracy", perspective="bull", predicted_verdict="BUY", actual_outcome="up")
→ call k3_perspective(action="get_weights")                                     # Current weights
→ call k3_perspective(action="recalibrate")                                     # Force recalibration
→ call k3_perspective(action="calibrated_decision", data={probability_below_target: 30, ...})
→ call k3_perspective(action="accuracy_stats")                                  # All perspective metrics
```
