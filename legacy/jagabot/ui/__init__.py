"""
JAGABOT UI — Streamlit Knowledge Graph Explorer

Provides:
- Neo4jConnector: thin wrapper around Neo4j driver
- JagabotUIBridge: single interface to all JAGABOT subsystems
- UISession: per-user session tracking
- UIConfig: configuration management
"""

from jagabot.ui.config import UIConfig

__all__ = [
    "UIConfig",
]

def __getattr__(name):
    """Lazy imports to avoid circular / missing-module errors at import time."""
    if name == "UISession":
        from jagabot.ui.session import UISession
        return UISession
    if name == "Neo4jConnector":
        from jagabot.ui.neo4j_connector import Neo4jConnector
        return Neo4jConnector
    if name == "JagabotUIBridge":
        from jagabot.ui.connectors import JagabotUIBridge
        return JagabotUIBridge
    raise AttributeError(f"module 'jagabot.ui' has no attribute {name!r}")
