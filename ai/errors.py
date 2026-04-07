class AIError(Exception):
    """Base error for the unified AI layer."""


class ProviderNotFoundError(AIError):
    """Raised when no provider matches the requested model."""


class AuthenticationError(AIError):
    """Raised when a provider API key is missing or invalid."""


class UnsupportedFeatureError(AIError):
    """Raised when a provider cannot satisfy a requested feature."""


class ProviderResponseError(AIError):
    """Raised when a provider returns malformed data or the SDK fails."""
