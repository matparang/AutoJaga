"""
Kernel 1: Bayesian Inference — probabilistic reasoning with calibration persistence.

Adapted from nanobot/kernel/bayesian.py. Adds:
- CalibrationStore: persist predicted vs actual outcomes per perspective
- Brier score tracking for calibration quality
- Confidence refinement based on historical accuracy
"""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


class CalibrationStore:
    """Persists calibration records: (predicted_prob, actual_outcome) per perspective."""

    def __init__(self, workspace: str | Path | None = None) -> None:
        ws = Path(workspace) if workspace else Path.home() / ".jagabot" / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        self._path = ws / "calibration.json"
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                logger.debug("CalibrationStore load fallback: {}", exc)
                self._data = {}

    def _save(self) -> None:
        try:
            self._path.write_text(json.dumps(self._data, indent=2))
        except OSError as exc:
            logger.debug("CalibrationStore save error: {}", exc)

    def record(self, perspective: str, predicted_prob: float, actual: bool,
               prediction_id: str | None = None) -> None:
        """Record a calibration data point."""
        if perspective not in self._data:
            self._data[perspective] = []
        self._data[perspective].append({
            "predicted": round(max(0.0, min(1.0, predicted_prob)), 6),
            "actual": 1.0 if actual else 0.0,
            "id": prediction_id or f"pred_{int(time.time())}",
            "ts": time.time(),
        })
        self._save()

    def brier_score(self, perspective: str) -> float | None:
        """Brier score = mean((predicted - actual)²). Lower = better. None if no data."""
        records = self._data.get(perspective, [])
        if not records:
            return None
        return sum((r["predicted"] - r["actual"]) ** 2 for r in records) / len(records)

    def get_records(self, perspective: str) -> List[Dict[str, Any]]:
        return list(self._data.get(perspective, []))

    def get_all_perspectives(self) -> List[str]:
        return list(self._data.keys())

    def count(self, perspective: str) -> int:
        return len(self._data.get(perspective, []))

    def clear(self, perspective: str | None = None) -> None:
        if perspective:
            self._data.pop(perspective, None)
        else:
            self._data.clear()
        self._save()


class K1Bayesian:
    """
    Bayesian reasoning kernel with calibration persistence.

    Core math adapted from nanobot BayesianInferenceKernel.
    Adds calibration tracking and confidence refinement.
    """

    def __init__(self, workspace: str | Path | None = None) -> None:
        self._calibration = CalibrationStore(workspace)
        self._history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Core Bayesian operations (from nanobot kernel)
    # ------------------------------------------------------------------

    def prior(self, topic: str) -> float:
        """P(topic) — uninformative prior (0.5) without external engine."""
        return 0.5

    def likelihood(self, data: Dict[str, Any], hypothesis: str = "") -> float:
        """P(data|hypothesis) — estimate from data structure."""
        if not data:
            return 0.5
        values = []
        for v in data.values():
            try:
                fv = float(v)
                values.append(max(0.0, min(1.0, fv)))
            except (TypeError, ValueError):
                continue
        return sum(values) / len(values) if values else 0.5

    def posterior(self, prior_val: float, likelihood_val: float) -> float:
        """P(H|D) ∝ P(D|H) × P(H) — normalised."""
        numerator = likelihood_val * prior_val
        p_d_not_h = max(0.01, 1.0 - likelihood_val)
        denominator = numerator + p_d_not_h * (1.0 - prior_val)
        if denominator <= 0:
            return 0.5
        return max(0.0, min(1.0, numerator / denominator))

    def update(self, topic: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Bayesian belief update with history tracking."""
        p = self.prior(topic)
        lk = self.likelihood(evidence, hypothesis=topic)
        post = self.posterior(p, lk)
        bayes_factor = lk / max(0.01, 1.0 - lk)
        record = {
            "topic": topic,
            "prior": round(p, 4),
            "likelihood": round(lk, 4),
            "posterior": round(post, 4),
            "bayes_factor": round(bayes_factor, 4),
            "belief_change": round(post - p, 4),
            "direction": "strengthened" if post > p else "weakened" if post < p else "unchanged",
        }
        self._history.append(record)
        return record

    def ci(self, prob: float, n: int = 100) -> Tuple[float, float]:
        """Wilson score confidence interval."""
        if n <= 0:
            return (0.0, 1.0)
        z = 1.96
        denom = 1 + z * z / n
        centre = (prob + z * z / (2 * n)) / denom
        margin = z * math.sqrt((prob * (1 - prob) + z * z / (4 * n)) / n) / denom
        return (round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4))

    def assess(self, problem: str) -> Dict[str, Any]:
        """Full uncertainty assessment."""
        p = self.prior(problem)
        lo, hi = self.ci(p)
        return {
            "prior": round(p, 4),
            "ci_lower": lo,
            "ci_upper": hi,
            "uncertainty": round(hi - lo, 4),
        }

    # ------------------------------------------------------------------
    # Calibration layer (new for jagabot)
    # ------------------------------------------------------------------

    def refine_confidence(self, raw_confidence: float, perspective: str) -> float:
        """Adjust confidence based on historical calibration of this perspective.

        If historical Brier score shows overconfidence, shrink toward 50%.
        If underconfident, expand away from 50%.
        Requires ≥5 calibration records to activate.
        """
        brier = self._calibration.brier_score(perspective)
        n = self._calibration.count(perspective)
        if brier is None or n < 5:
            return round(raw_confidence, 2)

        # Perfect calibration → Brier ≈ 0. Random → Brier ≈ 0.25.
        # Shrinkage factor: 1.0 (perfect) → 0.5 (terrible, Brier ≥ 0.25)
        shrinkage = max(0.5, 1.0 - brier * 2)
        midpoint = 50.0
        refined = midpoint + (raw_confidence - midpoint) * shrinkage
        return round(max(0.0, min(100.0, refined)), 2)

    def record_outcome(self, perspective: str, predicted_prob: float,
                       actual: bool, prediction_id: str | None = None) -> Dict[str, Any]:
        """Record actual outcome for calibration tracking."""
        self._calibration.record(perspective, predicted_prob, actual, prediction_id)
        brier = self._calibration.brier_score(perspective)
        return {
            "perspective": perspective,
            "predicted": round(predicted_prob, 4),
            "actual": actual,
            "brier_score": round(brier, 4) if brier is not None else None,
            "n_records": self._calibration.count(perspective),
        }

    def get_calibration(self, perspective: str | None = None) -> Dict[str, Any]:
        """Return calibration metrics for one or all perspectives."""
        if perspective:
            brier = self._calibration.brier_score(perspective)
            n = self._calibration.count(perspective)
            quality = "insufficient_data"
            if n >= 5 and brier is not None:
                if brier < 0.05:
                    quality = "excellent"
                elif brier < 0.1:
                    quality = "good"
                elif brier < 0.2:
                    quality = "fair"
                else:
                    quality = "poor"
            return {
                "perspective": perspective,
                "brier_score": round(brier, 4) if brier is not None else None,
                "n_records": n,
                "quality": quality,
            }

        result = {}
        for p in self._calibration.get_all_perspectives():
            result[p] = self.get_calibration(p)
        return result if result else {"message": "No calibration data yet"}

    @property
    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    @property
    def calibration_store(self) -> CalibrationStore:
        return self._calibration
