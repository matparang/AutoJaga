"""LiteLLM provider implementation for multi-provider support."""

import json
import os
from typing import Any

import litellm
from litellm import acompletion
from loguru import logger

from jagabot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from jagabot.providers.registry import find_by_model, find_gateway

# Global OpenRouter compatibility: disable problematic LiteLLM features
# OpenRouter doesn't accept certain parameters that LiteLLM tries to pass
os.environ.setdefault("LITELLM_DROP_PARAMS", "True")
os.environ.setdefault("LITELLM_ALLOW_NON_OPENAI_KEYS", "True")

# Force LiteLLM to drop unsupported params BEFORE the call
import litellm
litellm.drop_params = True
litellm.set_verbose = False


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.
    
    Supports OpenRouter, Anthropic, OpenAI, Gemini, MiniMax, and many other providers through
    a unified interface.  Provider-specific logic is driven by the registry
    (see providers/registry.py) — no if-elif chains needed here.
    """
    
    def __init__(
        self, 
        api_key: str | None = None, 
        api_base: str | None = None,
        default_model: str = "anthropic/claude-opus-4-5",
        extra_headers: dict[str, str] | None = None,
        provider_name: str | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.extra_headers = extra_headers or {}
        
        # Detect gateway / local deployment.
        # provider_name (from config key) is the primary signal;
        # api_key / api_base are fallback for auto-detection.
        self._gateway = find_gateway(provider_name, api_key, api_base)
        
        # Configure environment variables
        if api_key:
            self._setup_env(api_key, api_base, default_model)
        
        if api_base:
            litellm.api_base = api_base
        
        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
        # Drop unsupported parameters for providers (e.g., gpt-5 rejects some params)
        litellm.drop_params = True
    
    def _setup_env(self, api_key: str, api_base: str | None, model: str) -> None:
        """Set environment variables based on detected provider."""
        spec = self._gateway or find_by_model(model)
        if not spec:
            return

        # Gateway/local overrides existing env; standard provider doesn't
        if self._gateway:
            os.environ[spec.env_key] = api_key
        else:
            os.environ.setdefault(spec.env_key, api_key)

        # Resolve env_extras placeholders:
        #   {api_key}  → user's API key
        #   {api_base} → user's api_base, falling back to spec.default_api_base
        effective_base = api_base or spec.default_api_base
        for env_name, env_val in spec.env_extras:
            resolved = env_val.replace("{api_key}", api_key)
            resolved = resolved.replace("{api_base}", effective_base)
            os.environ.setdefault(env_name, resolved)
    
    def _resolve_model(self, model: str) -> str:
        """Resolve model name by applying provider/gateway prefixes."""
        if self._gateway:
            # Gateway mode: apply gateway prefix, skip provider-specific prefixes
            prefix = self._gateway.litellm_prefix
            if self._gateway.strip_model_prefix:
                model = model.split("/")[-1]
            if prefix and not model.startswith(f"{prefix}/"):
                model = f"{prefix}/{model}"
            return model
        
        # Standard mode: auto-prefix for known providers
        spec = find_by_model(model)
        if spec and spec.litellm_prefix:
            if not any(model.startswith(s) for s in spec.skip_prefixes):
                model = f"{spec.litellm_prefix}/{model}"
        
        return model
    
    def _apply_model_overrides(self, model: str, kwargs: dict[str, Any]) -> None:
        """Apply model-specific parameter overrides from the registry."""
        model_lower = model.lower()
        spec = find_by_model(model)
        if spec:
            for pattern, overrides in spec.model_overrides:
                if pattern in model_lower:
                    kwargs.update(overrides)
                    return
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        extra_body: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """
        Send a chat completion request via LiteLLM.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5').
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            extra_body: Optional dict of provider-specific params (e.g. DashScope enable_search).

        Returns:
            LLMResponse with content and/or tool calls.
        """
        model = self._resolve_model(model or self.default_model)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        # Apply model-specific overrides (e.g. kimi-k2.5 temperature)
        self._apply_model_overrides(model, kwargs)
        
        # Pass api_key directly — more reliable than env vars alone
        if self.api_key:
            kwargs["api_key"] = self.api_key
        
        # Force api_base for DeepSeek — prevents LiteLLM routing to OpenAI
        model_str = kwargs.get("model", "")
        if "deepseek" in model_str.lower():
            kwargs.setdefault("api_base", "https://api.deepseek.com")
        
        # Pass api_base for custom endpoints
        if self.api_base:
            kwargs["api_base"] = self.api_base
        
        # Pass extra headers (e.g. APP-Code for AiHubMix)
        if self.extra_headers:
            kwargs["extra_headers"] = self.extra_headers
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        # Forward provider-specific body params (e.g. DashScope enable_search)
        if extra_body:
            kwargs["extra_body"] = extra_body
        
        # OpenRouter compatibility: don't pass usage tracking params
        # OpenRouter's API doesn't accept certain LiteLLM parameters
        # Check model name, provider name, and api_base
        is_openrouter = (
            "openrouter" in model.lower() or 
            "openrouter" in (self.api_base or "").lower() or
            (self._gateway and "openrouter" in (self._gateway.name or "").lower())
        )
        
        # Also check if OPENROUTER_API_KEY is set (global indicator)
        if os.getenv("OPENROUTER_API_KEY"):
            logger.debug(f"OpenRouter detected via OPENROUTER_API_KEY env var")
            is_openrouter = True
        
        if is_openrouter:
            logger.debug(f"OpenRouter mode: stripping usage params from kwargs")
            # Remove any usage-related params that might conflict
            kwargs.pop("usage", None)
            kwargs.pop("stream_options", None)
            kwargs.pop("include_usage", None)
            kwargs.pop("stream", None)  # Also remove stream param
            # Also remove from extra_body if present
            if "extra_body" in kwargs:
                kwargs["extra_body"].pop("usage", None)
                kwargs["extra_body"].pop("include_usage", None)
                kwargs["extra_body"].pop("stream_options", None)

        try:
            # OpenRouter workaround: LiteLLM adds 'usage' param internally
            # Must use raw OpenAI client to bypass LiteLLM for OpenRouter
            if is_openrouter:
                logger.debug(f"Using direct OpenAI client for OpenRouter (bypassing LiteLLM)")
                from openai import AsyncOpenAI
                
                # Get API key - try env var first, then fall back to self.api_key
                openrouter_key = os.getenv("OPENROUTER_API_KEY") or self.api_key
                logger.debug(f"OpenRouter API key: {'SET' if openrouter_key else 'MISSING'}")
                
                if not openrouter_key:
                    raise ValueError("OpenRouter API key not found - set OPENROUTER_API_KEY env var or configure openrouter provider in config.json")
                
                # Create OpenAI client pointed at OpenRouter
                client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=openrouter_key,
                    default_headers={
                        "HTTP-Referer": "https://github.com/jagabot",
                        "X-Title": "jagabot",
                    }
                )
                
                # Call OpenRouter directly (no LiteLLM!)
                model_name = kwargs["model"].replace("openrouter/", "").replace("openai/", "")
                logger.debug(f"Calling OpenRouter with model: {model_name}")
                
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=kwargs["messages"],
                    max_tokens=kwargs.get("max_tokens", 4096),
                    temperature=kwargs.get("temperature", 0.7),
                    tools=kwargs.get("tools"),
                    tool_choice="auto" if kwargs.get("tools") else None,
                )
                logger.debug(f"OpenRouter call succeeded")
            else:
                response = await acompletion(**kwargs)
            
            return self._parse_response(response)
        except Exception as e:
            # Return error as content for graceful handling
            logger.error(f"LLM call failed: {e}")
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )
    
    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message
        
        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments from JSON string if needed
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
        
        reasoning_content = getattr(message, "reasoning_content", None)
        
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
            reasoning_content=reasoning_content,
        )
    
    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
