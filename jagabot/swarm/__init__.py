"""Jagabot Swarm — parallel tool execution across worker processes.

The swarm module enables running jagabot's 21 financial analysis tools
in parallel via a worker pool, coordinated by a Memory Owner orchestrator.

Queue backends:
  - LocalBackend  — multiprocessing.Queue (zero dependencies, always available)
  - RedisBackend  — Redis pub/sub (optional, for distributed setups)

v2.1 additions: WorkerTracker, CostTracker, Watchdog, SwarmScheduler, Dashboard.

Usage:
  from jagabot.swarm import SwarmOrchestrator
  orchestrator = SwarmOrchestrator()
  result = orchestrator.process_query("Analyze oil crisis risk")
"""

from jagabot.swarm.memory_owner import SwarmOrchestrator
from jagabot.swarm.status import WorkerTracker
from jagabot.swarm.costs import CostTracker
from jagabot.swarm.watchdog import Watchdog
from jagabot.swarm.scheduler import SwarmScheduler
from jagabot.swarm.dashboard import generate_dashboard

__all__ = [
    "SwarmOrchestrator",
    "WorkerTracker",
    "CostTracker",
    "Watchdog",
    "SwarmScheduler",
    "generate_dashboard",
]
