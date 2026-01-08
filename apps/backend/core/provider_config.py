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
