"""
Engine Correlation Monitor

Records which engines fire per turn, their outputs, and timing.
Builds correlation data over time to identify:
  - Which engines always fire together
  - Which engines produce redundant output
  - Which engines never fire (dead weight)
  - Which combinations produce highest quality scores

Data stored in SQLite for analysis.
"""

from __future__ import annotations
import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from loguru import logger


@dataclass
class EngineEvent:
    """One engine firing event."""
    engine:     str
    fired:      bool
    duration_ms: float
    output_size: int    # chars of output
    output_hash: str    # first 8 chars for dedup detection
    quality:    float   # 0-1, from session_writer


@dataclass
class TurnRecord:
    """Full record of one agent turn."""
    turn_id:     str
    query:       str
    domain:      str
    complexity:  str
    events:      list[EngineEvent] = field(default_factory=list)
    quality:     float = 0.0
    bdi_score:   float = 0.0
    tokens_used: int   = 0
    started_at:  float = field(default_factory=time.time)


class EngineCorrelationMonitor:
    """
    Monitors engine firing patterns and builds correlation data.
    """

    ENGINES = [
        # Routing
        "fluid_dispatcher", "complexity_router", "model_switchboard",
        # Reasoning
        "belief_engine", "cognitive_stack", "means_end",
        # Memory
        "memory_manager", "memory_fleet", "context_builder",
        # Quality
        "epistemic_auditor", "response_auditor", "verifier_evaluator",
        # Learning
        "brier_scorer", "meta_learning", "k1_bayesian",
        # Safety
        "stake_escalation", "selective_guardrails", "behavior_monitor",
        # Tools
        "tool_filter", "cci", "jit_schema", "task_state_manager",
        # Performance
        "bdi_scorecard", "performance_tracker", "calibration_engine",
    ]

    def __init__(self, workspace: Path):
        self.workspace  = Path(workspace)
        self.db_path    = self.workspace / "memory" / "engine_monitor.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._current:  TurnRecord | None = None
        self._fired:    set[str] = set()
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS turns (
                id          TEXT PRIMARY KEY,
                query       TEXT,
                domain      TEXT,
                complexity  TEXT,
                quality     REAL,
                bdi_score   REAL,
                tokens_used INTEGER,
                engines_fired TEXT,
                started_at  TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS engine_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                turn_id     TEXT,
                engine      TEXT,
                fired       INTEGER,
                duration_ms REAL,
                output_size INTEGER,
                recorded_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS correlations (
                engine_a    TEXT,
                engine_b    TEXT,
                co_fires    INTEGER DEFAULT 0,
                total_turns INTEGER DEFAULT 0,
                correlation REAL DEFAULT 0.0,
                updated_at  TEXT,
                PRIMARY KEY (engine_a, engine_b)
            )
        """)
        conn.commit()
        conn.close()

    def start_turn(self, query: str, domain: str, complexity: str) -> None:
        """Start monitoring a new turn."""
        self._current = TurnRecord(
            turn_id    = f"{int(time.time())}_{hash(query) % 10000:04d}",
            query      = query[:100],
            domain     = domain,
            complexity = complexity,
        )
        self._fired = set()
        logger.debug(f"EngineMonitor: turn started {self._current.turn_id}")

    def record_engine(
        self,
        engine:      str,
        fired:       bool = True,
        duration_ms: float = 0.0,
        output_size: int = 0,
    ) -> None:
        """Record an engine firing event."""
        if not self._current:
            return
        if fired:
            self._fired.add(engine)
        event = EngineEvent(
            engine      = engine,
            fired       = fired,
            duration_ms = duration_ms,
            output_size = output_size,
            output_hash = "",
            quality     = 0.0,
        )
        self._current.events.append(event)

    def finish_turn(
        self,
        quality:     float = 0.0,
        bdi_score:   float = 0.0,
        tokens_used: int = 0,
    ) -> None:
        """Finish turn and save to database."""
        if not self._current:
            return

        self._current.quality     = quality
        self._current.bdi_score   = bdi_score
        self._current.tokens_used = tokens_used

        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO turns
                (id, query, domain, complexity, quality, bdi_score,
                 tokens_used, engines_fired, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self._current.turn_id,
                self._current.query,
                self._current.domain,
                self._current.complexity,
                quality, bdi_score, tokens_used,
                json.dumps(sorted(self._fired)),
                datetime.now().isoformat(),
            ))
            for event in self._current.events:
                conn.execute("""
                    INSERT INTO engine_events
                    (turn_id, engine, fired, duration_ms, output_size, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    self._current.turn_id,
                    event.engine, int(event.fired),
                    event.duration_ms, event.output_size,
                    datetime.now().isoformat(),
                ))
            conn.commit()
            conn.close()
            self._update_correlations()
        except Exception as e:
            logger.debug(f"EngineMonitor: save failed: {e}")

        logger.debug(
            f"EngineMonitor: turn complete — "
            f"{len(self._fired)} engines fired, "
            f"quality={quality:.2f}, bdi={bdi_score:.1f}"
        )
        self._current = None

    def _update_correlations(self) -> None:
        """Update co-firing correlation matrix."""
        try:
            conn   = sqlite3.connect(self.db_path)
            turns  = conn.execute(
                "SELECT engines_fired FROM turns ORDER BY started_at DESC LIMIT 100"
            ).fetchall()
            conn.close()

            if len(turns) < 5:
                return

            # Build co-firing matrix
            from collections import defaultdict
            co_fires: dict[tuple, int] = defaultdict(int)
            total_turns = len(turns)

            for (fired_json,) in turns:
                fired = set(json.loads(fired_json or "[]"))
                fired_list = sorted(fired)
                for i, a in enumerate(fired_list):
                    for b in fired_list[i+1:]:
                        co_fires[(a, b)] += 1

            # Save correlations
            conn = sqlite3.connect(self.db_path)
            for (a, b), count in co_fires.items():
                corr = count / total_turns
                conn.execute("""
                    INSERT INTO correlations (engine_a, engine_b, co_fires, total_turns, correlation, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(engine_a, engine_b) DO UPDATE SET
                        co_fires=excluded.co_fires,
                        total_turns=excluded.total_turns,
                        correlation=excluded.correlation,
                        updated_at=excluded.updated_at
                """, (a, b, count, total_turns, round(corr, 3), datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"EngineMonitor: correlation update failed: {e}")

    def get_report(self) -> dict:
        """Get engine firing report."""
        try:
            conn = sqlite3.connect(self.db_path)
            total = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
            if total == 0:
                conn.close()
                return {"total_turns": 0}

            # Engine firing rates
            rates = {}
            for engine in self.ENGINES:
                count = conn.execute("""
                    SELECT COUNT(*) FROM engine_events
                    WHERE engine=? AND fired=1
                """, (engine,)).fetchone()[0]
                rates[engine] = round(count / total, 2) if total > 0 else 0

            # Top correlations
            top_corr = conn.execute("""
                SELECT engine_a, engine_b, correlation, co_fires
                FROM correlations
                ORDER BY correlation DESC LIMIT 10
            """).fetchall()

            # Never-fired engines
            never = [e for e, r in rates.items() if r == 0]

            # Always-fired engines
            always = [e for e, r in rates.items() if r >= 0.9]

            # Quality by complexity
            quality = conn.execute("""
                SELECT complexity, AVG(quality), COUNT(*)
                FROM turns GROUP BY complexity
            """).fetchall()

            conn.close()

            return {
                "total_turns":   total,
                "firing_rates":  rates,
                "top_correlations": [
                    {"a": a, "b": b, "corr": c, "co_fires": f}
                    for a, b, c, f in top_corr
                ],
                "never_fired":   never,
                "always_fired":  always,
                "quality_by_complexity": {
                    row[0]: {"avg_quality": round(row[1], 2), "turns": row[2]}
                    for row in quality
                },
            }
        except Exception as e:
            return {"error": str(e)}

    def print_report(self) -> None:
        """Print gamified engine correlation report."""
        report = self.get_report()
        total  = report.get("total_turns", 0)

        print("\n" + "═" * 60)
        print("  🧠 JAGABOT ENGINE CORRELATION MONITOR")
        print("═" * 60)

        if total == 0:
            print("\n  📭 No data yet — run some queries first!")
            print("  Tip: Try 'jagabot agent' and ask a few questions.")
            print("═" * 60)
            return

        # Header stats
        rates  = report.get("firing_rates", {})
        always = report.get("always_fired", [])
        never  = report.get("never_fired", [])
        active = [e for e, r in rates.items() if 0 < r < 0.9]

        print(f"\n  📊 Total turns analyzed: {total}")
        print(f"  🔥 Always firing:  {len(always)} engines")
        print(f"  ⚡ Sometimes fire:  {len(active)} engines")
        print(f"  💀 Never fired:    {len(never)} engines")

        # Quality by complexity
        qbc = report.get("quality_by_complexity", {})
        if qbc:
            print("\n" + "─" * 60)
            print("  📈 QUALITY BY COMPLEXITY")
            print("─" * 60)
            for complexity, stats in sorted(qbc.items()):
                q = stats["avg_quality"]
                t = stats["turns"]
                bar = "█" * int(q * 20) + "░" * (20 - int(q * 20))
                grade = "S" if q >= 0.9 else "A" if q >= 0.8 else "B" if q >= 0.7 else "C" if q >= 0.6 else "D"
                print(f"  [{grade}] {complexity:<12} [{bar}] {q:.0%} ({t} turns)")

        # Engine firing rates — sorted by rate
        print("\n" + "─" * 60)
        print("  ⚙️  ENGINE FIRING RATES")
        print("─" * 60)
        sorted_rates = sorted(rates.items(), key=lambda x: x[1], reverse=True)
        for engine, rate in sorted_rates:
            if rate == 0:
                continue
            bar_len = int(rate * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            if rate >= 0.9:
                icon = "🔥"
            elif rate >= 0.5:
                icon = "⚡"
            elif rate >= 0.1:
                icon = "💤"
            else:
                icon = "❌"
            print(f"  {icon} {engine:<28} [{bar}] {rate:.0%}")

        # Never fired
        if never:
            print("\n" + "─" * 60)
            print("  💀 NEVER FIRED (optimization candidates)")
            print("─" * 60)
            for e in never:
                print(f"  ✂️  {e}")

        # Top correlations
        top_corr = report.get("top_correlations", [])
        if top_corr:
            print("\n" + "─" * 60)
            print("  🔗 TOP ENGINE CORRELATIONS")
            print("─" * 60)
            for c in top_corr[:8]:
                corr = c["corr"]
                bar  = "█" * int(corr * 15) + "░" * (15 - int(corr * 15))
                merge_hint = " ← MERGE CANDIDATE" if corr >= 0.95 else ""
                print(f"  {c['a']:<22} ↔ {c['b']:<22} [{bar}] {corr:.0%}{merge_hint}")

        # Optimization score
        opt_score = 100 - (len(never) * 3) - (len(always) * 0)
        opt_score = max(0, min(100, opt_score))
        grade = "S" if opt_score >= 90 else "A" if opt_score >= 80 else "B" if opt_score >= 70 else "C"
        print("\n" + "─" * 60)
        print(f"  🏆 OPTIMIZATION SCORE: {opt_score}/100 (Grade {grade})")
        if never:
            print(f"  💡 Tip: Remove {len(never)} dead engines to improve score")
        if any(c["corr"] >= 0.95 for c in top_corr):
            print(f"  💡 Tip: Merge highly correlated engine pairs")
        print("═" * 60 + "\n")
