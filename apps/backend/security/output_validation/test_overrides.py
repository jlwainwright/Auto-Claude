"""
Tests for Override Token Management
===================================

Comprehensive test suite for the override token system.
Tests cover:
- Token generation
- Token validation
- Token usage and exhaustion
- Scope matching
- Expiry handling
- File persistence
- Token revocation
- Cleanup of expired tokens
"""

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest import mock

import pytest

from .models import OverrideToken
from .overrides import (
    TokenStorage,
    OverrideTokenManager,
    cleanup_expired_tokens,
    format_command_scope,
    format_file_scope,
    generate_override_token,
    list_override_tokens,
    parse_scope,
    revoke_override_token,
    use_override_token,
    validate_and_use_override_token,
    validate_override_token,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_project_dir(tmp_path: Path):
    """Create a temporary project directory."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def manager(temp_project_dir: Path):
    """Create an OverrideTokenManager for testing."""
    return OverrideTokenManager(temp_project_dir)


@pytest.fixture
def storage(temp_project_dir: Path):
    """Create a TokenStorage for testing."""
    return TokenStorage(temp_project_dir)


# =============================================================================
# SCOPE FORMATTING TESTS
# =============================================================================

def test_format_file_scope():
    """Test formatting file scopes."""
    assert format_file_scope("/tmp/test.txt") == "file:/tmp/test.txt"
    assert format_file_scope("relative/path.txt") == "file:relative/path.txt"


def test_format_command_scope():
    """Test formatting command scopes."""
    assert format_command_scope("rm -rf /tmp") == "command:rm -rf /tmp"
    assert format_command_scope("npm install") == "command:npm install"


def test_parse_scope_all():
    """Test parsing 'all' scope."""
    scope_type, scope_value = parse_scope("all")
    assert scope_type == "all"
    assert scope_value == ""


def test_parse_scope_file():
    """Test parsing file scope."""
    scope_type, scope_value = parse_scope("file:/tmp/test.txt")
    assert scope_type == "file"
    assert scope_value == "/tmp/test.txt"


def test_parse_scope_command():
    """Test parsing command scope."""
    scope_type, scope_value = parse_scope("command:rm -rf")
    assert scope_type == "command"
    assert scope_value == "rm -rf"


def test_parse_scope_invalid():
    """Test parsing invalid scope (no colon)."""
    scope_type, scope_value = parse_scope("invalid_scope")
    assert scope_type == "unknown"
    assert scope_value == "invalid_scope"


# =============================================================================
# TOKEN STORAGE TESTS
# =============================================================================

def test_storage_initialization(storage: TokenStorage, temp_project_dir: Path):
    """Test TokenStorage initialization."""
    assert storage.project_dir == temp_project_dir.resolve()
    assert storage.tokens_file.name == "override-tokens.json"
    assert storage.tokens_file.parent.name == ".auto-claude"


def test_storage_creates_auto_claude_dir(storage: TokenStorage, temp_project_dir: Path):
    """Test that TokenStorage creates .auto-claude directory."""
    auto_claude_dir = temp_project_dir / ".auto-claude"
    assert auto_claude_dir.exists()
    assert auto_claude_dir.is_dir()


def test_storage_load_empty(storage: TokenStorage):
    """Test loading when tokens file doesn't exist."""
    tokens = storage.load_tokens()
    assert tokens == {}


def test_storage_save_and_load(storage: TokenStorage):
    """Test saving and loading tokens."""
    # Create a token
    token = OverrideToken(
        token_id="test-token-1",
        rule_id="bash-rm-rf",
        scope="all",
        expires_at="",
        max_uses=1,
        use_count=0,
        reason="Test token",
        creator="test",
    )

    # Save
    storage.add_token(token)
    storage.save_tokens()

    # Load into new storage instance
    new_storage = TokenStorage(storage.project_dir)
    loaded_tokens = new_storage.load_tokens()

    assert len(loaded_tokens) == 1
    assert "test-token-1" in loaded_tokens
    assert loaded_tokens["test-token-1"].rule_id == "bash-rm-rf"


def test_storage_get_token(storage: TokenStorage):
    """Test getting a token by ID."""
    token = OverrideToken(
        token_id="test-token-1",
        rule_id="bash-rm-rf",
        scope="all",
    )

    storage.add_token(token)

    # Get existing token
    retrieved = storage.get_token("test-token-1")
    assert retrieved is not None
    assert retrieved.token_id == "test-token-1"

    # Get non-existent token
    assert storage.get_token("non-existent") is None


def test_storage_remove_token(storage: TokenStorage):
    """Test removing a token."""
    token = OverrideToken(
        token_id="test-token-1",
        rule_id="bash-rm-rf",
        scope="all",
    )

    storage.add_token(token)

    # Remove existing token
    assert storage.remove_token("test-token-1") is True
    assert storage.get_token("test-token-1") is None

    # Remove non-existent token
    assert storage.remove_token("non-existent") is False


def test_storage_cleanup_expired(storage: TokenStorage):
    """Test cleanup of expired tokens."""
    now = datetime.now(timezone.utc)

    # Valid token
    valid_token = OverrideToken(
        token_id="valid-token",
        rule_id="bash-rm-rf",
        scope="all",
        expires_at=(now + timedelta(hours=1)).isoformat(),
    )

    # Expired token
    expired_token = OverrideToken(
        token_id="expired-token",
        rule_id="bash-rm-rf",
        scope="all",
        expires_at=(now - timedelta(hours=1)).isoformat(),
    )

    # Exhausted token
    exhausted_token = OverrideToken(
        token_id="exhausted-token",
        rule_id="bash-rm-rf",
        scope="all",
        max_uses=1,
        use_count=1,
    )

    storage.add_token(valid_token)
    storage.add_token(expired_token)
    storage.add_token(exhausted_token)

    # Cleanup
    cleanup_count = storage.cleanup_expired()

    assert cleanup_count == 2
    assert storage.get_token("valid-token") is not None
    assert storage.get_token("expired-token") is None
    assert storage.get_token("exhausted-token") is None


def test_storage_list_tokens(storage: TokenStorage):
    """Test listing tokens."""
    token1 = OverrideToken(
        token_id="token-1",
        rule_id="bash-rm-rf",
        scope="all",
    )

    token2 = OverrideToken(
        token_id="token-2",
        rule_id="file-write-system",
        scope="all",
    )

    storage.add_token(token1)
    storage.add_token(token2)

    # List all
    all_tokens = storage.list_tokens()
    assert len(all_tokens) == 2

    # Filter by rule_id
    filtered = storage.list_tokens(rule_id="bash-rm-rf")
    assert len(filtered) == 1
    assert filtered[0].token_id == "token-1"


# =============================================================================
# OVERRIDE TOKEN MANAGER TESTS
# =============================================================================

def test_manager_initialization(manager: OverrideTokenManager, temp_project_dir: Path):
    """Test OverrideTokenManager initialization."""
    assert manager.project_dir == temp_project_dir.resolve()
    assert manager.storage is not None


def test_manager_generate_token_default_params(manager: OverrideTokenManager):
    """Test generating a token with default parameters."""
    token = manager.generate_token(rule_id="bash-rm-rf")

    assert token.token_id is not None
    assert token.rule_id == "bash-rm-rf"
    assert token.scope == "all"
    assert token.max_uses == 1
    assert token.use_count == 0
    assert token.creator == "user"
    assert token.is_valid() is True


def test_manager_generate_token_custom_params(manager: OverrideTokenManager):
    """Test generating a token with custom parameters."""
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="file:/tmp/test.txt",
        expiry_minutes=30,
        max_uses=5,
        reason="Testing file cleanup",
        creator="test-user",
    )

    assert token.rule_id == "bash-rm-rf"
    assert token.scope == "file:/tmp/test.txt"
    assert token.max_uses == 5
    assert token.reason == "Testing file cleanup"
    assert token.creator == "test-user"

    # Check expiry is approximately 30 minutes from now
    expires_at = datetime.fromisoformat(token.expires_at)
    now = datetime.now(timezone.utc)
    time_diff = (expires_at - now).total_seconds() / 60
    assert 29 <= time_diff <= 31  # Allow 1 minute tolerance


