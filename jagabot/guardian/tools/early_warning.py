"""Early warning engine tool — detect warning signals and classify risk levels."""

import json
from typing import Any

from jagabot.agent.tools.base import Tool


def detect_warning_signals(metrics: dict) -> dict:
    """Detect early warning signals from market/portfolio metrics.

    Args:
        metrics: Dict with keys like volatility, drawdown, volume_change,
                 correlation_shift, spread_widening, momentum, etc.
    """
    signals = []
    level = "normal"
    score = 0.0

    # Volatility spike
    vol = metrics.get("volatility", 0.0)
    if vol > 0.5:
        signals.append({"type": "volatility_spike", "value": vol, "severity": "high"})
        score += 3.0
    elif vol > 0.3:
        signals.append({"type": "elevated_volatility", "value": vol, "severity": "medium"})
        score += 1.5

    # Drawdown
    dd = metrics.get("drawdown", 0.0)
    if dd > 0.2:
        signals.append({"type": "severe_drawdown", "value": dd, "severity": "high"})
        score += 3.0
    elif dd > 0.1:
        signals.append({"type": "moderate_drawdown", "value": dd, "severity": "medium"})
        score += 1.5

    # Volume anomaly
    vol_change = metrics.get("volume_change", 0.0)
    if abs(vol_change) > 2.0:
        signals.append({"type": "volume_anomaly", "value": vol_change, "severity": "medium"})
        score += 2.0

    # Correlation breakdown
    corr_shift = metrics.get("correlation_shift", 0.0)
    if abs(corr_shift) > 0.3:
        signals.append({"type": "correlation_breakdown", "value": corr_shift, "severity": "high"})
        score += 2.5

    # Spread widening
    spread = metrics.get("spread_widening", 0.0)
    if spread > 0.5:
        signals.append({"type": "spread_widening", "value": spread, "severity": "medium"})
        score += 1.5

    # Momentum divergence
    momentum = metrics.get("momentum", 0.0)
    if momentum < -0.3:
        signals.append({"type": "negative_momentum", "value": momentum, "severity": "medium"})
        score += 1.5

    # Classify overall level
    if score >= 6.0:
        level = "critical"
    elif score >= 4.0:
        level = "warning"
    elif score >= 2.0:
        level = "elevated"
    else:
        level = "normal"

    return {
        "signals": signals,
        "signal_count": len(signals),
        "risk_score": round(score, 2),
        "level": level,
        "metrics_analyzed": list(metrics.keys()),
    }


def classify_risk_level(signals: list[dict]) -> dict:
    """Classify aggregate risk level from a list of warning signals.

    Args:
        signals: List of signal dicts with 'severity' key.
    """
    severity_weights = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    total_weight = sum(severity_weights.get(s.get("severity", "low"), 1) for s in signals)

    if total_weight >= 10:
        classification = "critical"
        action = "immediate_action_required"
    elif total_weight >= 6:
        classification = "high"
        action = "close_monitoring"
    elif total_weight >= 3:
        classification = "moderate"
        action = "review_positions"
    else:
        classification = "low"
        action = "continue_monitoring"

    return {
        "classification": classification,
        "total_weight": total_weight,
        "signal_count": len(signals),
        "recommended_action": action,
        "severity_breakdown": {
            sev: sum(1 for s in signals if s.get("severity") == sev)
            for sev in ["low", "medium", "high", "critical"]
        },
    }


class EarlyWarningTool(Tool):
    """Early warning detection engine."""

    name = "early_warning"
    description = (
        "Early warning signal detection. Methods: detect_warning_signals, classify_risk_level"
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["detect_warning_signals", "classify_risk_level"],
                "description": "The method to call",
            },
            "params": {
                "type": "object",
                "description": "Parameters for the chosen method",
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "detect_warning_signals": detect_warning_signals,
        "classify_risk_level": classify_risk_level,
    }

    async def execute(self, method: str, params: dict, **kw: Any) -> str:
        fn = self._DISPATCH.get(method)
        if fn is None:
            return json.dumps({"error": f"Unknown method: {method}"})
        try:
            result = fn(**params)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})
