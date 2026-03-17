"""NaN / invalid literal injection attack."""
from __future__ import annotations

import random
from jagabot.swarm.attacks.base import AttackBase, RepairLog

_INVALID_VALUES = ["NaN", "nan", "None", "null", "", "undefined", "N/A"]


class NaNInjectionAttack(AttackBase):
    name = "nan_injection"
    description = "Injects NaN and invalid literals into pool data"

    def attack(
        self, pool: list[int], rng: random.Random, intensity: int = 3,
    ) -> tuple[list[str], list[dict]]:
        lines = [str(v) for v in pool]
        log: list[dict] = []
        positions = rng.sample(range(len(pool)), min(intensity, len(pool)))
        for pos in positions:
            bad = rng.choice(_INVALID_VALUES)
            lines[pos] = bad
            log.append({
                "attack": self.name,
                "line": pos,
                "original": pool[pos],
                "injected": bad,
            })
        return lines, log

    def mitigate(
        self,
        lines: list[str],
        pool_name: str,
        rng: random.Random,
    ) -> tuple[list[int], list[RepairLog]]:
        result: list[int] = []
        logs: list[RepairLog] = []
        for i, raw in enumerate(lines):
            stripped = raw.strip()
            try:
                v = int(stripped)
                result.append(v)
            except (ValueError, TypeError):
                replacement = rng.randint(0, 1000)
                logs.append(RepairLog(
                    pool=pool_name, line=i,
                    original=stripped, repaired=replacement,
                    reason="nan_injection",
                ))
                result.append(replacement)
        return result, logs