def test_manager_generate_token_no_expiry(manager: OverrideTokenManager):
    """Test generating a token with no expiry."""
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        expiry_minutes=0,
    )

    assert token.expires_at == ""


def test_manager_generate_token_invalid_rule_id(manager: OverrideTokenManager):
    """Test that invalid rule_id raises ValueError."""
    with pytest.raises(ValueError, match="rule_id must be a non-empty string"):
        manager.generate_token(rule_id="")

    with pytest.raises(ValueError, match="rule_id must be a non-empty string"):
        manager.generate_token(rule_id=None)


def test_manager_generate_token_invalid_expiry(manager: OverrideTokenManager):
    """Test that invalid expiry_minutes raises ValueError."""
    with pytest.raises(ValueError, match="expiry_minutes must be >= 0"):
        manager.generate_token(
            rule_id="bash-rm-rf",
            expiry_minutes=-1,
        )


def test_manager_generate_token_invalid_max_uses(manager: OverrideTokenManager):
    """Test that invalid max_uses raises ValueError."""
    with pytest.raises(ValueError, match="max_uses must be >= 0"):
        manager.generate_token(
            rule_id="bash-rm-rf",
            max_uses=-1,
        )


def test_manager_validate_token_valid(manager: OverrideTokenManager):
    """Test validating a valid token."""
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="file:/tmp/test.txt",
    )

    # Validate with matching rule_id
    is_valid = manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        context="file:/tmp/test.txt",
    )

    assert is_valid is True


