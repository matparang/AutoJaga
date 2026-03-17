"""
jagabot/core/token_budget.py
────────────────────────────
Central token usage tracker with per-session and daily limits.

Usage
-----
    from jagabot.core.token_budget import budget

    # After each API call (loop.py ~line 935):
    _u = response.usage
    if _u:
        budget.record(_u.prompt_tokens, _u.completion_tokens, model)

    # When trivial guard fires (no API call made):
    budget.record_skip()

    # At session end:
    budget.report()

Config
------
    JAGABOT_SESSION_LIMIT=50000   hard stop (raises RuntimeError)
    JAGABOT_CALL_LIMIT=10000      single-call alert threshold
    JAGABOT_DAILY_LIMIT=500000    daily soft warning
"""

from __future__ import annotations
import os, json
from datetime import date
from dataclasses import dataclass, field
from pathlib import Path
from loguru import logger

SESSION_LIMIT = int(os.getenv("JAGABOT_SESSION_LIMIT", "50000"))
CALL_LIMIT    = int(os.getenv("JAGABOT_CALL_LIMIT",   "10000"))
DAILY_LIMIT   = int(os.getenv("JAGABOT_DAILY_LIMIT", "500000"))
_STATE_PATH   = Path(os.getenv(
    "JAGABOT_BUDGET_STATE",
    str(Path.home() / ".jagabot" / "token_budget.json")
))


def _load_daily() -> dict:
    today = str(date.today())
    if _STATE_PATH.exists():
        try:
            s = json.loads(_STATE_PATH.read_text())
            if s.get("date") == today:
                return s
        except Exception:
            pass
    return {"date": today, "total": 0, "calls": 0}


def _save_daily(s: dict) -> None:
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(json.dumps(s, indent=2))
    except Exception as exc:
        logger.warning(f"token_budget: could not persist — {exc}")


@dataclass
class TokenBudget:
    session_limit: int = SESSION_LIMIT
    call_limit:    int = CALL_LIMIT
    daily_limit:   int = DAILY_LIMIT

    _in:     int  = field(default=0, init=False)
    _out:    int  = field(default=0, init=False)
    _calls:  int  = field(default=0, init=False)
    _skips:  int  = field(default=0, init=False)
    _models: dict = field(default_factory=dict, init=False)
    _daily:  dict = field(default_factory=_load_daily, init=False)

    # ── Public methods ────────────────────────────────────────────────────────

    def record(self, input_tokens: int, output_tokens: int, model: str = "unknown") -> None:
        """Call after every successful LLM API response."""
        self._in    += input_tokens
        self._out   += output_tokens
        self._calls += 1
        self._models[model] = self._models.get(model, 0) + 1

        call_total = input_tokens + output_tokens
        self._daily["total"] += call_total
        self._daily["calls"] += 1
        _save_daily(self._daily)

        logger.info(
            f"💰 tokens | call={call_total:,} "
            f"(in={input_tokens:,} out={output_tokens:,}) | "
            f"session={self._session_total:,} | "
            f"daily={self._daily['total']:,} | {model}"
        )

        if input_tokens > self.call_limit:
            logger.warning(
                f"⚠️  High input: {input_tokens:,} tokens in single call "
                f"(limit={self.call_limit:,}) — check tool payload size"
            )

        if self._session_total > self.session_limit:
            msg = (
                f"🛑 Session budget exceeded: "
                f"{self._session_total:,} > {self.session_limit:,}. "
                f"Raise JAGABOT_SESSION_LIMIT or start a new session."
            )
            logger.error(msg)
            raise RuntimeError(msg)

        if self._daily["total"] > self.daily_limit:
            logger.warning(
                f"📊 Daily limit exceeded: "
                f"{self._daily['total']:,} > {self.daily_limit:,}"
            )

    def record_skip(self) -> None:
        """Call when trivial guard fires and no LLM call is made."""
        self._skips += 1
        logger.info(f"⏭️  LLM skipped (trivial guard) — {self._skips} skips this session")

    def remaining(self) -> int:
        """Tokens remaining in the current session budget."""
        return max(0, self.session_limit - self._session_total)

    def summary(self) -> dict:
        return {
            "session_input":    self._in,
            "session_output":   self._out,
            "session_total":    self._session_total,
            "calls_made":       self._calls,
            "calls_skipped":    self._skips,
            "budget_remaining": self.remaining(),
            "daily_total":      self._daily["total"],
            "daily_calls":      self._daily["calls"],
            "model_breakdown":  dict(self._models),
        }

    def report(self) -> None:
        """Print a formatted session report. Call at session end."""
        s = self.summary()
        skip_pct = s["calls_skipped"] / max(1, s["calls_made"] + s["calls_skipped"]) * 100
        models = ", ".join(f"{m}×{n}" for m, n in s["model_breakdown"].items()) or "none"
        logger.info(
            "\n" + "═" * 52 + "\n"
            "  🐈 JAGABOT TOKEN REPORT\n"
            + "═" * 52 + "\n"
            f"  Session input    : {s['session_input']:>10,} tokens\n"
            f"  Session output   : {s['session_output']:>10,} tokens\n"
            f"  Session total    : {s['session_total']:>10,} tokens\n"
            f"  Budget remaining : {s['budget_remaining']:>10,} tokens\n"
            f"  LLM calls made   : {s['calls_made']:>10}\n"
            f"  Calls skipped    : {s['calls_skipped']:>10}  ({skip_pct:.0f}% avoided)\n"
            f"  Models used      : {models}\n"
            f"  Daily total      : {s['daily_total']:>10,} tokens\n"
            + "═" * 52
        )

    @property
    def _session_total(self) -> int:
        return self._in + self._out


# ── Singleton — import this, don't instantiate your own ──────────────────────
budget = TokenBudget()
