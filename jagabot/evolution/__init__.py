"""Jagabot Evolution — safe self-evolution via parameter mutation.

4-layer safety protocol:
  1. Factor clamping (×0.90–×1.10 only)
  2. Sandbox testing (50 evaluation cycles)
  3. Fitness validation (accept only if improves)
  4. Auto-rollback (revert on rejection)

Usage:
  from jagabot.evolution import EvolutionEngine
  engine = EvolutionEngine()
  result = engine.cycle()  # run one evolution step
"""

from jagabot.evolution.targets import MutationTarget, DEFAULT_VALUES, TARGET_DESCRIPTIONS
from jagabot.evolution.engine import (
    EvolutionEngine,
    Mutation,
    MutationResult,
    MutationSandbox,
    MIN_MUTATION_FACTOR,
    MAX_MUTATION_FACTOR,
    SANDBOX_CYCLES,
    MIN_CYCLES_BETWEEN,
)

__all__ = [
    "EvolutionEngine",
    "Mutation",
    "MutationResult",
    "MutationSandbox",
    "MutationTarget",
    "DEFAULT_VALUES",
    "TARGET_DESCRIPTIONS",
    "MIN_MUTATION_FACTOR",
    "MAX_MUTATION_FACTOR",
    "SANDBOX_CYCLES",
    "MIN_CYCLES_BETWEEN",
]
