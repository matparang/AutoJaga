"""Support subagent — structures data and detects patterns using CV + EarlyWarning engines."""

from typing import Any

from jagabot.agent.tools.financial_cv import calculate_cv, calculate_cv_ratios
from jagabot.agent.tools.early_warning import detect_warning_signals, classify_risk_level


async def support_agent(
    market_data: dict[str, Any],
    web_results: dict[str, Any],
) -> dict[str, Any]:
    """Structure market data and detect patterns.

    Uses FinancialEngine (CV analysis) and EarlyWarningEngine to produce
    structured analysis from raw market data and web search results.

    Does NOT access memory — only the orchestrator stores results.

    Args:
        market_data: Dict with 'historical_changes' (asset -> list[float]),
                     'current' (metrics dict), and optional other fields.
        web_results: Output from websearch_agent.

    Returns:
        Dict with structured_data, cv_analysis, warnings, and web_context.
    """
    # CV analysis for each asset
    cv_analysis = {}
    historical = market_data.get("historical_changes", {})
    for asset, changes in historical.items():
        if not isinstance(changes, list) or len(changes) < 2:
            cv_analysis[asset] = {"cv": 0.0, "pattern": "insufficient_data"}
            continue
        cv = calculate_cv(changes)
        ratios = calculate_cv_ratios(changes)
        cv_analysis[asset] = {
            "cv": round(cv, 6),
            "pattern": ratios.get("pattern", "unknown"),
            "trend": ratios.get("trend", 0.0),
            "windows": ratios.get("windows", {}),
        }

    # Early warning detection
    current_metrics = market_data.get("current", {})
    warnings = detect_warning_signals(current_metrics)

    # Risk classification
    risk_class = classify_risk_level(warnings.get("signals", []))

    return {
        "structured_data": market_data,
        "cv_analysis": cv_analysis,
        "warnings": warnings,
        "risk_classification": risk_class,
        "web_context": {
            "query": web_results.get("query", ""),
            "result_count": web_results.get("result_count", 0),
            "news_headlines": [
                item.get("title", "") for item in web_results.get("news", [])
            ],
        },
    }
