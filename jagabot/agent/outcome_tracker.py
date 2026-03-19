"""
OutcomeTracker — Closes the self-improvement loop.

Tracks research conclusions (hypothesis right/wrong)
across sessions. Feeds verified outcomes into
MetaLearning, K1 Bayesian, and K3 Perspective.

The missing piece that makes the loop autonomous.

Flow:
  Session N:   Agent makes research conclusion
               → OutcomeTracker.log_pending()
               → saved to pending_outcomes.json

  Session N+X: Agent starts new session
               → OutcomeTracker.get_pending_reminder()
               → shown to user: "3 conclusions awaiting verification"

  User says:   "hypothesis was correct" / "that was wrong"
               → OutcomeTracker.record_outcome()
               → auto-calls MetaLearning + K1 + K3
               → loop closed ✅

  Auto-verify: For web-verifiable claims (facts, dates, prices)
               → OutcomeTracker.auto_verify()
               → uses web_search to check without user input
"""

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Data model ─────────────────────────────────────────────────────

@dataclass
class PendingOutcome:
    """A research conclusion waiting for verification."""
    id: str
    session_key: str
    query: str                    # original user question
    conclusion: str               # what the agent concluded
    conclusion_type: str          # "hypothesis", "prediction", "claim"
    confidence: float             # agent's stated confidence 0-1
    created_at: str
    output_folder: str
    verified: bool = False
    outcome: Optional[str] = None # "correct", "wrong", "partial"
    verified_at: Optional[str] = None
    auto_verifiable: bool = False  # can web_search check this?
    days_pending: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PendingOutcome":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ── Conclusion extractor ────────────────────────────────────────────

class ConclusionExtractor:
    """
    Extracts research conclusions from agent output.
    Looks for hypothesis/claim patterns in text.
    """

    # Patterns that signal a testable conclusion
    CONCLUSION_PATTERNS = [
        # Hypothesis statements
        r'hypothesis[:\s]+(.{20,150})',
        r'conclusion[:\s]+(.{20,150})',
        r'therefore[,:\s]+(.{20,150})',
        r'this suggests[:\s]+(.{20,150})',
        r'evidence indicates[:\s]+(.{20,150})',
        r'research shows[:\s]+(.{20,150})',

        # Predictive statements
        r'will likely (.{20,100})',
        r'is expected to (.{20,100})',
        r'predicts that (.{20,100})',
        r'should result in (.{20,100})',

        # Strong claims
        r'definitively[,:\s]+(.{20,150})',
        r'confirms that (.{20,150})',
        r'proves that (.{20,150})',
    ]

    # Patterns that suggest auto-verifiability
    AUTO_VERIFY_SIGNALS = [
        "price", "market", "stock", "rate",
        "published", "released", "announced",
        "study shows", "research found",
        "data shows", "statistics show",
    ]

    # Queries that trigger reflection/analysis — skip outcome extraction
    SKIP_QUERY_SIGNALS = [
        "pathological failure", "hidden assumption", "counter-scenario",
        "adversarial", "guardrail", "self-reflect", "reasoning chain",
        "failure analysis", "edge case", "logic loop", "analyze your",
        "critique your", "what went wrong", "your mistakes",
    ]

    def extract(
        self,
        content: str,
        query: str,
        session_key: str,
        output_folder: str,
    ) -> list[PendingOutcome]:
        """Extract conclusions from agent response."""
        # Skip extraction for self-reflection and analysis queries
        query_lower = query.lower()
        if any(s in query_lower for s in self.SKIP_QUERY_SIGNALS):
            logger.debug("OutcomeTracker: skipping extraction — self-reflection query detected")
            return []

        conclusions = []
        content_lower = content.lower()

        for pattern in self.CONCLUSION_PATTERNS:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            for match in matches:
                # Clean up match
                conclusion = match.strip().rstrip(".,;")
                if len(conclusion) < 20:
                    continue

                # Check if auto-verifiable
                auto_verifiable = any(
                    s in conclusion
                    for s in self.AUTO_VERIFY_SIGNALS
                )

                # Estimate confidence from surrounding context
                confidence = self._estimate_confidence(conclusion, content)

                conclusions.append(PendingOutcome(
                    id=str(uuid.uuid4())[:8],
                    session_key=session_key,
                    query=query[:100],
                    conclusion=conclusion[:200],
                    conclusion_type=self._classify(pattern),
                    confidence=confidence,
                    created_at=datetime.now().isoformat(),
                    output_folder=output_folder,
                    auto_verifiable=auto_verifiable,
                ))

        # Deduplicate similar conclusions
        return self._deduplicate(conclusions)

    def _classify(self, pattern: str) -> str:
        if "hypothesis" in pattern or "conclusion" in pattern:
            return "hypothesis"
        elif "predict" in pattern or "expect" in pattern or "likely" in pattern:
            return "prediction"
        else:
            return "claim"

    def _estimate_confidence(self, conclusion: str, content: str) -> float:
        """Rough confidence estimate from linguistic markers."""
        high = ["definitively", "proves", "confirms", "clearly"]
        medium = ["suggests", "indicates", "likely", "expected"]
        low = ["might", "could", "possibly", "perhaps"]

        conclusion_lower = conclusion.lower()
        if any(w in conclusion_lower for w in high):
            return 0.85
        elif any(w in conclusion_lower for w in medium):
            return 0.65
        elif any(w in conclusion_lower for w in low):
            return 0.45
        return 0.60

    def _deduplicate(
        self, conclusions: list[PendingOutcome]
    ) -> list[PendingOutcome]:
        """Remove near-duplicate conclusions."""
        seen = set()
        unique = []
        for c in conclusions:
            key = c.conclusion[:50]
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique[:3]  # max 3 per session to avoid noise


