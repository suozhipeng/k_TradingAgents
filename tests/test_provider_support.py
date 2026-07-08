import pytest

from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.provider_support import get_provider_unavailable_message


@pytest.mark.unit
def test_google_provider_reports_temporarily_disabled():
    message = get_provider_unavailable_message("google")
    assert message is not None
    assert "Gemini support is temporarily disabled" in message
    assert "mootdx" in message


@pytest.mark.unit
def test_create_llm_client_rejects_google_provider():
    with pytest.raises(ValueError, match="Gemini support is temporarily disabled"):
        create_llm_client(provider="google", model="gemini-2.5-flash")
