"""
UISession — per-user session tracking for the Knowledge Graph UI.

Records user actions within a session for MetaLearning integration
and analytics.
"""

from __future__ import annotations

import uuid
from datetime import datetime


class UISession:
    """Tracks one user session in the Streamlit UI."""

    def __init__(self, user_id: str = "default"):
        self.session_id: str = str(uuid.uuid4())
        self.user_id: str = user_id
        self.start_time: datetime = datetime.now()
        self.history: list[dict] = []

    def log_action(self, action: str, data: dict | None = None) -> None:
        """Record a user action."""
        self.history.append(
            {
                "time": datetime.now().isoformat(),
                "action": action,
                "data": data or {},
            }
        )

    def get_summary(self) -> dict:
        """Return session summary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "start_time": self.start_time.isoformat(),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "action_count": len(self.history),
            "actions": [h["action"] for h in self.history],
        }

    def get_history(self) -> list[dict]:
        """Return full action history."""
        return list(self.history)
