"""
Kernel 3: Multi-Perspective — calibrated Bull/Bear/Buffet with accuracy tracking.

Adapted from nanobot/kernel/perspective.py. Adds:
- AccuracyTracker: persist per-perspective hit rates
- Adaptive weight recalibration based on rolling accuracy
- Integration with K1 for confidence refinement
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from jagabot.agent.tools.decision import (
    bull_perspective,
    bear_perspective,
    buffet_perspective,
    collapse_perspectives,
)
from jagabot.kernels.k1_bayesian import K1Bayesian


# Verdict → outcome direction mapping for accuracy scoring
_BULLISH_VERDICTS = {"STRONG BUY", "BUY", "BUY — Margin of Safety", "CAUTIOUS BUY"}
_BEARISH_VERDICTS = {"SELL", "SELL — Rule #1 Violated", "REDUCE", "REDUCE — Protect Capital"}

WINDOW_SIZE = 20  # rolling accuracy window


class AccuracyTracker:
    """Persists per-perspective accuracy records."""

    def __init__(self, workspace: str | Path | None = None) -> None:
        ws = Path(workspace) if workspace else Path.home() / ".jagabot" / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        self._path = ws / "accuracy.json"
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                logger.debug("AccuracyTracker load fallback: {}", exc)
                self._data = {}

    def _save(self) -> None:
        try:
            self._path.write_text(json.dumps(self._data, indent=2))
        except OSError as exc:
            logger.debug("AccuracyTracker save error: {}", exc)

    def _ensure(self, perspective: str) -> None:
        if perspective not in self._data:
            self._data[perspective] = {"correct": 0, "total": 0, "recent": []}

    def record(self, perspective: str, was_correct: bool) -> None:
        """Record whether a perspective's prediction was correct."""
        self._ensure(perspective)
        entry = self._data[perspective]
        entry["total"] += 1
        if was_correct:
            entry["correct"] += 1
        entry["recent"].append({"correct": was_correct, "ts": time.time()})
        if len(entry["recent"]) > WINDOW_SIZE:
            entry["recent"] = entry["recent"][-WINDOW_SIZE:]
        self._save()

    def accuracy(self, perspective: str) -> float | None:
        """Overall accuracy (correct/total). None if no data."""
        entry = self._data.get(perspective)
        if not entry or entry["total"] == 0:
            return None
        return entry["correct"] / entry["total"]

    def recent_accuracy(self, perspective: str) -> float | None:
        """Rolling accuracy over last WINDOW_SIZE outcomes."""
        entry = self._data.get(perspective)
        if not entry or not entry["recent"]:
            return None
        recent = entry["recent"]
        return sum(1 for r in recent if r["correct"]) / len(recent)

    def count(self, perspective: str) -> int:
        entry = self._data.get(perspective)
        return entry["total"] if entry else 0

    def get_stats(self, perspective: str) -> Dict[str, Any]:
        entry = self._data.get(perspective)
        if not entry:
            return {"perspective": perspective, "total": 0, "accuracy": None, "recent_accuracy": None}
        return {
            "perspective": perspective,
            "total": entry["total"],
            "correct": entry["correct"],
            "accuracy": round(entry["correct"] / entry["total"], 4) if entry["total"] else None,
            "recent_accuracy": self.recent_accuracy(perspective),
            "recent_window": len(entry["recent"]),
        }

    def get_all_perspectives(self) -> List[str]:
        return list(self._data.keys())

    def clear(self, perspective: str | None = None) -> None:
        if perspective:
            self._data.pop(perspective, None)
        else:
            self._data.clear()
        self._save()


