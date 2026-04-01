"""
ChallengeProblems — Synthetic calibration data generator

Generates verifiable questions across domains to feed BrierScorer
with real forecast→actual pairs.

Design:
  - Questions have known correct answers (ground truth)
  - Agent answers with confidence score
  - BrierScorer records forecast=confidence, actual=correct/wrong
  - Over time, trust scores become meaningful

Usage:
    generator = ChallengeProblemGenerator(workspace, brier_scorer)
    challenge = generator.next()
    # Show challenge to agent, get answer + confidence
    generator.record_outcome(challenge.id, agent_answer, confidence)
"""

from __future__ import annotations

import json
import random
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


# ── Challenge definitions ─────────────────────────────────────────

CHALLENGE_BANK: list[dict] = [

    # ── Financial domain ──────────────────────────────────────────
    {
        "domain": "financial",
        "perspective": "bear",
        "question": "A stock has VaR(95%) = -8%. What does this mean?",
        "correct": "There is a 5% chance of losing more than 8% in the period",
        "options": [
            "There is a 5% chance of losing more than 8% in the period",
            "The stock will lose exactly 8% with 95% probability",
            "The maximum possible loss is 8%",
            "The stock gains 8% in 95% of periods",
        ],
        "difficulty": "medium",
    },
    {
        "domain": "financial",
        "perspective": "bull",
        "question": "A company has P/E ratio of 15 and industry average is 25. What does this suggest?",
        "correct": "The stock may be undervalued relative to peers",
        "options": [
            "The stock may be undervalued relative to peers",
            "The stock is definitely overvalued",
            "The company has no growth prospects",
            "The stock should be sold immediately",
        ],
        "difficulty": "easy",
    },
    {
        "domain": "financial",
        "perspective": "buffet",
        "question": "What is the primary principle of value investing?",
        "correct": "Buy assets trading below their intrinsic value with margin of safety",
        "options": [
            "Buy assets trading below their intrinsic value with margin of safety",
            "Follow market momentum and buy rising stocks",
            "Diversify across all asset classes equally",
            "Invest only in technology companies",
        ],
        "difficulty": "easy",
    },
    {
        "domain": "financial",
        "perspective": "bear",
        "question": "CVaR (Conditional VaR) vs VaR: which is more conservative?",
        "correct": "CVaR — it measures expected loss beyond the VaR threshold",
        "options": [
            "CVaR — it measures expected loss beyond the VaR threshold",
            "VaR — it uses a higher confidence interval",
            "They are equivalent measures",
            "Neither — they measure different things entirely",
        ],
        "difficulty": "hard",
    },

    # ── Research domain ───────────────────────────────────────────
    {
        "domain": "research",
        "perspective": "general",
        "question": "What is the purpose of a control group in an experiment?",
        "correct": "To provide a baseline for comparison against the treatment group",
        "options": [
            "To provide a baseline for comparison against the treatment group",
            "To increase the sample size",
            "To eliminate all variables",
            "To confirm the hypothesis before testing",
        ],
        "difficulty": "easy",
    },
    {
        "domain": "research",
        "perspective": "general",
        "question": "What does p < 0.05 mean in hypothesis testing?",
        "correct": "There is less than 5% probability the result occurred by chance",
        "options": [
            "There is less than 5% probability the result occurred by chance",
            "The hypothesis is 95% correct",
            "The experiment failed 5% of the time",
            "The sample size is too small",
        ],
        "difficulty": "medium",
    },
    {
        "domain": "research",
        "perspective": "general",
        "question": "What is confirmation bias in research?",
        "correct": "Tendency to favor information that confirms existing beliefs",
        "options": [
            "Tendency to favor information that confirms existing beliefs",
            "Using too small a sample size",
            "Publishing only positive results",
            "Misinterpreting statistical significance",
        ],
        "difficulty": "easy",
    },

    # ── Calibration domain ────────────────────────────────────────
    {
        "domain": "calibration",
        "perspective": "general",
        "question": "A forecaster says 80% confident on 100 predictions. If well-calibrated, how many should be correct?",
        "correct": "Around 80",
        "options": [
            "Around 80",
            "Exactly 80",
            "100 — high confidence means always correct",
            "50 — confidence doesn't predict accuracy",
        ],
        "difficulty": "medium",
    },
    {
        "domain": "calibration",
        "perspective": "general",
        "question": "What does a Brier score of 0.0 mean?",
        "correct": "Perfect calibration — all predictions were correct with full confidence",
        "options": [
            "Perfect calibration — all predictions were correct with full confidence",
            "The model made no predictions",
            "All predictions were wrong",
            "The model is 50% accurate",
        ],
        "difficulty": "easy",
    },
    {
        "domain": "calibration",
        "perspective": "general",
        "question": "Overconfidence bias means a forecaster:",
        "correct": "Assigns higher confidence than their actual accuracy warrants",
        "options": [
            "Assigns higher confidence than their actual accuracy warrants",
            "Makes too many predictions",
            "Is always wrong",
            "Refuses to make uncertain predictions",
        ],
        "difficulty": "easy",
    },

    # ── Engineering domain ────────────────────────────────────────
    {
        "domain": "engineering",
        "perspective": "general",
        "question": "What does asyncio.gather() do in Python?",
        "correct": "Runs multiple coroutines concurrently and waits for all to complete",
        "options": [
            "Runs multiple coroutines concurrently and waits for all to complete",
            "Runs coroutines sequentially one after another",
            "Cancels all running tasks",
            "Creates a new event loop",
        ],
        "difficulty": "medium",
    },
    {
        "domain": "engineering",
        "perspective": "general",
        "question": "What is the purpose of a circuit breaker pattern in software?",
        "correct": "Prevent cascading failures by stopping calls to a failing service",
        "options": [
            "Prevent cascading failures by stopping calls to a failing service",
            "Speed up API calls",
            "Encrypt network traffic",
            "Balance load across servers",
        ],
        "difficulty": "medium",
    },
]


