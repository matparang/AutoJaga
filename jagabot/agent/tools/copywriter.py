"""Copywriter tool — drafts alerts and report summaries for financial analysis."""

import json
import time
from typing import Any

from jagabot.agent.tools.base import Tool


def draft_alert(
    risk_level: str = "moderate",
    tool_name: str = "",
    key_metric: str = "",
    value: float | str = "",
    locale: str = "en",
) -> dict[str, Any]:
    """Draft a concise risk alert message suitable for notifications.

    Args:
        risk_level: One of 'low', 'moderate', 'high', 'critical'.
        tool_name: The tool that triggered the alert.
        key_metric: The metric name (e.g. 'VaR', 'probability').
        value: The metric value.
        locale: 'en' or 'ms' for bilingual support.
    """
    emojis = {"low": "🟢", "moderate": "🟡", "high": "🟠", "critical": "🔴"}
    emoji = emojis.get(risk_level, "⚠️")

    if locale == "ms":
        templates = {
            "low": f"{emoji} Amaran rendah: {key_metric} = {value} ({tool_name}). Tiada tindakan segera diperlukan.",
            "moderate": f"{emoji} Amaran sederhana: {key_metric} = {value} ({tool_name}). Pantau dengan teliti.",
            "high": f"{emoji} Amaran tinggi: {key_metric} = {value} ({tool_name}). Pertimbangkan tindakan segera.",
            "critical": f"{emoji} KRITIKAL: {key_metric} = {value} ({tool_name}). Tindakan segera diperlukan!",
        }
    else:
        templates = {
            "low": f"{emoji} Low alert: {key_metric} = {value} ({tool_name}). No immediate action needed.",
            "moderate": f"{emoji} Moderate alert: {key_metric} = {value} ({tool_name}). Monitor closely.",
            "high": f"{emoji} High alert: {key_metric} = {value} ({tool_name}). Consider immediate action.",
            "critical": f"{emoji} CRITICAL: {key_metric} = {value} ({tool_name}). Immediate action required!",
        }

    message = templates.get(risk_level, templates["moderate"])

    return {
        "alert": message,
        "risk_level": risk_level,
        "tool": tool_name,
        "metric": key_metric,
        "value": value,
        "locale": locale,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def draft_report_summary(
    analysis_results: dict[str, Any] | None = None,
    query: str = "",
    locale: str = "en",
) -> dict[str, Any]:
    """Draft a human-readable summary paragraph from analysis results.

    Args:
        analysis_results: Dict of tool results keyed by tool name.
        query: The original analysis query.
        locale: 'en' or 'ms' for bilingual support.
    """
    results = analysis_results or {}
    tool_count = len(results)

    # Extract key findings
    findings = []
    risk_level = "moderate"

    for tool, data in results.items():
        if isinstance(data, dict):
            if "var_amount" in data:
                findings.append(f"VaR: ${data['var_amount']:,.2f}" if isinstance(data['var_amount'], (int, float)) else f"VaR: {data['var_amount']}")
            if "probability_below_target" in data:
                prob = data["probability_below_target"]
                findings.append(f"Probability below target: {prob}%")
                if isinstance(prob, (int, float)) and prob > 60:
                    risk_level = "high"
            if "cv" in data:
                findings.append(f"CV: {data['cv']}")
            if "warning_count" in data:
                wc = data["warning_count"]
                findings.append(f"Warnings: {wc}")
                if isinstance(wc, (int, float)) and wc > 3:
                    risk_level = "high"

    findings_text = "; ".join(findings) if findings else "No specific findings extracted"

    if locale == "ms":
        summary = (
            f"Analisis '{query}' menggunakan {tool_count} alat. "
            f"Penemuan utama: {findings_text}. "
            f"Tahap risiko keseluruhan: {risk_level}."
        )
    else:
        summary = (
            f"Analysis of '{query}' using {tool_count} tools. "
            f"Key findings: {findings_text}. "
            f"Overall risk level: {risk_level}."
        )

    return {
        "summary": summary,
        "tool_count": tool_count,
        "findings": findings,
        "risk_level": risk_level,
        "locale": locale,
        "query": query,
    }


class CopywriterTool(Tool):
    """Copywriter worker — drafts alerts and report summaries."""

    @property
    def name(self) -> str:
        return "copywriter"

    @property
    def description(self) -> str:
        return (
            "Content drafting tool with method draft_alert (risk notification messages) "
            "and method draft_report_summary (human-readable analysis summaries). "
            "Bilingual support (en/ms). Use after risk analysis; feed method results from VaR or Monte Carlo."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["draft_alert", "draft_report_summary"],
                    "description": "Copywriting method to run",
                },
                "params": {
                    "type": "object",
                    "description": "Method-specific parameters",
                },
            },
            "required": ["method"],
        }

    _DISPATCH = {
        "draft_alert": draft_alert,
        "draft_report_summary": draft_report_summary,
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
