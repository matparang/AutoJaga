#!/usr/bin/env python3
"""Basic financial analysis example using jagabot tools directly."""

import asyncio
import json
from jagabot.agent.tools import (
    FinancialCVTool, MonteCarloTool, EarlyWarningTool, VaRTool, VisualizationTool,
)


async def main():
    cv_tool = FinancialCVTool()
    cv_result = json.loads(await cv_tool.execute(
        method="calculate_cv", params={"changes": [0.02, -0.01, 0.03, -0.05, 0.01, -0.02, 0.04, -0.03]}
    ))
    cv_val = cv_result if isinstance(cv_result, (int, float)) else cv_result.get("cv", 0)
    print(f"CV = {cv_val:.4f}")

    ew_tool = EarlyWarningTool()
    signals = json.loads(await ew_tool.execute(
        method="detect_warning_signals",
        params={"cv": cv_val, "equity_ratio": 0.25, "trend": "declining"},
    ))
    sig_list = signals.get("signals", signals) if isinstance(signals, dict) else signals
    risk = json.loads(await ew_tool.execute(
        method="classify_risk_level", params={"signals": sig_list},
    ))
    risk_data = risk if isinstance(risk, dict) else {"risk_level": str(risk)}
    print(f"Risk level: {risk_data.get('risk_level', 'unknown')}")

    mc_tool = MonteCarloTool()
    mc_result = json.loads(await mc_tool.execute(
        current_price=4.50, target_price=3.80, vix=28,
    ))
    print(f"P(price ≤ RM3.80) = {mc_result['probability']:.1f}%")

    var_tool = VaRTool()
    var_result = json.loads(await var_tool.execute(
        method="parametric_var",
        params={
            "portfolio_value": 100_000,
            "mean_return": 0.001,
            "std_return": 0.02,
            "confidence": 0.95,
            "holding_period": 10,
        },
    ))
    print(f"10-day 95% VaR = RM{var_result['var_amount']:,.2f}")

    viz_tool = VisualizationTool()
    # Generate sample prices from MC percentiles for visualization
    import numpy as np
    np.random.seed(42)
    sample_prices = list(np.random.normal(mc_result["mean_price"], mc_result["std_price"], 50))
    chart = await viz_tool.execute(
        mode="ascii",
        prices=sample_prices,
        current_price=4.50,
        target_price=3.80,
        probability=mc_result["probability"],
    )
    print("\n" + chart)


if __name__ == "__main__":
    asyncio.run(main())
