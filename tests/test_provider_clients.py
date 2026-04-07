from __future__ import annotations

from ai.options import Options
from ai.providers.anthropic import AnthropicProvider
from ai.providers.openai import OpenAIProvider


def test_openai_client_kwargs_use_explicit_api_key_and_base_url(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.example.com/v1")

    provider = OpenAIProvider()
    kwargs = provider._client_kwargs(Options(timeout=12.5))

    assert kwargs == {
        "api_key": "test-openai-key",
        "timeout": 12.5,
        "base_url": "https://openai.example.com/v1",
    }


def test_anthropic_client_kwargs_use_explicit_api_key_and_base_url(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://anthropic.example.com")

    provider = AnthropicProvider()
    kwargs = provider._client_kwargs(Options(timeout=8.0))

    assert kwargs == {
        "api_key": "test-anthropic-key",
        "timeout": 8.0,
        "base_url": "https://anthropic.example.com",
    }
