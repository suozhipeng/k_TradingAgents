"""Provider support and temporary availability gates."""

from __future__ import annotations

TEMPORARILY_DISABLED_PROVIDERS = {
    "google": (
        "Gemini support is temporarily disabled. "
        "Current blocker: langchain-google-genai requires a newer httpx, "
        "which conflicts with mootdx 0.11.7 in the A-share provider stack."
    ),
}


def get_provider_unavailable_message(provider: str) -> str | None:
    """Return the unavailability message for a provider, if any."""
    return TEMPORARILY_DISABLED_PROVIDERS.get(str(provider).lower())


def is_provider_available(provider: str) -> bool:
    """Return True when the provider is currently enabled."""
    return get_provider_unavailable_message(provider) is None


def assert_provider_available(provider: str) -> None:
    """Raise ValueError when the provider is currently disabled."""
    message = get_provider_unavailable_message(provider)
    if message:
        raise ValueError(message)
