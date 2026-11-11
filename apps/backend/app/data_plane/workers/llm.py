"""LLM Runner protocol and Anthropic implementation for agent job workers."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import anthropic

from app.core.config import settings
from app.core.errors import FeatureDisabled


@runtime_checkable
class LlmRunner(Protocol):
    """Protocol for generating LLM completions."""

    async def complete(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        temperature: float,
    ) -> str:
        """Execute completion and return generated text."""
        ...


class AnthropicRunner:
    """Async Anthropic messages API runner."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.llm_api_key

    async def complete(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        temperature: float,
    ) -> str:
        if not self.api_key:
            raise FeatureDisabled("llm", "LLM_API_KEY not configured")

        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        res = await client.messages.create(**kwargs)
        text_blocks = [
            block.text for block in res.content if hasattr(block, "text") and block.text
        ]
        return "".join(text_blocks)


def get_llm_runner() -> LlmRunner:
    """Return configured LLM runner or raise FeatureDisabled if LLM_API_KEY is missing."""
    if not settings.llm_api_key:
        raise FeatureDisabled("llm", "LLM_API_KEY not configured")
    return AnthropicRunner()
