"""Configuration loading utilities."""

import json
import os
from pathlib import Path

from autojaga.config.schema import Config


def get_config_path() -> Path:
    """Get the default configuration file path."""
    return Path.home() / ".autojaga" / "config.json"


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from file or create default."""
    path = config_path or get_config_path()
    
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            data = _apply_env_vars(data)
            return Config.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Failed to load config from {path}: {e}")
    
    config = Config()
    config = _apply_env_to_config(config)
    return config


def _apply_env_vars(data: dict) -> dict:
    """Apply environment variables to config data."""
    providers = data.get("providers", {})
    
    if os.getenv("OPENAI_API_KEY"):
        providers.setdefault("openai", {})["api_key"] = os.getenv("OPENAI_API_KEY")
    if os.getenv("ANTHROPIC_API_KEY"):
        providers.setdefault("anthropic", {})["api_key"] = os.getenv("ANTHROPIC_API_KEY")
    if os.getenv("DEEPSEEK_API_KEY"):
        providers.setdefault("deepseek", {})["api_key"] = os.getenv("DEEPSEEK_API_KEY")
    if os.getenv("GEMINI_API_KEY"):
        providers.setdefault("gemini", {})["api_key"] = os.getenv("GEMINI_API_KEY")
    
    data["providers"] = providers
    return data


def _apply_env_to_config(config: Config) -> Config:
    """Apply environment variables to Config object."""
    if os.getenv("OPENAI_API_KEY"):
        config.providers.openai.api_key = os.getenv("OPENAI_API_KEY", "")
    if os.getenv("ANTHROPIC_API_KEY"):
        config.providers.anthropic.api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if os.getenv("DEEPSEEK_API_KEY"):
        config.providers.deepseek.api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if os.getenv("GEMINI_API_KEY"):
        config.providers.gemini.api_key = os.getenv("GEMINI_API_KEY", "")
    return config
