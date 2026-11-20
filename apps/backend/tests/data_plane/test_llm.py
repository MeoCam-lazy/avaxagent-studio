from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import BadRequestError

import app.data_plane.workers.llm as llm_module
from app.data_plane.workers.llm import OpenAIRunner


def mock_openai_client(monkeypatch, create: AsyncMock) -> None:
    class Client:
        def __init__(self, api_key: str) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(llm_module, "AsyncOpenAI", Client)


def completion(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


@pytest.mark.asyncio
async def test_openai_gpt6_uses_supported_default_temperature(monkeypatch):
    create = AsyncMock(return_value=completion("Agent response"))
    mock_openai_client(monkeypatch, create)

    result = await OpenAIRunner(api_key="test-key").complete(
        model="gpt-6-luna",
        system="You are helpful",
        prompt="Hello",
        temperature=0.3,
    )

    assert result == "Agent response"
    assert create.await_args.kwargs == {
        "model": "gpt-6-luna",
        "messages": [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ],
        "max_completion_tokens": 4096,
    }


@pytest.mark.asyncio
async def test_openai_retries_only_unsupported_temperature(monkeypatch):
    error = BadRequestError(
        "Unsupported value: 'temperature' does not support 0.3 with this model.",
        response=httpx.Response(
            400,
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        ),
        body={"param": "temperature", "code": "unsupported_value"},
    )
    create = AsyncMock(side_effect=[error, completion("Retried response")])
    mock_openai_client(monkeypatch, create)

    result = await OpenAIRunner(api_key="test-key").complete(
        model="new-reasoning-model",
        system="",
        prompt="Hello",
        temperature=0.3,
    )

    assert result == "Retried response"
    assert create.await_count == 2
    assert create.await_args_list[0].kwargs["temperature"] == 0.3
    assert "temperature" not in create.await_args_list[1].kwargs


@pytest.mark.asyncio
async def test_openai_keeps_temperature_for_supported_model(monkeypatch):
    create = AsyncMock(return_value=completion("Response"))
    mock_openai_client(monkeypatch, create)

    result = await OpenAIRunner(api_key="test-key").complete(
        model="gpt-4.1-mini",
        system="",
        prompt="Hello",
        temperature=0.2,
    )

    assert result == "Response"
    create.assert_awaited_once()
    assert create.await_args.kwargs["temperature"] == 0.2
