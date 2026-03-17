"""Zero-divide trap attack: injects expressions like '1/0'."""
from __future__ import annotations

import random
from jagabot.swarm.attacks.base import AttackBase, RepairLog

_TRAPS = ["1/0", "0/0", "inf", "-inf", "999/0", "2**999"]


class ZeroDivideAttack(AttackBase):
    name = "zero_divide"
    description = "Injects zero-division expressions and infinity values"

    def attack(
        self, pool: list[int], rng: random.Random, intensity: int = 2,
    ) -> tuple[list[str], list[dict]]:
        lines = [str(v) for v in pool]
        log: list[dict] = []
        positions = rng.sample(range(len(pool)), min(intensity, len(pool)))
        for pos in positions:
            trap = rng.choice(_TRAPS)
            lines[pos] = trap
            log.append({
                "attack": self.name,
                "line": pos,
                "original": pool[pos],
                "injected": trap,
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
            # Detect division expressions or infinity
            if "/" in stripped or "inf" in stripped.lower() or "**" in stripped:
                replacement = rng.randint(0, 1000)
                logs.append(RepairLog(
                    pool=pool_name, line=i,
                    original=stripped, repaired=replacement,
                    reason="zero_divide",
                ))
                result.append(replacement)
                continue
            try:
                v = int(stripped)
                result.append(v)
            except (ValueError, TypeError):
                replacement = rng.randint(0, 1000)
                logs.append(RepairLog(
                    pool=pool_name, line=i,
                    original=stripped, repaired=replacement,
                    reason="zero_divide_fallback",
                ))
                result.append(replacement)
        return result, logs