class K3MultiPerspective:
    """
    Calibrated multi-perspective kernel.

    Wraps existing Bull/Bear/Buffet decision functions and adds:
    - Confidence refinement via K1 Bayesian calibration
    - Per-perspective accuracy tracking
    - Adaptive weight recalibration
    """

    DEFAULT_WEIGHTS = {"bull": 0.20, "bear": 0.45, "buffet": 0.35}
    MIN_OBSERVATIONS = 10  # require this many outcomes before recalibrating weights

    def __init__(
        self,
        k1: K1Bayesian | None = None,
        workspace: str | Path | None = None,
    ) -> None:
        self._k1 = k1 or K1Bayesian(workspace)
        self._tracker = AccuracyTracker(workspace)
        self._workspace = workspace

    def get_perspective(self, ptype: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get a perspective with calibrated confidence.

        Args:
            ptype: "bull", "bear", or "buffet"
            data: Parameters for the perspective function (probability_below_target, etc.)
        """
        dispatch = {
            "bull": bull_perspective,
            "bear": bear_perspective,
            "buffet": buffet_perspective,
        }
        fn = dispatch.get(ptype)
        if fn is None:
            return {"error": f"Unknown perspective: {ptype}. Use bull/bear/buffet."}

        try:
            result = fn(**data)
        except Exception as exc:
            return {"error": f"Perspective {ptype} failed: {exc}"}

        raw_confidence = result.get("confidence", 50.0)
        refined = self._k1.refine_confidence(raw_confidence, ptype)
        result["raw_confidence"] = raw_confidence
        result["confidence"] = refined
        result["calibrated"] = refined != raw_confidence
        return result

    def update_accuracy(self, perspective: str, predicted_verdict: str,
                        actual_outcome: str) -> Dict[str, Any]:
        """Record whether a perspective's verdict matched the actual outcome.

        Args:
            perspective: "bull", "bear", or "buffet"
            predicted_verdict: The verdict that was given (e.g. "BUY", "SELL")
            actual_outcome: "up" (price went up) or "down" (price went down)
        """
        predicted_bullish = predicted_verdict in _BULLISH_VERDICTS
        actual_up = actual_outcome.lower() in ("up", "bullish", "positive", "gain")

        was_correct = (predicted_bullish and actual_up) or (not predicted_bullish and not actual_up)
        self._tracker.record(perspective, was_correct)

        # Also record in K1 calibration store
        prob = 0.8 if predicted_bullish else 0.2
        self._k1.record_outcome(perspective, prob, actual_up)

        stats = self._tracker.get_stats(perspective)
        stats["was_correct"] = was_correct
        return stats

    def get_weights(self) -> Dict[str, Any]:
        """Return current perspective weights (calibrated if enough data)."""
        weights = dict(self.DEFAULT_WEIGHTS)
        total_obs = sum(self._tracker.count(p) for p in ["bull", "bear", "buffet"])

        if total_obs < self.MIN_OBSERVATIONS:
            return {
                "weights": weights,
                "calibrated": False,
                "reason": f"Need {self.MIN_OBSERVATIONS} total outcomes, have {total_obs}",
            }

        return {
            "weights": self.recalibrate_weights(),
            "calibrated": True,
            "total_observations": total_obs,
        }

    def recalibrate_weights(self) -> Dict[str, float]:
        """Adjust weights based on rolling accuracy. Better accuracy → higher weight.

        Uses recent_accuracy if available, falls back to overall accuracy,
        then to default weight. Normalises to sum to 1.0.
        """
        raw = {}
        for p in ["bull", "bear", "buffet"]:
            acc = self._tracker.recent_accuracy(p)
            if acc is None:
                acc = self._tracker.accuracy(p)
            if acc is None:
                acc = self.DEFAULT_WEIGHTS[p]
            # Floor at 0.1 — never completely zero out a perspective
            raw[p] = max(0.1, acc)

        total = sum(raw.values())
        return {p: round(v / total, 4) for p, v in raw.items()}

    def calibrated_collapse(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run all 3 perspectives with calibrated confidence + adaptive weights, then collapse.

        Args:
            data: Must include probability_below_target, current_price, target_price.
                  May include var_pct, cvar_pct, warnings, risk_level, intrinsic_value,
                  recovery_months, cv, percentiles, equity, debt_ratio.
        """
        bull = self.get_perspective("bull", {
            k: data[k] for k in ["probability_below_target", "current_price", "target_price",
                                  "cv", "percentiles", "recovery_months"]
            if k in data
        })
        bear = self.get_perspective("bear", {
            k: data[k] for k in ["probability_below_target", "current_price", "target_price",
                                  "var_pct", "cvar_pct", "warnings", "risk_level", "margin_call"]
            if k in data
        })
        buffet = self.get_perspective("buffet", {
            k: data[k] for k in ["probability_below_target", "current_price", "target_price",
                                  "intrinsic_value", "recovery_months", "equity", "debt_ratio",
                                  "margin_call"]
            if k in data
        })

        if "error" in bull or "error" in bear or "error" in buffet:
            errors = {p: r.get("error") for p, r in
                      [("bull", bull), ("bear", bear), ("buffet", buffet)] if "error" in r}
            return {"error": "Perspective failure", "details": errors}

        weights_info = self.get_weights()
        weights = weights_info["weights"]

        collapsed = collapse_perspectives(bull, bear, buffet, weights=weights)
        collapsed["weights_calibrated"] = weights_info.get("calibrated", False)
        return collapsed

    def get_accuracy_stats(self) -> Dict[str, Any]:
        """Return accuracy stats for all tracked perspectives."""
        result = {}
        for p in self._tracker.get_all_perspectives():
            result[p] = self._tracker.get_stats(p)
        return result if result else {"message": "No accuracy data yet"}

    @property
    def accuracy_tracker(self) -> AccuracyTracker:
        return self._tracker
