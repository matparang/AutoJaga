"""LiteLLM provider implementation."""

import json
import os
from typing import Any

import litellm
from litellm import acompletion

from autojaga.providers.base import LLMProvider, LLMResponse, ToolCallRequest

# Global LiteLLM settings
os.environ.setdefault("LITELLM_DROP_PARAMS", "True")
litellm.drop_params = True
litellm.suppress_debug_info = True


class LiteLLMProvider(LLMProvider):
    """LLM provider using LiteLLM for multi-provider support."""
    
    def __init__(
        self, 
        api_key: str | None = None, 
        api_base: str | None = None,
        default_model: str = "openai/gpt-4o-mini",
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        
        # Set up environment
        if api_key:
            self._setup_env(api_key, default_model)
        
        if api_base:
            litellm.api_base = api_base
    
    def _setup_env(self, api_key: str, model: str) -> None:
        """Set environment variables based on model."""
        model_lower = model.lower()
        
        if "deepseek" in model_lower:
            os.environ.setdefault("DEEPSEEK_API_KEY", api_key)
        elif "claude" in model_lower or "anthropic" in model_lower:
            os.environ.setdefault("ANTHROPIC_API_KEY", api_key)
        elif "gemini" in model_lower:
            os.environ.setdefault("GEMINI_API_KEY", api_key)
        else:
            os.environ.setdefault("OPENAI_API_KEY", api_key)
    
    def _resolve_model(self, model: str) -> str:
        """Resolve model name with provider prefixes."""
        model_lower = model.lower()
        
        if "deepseek" in model_lower and not model.startswith("deepseek/"):
            return f"deepseek/{model}"
        if "gemini" in model_lower and not model.startswith("gemini/"):
            return f"gemini/{model}"
        
        return model
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
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
        
        if self.api_key:
            kwargs["api_key"] = self.api_key
        
        if "deepseek" in model.lower():
            kwargs.setdefault("api_base", "https://api.deepseek.com")
        
        if self.api_base:
            kwargs["api_base"] = self.api_base
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await acompletion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )
    
    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response."""
        choice = response.choices[0]
        message = choice.message
        
        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                
                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))
        
        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )
    
    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
