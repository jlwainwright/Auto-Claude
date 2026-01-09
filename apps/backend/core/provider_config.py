"""
Provider configuration helpers.

Centralizes provider normalization and OpenAI-compatible credential resolution.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_PROVIDER = "claude"
DEFAULT_ZAI_BASE_URL = "https://api.z.ai/api/coding/paas/v4"


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    api_key: str
    base_url: str | None


def normalize_provider(provider: str | None) -> str:
    if not provider:
        return DEFAULT_PROVIDER
    return provider.strip().lower()


def is_claude_provider(provider: str | None) -> bool:
    return normalize_provider(provider) == "claude"


def is_zhipuai_provider(provider: str | None) -> bool:
    """
    Check if the provider is a ZhipuAI/Z.AI provider.

    ZhipuAI providers (GLM models) use the official zhipuai SDK
    instead of the OpenAI-compatible API wrapper.
    """
    provider_id = normalize_provider(provider)
    return provider_id in ("zai", "glm", "zhipu", "zhipuai")


def get_zhipuai_api_key(provider: str | None) -> str:
    """
    Get the API key for ZhipuAI provider.

    Args:
        provider: Provider identifier (zai, glm, zhipu, zhipuai, etc.)

    Returns:
        API key to use

    Raises:
        ValueError: If no API key is found
    """
    provider_id = normalize_provider(provider)
    if provider_id not in ("zai", "glm", "zhipu", "zhipuai"):
        raise ValueError(f"Provider {provider_id} is not a ZhipuAI provider")

    api_key = (
        os.environ.get("ZAI_API_KEY")
        or os.environ.get("ZHIPUAI_API_KEY")
        or os.environ.get("GLM_API_KEY")
    )

    if not api_key:
        raise ValueError(
            "Missing ZhipuAI API key. Set ZAI_API_KEY, ZHIPUAI_API_KEY, or GLM_API_KEY."
        )

    return api_key


def get_provider_base_url(provider: str | None) -> str | None:
    """
    Get the custom base URL for a provider (for ANTHROPIC_BASE_URL routing).

    This allows using the native Claude SDK with alternative providers like Z.AI
    that offer Claude-compatible endpoints. This is the recommended approach over
    using OpenAICompatClient.

    Args:
        provider: Provider identifier (zai, glm, zhipu, zhipuai, etc.)

    Returns:
        Base URL to use for ANTHROPIC_BASE_URL, or None for default Anthropic endpoint
    """
    provider_id = normalize_provider(provider)

    if provider_id in ("zai", "glm", "zhipu", "zhipuai"):
        # Z.AI provides a Claude-compatible endpoint
        # See: https://docs.bigmodel.cn/cn/guide/develop/claude
        return (
            os.environ.get("ZAI_BASE_URL")
            or os.environ.get("GLM_BASE_URL")
            or "https://open.bigmodel.cn/api/anthropic"
        )

    # For claude provider, use default (None = Anthropic's default endpoint)
    return None


def get_provider_api_key(provider: str | None) -> str | None:
    """
    Get the API key for a provider (for ANTHROPIC_AUTH_TOKEN routing).

    Args:
        provider: Provider identifier (zai, glm, zhipu, zhipuai, etc.)

    Returns:
        API key to use, or None to use default OAuth authentication
    """
    provider_id = normalize_provider(provider)

    if provider_id in ("zai", "glm", "zhipu", "zhipuai"):
        return (
            os.environ.get("ZAI_API_KEY")
            or os.environ.get("ZHIPUAI_API_KEY")
            or os.environ.get("GLM_API_KEY")
        )

    # For claude provider, use default OAuth (None)
    return None


def get_openai_compat_config(provider: str | None) -> ProviderConfig:
    provider_id = normalize_provider(provider)

    if provider_id in ("zai", "glm", "zhipu", "zhipuai"):
        api_key = (
            os.environ.get("ZAI_API_KEY")
            or os.environ.get("ZHIPUAI_API_KEY")
            or os.environ.get("GLM_API_KEY")
        )
        base_url = (
            os.environ.get("ZAI_BASE_URL")
            or os.environ.get("GLM_BASE_URL")
            or DEFAULT_ZAI_BASE_URL
        )
        if not api_key:
            raise ValueError(
                "Missing Z.AI API key. Set ZAI_API_KEY (or ZHIPUAI_API_KEY)."
            )
        return ProviderConfig(provider=provider_id, api_key=api_key, base_url=base_url)

    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY for OpenAI-compatible provider.")
    return ProviderConfig(provider=provider_id, api_key=api_key, base_url=base_url)
