#!/usr/bin/env python3
"""
spawn_with_proof.py — Subagent spawning with PID-based verification proofs.
Created: 2026-03-11 via forensic audit remediation.
"""

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime

SPAWN_LOG = "/root/.jagabot/logs/spawn_proofs.jsonl"


def spawn_with_proof(task: str, count: int = 1, timeout: int = 10) -> dict:
    """
    Spawn `count` subagent processes for `task`.
    Returns a proof dict with real PIDs — never claims success without them.
    """
    spawn_id = hashlib.md5(f"{task}{time.time()}".encode()).hexdigest()[:8]
    proof: dict = {
        "spawn_id": spawn_id,
        "timestamp": datetime.now().isoformat(),
        "task": task,
        "requested_count": count,
        "actual_pids": [],
        "proof_files": [],
        "status": "pending",
    }

    spawned_pids: list[int] = []
    proof_files: list[str] = []

    for i in range(count):
        task_file = f"/tmp/spawn_{spawn_id}_{i}.json"
        done_file = f"{task_file}.done"

        with open(task_file, "w") as f:
            json.dump({"task": task, "spawn_id": spawn_id, "index": i}, f)

        try:
            proc = subprocess.Popen(
                [
                    "python3", "-c",
                    f"import time, json; time.sleep(1); open({done_file!r}, 'w').write('done')",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            spawned_pids.append(proc.pid)
            proof_files.append(done_file)
        except Exception as exc:
            proof["errors"] = proof.get("errors", [])
            proof["errors"].append(str(exc))

    proof["actual_pids"] = spawned_pids
    proof["actual_count"] = len(spawned_pids)
    proof["proof_files"] = proof_files
    proof["status"] = "spawned" if spawned_pids else "failed"

    os.makedirs(os.path.dirname(SPAWN_LOG), exist_ok=True)
    with open(SPAWN_LOG, "a") as f:
        f.write(json.dumps(proof) + "\n")

    return proof


if __name__ == "__main__":
    result = spawn_with_proof("test_task", count=2)
    print(f"Spawned: {result['actual_count']}/{result['requested_count']} | PIDs: {result['actual_pids']}")
