from ai import Model, get_model, list_models


def test_get_model_returns_priced_model() -> None:
    model = get_model("openai:gpt-5")

    assert isinstance(model, Model)
    assert model.id == "openai:gpt-5"
    assert model.provider == "openai"
    assert model.inputPrice is not None
    assert model.outputPrice is not None
    assert model.contextWindow > 0
    assert model.maxOutputTokens > 0


def test_list_models_can_filter_by_provider() -> None:
    models = list_models(provider="anthropic")

    assert models
    assert all(model.provider == "anthropic" for model in models)
