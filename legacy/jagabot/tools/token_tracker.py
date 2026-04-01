#!/usr/bin/env python3
"""
token_tracker.py — Real token usage tracking with JSONL ledger.
Created: 2026-03-11 via forensic audit remediation.
"""

import json
import os
import time
from datetime import datetime, timedelta

DEFAULT_LOG = "/root/.jagabot/logs/token_usage.jsonl"


class TokenTracker:
    """Log actual token usage and compute real savings over time periods."""

    def __init__(self, log_file: str = DEFAULT_LOG):
        self.log_file = log_file
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

    def log_usage(self, tool_name: str, tokens_used: int, operation: str) -> dict:
        """Append a token-usage entry to the JSONL ledger."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "tokens": tokens_used,
            "operation": operation,
            "proof": f"log_entry_{int(time.time())}",
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def get_total(self, hours: int = 24) -> int:
        """Sum tokens logged in the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        total = 0
        if not os.path.exists(self.log_file):
            return 0
        with open(self.log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if datetime.fromisoformat(entry["timestamp"]) > cutoff:
                        total += entry.get("tokens", 0)
                except Exception:
                    continue
        return total

    def get_savings_report(self) -> dict:
        """Return a dict with 1h/24h/7d token totals."""
        return {
            "last_1h": self.get_total(1),
            "last_24h": self.get_total(24),
            "last_7d": self.get_total(24 * 7),
            "generated_at": datetime.now().isoformat(),
            "source": self.log_file,
        }


# Module-level singleton
token_tracker = TokenTracker()

if __name__ == "__main__":
    tt = TokenTracker()
    tt.log_usage("risk_analyzer", 1200, "unified_risk_analysis")
    tt.log_usage("file_processor", 300, "file_edit")
    print(tt.get_savings_report())
