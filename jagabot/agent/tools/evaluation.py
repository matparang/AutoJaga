"""
K7 Evaluation tool — result scoring, anomaly detection, improvement suggestions, ROI.

Wraps EvaluationKernel (from nanobot/kernel/evaluation_kernel.py)
as a Tool ABC compliant tool for the agent loop.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from jagabot.agent.tools.base import Tool


@dataclass
class Evaluation:
    """Result of evaluating execution outcomes."""
    score: float = 0.0
    gap: float = 0.0
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    improvements: List[Dict[str, Any]] = field(default_factory=list)
    roi: float = 0.0
    quality_per_token: float = 0.0

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 4),
            "gap": round(self.gap, 4),
            "anomalies": self.anomalies,
            "improvements": self.improvements,
            "roi": round(self.roi, 4),
            "quality_per_token": round(self.quality_per_token, 6),
        }


class EvaluationKernel:
    """K7 — Result evaluation and improvement suggestions."""

    name = "K7"
    description = "Result evaluation and improvement suggestions"

    def evaluate_result(
        self,
        expected: Dict[str, Any],
        actual: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare actual results against expected outcomes. Returns {score, gap, details}."""
        if not expected or not actual:
            return {"score": 0.5, "gap": 0.5, "details": {"reason": "insufficient data"}}

        matches = 0
        total = 0
        details: Dict[str, Any] = {}

        for key in expected:
            total += 1
            exp_val = expected[key]
            act_val = actual.get(key)
            if act_val is None:
                details[key] = "missing"
                continue
            if isinstance(exp_val, (int, float)) and isinstance(act_val, (int, float)):
                if exp_val != 0:
                    ratio = abs(act_val - exp_val) / abs(exp_val)
                    if ratio <= 0.2:
                        matches += 1
                        details[key] = "match"
                    else:
                        details[key] = f"gap={ratio:.2%}"
                else:
                    matches += (1 if act_val == 0 else 0)
                    details[key] = "match" if act_val == 0 else "gap"
            elif isinstance(exp_val, bool):
                if exp_val == act_val:
                    matches += 1
                    details[key] = "match"
                else:
                    details[key] = "mismatch"
            else:
                if str(exp_val) == str(act_val):
                    matches += 1
                    details[key] = "match"
                else:
                    details[key] = "mismatch"

        score = matches / total if total > 0 else 0.5
        return {"score": round(score, 4), "gap": round(1 - score, 4), "details": details}

    def detect_anomaly(
        self,
        result: Dict[str, Any],
        history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check whether a result is anomalous vs historical baselines (z-score)."""
        if not history:
            return {"is_anomaly": False, "reason": "no history", "confidence": 0.0}

        anomalies: List[str] = []

        for key, val in result.items():
            if not isinstance(val, (int, float)):
                continue
            hist_vals = [h.get(key) for h in history if isinstance(h.get(key), (int, float))]
            if len(hist_vals) < 2:
                continue
            mean = sum(hist_vals) / len(hist_vals)
            std = (sum((v - mean) ** 2 for v in hist_vals) / len(hist_vals)) ** 0.5
            if std == 0:
                if val != mean:
                    anomalies.append(f"{key}: value {val} differs from constant {mean}")
                continue
            z = abs(val - mean) / std
            if z > 2.0:
                anomalies.append(f"{key}: z-score={z:.1f} (val={val}, μ={mean:.1f}, σ={std:.1f})")

        if anomalies:
            confidence = min(0.99, 0.5 + len(anomalies) * 0.15)
            return {
                "is_anomaly": True,
                "reason": "; ".join(anomalies),
                "confidence": round(confidence, 2),
            }
        return {"is_anomaly": False, "reason": "within normal range", "confidence": 0.0}

    def suggest_improvement(
        self,
        execution_log: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Analyse execution log and suggest improvements."""
        suggestions: List[Dict[str, Any]] = []
        if not execution_log:
            return suggestions

        slow = [s for s in execution_log if s.get("elapsed_ms", 0) > 100]
        if len(slow) >= 2:
            ids = [s["step_id"] for s in slow]
            suggestions.append({
                "type": "parallelize",
                "steps": ids,
                "reason": f"{len(slow)} steps >100ms — consider parallel execution",
            })

        failed = [s for s in execution_log if not s.get("success", True)]
        for f in failed:
            if "timeout" in (f.get("error") or "").lower():
                suggestions.append({
                    "type": "increase_timeout",
                    "step": f["step_id"],
                    "reason": f"Step {f['step_id']} timed out",
                })
            elif "not found" in (f.get("error") or "").lower():
                suggestions.append({
                    "type": "skip_or_fallback",
                    "step": f["step_id"],
                    "reason": f"Resource not found for {f['step_id']}",
                })

        kernel_counts: Dict[str, int] = {}
        for s in execution_log:
            k = s.get("kernel", "")
            if k:
                kernel_counts[k] = kernel_counts.get(k, 0) + 1
        for k, count in kernel_counts.items():
            if count >= 3:
                suggestions.append({
                    "type": "cache_results",
                    "kernel": k,
                    "reason": f"{k} called {count} times — consider caching",
                })

        return suggestions

    def calculate_roi(
        self,
        plan_tokens: int,
        result_score: float,
        total_tokens_used: int,
    ) -> Dict[str, Any]:
        """Calculate Return on Investment: quality per token invested."""
        tokens_k = max(total_tokens_used, 1) / 1000.0
        roi = result_score / tokens_k if tokens_k > 0 else 0.0
        qpt = result_score / max(total_tokens_used, 1)
        return {
            "roi": round(roi, 4),
            "quality_per_token": round(qpt, 6),
            "plan_tokens": plan_tokens,
            "actual_tokens": total_tokens_used,
            "efficiency": round(plan_tokens / max(total_tokens_used, 1), 4) if plan_tokens else 0.0,
        }

    def full_evaluate(
        self,
        expected: Dict[str, Any],
        actual: Dict[str, Any],
        history: List[Dict[str, Any]],
        execution_log: List[Dict[str, Any]],
        plan_tokens: int = 0,
        total_tokens_used: int = 0,
    ) -> Evaluation:
        """Run all evaluation steps and return a combined Evaluation."""
        ev = self.evaluate_result(expected, actual)
        anomaly = self.detect_anomaly(actual, history)
        improvements = self.suggest_improvement(execution_log)
        roi_info = self.calculate_roi(plan_tokens, ev["score"], total_tokens_used)

        return Evaluation(
            score=ev["score"],
            gap=ev["gap"],
            anomalies=[anomaly] if anomaly.get("is_anomaly") else [],
            improvements=improvements,
            roi=roi_info["roi"],
            quality_per_token=roi_info["quality_per_token"],
        )

    @staticmethod
    def estimate_tokens() -> int:
        return 500


class EvaluationTool(Tool):
    """Tool ABC wrapper for K7 Evaluation Kernel."""

    @property
    def name(self) -> str:
        return "evaluate_result"

    @property
    def description(self) -> str:
        return (
            "K7 Evaluation: score result quality against expectations, detect anomalies "
            "via z-score, suggest execution improvements, and calculate ROI per token."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["evaluate", "anomaly", "improve", "roi", "full"],
                    "description": (
                        "evaluate: compare expected vs actual results. "
                        "anomaly: detect anomalies against history. "
                        "improve: suggest improvements from execution log. "
                        "roi: calculate return on investment. "
                        "full: run all evaluation steps."
                    ),
                },
                "expected": {
                    "type": "object",
                    "description": "Expected outcomes dict (for evaluate/full).",
                },
                "actual": {
                    "type": "object",
                    "description": "Actual results dict (for evaluate/anomaly/full).",
                },
                "history": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "description": "Historical result object"
                    },
                    "description": "Historical result dicts for anomaly baseline (for anomaly/full).",
                },
                "execution_log": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step_id": {"type": "string"},
                            "elapsed_ms": {"type": "number"},
                            "success": {"type": "boolean"},
                            "kernel": {"type": "string"}
                        }
                    },
                    "description": "Execution log entries with step_id, elapsed_ms, success, kernel (for improve/full).",
                },
                "plan_tokens": {
                    "type": "integer",
                    "description": "Planned token budget (for roi/full).",
                },
                "total_tokens_used": {
                    "type": "integer",
                    "description": "Actual tokens consumed (for roi/full).",
                },
                "result_score": {
                    "type": "number",
                    "description": "Quality score 0-1 (for roi action only).",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "evaluate")
        kernel = EvaluationKernel()

        if action == "evaluate":
            expected = kwargs.get("expected", {})
            actual = kwargs.get("actual", {})
            result = kernel.evaluate_result(expected, actual)
            return json.dumps(result)

        elif action == "anomaly":
            actual = kwargs.get("actual", {})
            history = kwargs.get("history", [])
            result = kernel.detect_anomaly(actual, history)
            return json.dumps(result)

        elif action == "improve":
            log = kwargs.get("execution_log", [])
            result = kernel.suggest_improvement(log)
            return json.dumps({"suggestions": result, "count": len(result)})

        elif action == "roi":
            plan_tokens = kwargs.get("plan_tokens", 0)
            result_score = kwargs.get("result_score", 0.0)
            total_tokens = kwargs.get("total_tokens_used", 0)
            result = kernel.calculate_roi(plan_tokens, result_score, total_tokens)
            return json.dumps(result)

        elif action == "full":
            ev = kernel.full_evaluate(
                expected=kwargs.get("expected", {}),
                actual=kwargs.get("actual", {}),
                history=kwargs.get("history", []),
                execution_log=kwargs.get("execution_log", []),
                plan_tokens=kwargs.get("plan_tokens", 0),
                total_tokens_used=kwargs.get("total_tokens_used", 0),
            )
            return json.dumps(ev.to_dict())

        else:
            return json.dumps({"error": f"Unknown action: {action}. Use evaluate|anomaly|improve|roi|full."})
