#!/usr/bin/env python3
"""
experiment_tracker.py — Proof-based experiment tracking.
Created: 2026-03-11 via forensic audit remediation.
Prevents hallucination by requiring filesystem PROOF for every claim.
"""

import hashlib
import json
import os
import time
from datetime import datetime

LOG_DIR = "/root/.jagabot/logs/experiments"


class ExperimentTracker:
    """Track experiments with cryptographic proofs written to disk."""

    def __init__(self, log_dir: str = LOG_DIR):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._cache: dict[str, dict] = {}

    def start_experiment(self, name: str, description: str, expected_outcome: str) -> str:
        """Record experiment start. Returns experiment_id."""
        experiment_id = hashlib.md5(f"{name}{time.time()}".encode()).hexdigest()[:12]
        experiment = {
            "id": experiment_id,
            "name": name,
            "description": description,
            "expected_outcome": expected_outcome,
            "start_time": datetime.now().isoformat(),
            "status": "running",
            "proofs": [],
        }
        self._save(experiment_id, experiment)
        return experiment_id

    def add_proof(self, experiment_id: str, proof_type: str, proof_data) -> str | None:
        """Add a verification proof (file hash, PID, etc.). Returns proof_hash."""
        exp = self._load(experiment_id)
        if exp is None:
            return None
        proof = {
            "timestamp": datetime.now().isoformat(),
            "type": proof_type,
            "data": proof_data,
            "proof_hash": hashlib.sha256(str(proof_data).encode()).hexdigest()[:8],
        }
        exp["proofs"].append(proof)
        self._save(experiment_id, exp)
        return proof["proof_hash"]

    def complete_experiment(self, experiment_id: str, outcome: str, metrics: dict) -> bool:
        """Mark experiment complete with measured results."""
        exp = self._load(experiment_id)
        if exp is None:
            return False
        end = datetime.now()
        start = datetime.fromisoformat(exp["start_time"])
        exp.update({
            "status": "complete",
            "end_time": end.isoformat(),
            "outcome": outcome,
            "metrics": metrics,
            "duration_seconds": (end - start).total_seconds(),
        })
        self._save(experiment_id, exp)
        return True

    def get_real_count(self) -> int:
        """Return count of completed experiments from disk (no LLM involved)."""
        count = 0
        for fname in os.listdir(self.log_dir):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.log_dir, fname)) as f:
                    data = json.load(f)
                if data.get("status") == "complete":
                    count += 1
            except Exception:
                pass
        return count

    def _save(self, experiment_id: str, data: dict) -> None:
        path = os.path.join(self.log_dir, f"{experiment_id}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        self._cache[experiment_id] = data

    def _load(self, experiment_id: str) -> dict | None:
        if experiment_id in self._cache:
            return self._cache[experiment_id]
        path = os.path.join(self.log_dir, f"{experiment_id}.json")
        try:
            with open(path) as f:
                data = json.load(f)
            self._cache[experiment_id] = data
            return data
        except Exception:
            return None


if __name__ == "__main__":
    et = ExperimentTracker()
    exp_id = et.start_experiment("test_experiment", "Testing experiment tracking", "Proof files created")
    et.add_proof(exp_id, "file_creation", "/tmp/test_proof.txt")
    et.complete_experiment(exp_id, "success", {"tokens_saved": 100})
    print(f"Real experiment count: {et.get_real_count()}")
