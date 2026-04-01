"""JAGABOT Lab — centralized tool execution service.

v3.4: LabService provides validate → execute → log for all tools.
v3.4p2: ParallelLab adds batch submission, workflows, concurrency control.
v3.5: ScalableWorkerPool adds auto-scaling worker pools.
"""

from jagabot.lab.service import LabService
from jagabot.lab.parallel import ParallelLab
from jagabot.lab.scaling import ScalingConfig, ScalableWorkerPool

__all__ = ["LabService", "ParallelLab", "ScalingConfig", "ScalableWorkerPool"]
