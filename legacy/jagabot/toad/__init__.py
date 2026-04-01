"""
TOAD Integration for AutoJaga

This module provides integration between AutoJaga and TOAD TUI,
allowing AutoJaga to run as an ACP-compatible agent within TOAD.
"""

from .acp_adapter import AutoJagaACP, acp_run

__all__ = ["AutoJagaACP", "acp_run"]
__version__ = "5.0.0"
