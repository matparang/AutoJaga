"""
SessionWriter v2 — Saves research output to disk AND
auto-records to MetaLearning when quality is high enough.

Option C Hybrid Design:
- Always saves to disk (Karpathy-style, never fails)
- Auto-records to MetaLearning if quality >= 0.7
- Human can always manually correct/override
- Never records noisy or low-quality outcomes

Output structure:
    ~/.jagabot/workspace/research_output/
        {date}_{topic_slug}/
            report.md       <- full response (human readable)
            meta.json       <- tools, quality score, ML status
            tools_log.md    <- what tools ran (if any)

Drop into: jagabot/agent/session_writer.py

Wire into loop.py __init__:
    from jagabot.agent.session_writer import SessionWriter
    self.writer = SessionWriter(workspace, tool_registry=self.tools)

Wire into loop.py _process_message (after self.sessions.save):
    self.writer.save(
        content=final_content,
        query=msg.content,
        tools_used=tools_used,
        session_key=session.key,
        auditor_approved=auditor_result.approved,  # pass from auditor result
    )
"""

import json
import re
from datetime import datetime
from pathlib import Path

from loguru import logger


# ── Quality thresholds ──────────────────────────────────────────────
AUTO_RECORD_THRESHOLD = 0.70   # min quality to auto-record to MetaLearning
HIGH_QUALITY_THRESHOLD = 0.85  # threshold for "excellent" label


class QualityScorer:
    """
    Scores response quality automatically.
    Used to decide whether to auto-record to MetaLearning.

    Intentionally simple and conservative:
    we would rather under-record than record noisy outcomes.

    Score breakdown (0.0 - 1.0):
        Tools used correctly   +0.20
        Response has structure +0.20
        Response has substance +0.20
        No error signals       +0.20
        Auditor approved       +0.20
    """

    ERROR_SIGNALS = [
        "error", "failed", "exception", "traceback",
        "could not", "unable to", "i don't know",
        "i cannot", "i'm not sure", "hallucin",
        "max retries exhausted",
    ]

    STRUCTURE_SIGNALS = [
        "##", "**", "->", "✅", "1.", "2.", "3.",
        "- ", "* ", "| ",
    ]

    SUBSTANCE_MIN_WORDS = 50

    def score(
        self,
        content: str,
        tools_used: list | None,
        auditor_approved: bool = True,
        user_verified: bool = False,
    ) -> float:
        score = 0.0

        # +0.20 tools were used (agent did real work)
        if tools_used and len(tools_used) > 0:
            score += 0.20

        # +0.20 response has structure
        if any(s in content for s in self.STRUCTURE_SIGNALS):
            score += 0.20

        # +0.20 response has substance
        if len(content.split()) >= self.SUBSTANCE_MIN_WORDS:
            score += 0.20

        # +0.20 no error signals
        content_lower = content.lower()
        if not any(s in content_lower for s in self.ERROR_SIGNALS):
            score += 0.20

        # +0.20 auditor approved
        if auditor_approved:
            score += 0.20

        total = round(score, 2)

        # User verified correct → boost quality above threshold
        if user_verified:
            total = max(total, 0.85)

        return total


class MetaLearningConnector:
    """
    Thin wrapper to call MetaLearning tool safely.
    Fails silently — disk save always happens regardless.
    """

    def __init__(self, tool_registry=None) -> None:
        self.tool_registry = tool_registry

    def _check_available(self) -> bool:
        if self.tool_registry is None:
            return False
        try:
            return "meta_learning" in self.tool_registry
        except Exception:
            return False

    def record(
        self,
        query: str,
        session_key: str,
        quality_score: float,
        tools_used: list,
        output_folder: str,
    ) -> bool:
        if not self._check_available():
            logger.debug("MetaLearning not available — skipping auto-record")
            return False
        try:
            tool = self.tool_registry.get("meta_learning")
            if tool:
                import asyncio
                import concurrent.futures
                coro = tool.execute(
                    action="record_result",
                    strategy=f"auto_{session_key}",
                    success=quality_score >= AUTO_RECORD_THRESHOLD,
                    fitness_gain=quality_score,
                    context={
                        "query": query[:100],
                        "tools_used": tools_used,
                        "output_folder": output_folder,
                        "auto_recorded": True,
                    }
                )
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(coro)
                    else:
                        loop.run_until_complete(coro)
                except Exception:
                    asyncio.run(coro)
                logger.info(
                    f"✅ Auto-recorded to MetaLearning "
                    f"(quality={quality_score:.2f})"
                )
                return True
        except Exception as e:
            logger.debug(f"MetaLearning auto-record skipped: {e}")
        return False