def test_manager_validate_token_wrong_rule_id(manager: OverrideTokenManager):
    """Test validating a token with wrong rule_id."""
    token = manager.generate_token(rule_id="bash-rm-rf")

    # Try to validate for different rule
    is_valid = manager.validate_token(
        token_id=token.token_id,
        rule_id="different-rule",
    )

    assert is_valid is False


def test_manager_validate_token_wrong_scope(manager: OverrideTokenManager):
    """Test validating a token with wrong scope."""
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="file:/tmp/test.txt",
    )

    # Try to validate for different context
    is_valid = manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        context="file:/tmp/other.txt",
    )

    assert is_valid is False


def test_manager_validate_token_all_scope(manager: OverrideTokenManager):
    """Test that 'all' scope matches any context."""
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="all",
    )

    # Should match any context
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        context="file:/tmp/test.txt",
    ) is True

    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        context="command:rm -rf",
    ) is True


def test_manager_use_token(manager: OverrideTokenManager):
    """Test using a token."""
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        max_uses=3,
    )

    # Use token 3 times
    assert manager.use_token(token.token_id) is True
    assert manager.use_token(token.token_id) is True
    assert manager.use_token(token.token_id) is True

    # 4th use should fail
    assert manager.use_token(token.token_id) is False

    # Reload and verify usage count persisted
    manager2 = OverrideTokenManager(manager.project_dir)
    loaded_token = manager2.storage.get_token(token.token_id)
    assert loaded_token is None  # Exhausted tokens are filtered out


def test_manager_validate_and_use_token(manager: OverrideTokenManager):
    """Test validate_and_use_token combination."""
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="file:/tmp/test.txt",
    )

    # Valid call
    result = manager.validate_and_use_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        context="file:/tmp/test.txt",
    )

    assert result is True
    assert token.use_count == 1

    # Wrong rule_id
    result = manager.validate_and_use_token(
        token_id=token.token_id,
        rule_id="wrong-rule",
        context="file:/tmp/test.txt",
    )

    assert result is False
    assert token.use_count == 1  # Not incremented


