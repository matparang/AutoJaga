"""Configuration loading utilities."""

import json
import os
from pathlib import Path

from jagachatbot.config.schema import Config


def get_config_path() -> Path:
    """Get the configuration file path, respecting JAGACHATBOT_CONFIG env var override."""
    # Termux/offline override: set JAGACHATBOT_CONFIG to point to a custom config file
    env_path = os.getenv("JAGACHATBOT_CONFIG")
    if env_path:
        return Path(env_path)
    return Path.home() / ".jagachatbot" / "config.json"


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file or create default.
    
    Args:
        config_path: Optional path to config file. Uses default if not provided.
    
    Returns:
        Loaded configuration object.
    """
    path = config_path or get_config_path()
    
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            # Override with environment variables
            data = _apply_env_vars(data)
            return Config.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Failed to load config from {path}: {e}")
            print("Using default configuration.")
    
    # Create default config with env vars
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


def save_config(config: Config, config_path: Path | None = None) -> None:
    """Save configuration to file."""
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w") as f:
        json.dump(config.model_dump(), f, indent=2)