class SessionWriter:
    """
    v2 — Disk save + optional MetaLearning auto-record.

    Rules:
    - Disk save ALWAYS happens (never fails silently)
    - MetaLearning ONLY if quality >= AUTO_RECORD_THRESHOLD
    - Human can always manually correct via meta_learning tool
    - Fails in MetaLearning never block disk save
    """

    def __init__(
        self,
        workspace: Path,
        tool_registry=None,
        outcome_tracker=None,
    ) -> None:
        self.workspace = Path(workspace)
        self.root = self.workspace / "research_output"
        self.root.mkdir(parents=True, exist_ok=True)
        self.scorer = QualityScorer()
        self.ml = MetaLearningConnector(tool_registry)
        self.outcome_tracker = outcome_tracker

    # ── Public API ──────────────────────────────────────────────────

    def save(
        self,
        content: str,
        query: str = "",
        tools_used: list | None = None,
        session_key: str = "unknown",
        auditor_approved: bool = True,
        **kwargs,
    ) -> Path:
        """
        Save output to disk. Auto-record to MetaLearning
        if quality score >= AUTO_RECORD_THRESHOLD (0.70).
        Returns folder path.
        """
        timestamp = datetime.now()

        # Step 1 — score quality (user_verified overrides low scores)
        _user_verified = kwargs.get("user_verified", False)
        quality = self.scorer.score(
            content=content,
            tools_used=tools_used,
            auditor_approved=auditor_approved,
            user_verified=_user_verified,
        )
        label = (
            "excellent" if quality >= HIGH_QUALITY_THRESHOLD
            else "good" if quality >= AUTO_RECORD_THRESHOLD
            else "low"
        )

        # Step 2 — always save to disk
        folder = self._make_folder(timestamp, query)
        self._write_report(folder, content, query, timestamp, session_key)
        self._write_meta(folder, query, tools_used, session_key,
                         timestamp, quality, label)
        if tools_used:
            self._write_tools_log(folder, tools_used)

        logger.info(
            f"✅ Research saved -> {folder} "
            f"[quality={quality:.2f} ({label})]"
        )

        # Step 3 — auto-record to MetaLearning if quality is high
        if quality >= AUTO_RECORD_THRESHOLD:
            recorded = self.ml.record(
                query=query,
                session_key=session_key,
                quality_score=quality,
                tools_used=tools_used or [],
                output_folder=str(folder),
            )
            if not recorded:
                # MetaLearning unavailable — hint for manual record
                logger.debug(
                    f"💡 Good output (score={quality:.2f}) — "
                    f"manually record: meta_learning(record_result={{...}})"
                )
        else:
            logger.debug(
                f"Quality {quality:.2f} below threshold "
                f"{AUTO_RECORD_THRESHOLD} — skipping auto-record"
            )

        # Step 4 — extract and log research conclusions (loop closure)
        if self.outcome_tracker:
            self.outcome_tracker.extract_and_log(
                content=content,
                query=query,
                session_key=session_key,
                output_folder=str(folder),
            )

        return folder

    # ── Internal helpers ────────────────────────────────────────────

    def _make_folder(self, timestamp: datetime, query: str) -> Path:
        date_str = timestamp.strftime("%Y%m%d_%H%M%S")
        slug = self._slugify(query)[:40] if query else "session"
        folder = self.root / f"{date_str}_{slug}"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _write_report(self, folder, content, query, timestamp, session_key):
        header = "\n".join([
            "---",
            f"date: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"session: {session_key}",
            f"query: {query[:120] if query else 'N/A'}",
            "---",
            "",
            "# Research Output",
            f"**Query:** {query}",
            f"**Date:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
        ])
        (folder / "report.md").write_text(header + content, encoding="utf-8")

    def _write_meta(self, folder, query, tools_used, session_key,
                    timestamp, quality, label):
        meta = {
            "timestamp": timestamp.isoformat(),
            "session_key": session_key,
            "query": query,
            "tools_used": tools_used or [],
            "tool_count": len(tools_used) if tools_used else 0,
            "output_folder": str(folder),
            "quality": {
                "score": quality,
                "label": label,
                "threshold": AUTO_RECORD_THRESHOLD,
                "auto_recorded": quality >= AUTO_RECORD_THRESHOLD,
            }
        }
        (folder / "meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

    def _write_tools_log(self, folder, tools_used):
        lines = [
            "# Tools Used This Session", "",
            f"Total: {len(tools_used)} tool(s)", "",
        ]
        for i, tool in enumerate(tools_used, 1):
            lines.append(f"{i}. `{tool}`")
        (folder / "tools_log.md").write_text(
            "\n".join(lines), encoding="utf-8"
        )

    @staticmethod
    def _slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "_", text)
        return text.strip("_")
