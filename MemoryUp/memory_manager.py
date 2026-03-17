# jagabot/memory/memory_manager.py
"""
MemoryManager — Robust unified memory system for AutoJaga.

Inspired by OpenClaw + Hermes Agent memory architecture.
Wraps all five memory improvements into one class:

1. FTS5 full-text search    (OpenClaw + Hermes)
2. Temporal decay scoring   (OpenClaw)
3. Daily dated notes        (OpenClaw)
4. Pre-compaction flush     (OpenClaw)
5. Skill documents          (Hermes)
6. User modeling            (Hermes / lightweight)

Integrates with existing AutoJaga components:
- MemoryOutcomeBridge  → verification status
- SessionIndex        → session awareness
- OutcomeTracker      → pending conclusions
- FractalManager      → hierarchical nodes (unchanged)
- MEMORY.md           → curated facts (unchanged)
- HISTORY.md          → event log (unchanged)

Drop into: jagabot/memory/memory_manager.py

Wire into loop.py __init__:
    from jagabot.memory.memory_manager import MemoryManager
    self.memory_mgr = MemoryManager(workspace)

Wire into loop.py _process_message:
    # START — load relevant context
    memory_context = self.memory_mgr.get_context(
        query=msg.content,
        session_key=session.key,
    )
    
    # END — store findings + update user model
    self.memory_mgr.store_turn(
        query=msg.content,
        response=final_content,
        tools_used=tools_used,
        quality=quality_score,
        topic=detected_topic,
    )

Wire into context_builder.py Layer 2:
    # Replace current _load_relevant_memory() with:
    layer2 = self.memory_mgr.get_context(query, session_key)
"""

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Config ──────────────────────────────────────────────────────────
HALF_LIFE_RESEARCH  = 30    # days — research findings decay
HALF_LIFE_VERIFIED  = 90    # days — verified facts decay slower
HALF_LIFE_SKILL     = 180   # days — skills are long-lived
MIN_QUALITY_FOR_SKILL = 0.8 # minimum YOLO quality to auto-generate skill
MAX_CONTEXT_TOKENS  = 400   # max tokens for memory context injection
FTS_RESULT_LIMIT    = 8     # max FTS results before re-ranking


# ── Data classes ────────────────────────────────────────────────────

@dataclass
class MemoryEntry:
    """A single memory entry with metadata."""
    content:    str
    source:     str         # file path
    date:       str         # ISO date
    topic:      str         # topic tag
    verified:   str         # "correct" | "wrong" | "partial" | "unknown"
    entry_type: str         # "fact" | "skill" | "session" | "daily"
    score:      float = 0.0 # relevance score (set during search)


@dataclass
class UserModel:
    """Lightweight user model — preferences and patterns."""
    topic_frequency:    dict = field(default_factory=dict)
    tool_frequency:     dict = field(default_factory=dict)
    preferred_depth:    str  = "detailed"  # "brief" | "detailed" | "technical"
    preferred_language: str  = "en"
    session_count:      int  = 0
    last_active:        str  = ""


# ── Main class ───────────────────────────────────────────────────────