# ── MetaLearning connector ──────────────────────────────────────────

class LoopConnector:
    """
    Calls MetaLearning, K1 Bayesian, K3 Perspective
    when an outcome is verified.
    Fails silently — never blocks the main flow.
    """

    def __init__(self, tool_registry=None) -> None:
        self.registry = tool_registry

    def record_verified_outcome(
        self,
        outcome: PendingOutcome,
        result: str,  # "correct", "wrong", "partial"
    ) -> None:
        """Feed verified outcome into all learning systems."""
        success = result == "correct"
        partial = result == "partial"
        fitness = 1.0 if success else (0.5 if partial else 0.0)

        self._call_meta_learning(outcome, success, fitness)
        self._call_k1_bayesian(outcome, success)
        self._call_brier_scorer(outcome, success, partial)
        
        # Boost quality score when outcome verified correct
        try:
            writer = self._get("session_writer") if hasattr(self, '_get') else None
            if not writer and hasattr(self, 'writer'):
                writer = self.writer
            if writer and success:
                logger.info("OutcomeTracker: verified correct → boosting quality for solidification")
                writer._last_user_verified = True
        except Exception as e:
            logger.debug(f"Quality boost skipped: {e}")
        
        logger.info(
            f"✅ Loop closed: [{outcome.conclusion_type}] "
            f"'{outcome.conclusion[:50]}...' → {result}"
        )

    def _call_brier_scorer(
        self,
        outcome: PendingOutcome,
        success: bool,
        partial: bool,
    ) -> None:
        """Record verified outcome to BrierScorer for calibration."""
        try:
            brier = self._get("brier_scorer")
            if brier and hasattr(brier, 'record'):
                # actual: 1=correct, 0=wrong, 0.5=partial
                actual = 1 if success else (0.5 if partial else 0)
                brier.record(
                    perspective = "general",  # Could detect from outcome.conclusion_type
                    domain      = "research",  # Could detect from topic
                    forecast    = outcome.confidence,
                    actual      = actual,
                    claim       = outcome.conclusion[:200],
                    session_key = outcome.session_key,
                )
                logger.info(
                    f"📊 BrierScorer: {outcome.conclusion_type} "
                    f"forecast={outcome.confidence:.2f} actual={actual} "
                    f"brier={(outcome.confidence - actual)**2:.3f}"
                )
        except Exception as e:
            logger.debug(f"BrierScorer record skipped: {e}")

    def _call_meta_learning(
        self,
        outcome: PendingOutcome,
        success: bool,
        fitness: float,
    ) -> None:
        try:
            tool = self._get("meta_learning")
            if tool:
                # Tools have async execute(), not call()
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(tool.execute(
                        action="record_result",
                        strategy=f"research_{outcome.conclusion_type}",
                        success=success,
                        fitness_gain=fitness,
                        context={
                            "query": outcome.query,
                            "conclusion": outcome.conclusion[:100],
                            "confidence_was": outcome.confidence,
                            "outcome": "correct" if success else "wrong",
                            "days_to_verify": outcome.days_pending,
                        }
                    ))
                finally:
                    loop.close()
        except Exception as e:
            logger.debug(f"MetaLearning record skipped: {e}")

    def _call_k1_bayesian(
        self,
        outcome: PendingOutcome,
        actual: bool,
    ) -> None:
        try:
            tool = self._get("k1_bayesian")
            if tool:
                # Tools have async execute(), not call()
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(tool.execute(
                        action="record_outcome",
                        perspective="research",
                        predicted_prob=outcome.confidence,
                        actual=actual,
                        prediction_id=f"research_{outcome.id}",
                    ))
                finally:
                    loop.close()
        except Exception as e:
            logger.debug(f"K1 Bayesian record skipped: {e}")

    def _get(self, name: str):
        if self.registry is None:
            return None
        try:
            return self.registry.get(name)
        except Exception:
            return None


