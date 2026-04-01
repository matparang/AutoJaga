"""Early warning engine tool — detect warning signals and classify risk levels."""

import json
from typing import Any

from jagabot.agent.tools.base import Tool


# ---------------------------------------------------------------------------
# Locale-aware labels
# ---------------------------------------------------------------------------

_LEVEL_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "normal": "normal",
        "elevated": "elevated",
        "warning": "warning",
        "critical": "critical",
    },
    "ms": {
        "normal": "NORMAL",
        "elevated": "MENINGKAT",
        "warning": "AMARAN",
        "critical": "KRITIKAL",
    },
    "id": {
        "normal": "NORMAL",
        "elevated": "MENINGKAT",
        "warning": "PERINGATAN",
        "critical": "KRITIS",
    },
}

_CLASSIFICATION_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "low": "low",
        "moderate": "moderate",
        "high": "high",
        "critical": "critical",
    },
    "ms": {
        "low": "RENDAH",
        "moderate": "SEDERHANA",
        "high": "TINGGI",
        "critical": "KRITIKAL",
    },
    "id": {
        "low": "RENDAH",
        "moderate": "SEDANG",
        "high": "TINGGI",
        "critical": "KRITIS",
    },
}

_ACTION_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "continue_monitoring": "continue_monitoring",
        "review_positions": "review_positions",
        "close_monitoring": "close_monitoring",
        "immediate_action_required": "immediate_action_required",
    },
    "ms": {
        "continue_monitoring": "TERUSKAN PEMANTAUAN",
        "review_positions": "SEMAK POSISI",
        "close_monitoring": "PANTAU RAPAT",
        "immediate_action_required": "TINDAKAN SEGERA DIPERLUKAN",
    },
    "id": {
        "continue_monitoring": "LANJUTKAN PEMANTAUAN",
        "review_positions": "TINJAU POSISI",
        "close_monitoring": "PANTAU KETAT",
        "immediate_action_required": "TINDAKAN SEGERA DIPERLUKAN",
    },
}


def _loc(mapping: dict[str, dict[str, str]], key: str, locale: str) -> str:
    return mapping.get(locale, mapping["en"]).get(key, key)


def detect_warning_signals(metrics: dict, locale: str = "en") -> dict:
    """Detect early warning signals from market/portfolio metrics.

    Args:
        metrics: Dict with keys like volatility, drawdown, volume_change,
                 correlation_shift, spread_widening, momentum, etc.
        locale: Language for labels — "en", "ms", or "id".
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
        "level": _loc(_LEVEL_LABELS, level, locale),
        "metrics_analyzed": list(metrics.keys()),
    }


def classify_risk_level(signals: list[dict], locale: str = "en") -> dict:
    """Classify aggregate risk level from a list of warning signals.

    Args:
        signals: List of signal dicts with 'severity' key.
        locale: Language for labels — "en", "ms", or "id".
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
        "classification": _loc(_CLASSIFICATION_LABELS, classification, locale),
        "total_weight": total_weight,
        "signal_count": len(signals),
        "recommended_action": _loc(_ACTION_LABELS, action, locale),
        "severity_breakdown": {
            sev: sum(1 for s in signals if s.get("severity") == sev)
            for sev in ["low", "medium", "high", "critical"]
        },
    }


class EarlyWarningTool(Tool):
    """Early warning detection engine."""

    name = "early_warning"
    description = (
        "Early warning signal detection for financial crisis monitoring. "
        "CALL THIS TOOL when analysing whether a stock/portfolio is approaching danger.\n\n"
        "Methods:\n"
        "- detect_warning_signals: Takes CV, equity ratio, trend → returns list of triggered warnings "
        "(supports locale: 'en','ms','id' for Malay/Indonesian labels)\n"
        "- classify_risk_level: Takes list of signals → returns risk level "
        "(critical/high/moderate/low) with recommended actions\n\n"
        "Chain: financial_cv → early_warning → dynamics_oracle → monte_carlo\n"
        "ALWAYS call this after computing CV to check for danger signals."
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["detect_warning_signals", "classify_risk_level"],
                "description": (
                    "detect_warning_signals: needs {cv, equity_ratio, trend, locale?}. "
                    "classify_risk_level: needs {signals: [...], locale?}."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Keyword arguments. Examples:\n"
                    "detect_warning_signals: {\"cv\": 0.65, \"equity_ratio\": 0.15, "
                    "\"trend\": \"declining\", \"locale\": \"ms\"}\n"
                    "classify_risk_level: {\"signals\": [\"high_cv\", \"low_equity\"], \"locale\": \"ms\"}"
                ),
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
