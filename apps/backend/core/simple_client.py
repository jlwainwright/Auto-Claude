"""
Simple Claude SDK Client Factory
================================

Factory for creating minimal Claude SDK clients for single-turn utility operations
like commit message generation, merge conflict resolution, and batch analysis.

These clients don't need full security configurations, MCP servers, or hooks.
Use `create_client()` from `core.client` for full agent sessions with security.

Example usage:
    from core.simple_client import create_simple_client

    # For commit message generation (text-only, no tools)
    client = create_simple_client(agent_type="commit_message")

    # For merge conflict resolution (text-only, no tools)
    client = create_simple_client(agent_type="merge_resolver")

    # For insights extraction (read tools only)
    client = create_simple_client(agent_type="insights", cwd=project_dir)
"""

from pathlib import Path
from typing import Any

from agents.tools_pkg import get_agent_config, get_default_thinking_level
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from core.auth import get_sdk_env_vars, require_auth_token
from core.provider_config import (
    get_openai_compat_config,
    is_claude_provider,
    normalize_provider,
)
from phase_config import get_thinking_budget
from providers.openai_compat import OpenAICompatClient


def create_simple_client(
    agent_type: str = "merge_resolver",
    model: str = "claude-haiku-4-5-20251001",
    provider: str | None = None,
    system_prompt: str | None = None,
    cwd: Path | None = None,
    max_turns: int = 1,
    max_thinking_tokens: int | None = None,
) -> Any:
    """
    Create a minimal Claude SDK client for single-turn utility operations.

    This factory creates lightweight clients without MCP servers, security hooks,
    or full permission configurations. Use for text-only analysis tasks.

    Args:
        agent_type: Agent type from AGENT_CONFIGS. Determines available tools.
                   Common utility types:
                   - "merge_resolver" - Text-only merge conflict analysis
                   - "commit_message" - Text-only commit message generation
                   - "insights" - Read-only code insight extraction
                   - "batch_analysis" - Read-only batch issue analysis
                   - "batch_validation" - Read-only validation
        model: Model to use (defaults to Haiku for fast/cheap operations)
        provider: Provider identifier (claude, zai, or other OpenAI-compatible)
        system_prompt: Optional custom system prompt (for specialized tasks)
        cwd: Working directory for file operations (optional)
        max_turns: Maximum conversation turns (default: 1 for single-turn)
        max_thinking_tokens: Override thinking budget (None = use agent default from
                            AGENT_CONFIGS, converted using phase_config.THINKING_BUDGET_MAP)

    Returns:
        Configured ClaudeSDKClient for single-turn operations

    Raises:
        ValueError: If agent_type is not found in AGENT_CONFIGS
    """
    provider_id = normalize_provider(provider)

    # Get agent configuration (raises ValueError if unknown type)
    config = get_agent_config(agent_type)

    # Get tools from config (no MCP tools for simple clients)
    allowed_tools = list(config.get("tools", []))

    # Determine thinking budget using the single source of truth (phase_config.py)
    if max_thinking_tokens is None:
        thinking_level = get_default_thinking_level(agent_type)
        max_thinking_tokens = get_thinking_budget(thinking_level)

    # Debug: Show which provider is being used
    import os
    print(f"[DEBUG] create_simple_client: provider_id={provider_id}, is_claude={is_claude_provider(provider_id)}")
    print(f"[DEBUG] create_simple_client: model={model}, agent_type={agent_type}")

    if is_claude_provider(provider_id):
        print(f"[DEBUG] Using Claude SDK (native provider)")
        # Get authentication
        oauth_token = require_auth_token()

        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token

        # Get environment variables for SDK
        sdk_env = get_sdk_env_vars()

        return ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model=model,
                system_prompt=system_prompt,
                allowed_tools=allowed_tools,
                max_turns=max_turns,
                cwd=str(cwd.resolve()) if cwd else None,
                env=sdk_env,
                max_thinking_tokens=max_thinking_tokens,
            )
        )

    print(f"[DEBUG] Using OpenAI-compatible provider")
    provider_cfg = get_openai_compat_config(provider_id)
    print(f"[DEBUG] Provider config: provider={provider_cfg.provider}, base_url={provider_cfg.base_url}, api_key_set={bool(provider_cfg.api_key)}")
    resolved_cwd = cwd.resolve() if cwd else Path.cwd().resolve()
    return OpenAICompatClient(
        model=model,
        system_prompt=system_prompt or "",
        allowed_tools=allowed_tools,
        project_dir=resolved_cwd,
        spec_dir=resolved_cwd,
        api_key=provider_cfg.api_key,
        base_url=provider_cfg.base_url,
        max_turns=max_turns,
    )
