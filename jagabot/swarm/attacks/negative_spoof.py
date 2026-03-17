"""Negative-spoof attack: injects negative numbers into a pool."""
from __future__ import annotations

import random
from jagabot.swarm.attacks.base import AttackBase, RepairLog


class NegativeSpoofAttack(AttackBase):
    name = "negative_spoof"
    description = "Injects negative numbers that shouldn't exist in [0, 1000] pools"

    def attack(
        self, pool: list[int], rng: random.Random, intensity: int = 3,
    ) -> tuple[list[str], list[dict]]:
        lines = [str(v) for v in pool]
        log: list[dict] = []
        positions = rng.sample(range(len(pool)), min(intensity, len(pool)))
        for pos in positions:
            neg = -rng.randint(100, 9999)
            lines[pos] = str(neg)
            log.append({
                "attack": self.name,
                "line": pos,
                "original": pool[pos],
                "injected": neg,
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
            try:
                v = int(raw.strip())
            except (ValueError, TypeError):
                v = -1  # will be caught below
            if v < 0:
                replacement = rng.randint(0, 1000)
                logs.append(RepairLog(
                    pool=pool_name, line=i,
                    original=raw.strip(), repaired=replacement,
                    reason="negative_spoof",
                ))
                result.append(replacement)
            else:
                result.append(v)
        return result, logs
