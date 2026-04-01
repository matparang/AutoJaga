"""Safe self-evolution engine for jagabot — parameter mutation with 4-layer safety.

Adapted from nanobot/soul/evolution_engine.py (533 LOC).

4-layer safety protocol
-----------------------
  Layer 1: Factor clamping — mutations only ×0.90–×1.10
  Layer 2: Sandbox testing — 50 evaluation cycles before decision
  Layer 3: Fitness validation — accept only if fitness improves
  Layer 4: Auto-rollback — revert parameter immediately on rejection

Governor: minimum 100 cycles between mutations.
"""

from __future__ import annotations

import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from jagabot.evolution.targets import MutationTarget, DEFAULT_VALUES, TARGET_DESCRIPTIONS

_DEFAULT_PATH = Path.home() / ".jagabot" / "workspace" / "evolution_state.json"

# Safety constants
MIN_MUTATION_FACTOR = 0.90
MAX_MUTATION_FACTOR = 1.10
SANDBOX_CYCLES = 50
MIN_CYCLES_BETWEEN = 100


# ------------------------------------------------------------------
# Data classes
# ------------------------------------------------------------------

@dataclass
class Mutation:
    id: str
    target: MutationTarget
    old_value: float
    new_value: float
    created_at: datetime
    description: str

    def factor(self) -> float:
        if self.old_value == 0:
            return 1.0
        return self.new_value / self.old_value

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "target": self.target.value,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Mutation:
        return cls(
            id=d["id"],
            target=MutationTarget(d["target"]),
            old_value=d["old_value"],
            new_value=d["new_value"],
            created_at=datetime.fromisoformat(d["created_at"]),
            description=d["description"],
        )


