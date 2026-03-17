# jagabot/agent/session_index.py
"""
SessionIndex — Solves "which session do I continue?"

Builds a searchable index of all past research sessions.
Shows reminder at session start with recent topics,
pending outcomes, and quality scores.

Storage: ~/.jagabot/workspace/memory/session_index.json

Wire into loop.py __init__:
    from jagabot.agent.session_index import SessionIndex
    self.session_index = SessionIndex(workspace)

Wire into loop.py _process_message (FIRST message only):
    if self._is_first_message:
        reminder = self.session_index.get_startup_reminder()
        if reminder:
            self._inject_system(reminder)
        self._is_first_message = False

Wire into session_writer.py save() at end:
    self.session_index.update(
        session_key=session_key,
        query=query,
        content=content,
        quality=quality,
        tools_used=tools_used,
    )
"""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Topic detection keywords ────────────────────────────────────────
TOPIC_MAP = {
    "causal":      ["ipw", "causal", "confounder", "ate", "propensity"],
    "financial":   ["stock", "portfolio", "var", "cvar", "margin", "equity",
                    "monte carlo", "risk", "volatility", "vix"],
    "healthcare":  ["hospital", "patient", "clinical", "hipaa", "gdpr",
                    "counselor", "mental health", "therapy"],
    "research":    ["hypothesis", "experiment", "research", "study",
                    "literature", "paper", "quantum", "ai"],
    "engineering": ["code", "agent", "tool", "harness", "loop", "tui",
                    "kernel", "engine", "context", "session"],
    "ideas":       ["brainstorm", "idea", "creative", "novel", "strategy",
                    "innovative", "out of the box"],
}


