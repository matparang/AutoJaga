"""Financial mutation targets for the EvolutionEngine.

Each target maps to a tunable parameter in jagabot's analysis pipeline.
The engine mutates these within tight safety bounds (×0.90–×1.10) to
self-optimise over time.
"""

from __future__ import annotations

from enum import Enum


class MutationTarget(str, Enum):
    """Tunable financial-analysis parameters."""

    RISK_THRESHOLD = "risk_threshold"
    VOLATILITY_WEIGHT = "volatility_weight"
    CORRELATION_THRESHOLD = "correlation_threshold"
    PERSPECTIVE_WEIGHT = "perspective_weight"
    LEARNING_RATE = "learning_rate"


DEFAULT_VALUES: dict[MutationTarget, float] = {
    MutationTarget.RISK_THRESHOLD: 0.95,
    MutationTarget.VOLATILITY_WEIGHT: 0.30,
    MutationTarget.CORRELATION_THRESHOLD: 0.60,
    MutationTarget.PERSPECTIVE_WEIGHT: 0.35,
    MutationTarget.LEARNING_RATE: 0.40,
}

TARGET_DESCRIPTIONS: dict[MutationTarget, str] = {
    MutationTarget.RISK_THRESHOLD: "VaR confidence level (0.90–0.99)",
    MutationTarget.VOLATILITY_WEIGHT: "CV pattern classification weight",
    MutationTarget.CORRELATION_THRESHOLD: "Minimum correlation to trigger alerts",
    MutationTarget.PERSPECTIVE_WEIGHT: "K3 bear/buffet weight balance",
    MutationTarget.LEARNING_RATE: "MetaLearning problem-detection threshold",
}