# ── Data classes ──────────────────────────────────────────────────

@dataclass
class Challenge:
    """A single calibration challenge."""
    id:           str
    domain:       str
    perspective:  str
    question:     str
    correct:      str
    options:      list[str]
    difficulty:   str
    created_at:   str = field(default_factory=lambda: datetime.now().isoformat())
    answered:     bool = False
    agent_answer: str = ""
    confidence:   float = 0.0
    was_correct:  bool = False
    brier_score:  float = 0.0


@dataclass
class ChallengeResult:
    """Result after agent answers a challenge."""
    challenge_id: str
    was_correct:  bool
    brier_score:  float
    confidence:   float
    domain:       str
    perspective:  str


# ── Generator ─────────────────────────────────────────────────────

class ChallengeProblemGenerator:
    """
    Generates synthetic calibration challenges and records outcomes.

    Flow:
        1. next() → returns Challenge with question + options
        2. Agent answers with confidence
        3. record_outcome() → records to BrierScorer
        4. BrierScorer builds trust scores per domain
    """

    def __init__(self, workspace: Path, brier_scorer=None):
        self.workspace    = Path(workspace)
        self.brier        = brier_scorer
        self.db_path      = self.workspace / "memory" / "challenges.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._pending: dict[str, Challenge] = {}

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS challenges (
                id           TEXT PRIMARY KEY,
                domain       TEXT,
                perspective  TEXT,
                question     TEXT,
                correct      TEXT,
                agent_answer TEXT,
                confidence   REAL,
                was_correct  INTEGER,
                brier_score  REAL,
                created_at   TEXT,
                answered_at  TEXT
            )
        """)
        conn.commit()
        conn.close()

    def next(
        self,
        domain: str | None = None,
        difficulty: str | None = None,
    ) -> Challenge:
        """Return next challenge, optionally filtered by domain/difficulty."""
        pool = CHALLENGE_BANK.copy()
        if domain:
            pool = [c for c in pool if c["domain"] == domain] or pool
        if difficulty:
            pool = [c for c in pool if c["difficulty"] == difficulty] or pool

        template = random.choice(pool)
        options  = template["options"].copy()
        random.shuffle(options)

        challenge = Challenge(
            id          = str(uuid.uuid4())[:8],
            domain      = template["domain"],
            perspective = template["perspective"],
            question    = template["question"],
            correct     = template["correct"],
            options     = options,
            difficulty  = template["difficulty"],
        )
        self._pending[challenge.id] = challenge
        logger.info(
            f"Challenge [{challenge.id}]: {template['domain']}/{template['difficulty']} "
            f"— '{challenge.question[:60]}'"
        )
        return challenge

    def format_for_agent(self, challenge: Challenge) -> str:
        """Format challenge as a prompt for the agent."""
        options_text = "\n".join(
            f"  {chr(65+i)}) {opt}"
            for i, opt in enumerate(challenge.options)
        )
        return (
            f"📊 CALIBRATION CHALLENGE [{challenge.id}]\n"
            f"Domain: {challenge.domain} | Difficulty: {challenge.difficulty}\n\n"
            f"Question: {challenge.question}\n\n"
            f"Options:\n{options_text}\n\n"
            f"Reply with:\n"
            f"ANSWER: [A/B/C/D]\n"
            f"CONFIDENCE: [0.0-1.0]\n"
            f"REASONING: [brief explanation]"
        )

    def record_outcome(
        self,
        challenge_id: str,
        agent_answer: str,
        confidence:   float,
    ) -> ChallengeResult | None:
        """Record agent's answer and feed to BrierScorer."""
        challenge = self._pending.get(challenge_id)
        if not challenge:
            logger.warning(f"Challenge [{challenge_id}] not found in pending")
            return None

        # Check correctness
        answer_clean   = agent_answer.strip().lower()
        correct_clean  = challenge.correct.strip().lower()
        was_correct    = (
            answer_clean == correct_clean or
            answer_clean in correct_clean or
            correct_clean in answer_clean
        )

        # Calculate Brier score
        forecast   = max(0.001, min(0.999, confidence))
        actual     = 1 if was_correct else 0
        brier      = (forecast - actual) ** 2

        # Update challenge
        challenge.answered     = True
        challenge.agent_answer = agent_answer
        challenge.confidence   = confidence
        challenge.was_correct  = was_correct
        challenge.brier_score  = brier

        # Save to DB
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO challenges
            (id, domain, perspective, question, correct,
             agent_answer, confidence, was_correct, brier_score,
             created_at, answered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            challenge.id, challenge.domain, challenge.perspective,
            challenge.question, challenge.correct,
            agent_answer, confidence, int(was_correct), brier,
            challenge.created_at, datetime.now().isoformat(),
        ))
        conn.commit()
        conn.close()

        # Feed to BrierScorer
        if self.brier:
            self.brier.record(
                perspective = challenge.perspective,
                domain      = challenge.domain,
                forecast    = forecast,
                actual      = actual,
                claim       = challenge.question[:200],
                session_key = f"challenge:{challenge.id}",
            )

        result = ChallengeResult(
            challenge_id = challenge.id,
            was_correct  = was_correct,
            brier_score  = brier,
            confidence   = confidence,
            domain       = challenge.domain,
            perspective  = challenge.perspective,
        )

        logger.info(
            f"Challenge [{challenge_id}] result: "
            f"{'✅ CORRECT' if was_correct else '❌ WRONG'} "
            f"confidence={confidence:.2f} brier={brier:.3f}"
        )

        # Remove from pending
        del self._pending[challenge_id]
        return result

    def get_stats(self) -> dict:
        """Return calibration stats from challenge history."""
        conn   = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT domain, perspective,
                   COUNT(*) as total,
                   SUM(was_correct) as correct,
                   AVG(brier_score) as avg_brier,
                   AVG(confidence) as avg_confidence
            FROM challenges
            WHERE answered_at IS NOT NULL
            GROUP BY domain, perspective
        """)
        rows = cursor.fetchall()
        conn.close()

        stats = {}
        for domain, perspective, total, correct, avg_brier, avg_conf in rows:
            key = f"{perspective}/{domain}"
            stats[key] = {
                "total":          total,
                "correct":        correct,
                "accuracy":       round(correct / total, 2) if total > 0 else 0,
                "avg_brier":      round(avg_brier, 3),
                "avg_confidence": round(avg_conf, 2),
                "calibration":    "good" if avg_brier < 0.1 else "needs work",
            }
        return stats

    def run_batch(self, n: int = 5, domain: str | None = None) -> list[str]:
        """
        Generate N challenges formatted for agent consumption.
        Returns list of formatted challenge prompts.
        """
        prompts = []
        for _ in range(n):
            challenge = self.next(domain=domain)
            prompts.append(self.format_for_agent(challenge))
        return prompts
