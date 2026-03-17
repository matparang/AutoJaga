"""
Offline Swarm Runner — Level-4 swarm test with pluggable attacks.

Generates pools of random integers, applies adversarial attacks via the
attack registry, repairs all corruption, verifies integrity, computes
stats, and writes a full audit manifest + report.

Can run standalone (``python -m jagabot.swarm.offline_swarm``) or be
imported and called from the TUI / agent tool.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from jagabot.swarm.attacks import ALL_ATTACKS, AttackBase
from jagabot.swarm.audit_manifest import AuditManifest


# ── Configuration ────────────────────────────────────────────────

DEFAULT_AGENTS = ["A", "B", "C", "D"]
POOLS_PER_AGENT = 3
POOL_SIZE = 50
POOL_RANGE = (0, 1000)


# ── Result dataclass ─────────────────────────────────────────────

class SwarmResult:
    """Outcome of a full offline swarm run."""

    def __init__(self) -> None:
        self.success: bool = False
        self.pools_generated: int = 0
        self.attacks_applied: int = 0
        self.repairs_made: int = 0
        self.report_path: Path | None = None
        self.manifest_path: Path | None = None
        self.markdown_path: Path | None = None
        self.elapsed: float = 0.0
        self.pool_stats: dict[str, dict[str, Any]] = {}
        self.overall_stats: dict[str, Any] = {}

    def summary(self) -> str:
        lines = [
            "Level-4 Offline Swarm Test Report",
            "=" * 40,
            f"Pools: {self.pools_generated}",
            f"Attacks applied: {self.attacks_applied}",
            f"Repairs made: {self.repairs_made}",
            f"Elapsed: {self.elapsed:.1f}s",
            "",
        ]
        if self.overall_stats:
            s = self.overall_stats
            lines.append(
                f"Overall: count={s.get('count')}, "
                f"mean={s.get('mean', 0):.2f}, "
                f"std={s.get('std', 0):.2f}, "
                f"min={s.get('min')}, max={s.get('max')}, "
                f"div_by_7={s.get('div_by_7')}"
            )
        lines.append(f"\nReport: {self.report_path}")
        lines.append(f"Manifest: {self.manifest_path}")
        return "\n".join(lines)


# ── Main runner ──────────────────────────────────────────────────

def run_offline_swarm(
    workspace: Path,
    seed: int | None = None,
    agents: list[str] | None = None,
    pools_per_agent: int = POOLS_PER_AGENT,
    pool_size: int = POOL_SIZE,
    attacks_per_pool: int = 2,
    dry_run: bool = False,
    attack_summary_callback: Any = None,
) -> SwarmResult:
    """Run a full Level-4 offline swarm test.

    Args:
        workspace: Directory for all output files.
        seed: Reproducibility seed (None = random).
        agents: Agent labels (default: A, B, C, D).
        pools_per_agent: Number of pools each agent manages.
        pool_size: Number of integers per pool.
        attacks_per_pool: Number of attack types applied per pool.
        dry_run: If True, simulate without writing files.
        attack_summary_callback: Optional callable(str) for live status.
    """
    t0 = time.time()
    rng = random.Random(seed)
    agents = agents or list(DEFAULT_AGENTS)

    out_dir = workspace / "swarm_test"
    audit_dir = out_dir / "audit"
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        audit_dir.mkdir(parents=True, exist_ok=True)

    manifest = AuditManifest()
    manifest.seed = seed
    manifest.meta = {
        "agents": agents,
        "pools_per_agent": pools_per_agent,
        "pool_size": pool_size,
        "attacks_per_pool": attacks_per_pool,
        "dry_run": dry_run,
    }

    result = SwarmResult()
    all_repaired: dict[str, list[int]] = {}
    available_attacks = [cls() for cls in ALL_ATTACKS]

    # ── Step 1: Generate pools ───────────────────────────────────
    pool_names: list[str] = []
    original_pools: dict[str, list[int]] = {}

    for agent in agents:
        for pidx in range(1, pools_per_agent + 1):
            name = f"{agent}_{pidx}"
            pool_names.append(name)
            pool = [rng.randint(*POOL_RANGE) for _ in range(pool_size)]
            original_pools[name] = pool

            pa = manifest.register_pool(name)
            pa.pre_attack_hash = manifest.hash_data(pool)

            if not dry_run:
                _write_pool(out_dir / f"{name}.txt", pool)

    result.pools_generated = len(pool_names)
    _notify(attack_summary_callback, f"Generated {len(pool_names)} pools")

    # ── Step 2: Apply attacks ────────────────────────────────────
    attacked_lines: dict[str, list[str]] = {}

    for name in pool_names:
        pool = list(original_pools[name])
        pa = manifest.get_pool(name)

        # Pick random subset of attacks for this pool
        chosen = rng.sample(
            available_attacks,
            min(attacks_per_pool, len(available_attacks)),
        )

        lines = [str(v) for v in pool]
        for atk in chosen:
            # Safe-parse: prior attacks may have corrupted some lines
            safe_ints = []
            for x in lines:
                try:
                    safe_ints.append(int(x.strip()))
                except (ValueError, TypeError):
                    safe_ints.append(rng.randint(0, 1000))
            lines, atk_log = atk.attack(
                safe_ints, rng, intensity=rng.randint(2, 5),
            )
            pa.attacks_applied.extend(atk_log)
            result.attacks_applied += len(atk_log)

        attacked_lines[name] = lines
        pa.post_attack_hash = manifest.hash_data(lines)

        if not dry_run:
            _write_lines(out_dir / f"{name}.txt", lines)

    _notify(attack_summary_callback, f"Applied {result.attacks_applied} attacks")

    if attack_summary_callback and dry_run:
        # In dry-run, print attack summary and stop
        for name in pool_names:
            pa = manifest.get_pool(name)
            for a in pa.attacks_applied:
                _notify(
                    attack_summary_callback,
                    f"  [{name}] {a['attack']} line {a['line']}: "
                    f"{a['original']} -> {a['injected']}",
                )
        result.elapsed = time.time() - t0
        return result

    # ── Step 3: Repair pools ─────────────────────────────────────
    for name in pool_names:
        lines = attacked_lines[name]
        pa = manifest.get_pool(name)

        # Apply ALL mitigations in sequence (each handles its own type)
        for atk in available_attacks:
            repaired_ints, repair_logs = atk.mitigate(lines, name, rng)
            if repair_logs:
                pa.repairs_applied.extend([asdict(r) for r in repair_logs])
                result.repairs_made += len(repair_logs)
            lines = [str(v) for v in repaired_ints]

        final_ints = [int(x) for x in lines]
        # Ensure pool_size (resample if dedup shortened)
        while len(final_ints) < pool_size:
            final_ints.append(rng.randint(*POOL_RANGE))
        final_ints = final_ints[:pool_size]

        all_repaired[name] = final_ints
        pa.post_repair_hash = manifest.hash_data(final_ints)

        if not dry_run:
            _write_pool(out_dir / f"repaired_{name}.txt", final_ints)

    _notify(attack_summary_callback, f"Repaired {result.repairs_made} corruptions")

    # ── Step 4: Compute stats ────────────────────────────────────
    total_count = 0
    total_sum = 0
    total_sum_sq = 0
    global_min = float("inf")
    global_max = float("-inf")
    div7 = 0

    for name in pool_names:
        arr = all_repaired[name]
        pa = manifest.get_pool(name)
        n = len(arr)
        s = sum(arr)
        ss = sum(x * x for x in arr)
        mn = min(arr)
        mx = max(arr)
        mean = s / n if n else 0
        std = math.sqrt(ss / n - mean * mean) if n else 0

        pa.stats = {
            "count": n, "mean": round(mean, 2), "std": round(std, 2),
            "min": mn, "max": mx,
        }
        result.pool_stats[name] = pa.stats

        total_count += n
        total_sum += s
        total_sum_sq += ss
        global_min = min(global_min, mn)
        global_max = max(global_max, mx)
        div7 += sum(1 for x in arr if x % 7 == 0)

    overall_mean = total_sum / total_count if total_count else 0
    overall_std = (
        math.sqrt(total_sum_sq / total_count - overall_mean * overall_mean)
        if total_count else 0
    )
    result.overall_stats = {
        "count": total_count,
        "mean": round(overall_mean, 2),
        "std": round(overall_std, 2),
        "min": int(global_min) if global_min != float("inf") else 0,
        "max": int(global_max) if global_max != float("-inf") else 0,
        "div_by_7": div7,
    }

    # ── Step 5: Write outputs ────────────────────────────────────
    if not dry_run:
        report_path = out_dir / "final_summary_swarm.txt"
        report_path.write_text(result.summary(), encoding="utf-8")
        result.report_path = report_path

        manifest_path = audit_dir / "audit_manifest.json"
        manifest.write_json(manifest_path)
        result.manifest_path = manifest_path

        md_path = audit_dir / "audit_report.md"
        manifest.write_markdown(md_path)
        result.markdown_path = md_path

        # SHA256 checksums file
        checksums_path = audit_dir / "checksums.sha256"
        ck_lines = []
        for name in pool_names:
            pa = manifest.get_pool(name)
            ck_lines.append(f"{pa.post_repair_hash}  repaired_{name}.txt")
        checksums_path.write_text("\n".join(ck_lines) + "\n", encoding="utf-8")

    result.success = True
    result.elapsed = time.time() - t0

    _notify(
        attack_summary_callback,
        f"COMPLETE: {result.pools_generated} pools, "
        f"{result.attacks_applied} attacks, "
        f"{result.repairs_made} repairs, "
        f"{result.elapsed:.1f}s",
    )

    return result


# ── Helpers ──────────────────────────────────────────────────────

def _write_pool(path: Path, data: list[int]) -> None:
    path.write_text("\n".join(str(v) for v in data) + "\n", encoding="utf-8")


def _write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _notify(cb: Any, msg: str) -> None:
    if cb:
        cb(msg)


# ── CLI entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Level-4 Offline Swarm Test")
    parser.add_argument("--workspace", default=".", help="Output directory")
    parser.add_argument("--seed", type=int, default=None, help="Reproducibility seed")
    parser.add_argument("--pools", type=int, default=12, help="Total pools (agents*pools_per_agent)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing files")
    parser.add_argument("--attack-summary", action="store_true", help="Print attack details")
    args = parser.parse_args()

    agents_count = 4
    ppa = max(1, args.pools // agents_count)

    def _print_status(msg: str) -> None:
        print(f"[SWARM] {msg}")

    cb = _print_status if args.attack_summary else None

    res = run_offline_swarm(
        workspace=Path(args.workspace),
        seed=args.seed,
        pools_per_agent=ppa,
        dry_run=args.dry_run,
        attack_summary_callback=cb,
    )

    print()
    print(res.summary())
    sys.exit(0 if res.success else 1)
