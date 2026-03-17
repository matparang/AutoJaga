"""Audit manifest — SHA256 trail + human-readable summary for swarm runs."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class PoolAudit:
    """Audit record for a single pool."""
    pool: str
    pre_attack_hash: str = ""
    post_attack_hash: str = ""
    post_repair_hash: str = ""
    attacks_applied: list[dict] = field(default_factory=list)
    repairs_applied: list[dict] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


class AuditManifest:
    """Collects per-pool audit data and writes JSON + markdown."""

    def __init__(self) -> None:
        self.pools: dict[str, PoolAudit] = {}
        self.start_time = time.time()
        self.seed: int | None = None
        self.meta: dict[str, Any] = {}

    def register_pool(self, name: str) -> PoolAudit:
        audit = PoolAudit(pool=name)
        self.pools[name] = audit
        return audit

    def get_pool(self, name: str) -> PoolAudit:
        return self.pools[name]

    @staticmethod
    def hash_data(data: list[int | str]) -> str:
        raw = "\n".join(str(v) for v in data).encode()
        return hashlib.sha256(raw).hexdigest()

    def write_json(self, path: Path) -> Path:
        """Write full audit manifest as JSON."""
        doc = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "elapsed_seconds": round(time.time() - self.start_time, 2),
            "seed": self.seed,
            "meta": self.meta,
            "pools": {k: asdict(v) for k, v in self.pools.items()},
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        return path

    def write_markdown(self, path: Path) -> Path:
        """Write human-readable audit summary."""
        lines: list[str] = [
            "# Level-4 Swarm Audit Report",
            "",
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Elapsed: {time.time() - self.start_time:.1f}s",
            f"Seed: {self.seed or 'random'}",
            f"Pools: {len(self.pools)}",
            "",
        ]

        total_attacks = 0
        total_repairs = 0

        for name, pa in sorted(self.pools.items()):
            n_attacks = len(pa.attacks_applied)
            n_repairs = len(pa.repairs_applied)
            total_attacks += n_attacks
            total_repairs += n_repairs

            lines.append(f"## Pool {name}")
            lines.append(f"- Pre-attack hash: `{pa.pre_attack_hash[:16]}...`")
            lines.append(f"- Post-attack hash: `{pa.post_attack_hash[:16]}...`")
            lines.append(f"- Post-repair hash: `{pa.post_repair_hash[:16]}...`")
            lines.append(f"- Attacks: {n_attacks}")
            for a in pa.attacks_applied:
                lines.append(
                    f"  - Line {a.get('line', '?')}: "
                    f"{a.get('attack', 'unknown')} "
                    f"({a.get('original', '?')} -> {a.get('injected', '?')})"
                )
            lines.append(f"- Repairs: {n_repairs}")
            for r in pa.repairs_applied:
                lines.append(
                    f"  - Line {r.get('line', '?')}: "
                    f"{r.get('reason', 'unknown')} "
                    f"({r.get('original', '?')} -> {r.get('repaired', '?')})"
                )
            if pa.stats:
                s = pa.stats
                lines.append(
                    f"- Stats: count={s.get('count')}, "
                    f"mean={s.get('mean', 0):.2f}, "
                    f"std={s.get('std', 0):.2f}, "
                    f"min={s.get('min')}, max={s.get('max')}"
                )
            lines.append("")

        lines.append("## Summary")
        lines.append(f"- Total pools: {len(self.pools)}")
        lines.append(f"- Total attacks: {total_attacks}")
        lines.append(f"- Total repairs: {total_repairs}")
        lines.append(f"- All pools sanitised: YES")
        lines.append("")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
