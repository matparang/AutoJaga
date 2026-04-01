"""Researcher tool — trend scanning and anomaly detection for financial data."""

import json
import time
import statistics
from typing import Any

from jagabot.agent.tools.base import Tool


def scan_trends(data_points: list[float], window: int = 5) -> dict[str, Any]:
    """Scan a time series for trend direction, momentum, and regime changes.

    Args:
        data_points: Sequential data values (prices, returns, etc.).
        window: Rolling window size for trend calculation.

    Returns:
        Dict with trend direction, strength, momentum, and detected regimes.
    """
    if len(data_points) < 3:
        return {"trend": "insufficient_data", "data_points": len(data_points)}

    # Trend direction
    first_half = statistics.mean(data_points[:len(data_points)//2])
    second_half = statistics.mean(data_points[len(data_points)//2:])
    if second_half > first_half * 1.02:
        direction = "uptrend"
    elif second_half < first_half * 0.98:
        direction = "downtrend"
    else:
        direction = "sideways"

    # Momentum (rate of change)
    changes = [data_points[i] - data_points[i-1] for i in range(1, len(data_points))]
    momentum = statistics.mean(changes) if changes else 0.0
    volatility = statistics.stdev(changes) if len(changes) > 1 else 0.0

    # Simple regime detection: split into windows and classify
    regimes = []
    for i in range(0, len(data_points) - window + 1, max(1, window // 2)):
        segment = data_points[i:i+window]
        seg_mean = statistics.mean(segment)
        seg_std = statistics.stdev(segment) if len(segment) > 1 else 0.0
        cv = seg_std / abs(seg_mean) if seg_mean != 0 else 0.0
        regime = "volatile" if cv > 0.1 else "stable"
        regimes.append({"start_idx": i, "regime": regime, "cv": round(cv, 4)})

    # Trend strength (0-100)
    if volatility == 0:
        strength = 0.0
    else:
        strength = min(100, abs(momentum) / volatility * 50)

    return {
        "direction": direction,
        "strength": round(strength, 1),
        "momentum": round(momentum, 6),
        "volatility": round(volatility, 6),
        "regimes": regimes,
        "data_points": len(data_points),
    }


def detect_anomalies(
    values: list[float],
    z_threshold: float = 2.0,
) -> dict[str, Any]:
    """Detect statistical anomalies in a data series using z-score method.

    Args:
        values: Data points to analyze.
        z_threshold: Z-score threshold for anomaly classification.

    Returns:
        Dict with detected anomalies, statistics, and severity ratings.
    """
    if len(values) < 3:
        return {"anomalies": [], "total": 0, "note": "insufficient data"}

    mean = statistics.mean(values)
    std = statistics.stdev(values)

    if std == 0:
        return {"anomalies": [], "total": 0, "mean": mean, "std": 0.0}

    anomalies = []
    for i, v in enumerate(values):
        z = (v - mean) / std
        if abs(z) > z_threshold:
            severity = "extreme" if abs(z) > 3.0 else "significant"
            anomalies.append({
                "index": i,
                "value": round(v, 6),
                "z_score": round(z, 3),
                "severity": severity,
                "direction": "above" if z > 0 else "below",
            })

    return {
        "anomalies": anomalies,
        "total": len(anomalies),
        "mean": round(mean, 6),
        "std": round(std, 6),
        "z_threshold": z_threshold,
        "data_points": len(values),
    }


class ResearcherTool(Tool):
    """Research worker — scans trends and detects anomalies in financial data."""

    @property
    def name(self) -> str:
        return "researcher"

    @property
    def description(self) -> str:
        return (
            "Financial research tool with method scan_trends (trend direction, momentum, regime detection) "
            "and method detect_anomalies (z-score anomaly detection). Bilingual support (en/ms). "
            "Chain with decision_engine or feed results into copywriter for alerts."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["scan_trends", "detect_anomalies"],
                    "description": "Research method to run",
                },
                "params": {
                    "type": "object",
                    "description": "Method-specific parameters",
                },
            },
            "required": ["method"],
        }

    _DISPATCH = {
        "scan_trends": scan_trends,
        "detect_anomalies": detect_anomalies,
    }

    async def execute(self, **kwargs: Any) -> str:
        method = kwargs.get("method", "")
        params = kwargs.get("params", {})

        fn = self._DISPATCH.get(method)
        if not fn:
            return json.dumps({"error": f"Unknown method: {method}. Use: {list(self._DISPATCH)}"})

        try:
            result = fn(**params)
            return json.dumps(result)
        except Exception as exc:
            return json.dumps({"error": str(exc)})
