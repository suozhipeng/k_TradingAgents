"""Tests for Azure OpenAI client configuration validation."""

from __future__ import annotations

import pytest

from tradingagents.llm_clients.azure_client import AzureOpenAIClient


def test_azure_client_reports_all_missing_required_configuration(monkeypatch):
    """Missing Azure settings must produce a project-level actionable error."""
    for name in (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "OPENAI_API_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError) as exc_info:
        AzureOpenAIClient("deployment-name").get_llm()

    message = str(exc_info.value)
    assert "Azure OpenAI configuration incomplete" in message
    assert "AZURE_OPENAI_API_KEY" in message
    assert "AZURE_OPENAI_ENDPOINT" in message
    assert "OPENAI_API_VERSION" in message


def test_azure_client_prefers_explicit_base_url_as_endpoint(monkeypatch):
    """An explicit client base URL must override the environment endpoint."""
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://env-resource.openai.azure.com/")
    monkeypatch.setenv("OPENAI_API_VERSION", "2025-03-01-preview")

    llm = AzureOpenAIClient(
        "deployment-name",
        base_url="https://explicit-resource.openai.azure.com/",
    ).get_llm()

    assert llm.azure_endpoint == "https://explicit-resource.openai.azure.com/"
    assert llm.openai_api_version == "2025-03-01-preview"
