import pytest

from ai import Model
from ai.errors import ProviderNotFoundError
from ai.providers.base import Provider
from ai.registry import ProviderRegistry


class CountingProvider(Provider):
    name = "stub"

    def supports(self, model: Model) -> bool:
        return model.provider == self.name

    async def stream(self, model: Model, context, options):  # pragma: no cover - registry tests do not stream
        raise NotImplementedError


STUB_MODEL = Model(
    id="stub:test-model",
    provider="stub",
    inputPrice=0.0,
    outputPrice=0.0,
    contextWindow=1,
    maxOutputTokens=1,
)


def test_registry_lazily_instantiates_provider_factory() -> None:
    created = {"count": 0}

    def factory() -> CountingProvider:
        created["count"] += 1
        return CountingProvider()

    registry = ProviderRegistry()
    registry.register_factory("stub", factory)

    assert created["count"] == 0

    provider = registry.resolve(STUB_MODEL)

    assert provider.name == "stub"
    assert created["count"] == 1


def test_registry_reuses_cached_provider_instance() -> None:
    created = {"count": 0}

    def factory() -> CountingProvider:
        created["count"] += 1
        return CountingProvider()

    registry = ProviderRegistry()
    registry.register_factory("stub", factory)

    first = registry.resolve(STUB_MODEL)
    second = registry.resolve(STUB_MODEL)

    assert first is second
    assert created["count"] == 1


def test_registry_raises_on_unknown_provider() -> None:
    registry = ProviderRegistry()
    model = Model(
        id="unknown:model",
        provider="unknown",
        inputPrice=0.0,
        outputPrice=0.0,
        contextWindow=1,
        maxOutputTokens=1,
    )
    with pytest.raises(ProviderNotFoundError):
        registry.resolve(model)


def test_registry_has_builtin_zhipu_factory() -> None:
    registry = ProviderRegistry()

    assert "zhipu" in registry.factories
