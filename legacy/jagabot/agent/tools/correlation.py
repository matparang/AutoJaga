"""Correlation analysis tool — pairwise, matrix, and rolling correlation."""

import json
from typing import Any

import numpy as np

from jagabot.agent.tools.base import Tool


def pairwise_correlation(
    series_a: list[float],
    series_b: list[float],
    name_a: str = "A",
    name_b: str = "B",
) -> dict:
    """Pearson correlation between two return series.

    Args:
        series_a: First return series.
        series_b: Second return series (same length).
        name_a: Label for first series.
        name_b: Label for second series.

    Returns:
        dict with correlation, strength, direction, n_observations.
    """
    if len(series_a) != len(series_b) or len(series_a) < 3:
        return {"error": "Series must have equal length >= 3"}
    a, b = np.array(series_a), np.array(series_b)
    corr = float(np.corrcoef(a, b)[0, 1])
    abs_corr = abs(corr)
    if abs_corr >= 0.8:
        strength = "very_strong"
    elif abs_corr >= 0.6:
        strength = "strong"
    elif abs_corr >= 0.4:
        strength = "moderate"
    elif abs_corr >= 0.2:
        strength = "weak"
    else:
        strength = "negligible"
    return {
        "pair": f"{name_a}/{name_b}",
        "correlation": round(corr, 4),
        "strength": strength,
        "direction": "positive" if corr > 0 else "negative" if corr < 0 else "none",
        "r_squared": round(corr ** 2, 4),
        "n_observations": len(series_a),
    }


def correlation_matrix(
    series_dict: dict[str, list[float]],
) -> dict:
    """Correlation matrix for multiple asset return series.

    Args:
        series_dict: Dict of {asset_name: [returns...]}.

    Returns:
        dict with matrix (nested dict), assets list, highest/lowest pairs.
    """
    names = list(series_dict.keys())
    if len(names) < 2:
        return {"error": "Need at least 2 series"}
    min_len = min(len(v) for v in series_dict.values())
    if min_len < 3:
        return {"error": "Each series must have >= 3 observations"}

    data = np.array([series_dict[n][:min_len] for n in names])
    corr_mat = np.corrcoef(data)

    matrix = {}
    pairs = []
    for i, ni in enumerate(names):
        matrix[ni] = {}
        for j, nj in enumerate(names):
            val = round(float(corr_mat[i, j]), 4)
            matrix[ni][nj] = val
            if i < j:
                pairs.append({"pair": f"{ni}/{nj}", "correlation": val})

    pairs.sort(key=lambda p: p["correlation"])
    return {
        "matrix": matrix,
        "assets": names,
        "n_observations": min_len,
        "highest_correlation": pairs[-1] if pairs else None,
        "lowest_correlation": pairs[0] if pairs else None,
        "all_pairs": pairs,
    }


def rolling_correlation(
    series_a: list[float],
    series_b: list[float],
    window: int = 20,
    name_a: str = "A",
    name_b: str = "B",
) -> dict:
    """Rolling correlation to detect regime changes.

    Args:
        series_a: First return series.
        series_b: Second return series (same length).
        window: Rolling window size.
        name_a: Label for first series.
        name_b: Label for second series.

    Returns:
        dict with rolling_values, avg, max, min, trend.
    """
    if len(series_a) != len(series_b):
        return {"error": "Series must have equal length"}
    n = len(series_a)
    if n < window + 2:
        return {"error": f"Need at least {window + 2} observations for window={window}"}

    a, b = np.array(series_a), np.array(series_b)
    rolling = []
    for i in range(n - window + 1):
        wa = a[i:i + window]
        wb = b[i:i + window]
        c = float(np.corrcoef(wa, wb)[0, 1])
        rolling.append(round(c, 4))

    avg = float(np.mean(rolling))
    first_half = rolling[:len(rolling) // 2]
    second_half = rolling[len(rolling) // 2:]
    avg_first = float(np.mean(first_half)) if first_half else avg
    avg_second = float(np.mean(second_half)) if second_half else avg
    if avg_second - avg_first > 0.1:
        trend = "increasing"
    elif avg_first - avg_second > 0.1:
        trend = "decreasing"
    else:
        trend = "stable"

    return {
        "pair": f"{name_a}/{name_b}",
        "window": window,
        "rolling_values": rolling,
        "average": round(avg, 4),
        "max": round(float(max(rolling)), 4),
        "min": round(float(min(rolling)), 4),
        "current": rolling[-1],
        "trend": trend,
        "n_windows": len(rolling),
    }


class CorrelationTool(Tool):
    """Multi-asset correlation analysis tool."""

    name = "correlation"
    description = (
        "Correlation analysis — measure how assets move together. "
        "CALL THIS TOOL when asked about diversification, portfolio correlation, "
        "or whether assets are related.\n\n"
        "Methods:\n"
        "- pairwise_correlation: Pearson correlation between 2 series → strength + direction\n"
        "- correlation_matrix: Full NxN matrix for multiple assets → identifies highest/lowest pairs\n"
        "- rolling_correlation: Time-varying correlation → detects regime changes in relationships\n\n"
        "Chain: Use with statistical_engine for deeper analysis. "
        "Feed correlation info into pareto_optimizer for portfolio allocation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["pairwise_correlation", "correlation_matrix", "rolling_correlation"],
                "description": (
                    "pairwise_correlation: needs {series_a: [...], series_b: [...], name_a?, name_b?}. "
                    "correlation_matrix: needs {series_dict: {asset: [returns]}}. "
                    "rolling_correlation: needs {series_a: [...], series_b: [...], window?, name_a?, name_b?}."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Keyword arguments. Examples:\n"
                    "pairwise_correlation: {\"series_a\": [0.01, -0.02, 0.03], \"series_b\": [0.02, -0.01, 0.01], "
                    "\"name_a\": \"AAPL\", \"name_b\": \"MSFT\"}\n"
                    "correlation_matrix: {\"series_dict\": {\"AAPL\": [0.01, -0.02], \"MSFT\": [0.02, -0.01], "
                    "\"GOOGL\": [0.005, -0.015]}}\n"
                    "rolling_correlation: {\"series_a\": [...50 values...], \"series_b\": [...50 values...], \"window\": 20}"
                ),
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "pairwise_correlation": pairwise_correlation,
        "correlation_matrix": correlation_matrix,
        "rolling_correlation": rolling_correlation,
    }

    async def execute(self, **kwargs: Any) -> str:
        method = kwargs.get("method", "")
        params = kwargs.get("params", {})
        fn = self._DISPATCH.get(method)
        if fn is None:
            return json.dumps({"error": f"Unknown method: {method}"})
        try:
            result = fn(**params)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})
