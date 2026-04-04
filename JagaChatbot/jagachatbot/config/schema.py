"""Configuration schema using Pydantic."""

from pathlib import Path
from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    api_key: str = ""
    api_base: str | None = None


class ProvidersConfig(BaseModel):
    """Configuration for LLM providers."""
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    # Local Ollama provider (Termux / offline deployments)
    ollama: ProviderConfig = Field(default_factory=ProviderConfig)


class AgentDefaults(BaseModel):
    """Default agent configuration."""
    workspace: str = "~/.jagachatbot/workspace"
    model: str = "openai/gpt-4o-mini"
    max_tokens: int = 4096
    temperature: float = 0.7
    memory_window: int = 50


class Config(BaseModel):
    """Root configuration for JagaChatbot."""
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.defaults.workspace).expanduser()

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model."""
        model_lower = (model or self.defaults.model).lower()

        # Local Ollama — always has a key (dummy "ollama" value is required by LiteLLM)
        if model_lower.startswith("ollama/") and self.providers.ollama.api_key:
            return self.providers.ollama.api_key
        if "deepseek" in model_lower and self.providers.deepseek.api_key:
            return self.providers.deepseek.api_key
        if ("claude" in model_lower or "anthropic" in model_lower) and self.providers.anthropic.api_key:
            return self.providers.anthropic.api_key
        if "gemini" in model_lower and self.providers.gemini.api_key:
            return self.providers.gemini.api_key
        if self.providers.openai.api_key:
            return self.providers.openai.api_key

        return None
