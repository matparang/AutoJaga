# Jagabot — The Guardian 🛡️

A financial analysis agent built on the jagabot framework with a 4-subagent sequential pipeline.

## Architecture

```
USER QUERY
    ↓
🛡️ Jagabot Orchestrator
    ├── MessageBus (async I/O)
    ├── MemoryStore (MEMORY.md + HISTORY.md)
    └── 4-step sequential pipeline:
        ↓
    STEP 1: 📡 WebSearch Subagent
        └── Fetches market news via Brave Search API
        ↓
    STEP 2: 🤝 Support Subagent
        ├── CV analysis (FinancialEngine)
        └── Warning detection (EarlyWarningEngine)
        ↓
    STEP 3: 💰 Billing Subagent
        ├── Monte Carlo GBM simulation
        ├── Equity + margin calculation
        └── Statistical confidence intervals
        ↓
    STEP 4: 🧠 Supervisor Subagent
        ├── Bayesian belief updates
        ├── Strategy ranking (Pareto)
        └── Final report generation
```

## 8 Engine Tools

All tools are **stateless pure functions** (stdlib-only, no numpy/pandas):

| Tool | Name | Methods |
|------|------|---------|
| FinancialTool | `financial_engine` | calculate_cv, calculate_cv_ratios, calculate_equity, calculate_leveraged_equity, check_margin_call, monte_carlo_gbm |
| DynamicsTool | `dynamics_oracle` | simulate, forecast_convergence |
| StatisticalTool | `statistical_engine` | confidence_interval, hypothesis_test, distribution_analysis |
| EarlyWarningTool | `early_warning` | detect_warning_signals, classify_risk_level |
| BayesianTool | `bayesian_reasoner` | update_belief, sequential_update, bayesian_network_inference |
| CounterfactualTool | `counterfactual_sim` | simulate_counterfactual, compare_scenarios |
| SensitivityTool | `sensitivity_analyzer` | analyze_sensitivity, tornado_analysis |
| ParetoTool | `pareto_optimizer` | find_pareto_optimal, rank_strategies, optimize_portfolio_allocation |

## Usage

```python
from jagabot.guardian import Jagabot

jaga = Jagabot(workspace="~/.jagabot/workspace", brave_api_key="your-key")

result = await jaga.handle_query(
    user_query="Analyze WTI oil price risk for next 30 days",
    portfolio={
        "capital": 100000,
        "positions": [
            {"symbol": "WTI", "quantity": 500, "current_price": 70.0, "entry_price": 65.0}
        ],
        "cash": 20000,
    },
    market_data={
        "historical_changes": {"WTI": [0.7, 2.4, 4.2, 6.7, 8.3, 7.4]},
        "current": {"WTI": 70.0, "volatility": 0.35, "drawdown": 0.08},
        "monte_carlo": {"threshold": 60.0, "n_sims": 10000, "days": 30},
    },
)

print(result["report"])
```

## Running Tests

```bash
pytest tests/jagabot/ -v
```
