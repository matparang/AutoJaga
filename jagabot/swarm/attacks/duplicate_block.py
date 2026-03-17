"""Duplicate-block attack: replaces a range of lines with copies of one line."""
from __future__ import annotations

import random
from jagabot.swarm.attacks.base import AttackBase, RepairLog


class DuplicateBlockAttack(AttackBase):
    name = "duplicate_block"
    description = "Overwrites a block of lines with a single repeated value"

    def attack(
        self, pool: list[int], rng: random.Random, intensity: int = 8,
    ) -> tuple[list[str], list[dict]]:
        lines = [str(v) for v in pool]
        log: list[dict] = []
        block_size = min(intensity, len(pool) // 2)
        if block_size < 2:
            return lines, log
        start = rng.randint(0, len(pool) - block_size)
        source_val = lines[start]
        for offset in range(1, block_size):
            pos = start + offset
            lines[pos] = source_val
            log.append({
                "attack": self.name,
                "line": pos,
                "original": pool[pos],
                "injected": int(source_val),
                "source_line": start,
            })
        return lines, log

    def mitigate(
        self,
        lines: list[str],
        pool_name: str,
        rng: random.Random,
    ) -> tuple[list[int], list[RepairLog]]:
        # Parse all to ints first
        parsed: list[int] = []
        for raw in lines:
            try:
                parsed.append(int(raw.strip()))
            except (ValueError, TypeError):
                parsed.append(rng.randint(0, 1000))

        # Detect low-entropy blocks (consecutive duplicates >= 3)
        logs: list[RepairLog] = []
        result = list(parsed)
        i = 0
        while i < len(result):
            run_start = i
            while i < len(result) - 1 and result[i] == result[i + 1]:
                i += 1
            run_len = i - run_start + 1
            if run_len >= 3:
                # Deduplicate: keep first, resample rest
                for j in range(run_start + 1, run_start + run_len):
                    original = result[j]
                    replacement = rng.randint(0, 1000)
                    logs.append(RepairLog(
                        pool=pool_name, line=j,
                        original=original, repaired=replacement,
                        reason="duplicate_block",
                    ))
                    result[j] = replacement
            i += 1
        return result, logs