def test_manager_revoke_token(manager: OverrideTokenManager):
    """Test revoking a token."""
    token = manager.generate_token(rule_id="bash-rm-rf")

    # Revoke
    assert manager.revoke_token(token.token_id) is True

    # Token should no longer be valid
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
    ) is False

    # Revoking again should return False
    assert manager.revoke_token(token.token_id) is False


def test_manager_list_tokens(manager: OverrideTokenManager):
    """Test listing tokens."""
    # Generate multiple tokens
    token1 = manager.generate_token(rule_id="bash-rm-rf")
    token2 = manager.generate_token(rule_id="file-write-system")
    token3 = manager.generate_token(rule_id="bash-rm-rf")

    # List all
    all_tokens = manager.list_tokens()
    assert len(all_tokens) == 3

    # Filter by rule_id
    filtered = manager.list_tokens(rule_id="bash-rm-rf")
    assert len(filtered) == 2


def test_manager_cleanup_expired(manager: OverrideTokenManager):
    """Test cleanup of expired tokens."""
    # Generate token with short expiry
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        expiry_minutes=0,  # No expiry
        max_uses=0,  # Unlimited
    )

    # Manually mark as expired
    token.expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    manager.storage.save_tokens()

    # Cleanup
    count = manager.cleanup_expired()
    assert count >= 1

    # Token should be gone
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
    ) is False


# =============================================================================
# CONVENIENCE FUNCTION TESTS
# =============================================================================

def test_generate_override_token(temp_project_dir: Path):
    """Test generate_override_token convenience function."""
    token = generate_override_token(
        rule_id="bash-rm-rf",
        project_dir=temp_project_dir,
        scope="file:/tmp/test.txt",
        expiry_minutes=30,
        reason="Test",
    )

    assert token.rule_id == "bash-rm-rf"
    assert token.scope == "file:/tmp/test.txt"
    assert token.reason == "Test"

    # Verify it was persisted
    manager = OverrideTokenManager(temp_project_dir)
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
    )


def test_validate_override_token(temp_project_dir: Path):
    """Test validate_override_token convenience function."""
    token = generate_override_token(
        rule_id="bash-rm-rf",
        project_dir=temp_project_dir,
    )

    # Valid
    assert validate_override_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        project_dir=temp_project_dir,
    ) is True

    # Invalid rule_id
    assert validate_override_token(
        token_id=token.token_id,
        rule_id="wrong-rule",
        project_dir=temp_project_dir,
    ) is False


def test_use_override_token(temp_project_dir: Path):
    """Test use_override_token convenience function."""
    token = generate_override_token(
        rule_id="bash-rm-rf",
        project_dir=temp_project_dir,
        max_uses=2,
    )

    # Use token
    assert use_override_token(
        token_id=token.token_id,
        project_dir=temp_project_dir,
    ) is True

    # Verify usage count
    manager = OverrideTokenManager(temp_project_dir)
    loaded_token = manager.storage.get_token(token.token_id)
    assert loaded_token.use_count == 1


def test_validate_and_use_override_token(temp_project_dir: Path):
    """Test validate_and_use_override_token convenience function."""
    token = generate_override_token(
        rule_id="bash-rm-rf",
        project_dir=temp_project_dir,
        scope="file:/tmp/test.txt",
    )

    # Valid call
    assert validate_and_use_override_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        project_dir=temp_project_dir,
        context="file:/tmp/test.txt",
    ) is True

    # Wrong context
    assert validate_and_use_override_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        project_dir=temp_project_dir,
        context="file:/tmp/other.txt",
    ) is False


