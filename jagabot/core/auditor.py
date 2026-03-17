"""
Pre-response Auditor — catches fabrications BEFORE the user sees them.

Instead of appending warnings to the response (post-hoc), the auditor
intercepts the draft, runs harness verification, and if it fails, sends
structured feedback back to the agent loop for self-correction.

The user never sees "VERIFICATION FAILED" warnings unless all retries
are exhausted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from jagabot.core.tool_harness import ToolHarness
    from jagabot.core.epistemic_auditor import EpistemicAuditor as _EpistemicType


@dataclass
class AuditResult:
    """Outcome of a single audit check."""
    approved: bool
    content: str          # original content (clean or with warnings)
    feedback: str | None  # structured feedback for LLM if rejected
    attempt: int = 0
    missing_files: list[str] = field(default_factory=list)  # track missing files across attempts


@dataclass
class _AuditEntry:
    """Internal log entry for one audit attempt."""
    attempt: int
    approved: bool
    timestamp: float
    warnings: str
    missing_files: list[str] = field(default_factory=list)


class ResponseAuditor:
    """
    Audits agent responses before they reach the user.

    Delegates to ToolHarness.verify_response() and detects whether
    warnings were appended. If so, constructs structured feedback
    for the LLM to self-correct.
    """

    def __init__(self, harness: "ToolHarness", max_retries: int = 2) -> None:
        self.harness = harness
        self.max_retries = max_retries
        self._log: list[_AuditEntry] = []
        self._pending_missing_files: list[str] = []  # Track missing files across attempts

        from jagabot.core.epistemic_auditor import EpistemicAuditor
        self._epistemic = EpistemicAuditor()

        from jagabot.core.causal_tracer import CausalTracer
        self.causal_tracer = CausalTracer()

    def verify_pending_files(self, workspace: Path) -> tuple[bool, list[str]]:
        """
        Directly verify if pending missing files now exist on disk.
        
        Returns:
            (all_exist, still_missing) - tuple of approval status and list of still-missing files
        """
        if not self._pending_missing_files:
            return True, []
        
        still_missing = []
        for fp in self._pending_missing_files:
            resolved = Path(fp) if Path(fp).is_absolute() else workspace / fp
            if not resolved.exists():
                still_missing.append(str(resolved))
        
        return len(still_missing) == 0, still_missing

    def audit(
        self,
        content: str,
        tools_used: list[str],
        attempt: int = 0,
        messages: list[dict] | None = None,
    ) -> AuditResult:
        """
        Audit a draft response.

        Args:
            messages: Conversation history — tool-role messages are included
                      in the epistemic corpus so numbers from previous turns
                      are not flagged as fabricated.

        Returns an AuditResult indicating whether the response is approved
        or needs correction, with structured feedback for the LLM.
        """
        if not content:
            return AuditResult(approved=True, content=content, feedback=None, attempt=attempt)

        # ── Phase 1: Epistemic check (catches simulated evidence) ──
        # Build corpus: current turn tool outputs + history tool results
        corpus = self.harness.tool_output_corpus
        if messages:
            history_parts: list[str] = []
            for msg in messages:
                role = msg.get("role", "")
                msg_content = msg.get("content", "")
                # Include tool-role messages (tool results from earlier turns)
                if role == "tool" and isinstance(msg_content, str):
                    history_parts.append(msg_content)
                # Include assistant messages (agent may have quoted tool output)
                elif role == "assistant" and isinstance(msg_content, str):
                    history_parts.append(msg_content)
            if history_parts:
                corpus = corpus + "\n" + "\n".join(history_parts)

        ep_result = self._epistemic.audit(content, corpus, tools_used=tools_used)
        if not ep_result.approved:
            self._log.append(_AuditEntry(
                attempt=attempt,
                approved=False,
                timestamp=time.time(),
                warnings=f"Epistemic: {ep_result.feedback or 'fabricated numerics'}",
            ))
            logger.warning(f"Auditor: attempt {attempt} REJECTED by epistemic check")
            return AuditResult(
                approved=False,
                content=content,
                feedback=ep_result.feedback,
                attempt=attempt,
            )

        # ── Phase 1.5: Causal trace (catches "I ran X" when X wasn't called) ──
        causal_result = self.causal_tracer.verify_claims(content)
        if not causal_result.approved:
            self._log.append(_AuditEntry(
                attempt=attempt,
                approved=False,
                timestamp=time.time(),
                warnings=f"Causal: {causal_result.feedback or 'unverified tool claims'}",
            ))
            logger.warning(f"Auditor: attempt {attempt} REJECTED by causal trace")
            return AuditResult(
                approved=False,
                content=content,
                feedback=causal_result.feedback,
                attempt=attempt,
            )

        # ── Phase 2: Harness verification (file claims + tool fabrication) ──
        verified = self.harness.verify_response(content, tools_used)

        if verified == content:
            # Clean — no warnings appended
            # BUT check if we have pending missing files from previous attempts
            if self._pending_missing_files:
                # Still have uncreated files - don't approve yet
                feedback = (
                    "[AUDITOR FEEDBACK - CRITICAL]\n"
                    f"Previous attempt claimed these files were created: {self._pending_missing_files}\n"
                    "These files STILL do not exist. You MUST:\n"
                    "1. Use write_file tool to create EACH missing file NOW\n"
                    "2. Do NOT claim success until ALL files exist\n"
                    "3. If you cannot create them, admit failure honestly\n"
                )
                self._log.append(_AuditEntry(
                    attempt=attempt,
                    approved=False,
                    timestamp=time.time(),
                    warnings=f"Pending missing files: {self._pending_missing_files}",
                    missing_files=list(self._pending_missing_files),
                ))
                logger.warning(f"Auditor: attempt {attempt} REJECTED — pending missing files: {self._pending_missing_files}")
                return AuditResult(
                    approved=False,
                    content=content,
                    feedback=feedback,
                    attempt=attempt,
                    missing_files=list(self._pending_missing_files),
                )
            
            # All clear - no warnings and no pending missing files
            self._log.append(_AuditEntry(
                attempt=attempt,
                approved=True,
                timestamp=time.time(),
                warnings="",
                missing_files=[],
            ))
            logger.debug(f"Auditor: attempt {attempt} APPROVED")
            return AuditResult(approved=True, content=content, feedback=None, attempt=attempt)

        # Harness appended warnings — extract them and track missing files
        warnings = verified[len(content):].strip()
        
        # Extract missing files from warnings for tracking
        import re
        missing_match = re.search(r'NOT found on disk: (\[.*?\])', warnings)
        if missing_match:
            import ast
            try:
                new_missing = ast.literal_eval(missing_match.group(1))
                # Update pending list - remove files that now exist, add new missing
                self._pending_missing_files = [
                    f for f in self._pending_missing_files 
                    if not (Path(f).is_absolute() and Path(f).exists())
                ]
                for f in new_missing:
                    if f not in self._pending_missing_files:
                        self._pending_missing_files.append(f)
            except:
                pass
        
        self._log.append(_AuditEntry(
            attempt=attempt,
            approved=False,
            timestamp=time.time(),
            warnings=warnings,
            missing_files=list(self._pending_missing_files),
        ))
        logger.warning(f"Auditor: attempt {attempt} REJECTED — {warnings[:120]}")

        # Build structured feedback for the LLM
        if self._pending_missing_files:
            feedback = (
                "[AUDITOR FEEDBACK - CRITICAL]\n"
                f"You claimed these files were created: {self._pending_missing_files}\n"
                f"VERIFICATION FAILED - Files do not exist on disk.\n\n"
                "REQUIRED ACTIONS:\n"
                "1. Use write_file tool to create EACH missing file NOW\n"
                "2. Verify each file exists after creation\n"
                "3. Do NOT claim success until ALL files are created\n"
                "4. If you cannot create them, admit failure honestly\n\n"
                f"Missing files: {self._pending_missing_files}"
            )
        else:
            feedback = (
                "[AUDITOR FEEDBACK - MUST FIX]\n"
                "Your previous response failed verification:\n"
                f"{warnings}\n\n"
                "Please correct your response:\n"
                "- If you claimed to create/write a file, use the write_file tool NOW.\n"
                "- If you cited tool results, actually run the tool first.\n"
                "- Do NOT repeat the same claim without executing the tool.\n"
                "- If you cannot perform the action, say so honestly."
            )

        return AuditResult(
            approved=False,
            content=verified,   # includes warnings (used as last-resort fallback)
            feedback=feedback,
            attempt=attempt,
            missing_files=list(self._pending_missing_files),
        )

    @property
    def audit_log(self) -> list[dict]:
        """Return audit log as dicts for external consumption."""
        return [
            {
                "attempt": e.attempt,
                "approved": e.approved,
                "timestamp": e.timestamp,
                "warnings": e.warnings,
            }
            for e in self._log
        ]

    @property
    def rejection_count(self) -> int:
        """Total rejected drafts across all messages this session."""
        return sum(1 for e in self._log if not e.approved)

    def clear_log(self) -> None:
        """Clear the audit log and pending missing files (e.g., between messages)."""
        self._log.clear()
        self._pending_missing_files.clear()
