import os
from typing import Any, Optional

from langchain_openai import AzureChatOpenAI

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model

_PASSTHROUGH_KWARGS = (
    "timeout", "max_retries", "api_key", "reasoning_effort", "temperature",
    "callbacks", "http_client", "http_async_client",
)


class NormalizedAzureChatOpenAI(AzureChatOpenAI):
    """AzureChatOpenAI with normalized content output."""

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))


class AzureOpenAIClient(BaseLLMClient):
    """Client for Azure OpenAI deployments.

    Requires environment variables:
        AZURE_OPENAI_API_KEY: API key
        AZURE_OPENAI_ENDPOINT: Endpoint URL (e.g. https://<resource>.openai.azure.com/)
        AZURE_OPENAI_DEPLOYMENT_NAME: Deployment name
        OPENAI_API_VERSION: API version (e.g. 2025-03-01-preview)
    """

    def __init__(self, model: str, base_url: Optional[str] = None, **kwargs):
        super().__init__(model, base_url, **kwargs)

    def get_llm(self) -> Any:
        """Return configured AzureChatOpenAI instance.

        Validate the Azure settings before constructing the LangChain client so
        callers receive one actionable project-level error instead of a
        provider-specific validation traceback.
        """
        self.warn_if_unknown_model()

        required_settings = {
            "AZURE_OPENAI_API_KEY": os.environ.get("AZURE_OPENAI_API_KEY"),
            "AZURE_OPENAI_ENDPOINT": self.base_url or os.environ.get("AZURE_OPENAI_ENDPOINT"),
            "OPENAI_API_VERSION": os.environ.get("OPENAI_API_VERSION"),
        }
        missing = [name for name, value in required_settings.items() if not value]
        if missing:
            raise ValueError(
                "Azure OpenAI configuration incomplete. Set "
                + ", ".join(missing)
                + "."
            )

        llm_kwargs = {
            "model": self.model,
            "api_key": required_settings["AZURE_OPENAI_API_KEY"],
            "azure_endpoint": required_settings["AZURE_OPENAI_ENDPOINT"],
            "api_version": required_settings["OPENAI_API_VERSION"],
            "azure_deployment": os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", self.model),
        }

        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        return NormalizedAzureChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        """Azure accepts any deployed model name."""
        return True
