"""Statistical test engine tool — confidence intervals, hypothesis tests, distribution analysis."""

import json
import math
from typing import Any

from jagabot.agent.tools.base import Tool


def _z_score(confidence: float) -> float:
    """Approximate z-score for common confidence levels using rational approximation."""
    common = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576, 0.999: 3.291}
    if confidence in common:
        return common[confidence]
    # Beasley-Springer-Moro approximation for normal inverse
    p = 1 - (1 - confidence) / 2
    t = math.sqrt(-2 * math.log(1 - p)) if p < 1 else 3.5
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    return t - (c0 + c1 * t + c2 * t * t) / (1 + d1 * t + d2 * t * t + d3 * t * t * t)


def confidence_interval(data: list[float], confidence: float = 0.95) -> dict:
    """Compute confidence interval for the mean."""
    if not data:
        return {"error": "empty data"}
    n = len(data)
    mean = sum(data) / n
    if n < 2:
        return {"mean": mean, "lower": mean, "upper": mean, "n": n, "confidence": confidence}
    variance = sum((x - mean) ** 2 for x in data) / (n - 1)
    se = math.sqrt(variance / n)
    z = _z_score(confidence)
    margin = z * se
    return {
        "mean": round(mean, 6),
        "std": round(math.sqrt(variance), 6),
        "se": round(se, 6),
        "lower": round(mean - margin, 6),
        "upper": round(mean + margin, 6),
        "margin_of_error": round(margin, 6),
        "n": n,
        "confidence": confidence,
    }


def hypothesis_test(data: list[float], mu0: float = 0.0, alpha: float = 0.05) -> dict:
    """One-sample z-test against a hypothesized mean."""
    if not data or len(data) < 2:
        return {"error": "need at least 2 data points"}
    n = len(data)
    mean = sum(data) / n
    variance = sum((x - mu0) ** 2 for x in data) / (n - 1)
    se = math.sqrt(variance / n)
    if se == 0:
        return {"z_stat": 0.0, "reject": False, "p_approx": 1.0, "mean": mean, "mu0": mu0}

    z_stat = (mean - mu0) / se
    # Approximate two-tailed p-value using error function
    p_approx = 2 * (1 - 0.5 * (1 + math.erf(abs(z_stat) / math.sqrt(2))))

    return {
        "z_stat": round(z_stat, 6),
        "p_approx": round(p_approx, 6),
        "alpha": alpha,
        "reject": p_approx < alpha,
        "mean": round(mean, 6),
        "mu0": mu0,
        "se": round(se, 6),
        "n": n,
        "conclusion": "reject H0" if p_approx < alpha else "fail to reject H0",
    }


def distribution_analysis(data: list[float]) -> dict:
    """Descriptive statistics and shape analysis."""
    if not data:
        return {"error": "empty data"}
    n = len(data)
    sorted_d = sorted(data)
    mean = sum(data) / n

    if n < 2:
        return {"mean": mean, "n": n, "min": mean, "max": mean}

    variance = sum((x - mean) ** 2 for x in data) / (n - 1)
    std = math.sqrt(variance)

    # skewness and kurtosis
    skew = (sum((x - mean) ** 3 for x in data) / n) / (std ** 3) if std > 0 else 0.0
    kurt = (sum((x - mean) ** 4 for x in data) / n) / (std ** 4) - 3.0 if std > 0 else 0.0

    q1_idx = int(n * 0.25)
    q2_idx = int(n * 0.50)
    q3_idx = int(n * 0.75)

    return {
        "n": n,
        "mean": round(mean, 6),
        "std": round(std, 6),
        "variance": round(variance, 6),
        "min": round(sorted_d[0], 6),
        "max": round(sorted_d[-1], 6),
        "median": round(sorted_d[q2_idx], 6),
        "q1": round(sorted_d[q1_idx], 6),
        "q3": round(sorted_d[q3_idx], 6),
        "iqr": round(sorted_d[q3_idx] - sorted_d[q1_idx], 6),
        "skewness": round(skew, 6),
        "kurtosis": round(kurt, 6),
        "shape": (
            "normal-like" if abs(skew) < 0.5 and abs(kurt) < 1
            else "skewed" if abs(skew) >= 0.5
            else "heavy-tailed"
        ),
    }


class StatisticalTool(Tool):
    """Statistical testing engine — CI, hypothesis tests, distribution analysis."""

    name = "statistical_engine"
    description = (
        "Statistical analysis engine. Methods: confidence_interval, "
        "hypothesis_test, distribution_analysis"
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["confidence_interval", "hypothesis_test", "distribution_analysis"],
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
        "confidence_interval": confidence_interval,
        "hypothesis_test": hypothesis_test,
        "distribution_analysis": distribution_analysis,
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
