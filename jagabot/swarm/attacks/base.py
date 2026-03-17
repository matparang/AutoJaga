"""Base class for pluggable swarm attacks."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RepairLog:
    """Structured log of a single repair action."""
    pool: str
    line: int
    original: Any
    repaired: Any
    reason: str


class AttackBase:
    """Abstract base for swarm attack plug-ins.

    Subclasses implement ``attack()`` and ``mitigate()``.
    """

    name: str = "base"
    description: str = "Base attack"

    def attack(
        self, pool: list[int], rng: random.Random, intensity: int = 3,
    ) -> tuple[list[str], list[dict]]:
        """Apply adversarial corruption to *pool* (list of ints).

        Returns:
            (corrupted_lines, attack_log)
            - corrupted_lines: list of string values (some may be invalid)
            - attack_log: list of dicts describing each injection
        """
        raise NotImplementedError

    def mitigate(
        self,
        lines: list[str],
        pool_name: str,
        rng: random.Random,
    ) -> tuple[list[int], list[RepairLog]]:
        """Repair corrupted *lines* back to valid integers.

        Returns:
            (repaired_ints, repair_logs)
        """
        raise NotImplementedError