def test_revoke_override_token(temp_project_dir: Path):
    """Test revoke_override_token convenience function."""
    token = generate_override_token(
        rule_id="bash-rm-rf",
        project_dir=temp_project_dir,
    )

    # Revoke
    assert revoke_override_token(
        token_id=token.token_id,
        project_dir=temp_project_dir,
    ) is True

    # Verify it's revoked
    assert validate_override_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        project_dir=temp_project_dir,
    ) is False


def test_list_override_tokens(temp_project_dir: Path):
    """Test list_override_tokens convenience function."""
    # Generate multiple tokens
    token1 = generate_override_token(
        rule_id="bash-rm-rf",
        project_dir=temp_project_dir,
    )
    token2 = generate_override_token(
        rule_id="file-write-system",
        project_dir=temp_project_dir,
    )

    # List all
    all_tokens = list_override_tokens(temp_project_dir)
    assert len(all_tokens) == 2

    # Filter by rule_id
    filtered = list_override_tokens(
        temp_project_dir,
        rule_id="bash-rm-rf",
    )
    assert len(filtered) == 1
    assert filtered[0].token_id == token1.token_id


def test_cleanup_expired_tokens(temp_project_dir: Path):
    """Test cleanup_expired_tokens convenience function."""
    # Generate token with short expiry
    token = generate_override_token(
        rule_id="bash-rm-rf",
        project_dir=temp_project_dir,
        expiry_minutes=0,
        max_uses=0,
    )

    # Manually mark as expired
    manager = OverrideTokenManager(temp_project_dir)
    loaded_token = manager.storage.get_token(token.token_id)
    loaded_token.expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    manager.storage.save_tokens()

    # Cleanup
    count = cleanup_expired_tokens(temp_project_dir)
    assert count >= 1


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

def test_token_persistence_across_managers(temp_project_dir: Path):
    """Test that tokens persist across manager instances."""
    # Create token with first manager
    manager1 = OverrideTokenManager(temp_project_dir)
    token = manager1.generate_token(rule_id="bash-rm-rf")

    # Load with second manager
    manager2 = OverrideTokenManager(temp_project_dir)
    assert manager2.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
    ) is True


def test_token_expiration_by_time(temp_project_dir: Path):
    """Test that tokens expire based on time."""
    # Create token with 1 second expiry
    manager = OverrideTokenManager(temp_project_dir)
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        expiry_minutes=0.016,  # ~1 second
    )

    # Should be valid immediately
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
    ) is True

    # Wait for expiry
    time.sleep(2)

    # Should be expired now
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
    ) is False


def test_file_scope_matching(temp_project_dir: Path):
    """Test file scope matching logic."""
    manager = OverrideTokenManager(temp_project_dir)

    # Token for specific file
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="file:/tmp/test.txt",
    )

    # Exact match
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        context="file:/tmp/test.txt",
    ) is True

    # Different file
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        context="file:/tmp/other.txt",
    ) is False

    # Command context
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        context="command:rm -rf",
    ) is False


def test_command_scope_matching(temp_project_dir: Path):
    """Test command scope matching logic."""
    manager = OverrideTokenManager(temp_project_dir)

    # Token for specific command
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="command:rm -rf /tmp/test",
    )

    # Exact match
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        context="command:rm -rf /tmp/test",
    ) is True

    # Different command
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        context="command:rm -rf /other",
    ) is False


def test_multiple_tokens_same_rule(temp_project_dir: Path):
    """Test having multiple tokens for the same rule."""
    manager = OverrideTokenManager(temp_project_dir)

    token1 = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="file:/tmp/test1.txt",
    )

    token2 = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="file:/tmp/test2.txt",
    )

    # Both should be valid for their respective scopes
    assert manager.validate_token(
        token_id=token1.token_id,
        rule_id="bash-rm-rf",
        context="file:/tmp/test1.txt",
    ) is True

    assert manager.validate_token(
        token_id=token2.token_id,
        rule_id="bash-rm-rf",
        context="file:/tmp/test2.txt",
    ) is True

    # But not cross-scope
    assert manager.validate_token(
        token_id=token1.token_id,
        rule_id="bash-rm-rf",
        context="file:/tmp/test2.txt",
    ) is False


