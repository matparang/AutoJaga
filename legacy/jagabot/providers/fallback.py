"""FallbackProvider — wraps a primary and a fallback LLM provider.

If the primary provider's chat() call returns finish_reason="error"
(network failure, auth error, quota exceeded), the request is
automatically retried on the fallback provider using its default model.
"""

from __future__ import annotations

from loguru import logger

from jagabot.providers.base import LLMProvider, LLMResponse


class FallbackProvider(LLMProvider):
    """
    Transparent provider wrapper that retries on the fallback when
    the primary returns finish_reason="error".

    Usage::

        provider = FallbackProvider(
            primary=LiteLLMProvider(api_key=qwen_key, ...),
            fallback=LiteLLMProvider(api_key=deepseek_key, ...),
        )
        # Used exactly like a plain LiteLLMProvider.
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self._primary = primary
        self._fallback = fallback

    async def chat(
        self,
        messages,
        tools=None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        response = await self._primary.chat(
            messages=messages,
            tools=tools,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if response.finish_reason == "error":
            fallback_model = self._fallback.get_default_model()
            logger.warning(
                f"Primary provider failed — retrying on fallback "
                f"(model: {fallback_model}). Error: {response.content}"
            )
            response = await self._fallback.chat(
                messages=messages,
                tools=tools,
                model=fallback_model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        return response

    def get_default_model(self) -> str:
        return self._primary.get_default_model()
