"""LLM runner protocol and provider implementations for agent job workers."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import anthropic
from openai import AsyncOpenAI

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

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        async with anthropic.AsyncAnthropic(api_key=self.api_key) as client:
            res = await client.messages.create(**kwargs)
        text_blocks = [
            block.text for block in res.content if hasattr(block, "text") and block.text
        ]
        return "".join(text_blocks)


class OpenAIRunner:
    """Async OpenAI Chat Completions runner."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.llm_key_for_provider("openai")

    async def complete(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        temperature: float,
    ) -> str:
        if not self.api_key:
            raise FeatureDisabled("llm", "OpenAI API key not configured")

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with AsyncOpenAI(api_key=self.api_key) as client:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=4096,
                temperature=temperature,
            )
        return response.choices[0].message.content or ""


def get_llm_runner(provider: str | None = None) -> LlmRunner:
    """Return the runner for a provider configured with an API key."""
    selected_provider = (provider or settings.llm_provider).lower()
    if selected_provider == "openai":
        if not settings.llm_key_for_provider(selected_provider):
            raise FeatureDisabled("llm", "OpenAI API key not configured")
        return OpenAIRunner()
    if selected_provider == "anthropic":
        if not settings.llm_key_for_provider(selected_provider):
            raise FeatureDisabled("llm", "Anthropic API key not configured")
        return AnthropicRunner(api_key=settings.llm_key_for_provider(selected_provider))
    raise FeatureDisabled("llm", f"Unsupported LLM provider: {selected_provider}")


def get_llm_providers() -> list[str]:
    """List providers with credentials configured."""
    return [
        provider
        for provider in ("openai", "anthropic")
        if settings.llm_key_for_provider(provider)
    ]


async def list_provider_models(provider: str) -> list[str]:
    """Fetch model IDs visible to the configured provider key."""
    api_key = settings.llm_key_for_provider(provider)
    if not api_key:
        raise FeatureDisabled("llm", "LLM_API_KEY not configured")

    if provider == "openai":
        async with AsyncOpenAI(api_key=api_key) as client:
            page = await client.models.list()
            model_ids = [
                model.id
                for model in page.data
                if model.id.startswith(("gpt-", "chatgpt-"))
                and not any(
                    modality in model.id
                    for modality in (
                        "image",
                        "audio",
                        "realtime",
                        "transcribe",
                        "tts",
                        "embedding",
                        "search-api",
                        "live-",
                    )
                )
            ]
    elif provider == "anthropic":
        async with anthropic.AsyncAnthropic(api_key=api_key) as client:
            page = await client.models.list(limit=100)
            model_ids = [model.id for model in page.data]
    else:
        raise FeatureDisabled("llm", f"Unsupported LLM provider: {provider}")

    return sorted(set(model_ids))
