from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from .errors import ProviderNotFoundError
from .providers.base import Provider

ProviderFactory = Callable[[], Provider]


def _default_factories() -> dict[str, ProviderFactory]:
    """返回内置 provider 的默认工厂映射。"""

    from .providers.anthropic import AnthropicProvider
    from .providers.openai import OpenAIProvider
    from .providers.zhipu import ZhipuProvider

    return {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "zhipu": ZhipuProvider,
    }


class ProviderRegistry:
    """维护 provider 工厂注册表，并按需懒加载 provider 实例。"""

    def __init__(
        self,
        providers: Iterable[Provider] | None = None,
        *,
        factories: dict[str, ProviderFactory] | None = None,
    ) -> None:
        """初始化注册表，并预注册内置工厂或已有实例。"""

        self._factories: dict[str, ProviderFactory] = dict(factories or _default_factories())
        self._instances: dict[str, Provider] = {}
        for provider in providers or []:
            self.register(provider)

    @property
    def providers(self) -> list[Provider]:
        """返回当前已经实例化的 provider 副本列表。"""

        return list(self._instances.values())

    @property
    def factories(self) -> dict[str, ProviderFactory]:
        """返回当前已注册的 provider 工厂映射副本。"""

        return dict(self._factories)

    def register(self, provider: Provider) -> None:
        """注册一个已经构造完成的 provider 实例。"""

        self._instances[provider.name] = provider

    def register_factory(self, name: str, factory: ProviderFactory) -> None:
        """注册一个按需实例化的 provider 工厂。"""

        self._factories[name] = factory

    def get_provider(self, model: Any) -> Provider:
        """根据模型解析 provider，并在首次使用时完成懒加载。"""

        provider_name = getattr(model, "provider", None)
        if provider_name:
            return self._get_or_create_by_name(provider_name, model)

        model_id = getattr(model, "id", model)
        if isinstance(model_id, str) and ":" in model_id:
            return self._get_or_create_by_name(model_id.split(":", 1)[0], model)

        for provider in self._all_candidates():
            if provider.supports(model):
                return provider
        raise ProviderNotFoundError(
            f"No provider registered for model '{getattr(model, 'id', model)}'"
        )

    def resolve(self, model: Any) -> Provider:
        """根据统一 `Model` 对象或模型 ID 选择 provider。"""

        return self.get_provider(model)

    def _get_or_create_by_name(self, name: str, model: Any) -> Provider:
        """按 provider 名获取实例，并校验其支持给定模型。"""

        provider = self._get_or_create(name)
        if provider.supports(model):
            return provider
        raise ProviderNotFoundError(
            f"Provider '{name}' does not support model '{getattr(model, 'id', model)}'"
        )

    def _get_or_create(self, name: str) -> Provider:
        """按 provider 名返回缓存实例，必要时通过工厂创建。"""

        if name in self._instances:
            return self._instances[name]
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise ProviderNotFoundError(f"No provider factory registered for '{name}'") from exc
        provider = factory()
        self._instances[name] = provider
        return provider

    def _all_candidates(self) -> list[Provider]:
        """返回当前可用于匹配模型的全部 provider 实例。"""

        providers = list(self._instances.values())
        for name in self._factories:
            if name not in self._instances:
                providers.append(self._get_or_create(name))
        return providers
