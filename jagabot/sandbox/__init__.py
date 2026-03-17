"""Sandbox module — Docker-based code execution, self-correction, tracking, and verification."""

from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig, ExecutionResult
from jagabot.sandbox.self_correct import SelfCorrectingRunner
from jagabot.sandbox.tracker import SandboxTracker
from jagabot.sandbox.verifier import SandboxVerifier

__all__ = [
    "SafePythonExecutor",
    "SandboxConfig",
    "ExecutionResult",
    "SelfCorrectingRunner",
    "SandboxTracker",
    "SandboxVerifier",
]
