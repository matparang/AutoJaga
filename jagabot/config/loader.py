"""Configuration loading utilities."""

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from jagabot.config.schema import Config

# Load .env file from jagabot directory
load_dotenv(Path.home() / ".jagabot" / ".env")


def get_config_path() -> Path:
    """Get the default configuration file path."""
    return Path.home() / ".jagabot" / "config.json"


def get_data_dir() -> Path:
    """Get the jagabot data directory."""
    from jagabot.utils.helpers import get_data_path
    return get_data_path()


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
            data = _migrate_config(data)
            data = _expand_env_vars(data)
            return Config.model_validate(convert_keys(data))
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Warning: Failed to load config from {path}: {e}")
            print("Using default configuration.")
    
    return Config()


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    Save configuration to file.
    
    Args:
        config: Configuration to save.
        config_path: Optional path to save to. Uses default if not provided.
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to camelCase format
    data = config.model_dump()
    data = convert_to_camel(data)
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _expand_env_vars(data: Any) -> Any:
    """Recursively expand ${VAR_NAME} placeholders in string values using os.environ."""
    if isinstance(data, dict):
        return {k: _expand_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_expand_env_vars(item) for item in data]
    if isinstance(data, str):
        return re.sub(r"\$\{([^}]+)\}", lambda m: os.environ.get(m.group(1), ""), data)
    return data


def _migrate_config(data: dict) -> dict:
    """Migrate old config formats to current."""
    # Ensure model_presets exist (for model switching)
    if "model_presets" not in data:
        data["model_presets"] = {
            "1": {
                "name": "GPT-4o-mini (Fast)",
                "model_id": "deepseek/deepseek-chat",
                "provider": "deepseek",
                "purpose": "routine",
                "max_tokens": 2000,
                "token_cost_per_1k_input": 0.00015,
                "token_cost_per_1k_output": 0.00060
            },
            "2": {
                "name": "GPT-4o (Smart)",
                "model_id": "deepseek/deepseek-reasoner",
                "provider": "deepseek",
                "purpose": "reasoning",
                "max_tokens": 4000,
                "token_cost_per_1k_input": 0.00250,
                "token_cost_per_1k_output": 0.01000
            }
        }
        print("✅ Added model_presets to config (model switching enabled)")
    
    # Ensure current_model and auto_switch exist
    if "current_model" not in data:
        data["current_model"] = "1"
    if "auto_switch" not in data:
        data["auto_switch"] = True
    
    # Fix agents.defaults.model to use Model 1's model_id (fallback only)
    # The actual model is selected by ModelSwitchboard based on profile
    if "agents" in data and "defaults" in data["agents"]:
        old_model = data["agents"]["defaults"].get("model", "")
        # If it's set to "modelPresets" or something invalid, fix it
        if old_model in ["modelPresets", "model_presets", "auto", "switching"]:
            data["agents"]["defaults"]["model"] = "openai/gpt-4o-mini"
            print("ℹ️ Fixed agents.defaults.model → openai/gpt-4o-mini (fallback only)")
    
    # Legacy migration: providers.deepseek_key → providers.deepseek.apiKey
    if "deepseek_key" in data.get("providers", {}):
        data["providers"]["deepseek"] = {
            "apiKey": data["providers"]["deepseek_key"],
            "apiBase": None,
            "extraHeaders": None
        }
        del data["providers"]["deepseek_key"]
    
    # Move tools.exec.restrictToWorkspace → tools.restrictToWorkspace
    tools = data.get("tools", {})
    exec_cfg = tools.get("exec", {})
    if "restrictToWorkspace" in exec_cfg and "restrictToWorkspace" not in tools:
        tools["restrictToWorkspace"] = exec_cfg.pop("restrictToWorkspace")
    
    return data


def convert_keys(data: Any) -> Any:
    """Convert camelCase keys to snake_case for Pydantic."""
    if isinstance(data, dict):
        return {camel_to_snake(k): convert_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_keys(item) for item in data]
    return data


def convert_to_camel(data: Any) -> Any:
    """Convert snake_case keys to camelCase."""
    if isinstance(data, dict):
        return {snake_to_camel(k): convert_to_camel(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_to_camel(item) for item in data]
    return data


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])
