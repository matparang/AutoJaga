"""Configuration module for jagabot."""

from jagabot.config.loader import load_config, get_config_path
from jagabot.config.schema import Config

__all__ = ["Config", "load_config", "get_config_path"]