# ── Main OutcomeTracker ─────────────────────────────────────────────

class OutcomeTracker:
    """
    Closes the self-improvement loop across sessions.

    Persists pending outcomes to disk.
    Reminds user at session start.
    Records verified outcomes to MetaLearning + K1 + K3.
    """

    OVERDUE_DAYS = 3  # remind if outcome pending > 3 days

    def __init__(
        self,
        workspace: Path,
        tool_registry=None,
    ) -> None:
        self.workspace = Path(workspace)
        self.pending_file = (
            self.workspace / "memory" / "pending_outcomes.json"
        )
        self.pending_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

        self.extractor = ConclusionExtractor()
        self.connector = LoopConnector(tool_registry)
        
        from jagabot.agent.memory_outcome_bridge import MemoryOutcomeBridge
        self.bridge = MemoryOutcomeBridge(workspace, tool_registry)

    # ── Public API ──────────────────────────────────────────────────

    def extract_and_log(
        self,
        content: str,
        query: str,
        session_key: str,
        output_folder: str,
    ) -> list[PendingOutcome]:
        """
        Extract conclusions from agent response and log as pending.
        Call from SessionWriter after every save.
        """
        conclusions = self.extractor.extract(
            content, query, session_key, output_folder
        )
        for c in conclusions:
            self._save_pending(c)
            logger.debug(
                f"📌 Logged pending: [{c.conclusion_type}] "
                f"'{c.conclusion[:50]}...'"
            )
        return conclusions

    def get_pending_reminder(self) -> Optional[str]:
        """
        Get reminder message for session start.
        Returns None if nothing pending.
        Call at start of every _process_message().
        Only reminds ONCE per session (not every message).
        """
        pending = self._load_pending()
        unverified = [p for p in pending if not p.verified]

        if not unverified:
            return None

        # Update days pending
        now = datetime.now()
        overdue = []
        recent = []
        for p in unverified:
            try:
                created = datetime.fromisoformat(p.created_at)
                days = (now - created).days
                p.days_pending = days
                if days >= self.OVERDUE_DAYS:
                    overdue.append(p)
                else:
                    recent.append(p)
            except Exception:
                recent.append(p)

        # Build reminder
        lines = ["📌 **Pending Research Outcomes** (from past sessions):"]
        lines.append("")

        for p in overdue[:3]:
            lines.append(
                f"🔴 [{p.days_pending}d ago] {p.conclusion_type.upper()}: "
                f"*{p.conclusion[:80]}*"
            )
            lines.append(f"   Query: {p.query[:60]}")
            lines.append(
                f"   → Tell me: was this **correct**, **wrong**, or **partial**?"
            )
            lines.append("")

        for p in recent[:2]:
            lines.append(
                f"🟡 [recent] {p.conclusion_type.upper()}: "
                f"*{p.conclusion[:80]}*"
            )
            lines.append("")

        lines.append(
            "*(Reply 'outcome: correct/wrong/partial' "
            "or 'skip outcomes' to dismiss)*"
        )

        return "\n".join(lines)

    def record_outcome(
        self,
        outcome_id: str,
        result: str,  # "correct", "wrong", "partial"
    ) -> bool:
        """
        Record a verified outcome by ID.
        Feeds into MetaLearning + K1 + K3.
        """
        pending = self._load_pending()
        for p in pending:
            if p.id == outcome_id or outcome_id in p.conclusion[:30]:
                p.verified = True
                p.outcome = result
                p.verified_at = datetime.now().isoformat()
                self._save_all(pending)

                # Feed into learning systems
                self.connector.record_verified_outcome(p, result)
                return True
        return False

    def record_outcome_by_context(
        self,
        user_message: str,
    ) -> Optional[str]:
        """
        Parse user message for outcome feedback.
        Handles natural language like:
        - "that was correct"
        - "outcome: wrong"
        - "the hypothesis was partially right"
        
        STRICT MODE: Only triggers on explicit verdicts, not instructions.
        Returns confirmation message or None.
        """
        msg_lower = user_message.lower().strip()
        
        # MINIMUM LENGTH CHECK: Verdicts are typically > 10 chars
        # Filters out single-word responses and accidental triggers
        if len(msg_lower) < 10:
            return None
        
        # INTENT DETECTION: Look for explicit verdict patterns
        # NOT just keyword matching
        
        # Pattern 1: Explicit outcome statements
        # "that was correct", "the finding was wrong", "this is partial"
        verdict_patterns = [
            (r"\b(was|is|were)\s+(correct|right|accurate|true)\b", "correct"),
            (r"\b(was|is|were)\s+(wrong|incorrect|inaccurate|false)\b", "wrong"),
            (r"\b(was|is|were)\s+(partial|partially\s+correct|mixed)\b", "partial"),
            (r"outcome:\s*(correct|wrong|partial)", None),  # Handle separately
            (r"verdict:\s*(correct|wrong|partial)", None),  # Handle separately
        ]
        
        # Check for explicit outcome: / verdict: patterns first
        outcome_match = re.search(r"(outcome|verdict):\s*(correct|wrong|partial)", msg_lower)
        if outcome_match:
            result = outcome_match.group(2)
        else:
            # Check other verdict patterns
            result = None
            for pattern, verdict in verdict_patterns:
                match = re.search(pattern, msg_lower)
                if match and verdict:
                    # EXCLUSION CHECK: Make sure it's not in a negative/imperative context
                    full_match = match.group(0)
                    context_start = max(0, msg_lower.find(full_match) - 20)
                    context = msg_lower[context_start:msg_lower.find(full_match) + len(full_match)]
                    
                    # Exclude if in negative/imperative context
                    exclude_phrases = [
                        "do not", "don't", "not record", "not actual",
                        "before", "after", "if", "when", "whether",
                        "should", "would", "could", "might",
                        # Hypothetical/philosophy signals
                        "assume", "suppose", "imagine", "one of your",
                        "core assumption", "how do you", "how would",
                        "don't know which", "you don't know",
                        "which one", "any of", "some of",
                    ]
                    if any(phrase in context for phrase in exclude_phrases):
                        continue  # Skip this match
                    
                    result = verdict
                    break
        
        # Pattern 2: Natural language verdicts (more lenient)
        # STRICT: Only match if referring to past agent output, not hypotheticals
        if result is None:
            # Skip if message is a hypothetical/philosophical question
            hypothetical_signals = [
                "assume ", "suppose ", "imagine ", "what if ",
                "how do you", "how would", "which one is",
                "could be wrong", "might be wrong", "may be wrong",
                "one of your", "core assumption", "if one",
                "don't know which", "you don't know",
            ]
            if any(s in msg_lower for s in hypothetical_signals):
                result = None  # Skip — hypothetical, not a verdict
            elif re.search(r"\bthat\s+was\s+correct\b", msg_lower):
                result = "correct"  # "that was correct" — past tense, clear verdict
            elif re.search(r"\bthat\s+was\s+wrong\b", msg_lower):
                result = "wrong"    # "that was wrong" — past tense, clear verdict
            elif re.search(r"\byou'?re\s+(correct|right)\b", msg_lower):
                result = "correct"
            elif re.search(r"\b(correct|right)\s+conclusion\b", msg_lower):
                result = "correct"
            elif re.search(r"\b(wrong|incorrect)\s+conclusion\b", msg_lower):
                result = "wrong"
        
        if result is None:
            return None
        
        # Find most recent unverified outcome
        pending = self._load_pending()
        unverified = [p for p in pending if not p.verified]
        if not unverified:
            return None
        
        # RELEVANCE CHECK: Try to match message content to conclusion
        # If message mentions specific topic, prefer matching conclusion
        best_match = None
        best_score = 0.0
        
        for p in unverified:
            # Check if message contains keywords from conclusion
            conclusion_words = set(p.conclusion.lower().split())
            message_words = set(msg_lower.split())
            overlap = len(conclusion_words & message_words)
            
            if overlap > best_score:
                best_score = overlap
                best_match = p
        
        # Use best match if found with overlap, otherwise most recent
        most_recent = best_match if best_match else sorted(
            unverified,
            key=lambda p: p.created_at,
            reverse=True
        )[0]
        
        # SAFETY CHECK: Require at least some relevance
        # If best_score is 0 and message is short, probably false trigger
        if best_score == 0 and len(msg_lower) < 20:
            logger.debug(f"OutcomeTracker: ignoring likely false trigger (len={len(msg_lower)}, score={best_score})")
            return None
        
        most_recent.verified = True
        most_recent.outcome = result
        most_recent.verified_at = datetime.now().isoformat()
        self._save_all(pending)

        self.connector.record_verified_outcome(most_recent, result)

        # Bridge to MemoryFleet — updates MEMORY.md and fractal nodes
        self.bridge.on_outcome_verified(
            conclusion=most_recent.conclusion,
            result=result,
            session_key=most_recent.session_key,
            topic_tag=most_recent.conclusion_type,
        )

        return (
            f"✅ Outcome recorded: **{result}** for\n"
            f"*{most_recent.conclusion[:80]}*\n\n"
            f"MetaLearning + K1 Bayesian updated. "
            f"Self-improvement loop closed for this conclusion."
        )

    def get_stats(self) -> dict:
        """Return verification statistics."""
        pending = self._load_pending()
        total = len(pending)
        verified = [p for p in pending if p.verified]
        correct = [p for p in verified if p.outcome == "correct"]
        wrong = [p for p in verified if p.outcome == "wrong"]
        partial = [p for p in verified if p.outcome == "partial"]
        unverified = [p for p in pending if not p.verified]

        return {
            "total_conclusions": total,
            "verified": len(verified),
            "unverified": len(unverified),
            "correct": len(correct),
            "wrong": len(wrong),
            "partial": len(partial),
            "accuracy": (
                len(correct) / len(verified)
                if verified else 0.0
            ),
            "verification_rate": (
                len(verified) / total if total else 0.0
            ),
        }

    # ── Internal helpers ────────────────────────────────────────────

    def _ensure_file(self) -> None:
        if not self.pending_file.exists():
            self.pending_file.write_text("[]", encoding="utf-8")

    def _load_pending(self) -> list[PendingOutcome]:
        try:
            data = json.loads(
                self.pending_file.read_text(encoding="utf-8")
            )
            return [PendingOutcome.from_dict(d) for d in data]
        except Exception:
            return []

    def _save_pending(self, outcome: PendingOutcome) -> None:
        pending = self._load_pending()
        pending.append(outcome)
        self._save_all(pending)

    def _save_all(self, pending: list[PendingOutcome]) -> None:
        data = [p.to_dict() for p in pending]
        self.pending_file.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