# =============================================================================
# JSON FORMAT TESTS
# =============================================================================

def test_token_json_format(temp_project_dir: Path):
    """Test that tokens are saved in correct JSON format."""
    manager = OverrideTokenManager(temp_project_dir)
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="file:/tmp/test.txt",
        expiry_minutes=30,
        max_uses=5,
        reason="Test token",
        creator="test-user",
    )

    # Load JSON file
    tokens_file = temp_project_dir / ".auto-claude" / "override-tokens.json"
    with open(tokens_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Verify structure
    assert "tokens" in data
    assert len(data["tokens"]) == 1

    token_data = data["tokens"][0]
    assert token_data["token_id"] == token.token_id
    assert token_data["rule_id"] == "bash-rm-rf"
    assert token_data["scope"] == "file:/tmp/test.txt"
    assert token_data["max_uses"] == 5
    assert token_data["reason"] == "Test token"
    assert token_data["creator"] == "test-user"


def test_invalid_json_is_handled(temp_project_dir: Path):
    """Test that invalid JSON is handled gracefully."""
    # Create invalid JSON file
    tokens_file = temp_project_dir / ".auto-claude" / "override-tokens.json"
    tokens_file.parent.mkdir(parents=True, exist_ok=True)

    with open(tokens_file, "w", encoding="utf-8") as f:
        f.write("invalid json {")

    # Should not crash, just return empty tokens
    manager = OverrideTokenManager(temp_project_dir)
    tokens = manager.list_tokens()
    assert tokens == []


# =============================================================================
# EDGE CASES
# =============================================================================

def test_zero_max_uses_unlimited(temp_project_dir: Path):
    """Test that max_uses=0 means unlimited uses."""
    manager = OverrideTokenManager(temp_project_dir)
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        max_uses=0,  # Unlimited
    )

    # Should be able to use many times
    for _ in range(100):
        assert manager.use_token(token.token_id) is True

    # Token should still be valid
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
    ) is True


def test_zero_expiry_no_expiration(temp_project_dir: Path):
    """Test that expiry_minutes=0 means no expiration."""
    manager = OverrideTokenManager(temp_project_dir)
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        expiry_minutes=0,  # No expiry
    )

    # Token should not expire
    assert token.expires_at == ""

    # Should be valid even after time passes
    time.sleep(0.1)
    assert manager.validate_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
    ) is True


def test_concurrent_token_usage(temp_project_dir: Path):
    """Test that tokens handle concurrent usage correctly."""
    manager = OverrideTokenManager(temp_project_dir)
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        max_uses=2,
    )

    # Simulate concurrent usage
    used1 = manager.use_token(token.token_id)
    used2 = manager.use_token(token.token_id)
    used3 = manager.use_token(token.token_id)

    assert used1 is True
    assert used2 is True
    assert used3 is False

    # Reload and verify
    manager2 = OverrideTokenManager(temp_project_dir)
    loaded_token = manager2.storage.get_token(token.token_id)
    assert loaded_token is None  # Exhausted


def test_empty_context_validation(temp_project_dir: Path):
    """Test validation with empty context string."""
    manager = OverrideTokenManager(temp_project_dir)

    # Token with 'all' scope
    token_all = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="all",
    )

    # Should validate even with empty context
    assert manager.validate_token(
        token_id=token_all.token_id,
        rule_id="bash-rm-rf",
        context="",
    ) is True

    # Token with specific scope
    token_file = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="file:/tmp/test.txt",
    )

    # Should not validate with empty context
    assert manager.validate_token(
        token_id=token_file.token_id,
        rule_id="bash-rm-rf",
        context="",
    ) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