@dataclass
class SessionEntry:
    session_key:      str
    topic:            str
    topic_tag:        str
    first_query:      str
    last_query:       str
    query_count:      int        = 0
    quality_avg:      float      = 0.0
    tools_used:       list       = field(default_factory=list)
    pending_outcomes: int        = 0
    created_at:       str        = ""
    last_active:      str        = ""
    summary:          str        = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SessionEntry":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class SessionIndex:
    """
    Maintains a searchable index of all past research sessions.
    Generates startup reminders showing recent work and pending items.
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace   = Path(workspace)
        self.memory_dir  = self.workspace / "memory"
        self.index_file  = self.memory_dir / "session_index.json"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_index()

    # ── Public API ──────────────────────────────────────────────────

    def update(
        self,
        session_key:      str,
        query:            str,
        content:          str,
        quality:          float      = 0.0,
        tools_used:       list       = None,
        pending_outcomes: int        = 0,
    ) -> None:
        """Update index entry for this session."""
        index = self._load()
        now   = datetime.now().isoformat()

        if session_key in index:
            entry = SessionEntry.from_dict(index[session_key])
            # Update existing
            entry.last_query       = query[:80]
            entry.query_count     += 1
            entry.last_active      = now
            entry.pending_outcomes = pending_outcomes
            # Rolling average quality
            entry.quality_avg = round(
                (entry.quality_avg * (entry.query_count - 1) + quality)
                / entry.query_count, 2
            )
            # Accumulate unique tools
            for t in (tools_used or []):
                if t not in entry.tools_used:
                    entry.tools_used.append(t)
            # Update summary from content
            entry.summary = self._extract_summary(content)
        else:
            # New entry
            tag = self._detect_topic(query + " " + content)
            entry = SessionEntry(
                session_key      = session_key,
                topic            = query[:80],
                topic_tag        = tag,
                first_query      = query[:80],
                last_query       = query[:80],
                query_count      = 1,
                quality_avg      = quality,
                tools_used       = list(set(tools_used or [])),
                pending_outcomes = pending_outcomes,
                created_at       = now,
                last_active      = now,
                summary          = self._extract_summary(content),
            )

        index[session_key] = entry.to_dict()
        self._save(index)

    def get_startup_reminder(self, max_sessions: int = 5) -> str:
        """
        Generate startup reminder showing recent sessions.
        Inject this into system context at session start.
        Returns empty string if nothing worth showing.
        """
        index   = self._load()
        if not index:
            return ""

        # Sort by last_active descending
        entries = sorted(
            [SessionEntry.from_dict(v) for v in index.values()],
            key=lambda e: e.last_active,
            reverse=True
        )[:max_sessions]

        if not entries:
            return ""

        lines = [
            "## 📚 Recent Research Sessions",
            "",
        ]

        has_pending = False
        for i, e in enumerate(entries, 1):
            ts = self._format_time(e.last_active)
            quality_label = (
                "🟢" if e.quality_avg >= 0.8
                else "🟡" if e.quality_avg >= 0.6
                else "🔴"
            )
            pending_str = (
                f" ⚠️ {e.pending_outcomes} pending outcome(s)"
                if e.pending_outcomes > 0 else ""
            )
            lines.append(
                f"  [{i}] {quality_label} [{e.topic_tag}] "
                f"{e.topic[:50]} ({ts}){pending_str}"
            )
            if e.summary:
                lines.append(f"      → {e.summary[:80]}")
            if e.pending_outcomes > 0:
                has_pending = True

        lines.append("")

        if has_pending:
            lines.append(
                "⚠️ You have pending research outcomes to verify. "
                "Say 'show pending outcomes' to review them."
            )
            lines.append("")

        lines.append(
            "To continue a session, mention the topic. "
            "To start fresh, just ask your question."
        )

        return "\n".join(lines)

    def search(self, query: str) -> list[SessionEntry]:
        """Find sessions relevant to a query."""
        index   = self._load()
        q_lower = query.lower()
        results = []

        for entry_dict in index.values():
            entry = SessionEntry.from_dict(entry_dict)
            # Check topic, first_query, last_query, summary
            searchable = (
                f"{entry.topic} {entry.first_query} "
                f"{entry.last_query} {entry.summary} {entry.topic_tag}"
            ).lower()
            if any(word in searchable for word in q_lower.split()):
                results.append(entry)

        return sorted(results, key=lambda e: e.last_active, reverse=True)

    def get_stats(self) -> dict:
        """Return index statistics."""
        index = self._load()
        if not index:
            return {"total": 0}

        entries    = [SessionEntry.from_dict(v) for v in index.values()]
        total      = len(entries)
        pending    = sum(e.pending_outcomes for e in entries)
        avg_qual   = sum(e.quality_avg for e in entries) / total
        tags       = {}
        for e in entries:
            tags[e.topic_tag] = tags.get(e.topic_tag, 0) + 1

        return {
            "total_sessions":    total,
            "pending_outcomes":  pending,
            "avg_quality":       round(avg_qual, 2),
            "topics":            tags,
            "most_used_tools":   self._top_tools(entries),
        }

    # ── Internal helpers ────────────────────────────────────────────

    def _detect_topic(self, text: str) -> str:
        """Detect topic tag from text."""
        text_lower = text.lower()
        scores     = {}
        for tag, keywords in TOPIC_MAP.items():
            scores[tag] = sum(1 for kw in keywords if kw in text_lower)
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

    def _extract_summary(self, content: str) -> str:
        """Extract a short summary from agent output."""
        # Look for conclusion signals
        for marker in ["✅", "conclusion:", "result:", "finding:", "→"]:
            idx = content.lower().find(marker.lower())
            if idx > 0:
                snippet = content[idx:idx+100].strip()
                snippet = re.sub(r'\s+', ' ', snippet)
                return snippet[:80]
        # Fallback: first meaningful sentence
        sentences = content.split('.')
        for s in sentences:
            s = s.strip()
            if len(s) > 20:
                return s[:80]
        return ""

    def _format_time(self, iso: str) -> str:
        """Format ISO timestamp as human-readable."""
        try:
            dt   = datetime.fromisoformat(iso)
            now  = datetime.now()
            diff = now - dt
            if diff.days == 0:
                return f"today {dt.strftime('%H:%M')}"
            elif diff.days == 1:
                return "yesterday"
            else:
                return f"{diff.days}d ago"
        except Exception:
            return iso[:10]

    def _top_tools(self, entries: list) -> list:
        counts = {}
        for e in entries:
            for t in e.tools_used:
                counts[t] = counts.get(t, 0) + 1
        return sorted(counts, key=counts.get, reverse=True)[:5]

    def _ensure_index(self) -> None:
        if not self.index_file.exists():
            self.index_file.write_text("{}", encoding="utf-8")

    def _load(self) -> dict:
        try:
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, index: dict) -> None:
        self.index_file.write_text(
            json.dumps(index, indent=2), encoding="utf-8"
        )
