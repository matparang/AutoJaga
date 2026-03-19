"""
jagabot/core/token_budget.py
─────────────────────────────
Tracks token usage per-session and per-day.
Enforces limits and prints a report at session end.

Usage:
    from jagabot.core.token_budget import budget
    budget.record(input_tokens, output_tokens, model)
    budget.record_skip()   # when LLM call avoided
    budget.report()        # at session end

Config via env vars or config.json:
    JAGABOT_SESSION_LIMIT=500000    hard stop per session (default)
    JAGABOT_CALL_LIMIT=50000        alert if single call exceeds this
    JAGABOT_DAILY_LIMIT=2000000     soft daily cap
"""

from __future__ import annotations
import os
import json
from pathlib import Path
from datetime import date
from dataclasses import dataclass, field
from loguru import logger

# Load from config.json if available, else env vars, else defaults
def _load_budget_config():
    config_path = Path.home() / ".jagabot" / "config.json"
    session_limit = SESSION_LIMIT_DEFAULT
    daily_limit = DAILY_LIMIT_DEFAULT
    
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            budget_config = config.get("budget", {})
            session_limit = budget_config.get("session_limit", SESSION_LIMIT_DEFAULT)
            daily_limit = budget_config.get("daily_limit", DAILY_LIMIT_DEFAULT)
        except Exception:
            pass
    
    # Env vars override config
    session_limit = int(os.getenv("JAGABOT_SESSION_LIMIT", str(session_limit)))
    daily_limit = int(os.getenv("JAGABOT_DAILY_LIMIT", str(daily_limit)))
    
    return session_limit, daily_limit

SESSION_LIMIT_DEFAULT = 500000  # 500k tokens per session default
CALL_LIMIT_DEFAULT    = 50000   # 50k tokens per call warning default
DAILY_LIMIT_DEFAULT   = 2000000 # 2M tokens daily default

SESSION_LIMIT, DAILY_LIMIT = _load_budget_config()
CALL_LIMIT    = int(os.getenv("JAGABOT_CALL_LIMIT", str(CALL_LIMIT_DEFAULT)))
STATE_PATH    = Path(os.getenv("JAGABOT_BUDGET_STATE",
                    str(Path.home() / ".jagabot" / "token_budget.json")))


def _load_daily():
    today = str(date.today())
    if STATE_PATH.exists():
        try:
            s = json.loads(STATE_PATH.read_text())
            if s.get("date") == today:
                return s
        except Exception:
            pass
    return {"date": today, "total": 0, "calls": 0}


def _save_daily(s: dict):
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(s, indent=2))
    except Exception as e:
        logger.warning(f"token_budget: could not save state — {e}")


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

    def record(self, input_tokens: int, output_tokens: int, model: str, messages: list = None, workspace: Path = None, interactive: bool = False):
        self._in    += input_tokens
        self._out   += output_tokens
        self._calls += 1
        self._models[model] = self._models.get(model, 0) + 1
        total = input_tokens + output_tokens
        self._daily["total"] += total
        self._daily["calls"] += 1
        _save_daily(self._daily)

        logger.info(
            f"💰 tokens | call={total:,} (in={input_tokens:,} out={output_tokens:,}) "
            f"| session={self._in+self._out:,} | daily={self._daily['total']:,} | {model}"
        )
        if input_tokens > self.call_limit:
            logger.warning(f"⚠️ High input: {input_tokens:,} tokens — check tool payload")
        if self._in + self._out > self.session_limit:
            # Save checkpoint first
            if messages and workspace:
                from jagabot.core.session_checkpoint import save_checkpoint
                save_checkpoint(messages, self._calls, workspace)
                logger.warning(f"💾 Session checkpoint saved")
            
            if interactive:
                # Interactive mode: ask user what to do
                logger.warning(f"⚠️  Session budget exceeded: {self._in+self._out:,} / {self.session_limit:,}")
                logger.info("💡 Options:")
                logger.info("   1. Continue this session (budget override)")
                logger.info("   2. Save and start new session")
                logger.info("   3. Stop and exit")
                return "BUDGET_EXCEEDED_ASK_USER"
            else:
                # Non-interactive: raise error
                raise RuntimeError(
                    f"🛑 Session budget exceeded: {self._in+self._out:,} > {self.session_limit:,}. "
                    f"Checkpoint saved. Use /resume to continue."
                )
        if self._daily["total"] > self.daily_limit:
            logger.warning(f"📊 Daily budget exceeded: {self._daily['total']:,}")
            if interactive:
                return "DAILY_EXCEEDED_WARNING"

    def record_skip(self):
        self._skips += 1
        logger.info(f"⏭️ LLM skipped (trivial) — {self._skips} skips this session")

    def remaining(self) -> int:
        return max(0, self.session_limit - (self._in + self._out))

    def report(self):
        models = ", ".join(f"{m}×{n}" for m, n in self._models.items()) or "none"
        skip_pct = self._skips / max(1, self._calls + self._skips) * 100
        logger.info(
            "\n" + "═"*50 + "\n"
            "  🏁 JAGABOT TOKEN REPORT\n" + "═"*50 + "\n"
            f"  Session input   : {self._in:>10,}\n"
            f"  Session output  : {self._out:>10,}\n"
            f"  Session total   : {self._in+self._out:>10,}\n"
            f"  Budget remaining: {self.remaining():>10,}\n"
            f"  LLM calls made  : {self._calls:>10}\n"
            f"  Calls skipped   : {self._skips:>10}  ({skip_pct:.0f}% avoided)\n"
            f"  Models          : {models}\n"
            f"  Daily total     : {self._daily['total']:>10,}\n"
            + "═"*50
        )


budget = TokenBudget()