class MemoryManager:
    """
    Unified memory system combining OpenClaw + Hermes approaches.
    
    Designed to be a drop-in upgrade over the current 
    FractalManager + grep-based memory retrieval.
    Does NOT replace MEMORY.md, HISTORY.md, or FractalManager —
    it adds search, decay, daily notes, and skill docs on top.
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace   = Path(workspace)
        self.memory_dir  = self.workspace / "memory"
        self.skill_dir   = self.workspace / "skills" / "auto_generated"
        self.db_path     = self.memory_dir / "memory_fts.db"
        self.als_path    = self.memory_dir / "ALS.json"
        self.user_model  = UserModel()

        # Ensure directories exist
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.skill_dir.mkdir(parents=True, exist_ok=True)

        # Initialise FTS5 database
        self._init_fts_db()

        # Load user model
        self._load_user_model()

        # Index existing memory files on startup
        self._index_on_startup()

    # ── Public API ───────────────────────────────────────────────────

    def get_context(
        self,
        query:       str,
        session_key: str = "",
        max_tokens:  int = MAX_CONTEXT_TOKENS,
    ) -> str:
        """
        Primary context retrieval — replaces grep-based search.
        
        Returns ranked, deduplicated, temporally-decayed
        memory context ready for injection into system prompt.
        """
        if not query.strip():
            return ""

        # 1. FTS5 search across all indexed memory
        raw_results = self._fts_search(query, limit=FTS_RESULT_LIMIT)

        # 2. Apply temporal decay scoring
        ranked = self._apply_temporal_decay(raw_results)

        # 3. MMR deduplication (OpenClaw style)
        diverse = self._mmr_deduplicate(ranked, query, top_k=4)

        # 4. Format for context injection
        context = self._format_context(diverse, max_tokens)

        if context:
            logger.debug(
                f"MemoryManager: retrieved {len(diverse)} memories "
                f"for query '{query[:40]}'"
            )

        return context

    def store_turn(
        self,
        query:     str,
        response:  str,
        tools_used:list      = None,
        quality:   float     = 0.0,
        topic:     str       = "general",
        session_key: str     = "",
    ) -> None:
        """
        Store a conversation turn across multiple memory layers.
        Called after every agent response.
        """
        tools_used = tools_used or []
        now        = datetime.now()

        # 1. Append to today's daily note (OpenClaw style)
        self._append_daily_note(query, response, topic, quality)

        # 2. Extract and index important facts
        facts = self._extract_facts(response, topic)
        for fact in facts:
            self._index_entry(fact)

        # 3. Update user model (Hermes style)
        self._update_user_model(query, tools_used, topic)

        # 4. Index today's note for search
        today_file = self._today_file()
        if today_file.exists():
            self._index_file(today_file, force=False)

        logger.debug(
            f"MemoryManager: stored turn — "
            f"{len(facts)} facts extracted, topic={topic}"
        )

    def pre_compaction_flush(
        self,
        session_content: str,
        session_key:     str = "",
    ) -> int:
        """
        Called when context window nears limit.
        Extracts and saves important content before compression.
        OpenClaw's memoryFlush equivalent.
        
        Returns number of entries saved.
        """
        # Signals that indicate important content
        important_signals = [
            "conclusion:", "finding:", "verified:",
            "remember:", "important:", "key insight:",
            "✅", "❌", "hypothesis:", "result:",
            "proved", "disproved", "confirmed",
        ]

        lines   = session_content.split("\n")
        saved   = []
        for line in lines:
            line_stripped = line.strip()
            if (
                len(line_stripped) > 30 and
                any(s in line.lower() for s in important_signals)
            ):
                saved.append(line_stripped)

        if not saved:
            return 0

        # Write to today's file under a special section
        ts      = datetime.now().strftime("%H:%M")
        content = "\n".join(saved[:15])  # cap at 15 entries
        entry   = (
            f"\n### {ts} — pre-compaction-flush\n"
            f"*Context saved before window compression*\n\n"
            f"{content}\n"
        )

        today = self._today_file()
        with open(today, "a", encoding="utf-8") as f:
            f.write(entry)

        # Re-index today's file
        self._index_file(today, force=True)

        logger.info(
            f"MemoryManager: pre-compaction flush saved "
            f"{len(saved)} entries"
        )
        return len(saved)

    def auto_generate_skill(
        self,
        task:        str,
        steps:       list[dict],
        quality:     float,
        topic:       str,
        session_key: str = "",
    ) -> Optional[Path]:
        """
        Auto-generate a skill document from a successful YOLO run.
        Hermes Agent's procedural memory equivalent.
        
        Only generates if quality >= MIN_QUALITY_FOR_SKILL (0.8).
        Returns path to skill file, or None if not generated.
        """
        if quality < MIN_QUALITY_FOR_SKILL:
            logger.debug(
                f"MemoryManager: skill not generated — "
                f"quality {quality:.2f} below threshold"
            )
            return None

        slug       = self._slugify(task)[:40]
        skill_file = self.skill_dir / f"{slug}.md"

        # Don't overwrite a higher-quality existing skill
        if skill_file.exists():
            existing = self._read_skill_quality(skill_file)
            if existing >= quality:
                return skill_file

        content = self._format_skill_doc(
            task, steps, quality, topic
        )
        skill_file.write_text(content, encoding="utf-8")

        # Index for search
        self._index_file(skill_file, force=True)

        logger.info(
            f"MemoryManager: skill generated — "
            f"{skill_file.name} (quality={quality:.2f})"
        )
        return skill_file

    def search_skills(self, query: str) -> list[MemoryEntry]:
        """
        Search auto-generated skill documents.
        Used at YOLO session start to find reusable approaches.
        """
        results = self._fts_search(
            query,
            limit=3,
            entry_type_filter="skill",
        )
        return self._apply_temporal_decay(results)

    def get_user_model(self) -> UserModel:
        """Return current user model."""
        return self.user_model

    def get_stats(self) -> dict:
        """Return memory system statistics."""
        conn  = sqlite3.connect(self.db_path)
        total = conn.execute(
            "SELECT COUNT(*) FROM memory_fts"
        ).fetchone()[0]
        skills = conn.execute(
            "SELECT COUNT(*) FROM memory_fts WHERE entry_type='skill'"
        ).fetchone()[0]
        conn.close()

        daily_files = list(self.memory_dir.glob("????-??-??.md"))

        return {
            "indexed_entries":   total,
            "skill_documents":   skills,
            "daily_notes":       len(daily_files),
            "user_sessions":     self.user_model.session_count,
            "top_topics":        self._top_topics(),
            "db_size_kb":        self.db_path.stat().st_size // 1024
                                 if self.db_path.exists() else 0,
        }

    # ── FTS5 database ────────────────────────────────────────────────

    def _init_fts_db(self) -> None:
        """Initialise SQLite FTS5 database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
            USING fts5(
                content,
                source,
                date,
                topic,
                verified,
                entry_type,
                tokenize='porter unicode61'
            )
        """)
        # Metadata table for tracking indexed files
        conn.execute("""
            CREATE TABLE IF NOT EXISTS indexed_files (
                path      TEXT PRIMARY KEY,
                mtime     REAL,
                indexed_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _index_on_startup(self) -> None:
        """Index all memory files on startup if not already indexed."""
        files_to_index = [
            self.memory_dir / "MEMORY.md",
            self.memory_dir / "HISTORY.md",
        ]

        # Add all daily notes
        files_to_index.extend(
            self.memory_dir.glob("????-??-??.md")
        )

        # Add all auto-generated skills
        files_to_index.extend(
            self.skill_dir.glob("*.md")
        )

        indexed = 0
        for f in files_to_index:
            if f.exists():
                if self._index_file(f, force=False):
                    indexed += 1

        if indexed > 0:
            logger.debug(
                f"MemoryManager: indexed {indexed} files on startup"
            )

    def _index_file(self, path: Path, force: bool = False) -> bool:
        """
        Index a file into FTS5.
        Returns True if indexed, False if skipped (already current).
        """
        try:
            mtime = path.stat().st_mtime
            conn  = sqlite3.connect(self.db_path)

            # Check if already indexed and current
            if not force:
                existing = conn.execute(
                    "SELECT mtime FROM indexed_files WHERE path=?",
                    (str(path),)
                ).fetchone()
                if existing and existing[0] == mtime:
                    conn.close()
                    return False  # already indexed, skip

            # Remove old entries for this file
            conn.execute(
                "DELETE FROM memory_fts WHERE source=?",
                (str(path),)
            )

            # Determine entry type from path
            entry_type = self._detect_entry_type(path)
            topic      = self._detect_topic_from_path(path)
            date_str   = self._extract_date_from_path(path)

            # Split content into chunks for granular retrieval
            content = path.read_text(encoding="utf-8")
            chunks  = self._split_into_chunks(content)

            for chunk in chunks:
                if len(chunk.strip()) > 20:
                    verified = self._detect_verification(chunk)
                    conn.execute(
                        "INSERT INTO memory_fts VALUES (?,?,?,?,?,?)",
                        (chunk, str(path), date_str,
                         topic, verified, entry_type)
                    )

            # Update indexed files tracker
            conn.execute("""
                INSERT OR REPLACE INTO indexed_files 
                VALUES (?, ?, ?)
            """, (str(path), mtime, datetime.now().isoformat()))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.debug(f"MemoryManager: index failed for {path}: {e}")
            return False

    def _index_entry(self, entry: MemoryEntry) -> None:
        """Index a single memory entry directly."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO memory_fts VALUES (?,?,?,?,?,?)",
                (entry.content, entry.source, entry.date,
                 entry.topic, entry.verified, entry.entry_type)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"MemoryManager: entry index failed: {e}")

    def _fts_search(
        self,
        query:             str,
        limit:             int  = FTS_RESULT_LIMIT,
        entry_type_filter: str  = None,
    ) -> list[MemoryEntry]:
        """Execute FTS5 search with optional type filter."""
        try:
            conn = sqlite3.connect(self.db_path)

            if entry_type_filter:
                rows = conn.execute("""
                    SELECT content, source, date, topic,
                           verified, entry_type, rank
                    FROM memory_fts
                    WHERE memory_fts MATCH ?
                    AND entry_type = ?
                    ORDER BY rank
                    LIMIT ?
                """, (self._clean_query(query),
                      entry_type_filter, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT content, source, date, topic,
                           verified, entry_type, rank
                    FROM memory_fts
                    WHERE memory_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (self._clean_query(query), limit)).fetchall()

            conn.close()

            return [
                MemoryEntry(
                    content    = r[0][:300],
                    source     = r[1],
                    date       = r[2],
                    topic      = r[3],
                    verified   = r[4],
                    entry_type = r[5],
                    score      = abs(r[6]) if r[6] else 1.0,
                )
                for r in rows
            ]

        except Exception as e:
            logger.debug(f"MemoryManager: FTS search failed: {e}")
            return []

    # ── Temporal decay (OpenClaw style) ─────────────────────────────

    def _apply_temporal_decay(
        self,
        entries: list[MemoryEntry],
    ) -> list[MemoryEntry]:
        """Apply temporal decay to search results."""
        for entry in entries:
            age_days = self._age_days(entry.date)
            half_life = self._get_half_life(
                entry.entry_type,
                entry.verified,
            )
            # Exponential decay
            decay       = math.pow(0.5, age_days / half_life)
            entry.score = entry.score * decay

        return sorted(entries, key=lambda x: x.score, reverse=True)

    def _get_half_life(self, entry_type: str, verified: str) -> float:
        """Return appropriate half-life for an entry type."""
        if entry_type == "skill":
            return HALF_LIFE_SKILL
        if verified == "correct":
            return HALF_LIFE_VERIFIED
        if verified == "wrong":
            return 7.0  # wrong conclusions decay very fast
        return HALF_LIFE_RESEARCH

    def _age_days(self, date_str: str) -> float:
        """Calculate age in days from ISO date string."""
        try:
            dt       = datetime.fromisoformat(date_str)
            age      = (datetime.now() - dt).total_seconds() / 86400
            return max(0.0, age)
        except Exception:
            return 7.0  # unknown date → assume 1 week old

    # ── MMR deduplication (OpenClaw style) ──────────────────────────

    def _mmr_deduplicate(
        self,
        entries:  list[MemoryEntry],
        query:    str,
        top_k:    int = 4,
        lambda_:  float = 0.7,  # 0=max diversity, 1=max relevance
    ) -> list[MemoryEntry]:
        """
        Maximal Marginal Relevance deduplication.
        Balances relevance with diversity.
        Prevents returning 4 entries that all say the same thing.
        """
        if len(entries) <= top_k:
            return entries

        selected  = [entries[0]]  # always include top result
        remaining = entries[1:]

        while len(selected) < top_k and remaining:
            best_score = -float("inf")
            best_entry = None

            for candidate in remaining:
                # Relevance score (from FTS + decay)
                relevance = candidate.score

                # Similarity penalty — how similar to already selected
                max_sim = max(
                    self._text_similarity(
                        candidate.content, s.content
                    )
                    for s in selected
                )

                # MMR score
                mmr = lambda_ * relevance - (1 - lambda_) * max_sim

                if mmr > best_score:
                    best_score = mmr
                    best_entry = candidate

            if best_entry:
                selected.append(best_entry)
                remaining.remove(best_entry)

        return selected

    def _text_similarity(self, text1: str, text2: str) -> float:
        """Simple word overlap similarity (no external deps)."""
        stop = {"the", "a", "an", "is", "are", "was", "and", "or",
                "it", "this", "that", "in", "on", "to", "for", "of"}
        w1   = {
            w for w in re.findall(r'\b\w+\b', text1.lower())
            if w not in stop and len(w) > 3
        }
        w2   = {
            w for w in re.findall(r'\b\w+\b', text2.lower())
            if w not in stop and len(w) > 3
        }
        if not w1 or not w2:
            return 0.0
        return len(w1 & w2) / max(len(w1), len(w2))

    # ── Daily notes (OpenClaw style) ─────────────────────────────────

    def _today_file(self) -> Path:
        """Get today's daily note file path."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.memory_dir / f"{today}.md"

    def _append_daily_note(
        self,
        query:    str,
        response: str,
        topic:    str,
        quality:  float,
    ) -> None:
        """Append a session turn to today's daily note."""
        try:
            if quality < 0.5:
                return  # don't record low-quality turns

            ts       = datetime.now().strftime("%H:%M")
            summary  = self._extract_first_sentence(response)
            entry    = (
                f"\n### {ts} [{topic}] q={quality:.1f}\n"
                f"**Q:** {query[:100]}\n"
                f"**A:** {summary}\n"
            )

            with open(self._today_file(), "a", encoding="utf-8") as f:
                f.write(entry)

        except Exception as e:
            logger.debug(f"MemoryManager: daily note failed: {e}")

    # ── Skill documents (Hermes style) ───────────────────────────────

    def _format_skill_doc(
        self,
        task:    str,
        steps:   list[dict],
        quality: float,
        topic:   str,
    ) -> str:
        """Format a skill document from YOLO session results."""
        now   = datetime.now()
        lines = [
            f"# Skill: {task[:80]}",
            f"",
            f"**Topic:** {topic}",
            f"**Quality:** {quality:.2f}",
            f"**Generated:** {now.strftime('%Y-%m-%d')}",
            f"**Auto-generated from YOLO session**",
            f"",
            f"## Approach",
            f"",
            f"Use this approach for similar tasks:",
            f"",
        ]

        success_steps = [
            s for s in steps if s.get("status") == "done"
        ]
        for i, s in enumerate(success_steps, 1):
            lines.append(f"### Step {i}: {s.get('name', '')}")
            if s.get("summary"):
                lines.append(s["summary"])
            lines.append("")

        lines += [
            f"## Notes",
            f"",
            f"- Verified quality: {quality:.2f}/1.0",
            f"- Topic: {topic}",
            f"- Last used: {now.strftime('%Y-%m-%d')}",
        ]

        return "\n".join(lines)

    def _read_skill_quality(self, path: Path) -> float:
        """Extract quality score from existing skill doc."""
        try:
            content = path.read_text()
            match   = re.search(r'Quality:\*\*\s*([\d.]+)', content)
            return float(match.group(1)) if match else 0.0
        except Exception:
            return 0.0

    # ── User model (Hermes lightweight) ──────────────────────────────

    def _update_user_model(
        self,
        query:      str,
        tools_used: list,
        topic:      str,
    ) -> None:
        """Update lightweight user model from turn data."""
        model = self.user_model

        # Track topic frequency
        model.topic_frequency[topic] = \
            model.topic_frequency.get(topic, 0) + 1

        # Track tool frequency
        for tool in tools_used:
            model.tool_frequency[tool] = \
                model.tool_frequency.get(tool, 0) + 1

        # Detect language preference from query
        malay_signals = [
            "apa", "bagaimana", "tolong", "boleh",
            "saya", "kamu", "ini", "itu"
        ]
        if any(s in query.lower() for s in malay_signals):
            model.preferred_language = "ms"

        # Detect depth preference
        brief_signals  = ["brief", "quick", "short", "summary only"]
        detail_signals = ["detailed", "explain", "deep", "thorough"]
        q_lower        = query.lower()

        if any(s in q_lower for s in brief_signals):
            model.preferred_depth = "brief"
        elif any(s in q_lower for s in detail_signals):
            model.preferred_depth = "detailed"

        model.session_count += 1
        model.last_active    = datetime.now().isoformat()

        self._save_user_model()

    def _load_user_model(self) -> None:
        """Load user model from ALS.json."""
        if not self.als_path.exists():
            return
        try:
            data = json.loads(self.als_path.read_text())
            um   = data.get("user_model", {})
            self.user_model = UserModel(
                topic_frequency    = um.get("topic_frequency", {}),
                tool_frequency     = um.get("tool_frequency", {}),
                preferred_depth    = um.get("preferred_depth", "detailed"),
                preferred_language = um.get("preferred_language", "en"),
                session_count      = um.get("session_count", 0),
                last_active        = um.get("last_active", ""),
            )
        except Exception as e:
            logger.debug(f"MemoryManager: user model load failed: {e}")

    def _save_user_model(self) -> None:
        """Save user model to ALS.json."""
        try:
            existing = {}
            if self.als_path.exists():
                existing = json.loads(self.als_path.read_text())

            existing["user_model"] = {
                "topic_frequency":    self.user_model.topic_frequency,
                "tool_frequency":     self.user_model.tool_frequency,
                "preferred_depth":    self.user_model.preferred_depth,
                "preferred_language": self.user_model.preferred_language,
                "session_count":      self.user_model.session_count,
                "last_active":        self.user_model.last_active,
            }

            self.als_path.write_text(
                json.dumps(existing, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.debug(f"MemoryManager: user model save failed: {e}")

    # ── Context formatting ────────────────────────────────────────────

    def _format_context(
        self,
        entries:    list[MemoryEntry],
        max_tokens: int,
    ) -> str:
        """Format memory entries for context injection."""
        if not entries:
            return ""

        lines  = ["## Relevant Memory", ""]
        tokens = 0

        for entry in entries:
            # Verification badge
            badge = {
                "correct": " [✅ verified]",
                "wrong":   " [❌ wrong — ignore]",
                "partial": " [⚠️ partial]",
            }.get(entry.verified, "")

            # Source label
            source_name = Path(entry.source).name
            line = f"*{source_name}{badge}*: {entry.content[:150]}"

            line_tokens = len(line) // 4
            if tokens + line_tokens > max_tokens:
                break

            lines.append(line)
            tokens += line_tokens

        if len(lines) <= 2:
            return ""

        return "\n".join(lines)

    # ── Helpers ───────────────────────────────────────────────────────

    def _extract_facts(
        self, response: str, topic: str
    ) -> list[MemoryEntry]:
        """Extract important facts from an agent response."""
        fact_signals = [
            "conclusion:", "finding:", "verified:",
            "key insight:", "important:", "✅", "result:",
        ]
        facts = []
        now   = datetime.now().isoformat()

        for line in response.split("\n"):
            line = line.strip()
            if (
                len(line) > 40 and
                any(s in line.lower() for s in fact_signals)
            ):
                facts.append(MemoryEntry(
                    content    = line[:200],
                    source     = "session_extraction",
                    date       = now,
                    topic      = topic,
                    verified   = "unknown",
                    entry_type = "fact",
                ))
        return facts[:5]  # cap at 5 per turn

    def _split_into_chunks(self, content: str) -> list[str]:
        """Split content into meaningful chunks for indexing."""
        # Split on markdown headers or double newlines
        chunks = re.split(r'\n#{1,3} |\n\n', content)
        return [c.strip() for c in chunks if len(c.strip()) > 20]

    def _detect_entry_type(self, path: Path) -> str:
        """Detect memory entry type from file path."""
        name = path.name.lower()
        if re.match(r'\d{4}-\d{2}-\d{2}', name):
            return "daily"
        if "memory" in name:
            return "fact"
        if "history" in name:
            return "session"
        if path.parent.name == "auto_generated":
            return "skill"
        return "fact"

    def _detect_topic_from_path(self, path: Path) -> str:
        """Extract topic from file path or content."""
        name = path.stem.lower()
        for topic in [
            "financial", "healthcare", "research",
            "causal", "engineering", "ideas"
        ]:
            if topic in name:
                return topic
        return "general"

    def _extract_date_from_path(self, path: Path) -> str:
        """Extract date from file name or use mod time."""
        name = path.stem
        if re.match(r'\d{4}-\d{2}-\d{2}', name):
            return name
        try:
            mtime = path.stat().st_mtime
            return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
        except Exception:
            return datetime.now().strftime("%Y-%m-%d")

    def _detect_verification(self, text: str) -> str:
        """Detect verification status from text."""
        text_lower = text.lower()
        if "verified correct" in text_lower or "✅ verified" in text_lower:
            return "correct"
        if "verified wrong" in text_lower or "❌ verified" in text_lower:
            return "wrong"
        if "partially correct" in text_lower:
            return "partial"
        return "unknown"

    def _extract_first_sentence(self, text: str) -> str:
        """Extract first meaningful sentence from text."""
        sentences = re.split(r'[.!?]\s+', text.strip())
        for s in sentences:
            if len(s.strip()) > 20:
                return s.strip()[:150]
        return text[:100].strip()

    def _clean_query(self, query: str) -> str:
        """Clean query for FTS5 — remove special characters."""
        cleaned = re.sub(r'[^\w\s]', ' ', query)
        cleaned = ' '.join(cleaned.split())
        return cleaned[:100] if cleaned else "memory"

    def _top_topics(self) -> dict:
        """Return top researched topics from user model."""
        freq = self.user_model.topic_frequency
        return dict(sorted(
            freq.items(), key=lambda x: x[1], reverse=True
        )[:5])

    @staticmethod
    def _slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '_', text)
        return text.strip('_')
