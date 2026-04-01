"""
MetaLearningEngine — learns how jagabot's analysis strategies perform over time.

Adapted from nanobot/soul/meta_learning_engine.py. Changes:
- 11 chess heartbeat strategies → 10 financial analysis strategies
- Storage path: ~/.jagabot/workspace/meta_state.json
- Integration: feeds outcomes into K1 CalibrationStore + K3 AccuracyTracker
- Removed nanobot-specific engines (goal, chi, evolution, self_model)
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

_DEFAULT_DIR = Path.home() / ".jagabot" / "workspace"

META_CYCLE_INTERVAL = 100
MIN_SAMPLES_FOR_STRATEGY = 5
LEARNING_PROBLEM_THRESHOLD = 0.4

KNOWN_STRATEGIES = [
    "bull_analysis",
    "bear_analysis",
    "buffet_analysis",
    "risk_assessment",
    "early_warning",
    "monte_carlo_sim",
    "portfolio_optimization",
    "bayesian_update",
    "education_delivery",
    "self_improvement",
]


@dataclass
class StrategyStats:
    """Performance statistics for one analysis strategy."""
    name: str
    attempts: int = 0
    successes: int = 0
    total_fitness_gain: float = 0.0
    last_used: Optional[datetime] = None

    def success_rate(self) -> float:
        if self.attempts == 0:
            return 0.0
        return self.successes / self.attempts

    def avg_fitness_gain(self) -> float:
        if self.attempts == 0:
            return 0.0
        return self.total_fitness_gain / self.attempts

    def confidence(self) -> float:
        return min(1.0, self.attempts / MIN_SAMPLES_FOR_STRATEGY)

    def score(self) -> float:
        success_score = self.success_rate()
        gain_score = min(1.0, max(0.0, self.avg_fitness_gain() * 10))
        raw = success_score * 0.5 + gain_score * 0.3
        return raw * self.confidence()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "attempts": self.attempts,
            "successes": self.successes,
            "total_fitness_gain": round(self.total_fitness_gain, 6),
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> StrategyStats:
        return cls(
            name=d["name"],
            attempts=d.get("attempts", 0),
            successes=d.get("successes", 0),
            total_fitness_gain=d.get("total_fitness_gain", 0.0),
            last_used=datetime.fromisoformat(d["last_used"]) if d.get("last_used") else None,
        )


@dataclass
class MetaMetrics:
    """High-level learning health metrics."""
    cycle: int = 0
    avg_strategy_success: float = 0.0
    learning_efficiency: float = 0.0
    problems_detected: list[str] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)


class MetaLearningEngine:
    """
    Tracks analysis strategy effectiveness, detects learning problems,
    and applies meta-fixes to improve jagabot over time.
    """

    def __init__(self, workspace: str | Path | None = None) -> None:
        ws = Path(workspace) if workspace else _DEFAULT_DIR
        ws.mkdir(parents=True, exist_ok=True)
        self._path = ws / "meta_state.json"

        self.strategies: dict[str, StrategyStats] = {}
        self.metrics = MetaMetrics()
        self.cycle_count: int = 0
        self.total_records: int = 0
        self.problems: list[str] = []
        self.fixes: list[str] = []
        self._last_efficiency_base: float = 0.0
        self._last_efficiency_record: int = 0

        self._init_strategies()
        self._load_state()

    def _init_strategies(self) -> None:
        for name in KNOWN_STRATEGIES:
            if name not in self.strategies:
                self.strategies[name] = StrategyStats(name=name)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self.cycle_count = data.get("cycle_count", 0)
            self.total_records = data.get("total_records", 0)
            self.problems = data.get("problems", [])
            self.fixes = data.get("fixes", [])
            self._last_efficiency_base = data.get("last_efficiency_base", 0.0)
            self._last_efficiency_record = data.get("last_efficiency_record", 0)

            for name, sd in data.get("strategies", {}).items():
                self.strategies[name] = StrategyStats.from_dict(sd)

            m = data.get("metrics", {})
            self.metrics = MetaMetrics(
                cycle=m.get("cycle", 0),
                avg_strategy_success=m.get("avg_strategy_success", 0.0),
                learning_efficiency=m.get("learning_efficiency", 0.0),
                problems_detected=m.get("problems_detected", []),
                fixes_applied=m.get("fixes_applied", []),
            )
        except Exception as exc:
            logger.warning("MetaLearningEngine: failed to load state: {}", exc)

    def _save_state(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "cycle_count": self.cycle_count,
                "total_records": self.total_records,
                "problems": self.problems[-20:],
                "fixes": self.fixes[-20:],
                "last_efficiency_base": self._last_efficiency_base,
                "last_efficiency_record": self._last_efficiency_record,
                "strategies": {n: s.to_dict() for n, s in self.strategies.items()},
                "metrics": {
                    "cycle": self.metrics.cycle,
                    "avg_strategy_success": self.metrics.avg_strategy_success,
                    "learning_efficiency": self.metrics.learning_efficiency,
                    "problems_detected": self.metrics.problems_detected,
                    "fixes_applied": self.metrics.fixes_applied,
                },
            }
            self._path.write_text(json.dumps(data, indent=2))
        except Exception as exc:
            logger.warning("MetaLearningEngine: failed to save state: {}", exc)

    # ------------------------------------------------------------------
    # Strategy tracking
    # ------------------------------------------------------------------

    def record_strategy_result(
        self,
        strategy_name: str,
        success: bool,
        fitness_gain: float = 0.0,
    ) -> dict[str, Any]:
        """Record outcome of an analysis strategy. Auto-triggers meta_cycle."""
        if strategy_name not in self.strategies:
            self.strategies[strategy_name] = StrategyStats(name=strategy_name)

        s = self.strategies[strategy_name]
        s.attempts += 1
        if success:
            s.successes += 1
        s.total_fitness_gain += fitness_gain
        s.last_used = datetime.now()
        self.total_records += 1

        logger.debug(
            "MetaLearning: recorded {} {} (gain={:+.4f}, total={})",
            strategy_name, "✅" if success else "❌", fitness_gain, self.total_records,
        )

        cycle_result = None
        if self.total_records % META_CYCLE_INTERVAL == 0:
            cycle_result = self.meta_cycle()

        self._save_state()
        return {
            "strategy": strategy_name,
            "success": success,
            "fitness_gain": round(fitness_gain, 4),
            "total_records": self.total_records,
            "strategy_score": round(s.score(), 4),
            "meta_cycle_triggered": cycle_result is not None,
            "meta_cycle_result": cycle_result,
        }

    def get_strategy_score(self, strategy_name: str) -> float:
        stats = self.strategies.get(strategy_name)
        if not stats:
            return 0.5
        return stats.score()

    def select_best_strategy(self, available: list[str] | None = None) -> dict[str, Any]:
        """Select highest-scoring strategy with explore-exploit balance."""
        if available is None:
            available = KNOWN_STRATEGIES

        under_sampled = [
            s for s in available
            if self.strategies.get(s, StrategyStats(s)).attempts < MIN_SAMPLES_FOR_STRATEGY
        ]
        explored = [s for s in available if s not in under_sampled]

        best_explored: str | None = None
        best_score: float = -1.0
        if explored:
            for name in explored:
                sc = self.get_strategy_score(name)
                if sc > best_score:
                    best_score = sc
                    best_explored = name

        if best_explored is None or best_score < 0.3:
            chosen = random.choice(under_sampled) if under_sampled else random.choice(available)
            return {"strategy": chosen, "reason": "exploration", "score": round(self.get_strategy_score(chosen), 4)}

        return {"strategy": best_explored, "reason": "exploitation", "score": round(best_score, 4)}

    # ------------------------------------------------------------------
    # Problem detection + meta-fixes
    # ------------------------------------------------------------------

    def _get_avg_strategy_success(self) -> float:
        rates = [s.success_rate() for s in self.strategies.values() if s.attempts > 0]
        return sum(rates) / len(rates) if rates else 0.0

    def _get_learning_efficiency(self) -> float:
        records_since = self.total_records - self._last_efficiency_record
        if records_since == 0:
            return 0.0
        gain = self.metrics.avg_strategy_success - self._last_efficiency_base
        return gain / records_since

    def detect_learning_problems(self) -> list[str]:
        """Scan for systemic learning problems."""
        self.metrics.avg_strategy_success = self._get_avg_strategy_success()
        self.metrics.learning_efficiency = self._get_learning_efficiency()

        problems = []

        if self.metrics.avg_strategy_success < LEARNING_PROBLEM_THRESHOLD:
            problems.append("low_strategy_success")

        if self.total_records >= MIN_SAMPLES_FOR_STRATEGY and self.metrics.learning_efficiency < 0.001:
            problems.append("stalled_learning")

        high = [s for s in self.strategies.values()
                if s.attempts >= MIN_SAMPLES_FOR_STRATEGY and s.success_rate() > 0.7]
        low = [s for s in self.strategies.values()
               if s.attempts >= MIN_SAMPLES_FOR_STRATEGY and s.success_rate() < 0.3]
        if len(low) > len(high):
            problems.append("strategy_imbalance")

        if problems:
            self.metrics.problems_detected = problems
            self.problems.extend(problems)

        return problems

    def apply_meta_fix(self, problem: str) -> bool:
        """Apply a targeted fix for a detected learning problem."""
        if problem == "low_strategy_success":
            worst: StrategyStats | None = None
            for s in self.strategies.values():
                if s.attempts >= MIN_SAMPLES_FOR_STRATEGY:
                    if worst is None or s.success_rate() < worst.success_rate():
                        worst = s
            if worst is not None:
                logger.info("MetaLearning: reset '{}' (rate={:.1%})", worst.name, worst.success_rate())
                self.strategies[worst.name] = StrategyStats(name=worst.name)
                self.fixes.append(f"low_strategy_success:{worst.name}@{datetime.now().isoformat()}")
                return True

        elif problem == "stalled_learning":
            # Reset the two least-used strategies to encourage re-exploration
            by_attempts = sorted(self.strategies.values(), key=lambda s: s.attempts)
            reset = 0
            for s in by_attempts[:2]:
                if s.attempts > 0:
                    self.strategies[s.name] = StrategyStats(name=s.name)
                    reset += 1
            if reset:
                self.fixes.append(f"stalled_learning:{reset}@{datetime.now().isoformat()}")
                return True

        elif problem == "strategy_imbalance":
            reset_count = 0
            for name in list(self.strategies):
                s = self.strategies[name]
                if s.attempts >= MIN_SAMPLES_FOR_STRATEGY and s.success_rate() < 0.3:
                    self.strategies[name] = StrategyStats(name=name)
                    reset_count += 1
            if reset_count > 0:
                self.fixes.append(f"strategy_imbalance:{reset_count}@{datetime.now().isoformat()}")
                return True

        return False

    def meta_cycle(self) -> dict[str, Any]:
        """Run one meta-learning analysis cycle."""
        self.cycle_count += 1
        self.metrics.cycle = self.cycle_count

        problems = self.detect_learning_problems()
        fixes_applied = []
        for problem in problems:
            if self.apply_meta_fix(problem):
                fixes_applied.append(problem)

        if fixes_applied:
            self.metrics.fixes_applied = fixes_applied

        self._last_efficiency_base = self.metrics.avg_strategy_success
        self._last_efficiency_record = self.total_records

        result = {
            "cycle": self.cycle_count,
            "problems_detected": problems,
            "fixes_applied": fixes_applied,
            "metrics": {
                "avg_strategy_success": round(self.metrics.avg_strategy_success, 4),
                "learning_efficiency": round(self.metrics.learning_efficiency, 6),
            },
        }
        self._save_state()
        return result

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle_count,
            "total_records": self.total_records,
            "strategies_tracked": len(self.strategies),
            "strategies_with_data": sum(1 for s in self.strategies.values() if s.attempts > 0),
            "problems_detected": self.metrics.problems_detected,
            "fixes_applied": self.metrics.fixes_applied,
            "metrics": {
                "avg_strategy_success": round(self.metrics.avg_strategy_success, 4),
                "learning_efficiency": round(self.metrics.learning_efficiency, 6),
            },
        }

    def get_strategy_rankings(self) -> list[dict]:
        """Return strategies sorted by score descending."""
        rankings = []
        for name, s in self.strategies.items():
            rankings.append({
                "name": name,
                "attempts": s.attempts,
                "successes": s.successes,
                "success_rate": round(s.success_rate(), 4),
                "avg_gain": round(s.avg_fitness_gain(), 4),
                "confidence": round(s.confidence(), 4),
                "score": round(s.score(), 4),
                "last_used": s.last_used.isoformat() if s.last_used else None,
            })
        rankings.sort(key=lambda x: x["score"], reverse=True)
        return rankings
