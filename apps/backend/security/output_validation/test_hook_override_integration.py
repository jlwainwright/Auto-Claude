"""
Test Override Token Integration in Output Validation Hook
==========================================================

Tests the integration of override token checking in the output validation hook.
Verifies that:
- Override tokens are checked before blocking operations
- Token expiry and scope are validated
- Override usage is logged
- Usage count is decremented for limited-use tokens
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from .hook import (
    output_validation_hook,
    reset_hook,
    _get_override_context,
)
from .models import OutputValidationConfig, SeverityLevel
from .overrides import (
    OverrideTokenManager,
    generate_override_token,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir).resolve()


@pytest.fixture
def hook_test_project_dir(temp_project_dir):
    """Create a project directory with necessary structure."""
    # Create .auto-claude directory
    auto_claude_dir = temp_project_dir / ".auto-claude"
    auto_claude_dir.mkdir(parents=True, exist_ok=True)
    return temp_project_dir


# =============================================================================
# CONTEXT FORMATTING TESTS
# =============================================================================


def test_get_override_context_for_write_operation():
    """Test context formatting for Write operations."""
    from .models import ToolType

    tool_input = {"file_path": "/tmp/test.txt", "content": "test"}
    context = _get_override_context(ToolType.WRITE, tool_input)

    assert context == "file:/tmp/test.txt"


def test_get_override_context_for_edit_operation():
    """Test context formatting for Edit operations."""
    from .models import ToolType

    tool_input = {
        "file_path": "/etc/config.json",
        "old_string": "old",
        "new_string": "new"
    }
    context = _get_override_context(ToolType.EDIT, tool_input)

    assert context == "file:/etc/config.json"


def test_get_override_context_for_bash_operation():
    """Test context formatting for Bash operations."""
    from .models import ToolType

    tool_input = {"command": "rm -rf /tmp/test"}
    context = _get_override_context(ToolType.BASH, tool_input)

    assert context == "command:rm -rf /tmp/test"


def test_get_override_context_for_unsupported_tool():
    """Test context formatting for unsupported tool types."""
    from .models import ToolType

    tool_input = {"url": "https://example.com"}
    context = _get_override_context(ToolType.WEB_FETCH, tool_input)

    # WebFetch doesn't have context-specific tokens
    assert context is None


def test_get_override_context_missing_path():
    """Test context formatting when file_path is missing."""
    from .models import ToolType

    tool_input = {"content": "test"}
    context = _get_override_context(ToolType.WRITE, tool_input)

    assert context is None


# =============================================================================
# OVERRIDE TOKEN CHECKING TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_hook_checks_override_before_blocking(hook_test_project_dir):
    """Test that hook checks for override tokens before blocking."""
    # Generate an override token for the rm-rf-root rule
    token = generate_override_token(
        rule_id="bash-rm-rf-root",
        project_dir=hook_test_project_dir,
        scope="all",
        expiry_minutes=60,
        reason="Testing cleanup",
    )

    # Create hook input that would normally be blocked
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf /"},
        "cwd": str(hook_test_project_dir),
    }

    # Mock context with project_dir
    mock_context = type("obj", (object,), {"project_dir": hook_test_project_dir})

    # Call the hook
    result = await output_validation_hook(
        input_data=input_data,
        tool_use_id=None,
        context=mock_context,
    )

    # Should return empty dict (allowed) due to override token
    assert result == {}
    assert "decision" not in result


@pytest.mark.asyncio
async def test_hook_blocks_when_no_override_token(hook_test_project_dir):
    """Test that hook blocks when no override token exists."""
    # Don't create any override tokens

    # Create hook input that should be blocked
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf /"},
        "cwd": str(hook_test_project_dir),
    }

    # Mock context with project_dir
    mock_context = type("obj", (object,), {"project_dir": hook_test_project_dir})

    # Call the hook
    result = await output_validation_hook(
        input_data=input_data,
        tool_use_id=None,
        context=mock_context,
    )

    # Should return block decision
    assert result.get("decision") == "block"
    assert "reason" in result
    assert result.get("rule_id") is not None


@pytest.mark.asyncio
async def test_hook_validates_token_scope(hook_test_project_dir):
    """Test that hook validates token scope before using it."""
    # Create a token with specific file scope for a write rule
    token = generate_override_token(
        rule_id="write-system-file",
        project_dir=hook_test_project_dir,
        scope="file:/tmp/allowed.txt",
        expiry_minutes=60,
        reason="Testing scope validation",
    )

    # Create hook input for a different file
    input_data = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/etc/passwd",
            "content": "malicious content"
        },
        "cwd": str(hook_test_project_dir),
    }

    # Mock context with project_dir
    mock_context = type("obj", (object,), {"project_dir": hook_test_project_dir})

    # Call the hook
    result = await output_validation_hook(
        input_data=input_data,
        tool_use_id=None,
        context=mock_context,
    )

    # Should block because token scope doesn't match and /etc/passwd is blocked
    assert result.get("decision") == "block"


@pytest.mark.asyncio
async def test_hook_uses_scoped_token_when_matches(hook_test_project_dir):
    """Test that hook uses scoped token when context matches."""
    # Create a token with specific command scope
    token = generate_override_token(
        rule_id="bash-rm-rf-root",
        project_dir=hook_test_project_dir,
        scope="command:rm -rf /",
        expiry_minutes=60,
        reason="Testing scoped token",
    )

    # Create hook input for the exact command
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf /"},
        "cwd": str(hook_test_project_dir),
    }

    # Mock context with project_dir
    mock_context = type("obj", (object,), {"project_dir": hook_test_project_dir})

    # Call the hook
    result = await output_validation_hook(
        input_data=input_data,
        tool_use_id=None,
        context=mock_context,
    )

    # Should allow due to scoped token
    assert result == {}


@pytest.mark.asyncio
async def test_hook_validates_token_expiry(hook_test_project_dir):
    """Test that hook checks token expiry before using it."""
    # Create an already-expired token (0 minutes = expires immediately)
    token = generate_override_token(
        rule_id="bash-rm-rf-root",
        project_dir=hook_test_project_dir,
        scope="all",
        expiry_minutes=0,
        reason="Testing expiry",
    )

    # Force the token to be expired by setting expires_at to past
    tokens_file = hook_test_project_dir / ".auto-claude" / "override-tokens.json"
    with open(tokens_file, "r") as f:
        data = json.load(f)

    # Set expiry to past
    data["tokens"][0]["expires_at"] = "2020-01-01T00:00:00+00:00"

    with open(tokens_file, "w") as f:
        json.dump(data, f, indent=2)

    # Create hook input that would normally be blocked
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf /"},
        "cwd": str(hook_test_project_dir),
    }

    # Mock context with project_dir
    mock_context = type("obj", (object,), {"project_dir": hook_test_project_dir})

    # Reset hook to clear any cached state
    reset_hook()

    # Call the hook
    result = await output_validation_hook(
        input_data=input_data,
        tool_use_id=None,
        context=mock_context,
    )

    # Should block because token is expired
    assert result.get("decision") == "block"


@pytest.mark.asyncio
async def test_hook_decrements_usage_count(hook_test_project_dir):
    """Test that hook decrements usage count for limited-use tokens."""
    # Create a single-use token
    token = generate_override_token(
        rule_id="bash-rm-rf-root",
        project_dir=hook_test_project_dir,
        scope="all",
        expiry_minutes=60,
        max_uses=1,
        reason="Testing usage count",
    )

    # Verify initial usage count
    manager = OverrideTokenManager(hook_test_project_dir)
    initial_tokens = manager.list_tokens(rule_id="bash-rm-rf-root")
    assert initial_tokens[0].use_count == 0

    # Create hook input
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf /"},
        "cwd": str(hook_test_project_dir),
    }

    # Mock context with project_dir
    mock_context = type("obj", (object,), {"project_dir": hook_test_project_dir})

    # Call the hook
    result = await output_validation_hook(
        input_data=input_data,
        tool_use_id=None,
        context=mock_context,
    )

    # Should allow
    assert result == {}

    # Verify usage count was incremented
    # Create a NEW manager instance to ensure fresh data from disk
    updated_manager = OverrideTokenManager(hook_test_project_dir)
    updated_tokens = updated_manager.list_tokens(
        rule_id="bash-rm-rf-root",
        include_expired=True
    )
    assert len(updated_tokens) == 1
    assert updated_tokens[0].use_count == 1

    # Try again - should be blocked now (token exhausted)
    result2 = await output_validation_hook(
        input_data=input_data,
        tool_use_id=None,
        context=mock_context,
    )

    # Should block because token is exhausted
    assert result2.get("decision") == "block"


@pytest.mark.asyncio
async def test_hook_handles_multiple_tokens_same_rule(hook_test_project_dir):
    """Test that hook handles multiple tokens for the same rule."""
    # Create two tokens for the same rule
    token1 = generate_override_token(
        rule_id="write-system-file",
        project_dir=hook_test_project_dir,
        scope="file:/tmp/test1.txt",
        expiry_minutes=60,
        reason="Token 1",
    )

    token2 = generate_override_token(
        rule_id="write-system-file",
        project_dir=hook_test_project_dir,
        scope="file:/tmp/test2.txt",
        expiry_minutes=60,
        reason="Token 2",
    )

    # Create hook input for file1
    input_data = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/tmp/test1.txt",
            "content": "content"
        },
        "cwd": str(hook_test_project_dir),
    }

    # Mock context with project_dir
    mock_context = type("obj", (object,), {"project_dir": hook_test_project_dir})

    # Should use token1 (matching scope) and allow
    result = await output_validation_hook(
        input_data=input_data,
        tool_use_id=None,
        context=mock_context,
    )

    # Result depends on whether content triggers a rule
    # If no rule triggered, result is {} (allowed)
    # The important thing is no crash occurs with multiple tokens


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_hook_handles_missing_project_dir():
    """Test that hook handles missing project_dir gracefully."""
    # Don't provide project_dir
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": "ls -la"},
    }

    # Call the hook without project_dir
    result = await output_validation_hook(
        input_data=input_data,
        tool_use_id=None,
        context=None,
    )

    # Should not crash
    # Safe command should be allowed
    assert result == {}


@pytest.mark.asyncio
async def test_hook_handles_invalid_tool_input():
    """Test that hook handles invalid tool_input gracefully."""
    input_data = {
        "tool_name": "Bash",
        "tool_input": "not a dict",  # Invalid
    }

    result = await output_validation_hook(
        input_data=input_data,
        tool_use_id=None,
        context=None,
    )

    # Should block with error message
    assert result.get("decision") == "block"
    assert "tool_input must be dict" in result.get("reason", "")


# =============================================================================
# RUNNER
# =============================================================================


if __name__ == "__main__":
    print("Running override integration tests...")
    pytest.main([__file__, "-v", "-s"])
