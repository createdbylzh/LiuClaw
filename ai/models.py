from __future__ import annotations

from .errors import ProviderNotFoundError
from .types import Model

_MODEL_CATALOG: dict[str, Model] = {
    "openai:gpt-5": Model(
        id="openai:gpt-5",
        provider="openai",
        inputPrice=1.25,
        outputPrice=10.0,
        contextWindow=272000,
        maxOutputTokens=128000,
        supports_reasoning_levels=("off", "minimal", "low", "medium", "high", "xhigh"),
        supports_images=True,
        supports_prompt_cache=True,
        supports_session=True,
    ),
    "openai:gpt-5-mini": Model(
        id="openai:gpt-5-mini",
        provider="openai",
        inputPrice=0.25,
        outputPrice=2.0,
        contextWindow=272000,
        maxOutputTokens=128000,
        supports_reasoning_levels=("off", "minimal", "low", "medium", "high"),
        supports_images=True,
        supports_prompt_cache=True,
        supports_session=True,
    ),
    "anthropic:claude-sonnet-4": Model(
        id="anthropic:claude-sonnet-4",
        provider="anthropic",
        inputPrice=3.0,
        outputPrice=15.0,
        contextWindow=200000,
        maxOutputTokens=64000,
        supports_reasoning_levels=("off", "low", "medium", "high", "xhigh"),
        supports_images=True,
        supports_prompt_cache=True,
    ),
    "anthropic:claude-haiku-3-5": Model(
        id="anthropic:claude-haiku-3-5",
        provider="anthropic",
        inputPrice=0.8,
        outputPrice=4.0,
        contextWindow=200000,
        maxOutputTokens=64000,
        supports_reasoning_levels=("off", "low", "medium", "high"),
        supports_images=True,
        supports_prompt_cache=True,
    ),
    "zhipu:glm-5": Model(
        id="zhipu:glm-5",
        provider="zhipu",
        inputPrice=0.0,
        outputPrice=0.0,
        contextWindow=200000,
        maxOutputTokens=128000,
        metadata={"priceStatus": "needs_manual_sync"},
        supports_reasoning_levels=("off", "low", "medium", "high"),
    ),
    "zhipu:glm-5-turbo": Model(
        id="zhipu:glm-5-turbo",
        provider="zhipu",
        inputPrice=0.0,
        outputPrice=0.0,
        contextWindow=200000,
        maxOutputTokens=128000,
        metadata={"priceStatus": "needs_manual_sync"},
        supports_reasoning_levels=("off", "low", "medium", "high"),
    ),
    "zhipu:glm-4.7": Model(
        id="zhipu:glm-4.7",
        provider="zhipu",
        inputPrice=0.0,
        outputPrice=0.0,
        contextWindow=200000,
        maxOutputTokens=128000,
        metadata={"priceStatus": "needs_manual_sync"},
        supports_reasoning_levels=("off", "low", "medium", "high"),
    ),
    "zhipu:glm-4.6": Model(
        id="zhipu:glm-4.6",
        provider="zhipu",
        inputPrice=0.0,
        outputPrice=0.0,
        contextWindow=200000,
        maxOutputTokens=128000,
        metadata={"priceStatus": "needs_manual_sync"},
        supports_reasoning_levels=("off", "low", "medium", "high"),
    ),
}


def get_model(model_id: str) -> Model:
    """根据模型 ID 返回内置模型目录中的模型定义。"""

    try:
        return _MODEL_CATALOG[model_id]
    except KeyError as exc:
        raise ProviderNotFoundError(f"Unknown model '{model_id}'") from exc



def list_models(provider: str | None = None) -> list[Model]:
    """返回内置模型目录，可按 provider 过滤。"""

    models = list(_MODEL_CATALOG.values())
    if provider is None:
        return models
    return [model for model in models if model.provider == provider]