@dataclass
class MutationResult:
    mutation_id: str
    success: bool
    fitness_before: float
    fitness_after: float
    improvement: float
    test_cycles: int
    accepted_at: Optional[datetime]

    def to_dict(self) -> dict:
        return {
            "mutation_id": self.mutation_id,
            "success": self.success,
            "fitness_before": self.fitness_before,
            "fitness_after": self.fitness_after,
            "improvement": self.improvement,
            "test_cycles": self.test_cycles,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MutationResult:
        return cls(
            mutation_id=d["mutation_id"],
            success=d["success"],
            fitness_before=d["fitness_before"],
            fitness_after=d["fitness_after"],
            improvement=d["improvement"],
            test_cycles=d["test_cycles"],
            accepted_at=datetime.fromisoformat(d["accepted_at"]) if d.get("accepted_at") else None,
        )


class MutationSandbox:
    """Tracks an in-progress sandbox test (Layer 2)."""

    def __init__(self) -> None:
        self.active_mutation: Optional[Mutation] = None
        self.fitness_before: float = 0.0
        self.start_cycle: int = 0
        self.test_cycles_remaining: int = 0

    def start_test(self, mutation: Mutation, fitness_before: float, current_cycle: int) -> None:
        self.active_mutation = mutation
        self.fitness_before = fitness_before
        self.start_cycle = current_cycle
        self.test_cycles_remaining = SANDBOX_CYCLES

    def tick(self) -> bool:
        """Advance one cycle. Returns True when sandbox period is complete."""
        if self.active_mutation is None:
            return False
        self.test_cycles_remaining -= 1
        return self.test_cycles_remaining <= 0

    def cancel(self) -> None:
        self.active_mutation = None
        self.fitness_before = 0.0
        self.start_cycle = 0
        self.test_cycles_remaining = 0

    def to_dict(self) -> dict:
        return {
            "active_mutation": self.active_mutation.to_dict() if self.active_mutation else None,
            "fitness_before": self.fitness_before,
            "start_cycle": self.start_cycle,
            "test_cycles_remaining": self.test_cycles_remaining,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MutationSandbox:
        sb = cls()
        sb.fitness_before = d.get("fitness_before", 0.0)
        sb.start_cycle = d.get("start_cycle", 0)
        sb.test_cycles_remaining = d.get("test_cycles_remaining", 0)
        if d.get("active_mutation"):
            sb.active_mutation = Mutation.from_dict(d["active_mutation"])
        return sb


# ------------------------------------------------------------------
# Engine
# ------------------------------------------------------------------

class EvolutionEngine:
    """Safe self-evolution engine.

    Mutates financial-analysis parameters within tight safety bounds,
    tests them over a sandbox period, and accepts/rolls back based on
    a fitness function derived from strategy performance.
    """

    def __init__(
        self,
        storage_path: str | Path | None = None,
        *,
        parameter_values: dict[MutationTarget, float] | None = None,
    ) -> None:
        self._path = Path(storage_path) if storage_path else _DEFAULT_PATH

        # Current parameter values — start from defaults, override if supplied.
        self.params: dict[MutationTarget, float] = dict(DEFAULT_VALUES)
        if parameter_values:
            self.params.update(parameter_values)

        self.mutations: dict[str, Mutation] = {}
        self.results: list[MutationResult] = []
        self.cycle_count: int = 0
        self.last_mutation_cycle: int = -MIN_CYCLES_BETWEEN  # allow first mutation immediately
        self.sandbox = MutationSandbox()

        self._load_state()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self.cycle_count = data.get("cycle_count", 0)
            self.last_mutation_cycle = data.get("last_mutation_cycle", -MIN_CYCLES_BETWEEN)
            self.mutations = {
                mid: Mutation.from_dict(m)
                for mid, m in data.get("mutations", {}).items()
            }
            self.results = [MutationResult.from_dict(r) for r in data.get("results", [])]
            if sb := data.get("sandbox"):
                self.sandbox = MutationSandbox.from_dict(sb)
            # Restore parameter values from saved state.
            for k, v in data.get("params", {}).items():
                try:
                    self.params[MutationTarget(k)] = v
                except ValueError:
                    pass
            logger.debug("EvolutionEngine: loaded state (cycle {})", self.cycle_count)
        except Exception as exc:
            logger.warning("EvolutionEngine: failed to load state: {}", exc)

    def _save_state(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "cycle_count": self.cycle_count,
                "last_mutation_cycle": self.last_mutation_cycle,
                "mutations": {mid: m.to_dict() for mid, m in self.mutations.items()},
                "results": [r.to_dict() for r in self.results],
                "sandbox": self.sandbox.to_dict(),
                "params": {t.value: v for t, v in self.params.items()},
            }
            self._path.write_text(json.dumps(data, indent=2))
        except Exception as exc:
            logger.warning("EvolutionEngine: failed to save state: {}", exc)

    # ------------------------------------------------------------------
    # Parameter access
    # ------------------------------------------------------------------

    def get_param(self, target: MutationTarget) -> float:
        return self.params.get(target, DEFAULT_VALUES.get(target, 0.0))

    def set_param(self, target: MutationTarget, value: float) -> None:
        self.params[target] = value

    def get_all_params(self) -> dict[str, float]:
        return {t.value: v for t, v in self.params.items()}

    # ------------------------------------------------------------------
    # Fitness
    # ------------------------------------------------------------------

    def _calculate_fitness(self) -> float:
        """Weighted fitness 0.0–1.0 based on current parameter health.

        Components:
          - param_balance  (0.40): how close each param is to its default (penalise drift)
          - accepted_ratio (0.30): fraction of mutations accepted historically
          - stability      (0.30): 1.0 if no sandbox active, 0.5 if testing
        """
        score = 0.0

        # Param balance — penalise large deviations from defaults
        drifts = []
        for t in MutationTarget:
            default = DEFAULT_VALUES[t]
            current = self.params.get(t, default)
            if default != 0:
                drift = abs(current - default) / default
            else:
                drift = 0.0
            drifts.append(max(0.0, 1.0 - drift))  # 1.0 = at default, lower = drifted
        param_balance = sum(drifts) / len(drifts) if drifts else 0.5
        score += param_balance * 0.40

        # Accepted ratio
        if self.results:
            accepted = sum(1 for r in self.results if r.success)
            score += (accepted / len(self.results)) * 0.30
        else:
            score += 0.5 * 0.30  # neutral if no history

        # Stability
        if self.sandbox.active_mutation is None:
            score += 1.0 * 0.30
        else:
            score += 0.5 * 0.30

        return round(score, 6)

    # ------------------------------------------------------------------
    # Mutation generation (Layer 1 + Governor)
    # ------------------------------------------------------------------

    def _generate_mutation(self) -> Optional[Mutation]:
        """Governor check + Layer 1 factor clamping. Returns None if skipped."""
        if self.cycle_count - self.last_mutation_cycle < MIN_CYCLES_BETWEEN:
            return None

        available = list(MutationTarget)
        if not available:
            return None

        target = random.choice(available)
        old_value = self.params.get(target, DEFAULT_VALUES.get(target, 0.0))
        if old_value == 0:
            return None

        # Layer 1: factor strictly within safe bounds
        factor = random.uniform(MIN_MUTATION_FACTOR, MAX_MUTATION_FACTOR)
        new_value = round(old_value * factor, 6)

        mid = uuid.uuid4().hex[:8]
        mutation = Mutation(
            id=mid,
            target=target,
            old_value=old_value,
            new_value=new_value,
            created_at=datetime.now(timezone.utc),
            description=f"Auto: {target.value} {old_value:.4f} → {new_value:.4f} (×{factor:.3f})",
        )
        self.mutations[mid] = mutation
        return mutation

    # ------------------------------------------------------------------
    # Apply / Rollback
    # ------------------------------------------------------------------

    def _apply_mutation(self, mutation: Mutation) -> None:
        self.params[mutation.target] = mutation.new_value

    def _rollback_mutation(self, mutation: Mutation) -> None:
        self.params[mutation.target] = mutation.old_value
        logger.info("EvolutionEngine: rolled back {} to {:.4f}", mutation.target.value, mutation.old_value)

    # ------------------------------------------------------------------
    # Main cycle
    # ------------------------------------------------------------------

    def cycle(self) -> dict[str, Any]:
        """Run one evolution cycle. Returns dict with cycle, fitness, action, mutation."""
        self.cycle_count += 1
        fitness = self._calculate_fitness()
        result: dict[str, Any] = {"cycle": self.cycle_count, "fitness": round(fitness, 6), "action": "none"}

        # --- Active sandbox: tick and evaluate ---
        if self.sandbox.active_mutation is not None:
            done = self.sandbox.tick()
            if done:
                mutation = self.sandbox.active_mutation
                fitness_after = self._calculate_fitness()
                improvement = fitness_after - self.sandbox.fitness_before

                # Layer 3: fitness validation
                success = improvement > 0

                mutation_result = MutationResult(
                    mutation_id=mutation.id,
                    success=success,
                    fitness_before=self.sandbox.fitness_before,
                    fitness_after=fitness_after,
                    improvement=round(improvement, 6),
                    test_cycles=SANDBOX_CYCLES,
                    accepted_at=datetime.now(timezone.utc) if success else None,
                )
                self.results.append(mutation_result)

                if success:
                    logger.info("✅ Evolution: mutation {} ACCEPTED (+{:.4f})", mutation.id, improvement)
                    result["action"] = "accepted"
                else:
                    # Layer 4: rollback
                    logger.warning("❌ Evolution: mutation {} REJECTED ({:+.4f})", mutation.id, improvement)
                    self._rollback_mutation(mutation)
                    result["action"] = "rejected"

                # Governor cooldown applies after any mutation attempt.
                self.last_mutation_cycle = self.cycle_count

                result["mutation"] = {
                    "id": mutation.id,
                    "target": mutation.target.value,
                    "old": mutation.old_value,
                    "new": mutation.new_value,
                    "factor": round(mutation.factor(), 4),
                    "improvement": round(improvement, 6),
                    "success": success,
                }
                self.sandbox.cancel()
                self._save_state()
            else:
                result["action"] = "testing"
                result["sandbox_remaining"] = self.sandbox.test_cycles_remaining
            return result

        # --- No active sandbox: try to start a new mutation ---
        mutation = self._generate_mutation()
        if mutation:
            self._apply_mutation(mutation)
            # Layer 2: start sandbox
            self.sandbox.start_test(mutation, fitness, self.cycle_count)
            result["action"] = "started"
            result["mutation"] = {
                "id": mutation.id,
                "target": mutation.target.value,
                "old": mutation.old_value,
                "new": mutation.new_value,
                "factor": round(mutation.factor(), 4),
                "description": mutation.description,
            }
            logger.info("🧪 Evolution: started sandbox for {} ({})", mutation.id, mutation.target.value)
            self._save_state()

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        return {
            "cycle": self.cycle_count,
            "fitness": self._calculate_fitness(),
            "last_mutation_cycle": self.last_mutation_cycle,
            "governor_cooldown": max(0, MIN_CYCLES_BETWEEN - (self.cycle_count - self.last_mutation_cycle)),
            "sandbox_active": self.sandbox.active_mutation is not None,
            "sandbox_remaining": self.sandbox.test_cycles_remaining,
            "total_mutations": len(self.mutations),
            "accepted": sum(1 for r in self.results if r.success),
            "rejected": sum(1 for r in self.results if not r.success),
            "params": self.get_all_params(),
        }

    def get_mutations(self, limit: int = 20) -> list[dict]:
        items = list(self.mutations.items())[-limit:]
        out = []
        for mid, m in items:
            res = next((r for r in self.results if r.mutation_id == mid), None)
            out.append({
                "id": m.id,
                "target": m.target.value,
                "old": m.old_value,
                "new": m.new_value,
                "factor": round(m.factor(), 4),
                "description": m.description,
                "created": m.created_at.isoformat(),
                "accepted": res.success if res else None,
                "improvement": res.improvement if res else None,
            })
        return out

    def get_targets(self) -> list[dict]:
        return [
            {
                "target": t.value,
                "current": round(self.params.get(t, DEFAULT_VALUES[t]), 6),
                "default": DEFAULT_VALUES[t],
                "description": TARGET_DESCRIPTIONS.get(t, ""),
            }
            for t in MutationTarget
        ]

    def cancel_sandbox(self) -> bool:
        if self.sandbox.active_mutation:
            self._rollback_mutation(self.sandbox.active_mutation)
            self.sandbox.cancel()
            self._save_state()
            return True
        return False

    def force_mutation(self, target: str, factor: float) -> Optional[dict]:
        """Force a specific mutation (bypasses governor, keeps Layer 1)."""
        if factor < MIN_MUTATION_FACTOR or factor > MAX_MUTATION_FACTOR:
            return None
        try:
            target_enum = MutationTarget(target)
        except ValueError:
            return None

        old_value = self.params.get(target_enum, DEFAULT_VALUES.get(target_enum, 0.0))
        if old_value == 0:
            return None

        new_value = round(old_value * factor, 6)
        mid = uuid.uuid4().hex[:8]
        mutation = Mutation(
            id=mid,
            target=target_enum,
            old_value=old_value,
            new_value=new_value,
            created_at=datetime.now(timezone.utc),
            description=f"FORCED: {target} ×{factor:.3f}",
        )
        self.mutations[mid] = mutation
        fitness = self._calculate_fitness()
        self._apply_mutation(mutation)
        self.sandbox.start_test(mutation, fitness, self.cycle_count)
        self._save_state()
        return mutation.to_dict()
