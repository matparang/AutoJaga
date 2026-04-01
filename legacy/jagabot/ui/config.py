"""
Configuration for JAGABOT UI — Neo4j connection + display settings.
"""

import json
import os
from pathlib import Path


class UIConfig:
    """Centralised configuration for the Knowledge Graph UI."""

    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str | None = None
    NEO4J_AUTH_ENABLED: bool = False

    MAX_NODES: int = 50
    DEFAULT_DEPTH: int = 2
    STREAMLIT_PORT: int = 8501

    # Obsidian Black theme colours
    BG_PRIMARY: str = "#1e1e1e"
    BG_SECONDARY: str = "#252525"
    TEXT_PRIMARY: str = "#d4d4d4"
    ACCENT_BLUE: str = "#569cd6"
    ACCENT_GREEN: str = "#6a9955"
    ACCENT_ORANGE: str = "#ce9178"
    ACCENT_YELLOW: str = "#dcdcaa"

    @classmethod
    def load(cls) -> "UIConfig":
        """Load config from env vars → ~/.jagabot/config.json → defaults."""
        inst = cls()

        # 1) Environment variables (highest priority)
        inst.NEO4J_URI = os.getenv("NEO4J_URI", inst.NEO4J_URI)
        inst.NEO4J_USER = os.getenv("NEO4J_USER", inst.NEO4J_USER)
        inst.NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", inst.NEO4J_PASSWORD)
        auth_env = os.getenv("NEO4J_AUTH_ENABLED")
        if auth_env is not None:
            inst.NEO4J_AUTH_ENABLED = auth_env.lower() in ("true", "1", "yes")

        # 2) Config file (lower priority — won't overwrite env values)
        config_file = Path.home() / ".jagabot" / "config.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    data = json.load(f)
                neo4j_cfg = data.get("neo4j", {})
                if not os.getenv("NEO4J_URI"):
                    inst.NEO4J_URI = neo4j_cfg.get("uri", inst.NEO4J_URI)
                if not os.getenv("NEO4J_USER"):
                    inst.NEO4J_USER = neo4j_cfg.get("user", inst.NEO4J_USER)
                if not os.getenv("NEO4J_PASSWORD"):
                    inst.NEO4J_PASSWORD = neo4j_cfg.get("password", inst.NEO4J_PASSWORD)
                if auth_env is None:
                    inst.NEO4J_AUTH_ENABLED = neo4j_cfg.get(
                        "auth_enabled", inst.NEO4J_AUTH_ENABLED
                    )

                ui_cfg = data.get("ui", {})
                inst.MAX_NODES = ui_cfg.get("max_nodes", inst.MAX_NODES)
                inst.DEFAULT_DEPTH = ui_cfg.get("default_depth", inst.DEFAULT_DEPTH)
                inst.STREAMLIT_PORT = ui_cfg.get("port", inst.STREAMLIT_PORT)
            except (json.JSONDecodeError, OSError):
                pass  # graceful — use defaults

        return inst

    def neo4j_auth(self) -> tuple[str, str] | None:
        """Return (user, password) tuple or None if auth disabled."""
        if not self.NEO4J_AUTH_ENABLED or self.NEO4J_PASSWORD is None:
            return None
        return (self.NEO4J_USER, self.NEO4J_PASSWORD)

    def to_dict(self) -> dict:
        return {
            "neo4j_uri": self.NEO4J_URI,
            "neo4j_user": self.NEO4J_USER,
            "neo4j_auth_enabled": self.NEO4J_AUTH_ENABLED,
            "max_nodes": self.MAX_NODES,
            "default_depth": self.DEFAULT_DEPTH,
            "streamlit_port": self.STREAMLIT_PORT,
        }
