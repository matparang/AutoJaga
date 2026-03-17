"""Self-improver tool — analyzes past predictions and suggests calibration improvements."""

import json
import statistics
from typing import Any

from jagabot.agent.tools.base import Tool


def analyze_mistakes(
    predictions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Analyze past predictions to find systematic biases and errors.

    Args:
        predictions: List of dicts with keys: 'predicted', 'actual', 'tool' (optional), 'date' (optional).

    Returns:
        Dict with bias analysis, accuracy metrics, and common error patterns.
    """
    preds = predictions or []
    if not preds:
        return {
            "error_count": 0,
            "note": "No predictions provided for analysis",
            "suggestions": ["Start logging predictions to enable self-improvement"],
        }

    errors = []
    by_tool: dict[str, list[float]] = {}

    for p in preds:
        predicted = p.get("predicted", 0)
        actual = p.get("actual", 0)
        if isinstance(predicted, (int, float)) and isinstance(actual, (int, float)):
            error = predicted - actual
            errors.append(error)
            tool = p.get("tool", "unknown")
            by_tool.setdefault(tool, []).append(error)

    if not errors:
        return {
            "error_count": 0,
            "note": "No numeric prediction/actual pairs found",
            "suggestions": ["Ensure predictions have 'predicted' and 'actual' numeric fields"],
        }

    mean_error = statistics.mean(errors)
    abs_errors = [abs(e) for e in errors]
    mae = statistics.mean(abs_errors)
    bias = "optimistic" if mean_error > 0 else "pessimistic" if mean_error < 0 else "neutral"

    # Per-tool breakdown
    tool_analysis = {}
    for tool, tool_errors in by_tool.items():
        tool_analysis[tool] = {
            "count": len(tool_errors),
            "mean_error": round(statistics.mean(tool_errors), 6),
            "mae": round(statistics.mean([abs(e) for e in tool_errors]), 6),
            "bias": "optimistic" if statistics.mean(tool_errors) > 0 else "pessimistic",
        }

    return {
        "error_count": len(errors),
        "mean_error": round(mean_error, 6),
        "mae": round(mae, 6),
        "bias": bias,
        "by_tool": tool_analysis,
        "worst_errors": sorted(errors, key=abs, reverse=True)[:5],
    }


def suggest_improvements(
    analysis_results: dict[str, Any] | None = None,
    current_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Suggest parameter tweaks and process improvements based on analysis.

    Args:
        analysis_results: Output from analyze_mistakes or any analysis summary.
        current_config: Current tool configuration (optional).

    Returns:
        Dict with prioritized suggestions for improvement.
    """
    results = analysis_results or {}
    suggestions = []

    bias = results.get("bias", "neutral")
    mae = results.get("mae", 0)
    by_tool = results.get("by_tool", {})

    # Bias correction suggestions
    if bias == "optimistic":
        suggestions.append({
            "priority": "high",
            "category": "calibration",
            "suggestion": "Apply pessimistic correction: models consistently overestimate. "
                          "Consider widening confidence intervals by 10-15%.",
        })
    elif bias == "pessimistic":
        suggestions.append({
            "priority": "medium",
            "category": "calibration",
            "suggestion": "Models tend to underestimate. Consider tightening worst-case "
                          "scenarios to avoid unnecessary risk aversion.",
        })

    # Accuracy improvements
    if mae > 0.1:
        suggestions.append({
            "priority": "high",
            "category": "accuracy",
            "suggestion": f"Mean absolute error is {mae:.4f} — consider using ensemble methods "
                          "or increasing Monte Carlo simulation count.",
        })

    # Per-tool suggestions
    for tool, info in by_tool.items():
        if info.get("mae", 0) > 0.15:
            suggestions.append({
                "priority": "medium",
                "category": "tool_specific",
                "suggestion": f"Tool '{tool}' has high MAE ({info['mae']:.4f}). "
                              "Review input parameters and data quality.",
            })

    if not suggestions:
        suggestions.append({
            "priority": "low",
            "category": "general",
            "suggestion": "No significant improvements needed. Continue current approach.",
        })

    return {
        "suggestions": suggestions,
        "total": len(suggestions),
        "based_on": {
            "bias": bias,
            "mae": mae,
            "tools_analyzed": len(by_tool),
        },
    }


class SelfImproverTool(Tool):
    """Self-improvement worker — analyzes past mistakes and suggests calibration tweaks."""

    @property
    def name(self) -> str:
        return "self_improver"

    @property
    def description(self) -> str:
        return (
            "Self-improvement tool with method analyze_mistakes (find biases and error patterns in past predictions) "
            "and method suggest_improvements (generate calibration and process improvement suggestions). "
            "Chain with other tools; feed prediction history to improve accuracy."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["analyze_mistakes", "suggest_improvements"],
                    "description": "Self-improvement method to run",
                },
                "params": {
                    "type": "object",
                    "description": "Method-specific parameters",
                },
            },
            "required": ["method"],
        }

    _DISPATCH = {
        "analyze_mistakes": analyze_mistakes,
        "suggest_improvements": suggest_improvements,
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
