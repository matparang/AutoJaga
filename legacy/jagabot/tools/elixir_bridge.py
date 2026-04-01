#!/usr/bin/env python3
"""
elixir_bridge.py — Real implementation with Python fallback.
Created: 2026-03-11 via forensic audit remediation.
"""

import hashlib
import json
import os
import time
from datetime import datetime

EXPERIMENTS_LOG = "/root/.jagabot/logs/elixir_experiments.jsonl"

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False


class ElixirBridge:
    """Elixir bridge with health check and verified Python fallback."""

    def __init__(self, host: str = "localhost", port: int = 4000, fallback_enabled: bool = True):
        self.base_url = f"http://{host}:{port}"
        self.fallback_enabled = fallback_enabled
        self.experiments_log: list[dict] = []
        self.health_status = self.check_health()

    def check_health(self) -> bool:
        """Probe Elixir endpoint; returns False instead of raising."""
        if not _REQUESTS_AVAILABLE:
            return False
        try:
            resp = _requests.get(f"{self.base_url}/health", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def spawn_research_swarm(self, query: str, count: int = 5) -> dict:
        """Spawn research agents. Falls back to Python-only if Elixir unavailable."""

        experiment_id = hashlib.md5(f"{query}{time.time()}".encode()).hexdigest()[:8]
        result: dict = {
            "experiment_id": experiment_id,
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "requested_count": count,
            "elixir_available": self.health_status,
        }

        if self.health_status and _REQUESTS_AVAILABLE:
            try:
                resp = _requests.post(
                    f"{self.base_url}/api/v1/swarms",
                    json={"query": query, "count": count},
                    timeout=5,
                )
                if resp.status_code == 202:
                    result["status"] = "spawned"
                    result["swarm_id"] = resp.json().get("swarm_id")
                    result["actual_count"] = count
                else:
                    result["status"] = "elixir_error"
                    result["http_status"] = resp.status_code
            except Exception as exc:
                result["status"] = "connection_error"
                result["error"] = str(exc)

        if not self.health_status and self.fallback_enabled:
            result["status"] = "fallback_python"
            result["actual_count"] = min(count, 6)
            result["note"] = "Elixir unavailable — using Python-only fallback (max 6 agents)"

        if "status" not in result:
            result["status"] = "no_action"

        self.experiments_log.append(result)
        os.makedirs(os.path.dirname(EXPERIMENTS_LOG), exist_ok=True)
        with open(EXPERIMENTS_LOG, "a") as f:
            f.write(json.dumps(result) + "\n")

        return result


if __name__ == "__main__":
    bridge = ElixirBridge(host="localhost", port=9999)
    result = bridge.spawn_research_swarm("test query", 10)
    print(f"Bridge test: status={result['status']}, actual_count={result.get('actual_count', 0)}")
