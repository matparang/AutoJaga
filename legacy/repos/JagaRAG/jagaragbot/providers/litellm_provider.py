"""LiteLLM provider implementation for multi-provider support."""

import os
from typing import Any

import litellm
from litellm import acompletion

from jagaragbot.providers.base import LLMProvider, LLMResponse

# Global LiteLLM settings
os.environ.setdefault("LITELLM_DROP_PARAMS", "True")
litellm.drop_params = True
litellm.suppress_debug_info = True


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.
    
    Supports OpenAI, Anthropic, DeepSeek, Gemini, and many other providers
    through a unified interface.
    """
    
    def __init__(
        self, 
        api_key: str | None = None, 
        api_base: str | None = None,
        default_model: str = "openai/gpt-4o-mini",
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        
        # Set up environment for common providers
        if api_key:
            self._setup_env(api_key, default_model)
        
        if api_base:
            litellm.api_base = api_base
    
    def _setup_env(self, api_key: str, model: str) -> None:
        """Set environment variables based on detected provider."""
        model_lower = model.lower()
        
        if "deepseek" in model_lower:
            os.environ.setdefault("DEEPSEEK_API_KEY", api_key)
        elif "claude" in model_lower or "anthropic" in model_lower:
            os.environ.setdefault("ANTHROPIC_API_KEY", api_key)
        elif "gemini" in model_lower:
            os.environ.setdefault("GEMINI_API_KEY", api_key)
        else:
            # Default to OpenAI
            os.environ.setdefault("OPENAI_API_KEY", api_key)
    
    def _resolve_model(self, model: str) -> str:
        """Resolve model name by applying provider prefixes."""
        model_lower = model.lower()
        
        # Add provider prefix if needed
        if "deepseek" in model_lower and not model.startswith("deepseek/"):
            return f"deepseek/{model}"
        if "gemini" in model_lower and not model.startswith("gemini/"):
            return f"gemini/{model}"
        
        return model
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat completion request via LiteLLM."""
        model = self._resolve_model(model or self.default_model)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        # Pass api_key directly
        if self.api_key:
            kwargs["api_key"] = self.api_key
        
        # Force api_base for DeepSeek
        if "deepseek" in model.lower():
            kwargs.setdefault("api_base", "https://api.deepseek.com")
        
        if self.api_base:
            kwargs["api_base"] = self.api_base

        try:
            response = await acompletion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )
    
    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message
        
        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        return LLMResponse(
            content=message.content,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )
    
    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
