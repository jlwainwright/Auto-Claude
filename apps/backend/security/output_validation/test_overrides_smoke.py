"""
Manual Test Script for Override Token Management
================================================

This script can be run without pytest to verify the override token system.
It tests all the main functionality.

Usage:
    cd apps/backend
    python security/output_validation/test_overrides_smoke.py
"""

import json
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from security.output_validation.models import OverrideToken
from security.output_validation.overrides import (
    TokenStorage,
    OverrideTokenManager,
    cleanup_expired_tokens,
    format_command_scope,
    format_file_scope,
    parse_scope,
    generate_override_token,
    list_override_tokens,
    revoke_override_token,
    use_override_token,
    validate_and_use_override_token,
    validate_override_token,
)


def print_test_header(test_name: str):
    """Print a test header."""
    print(f"\n{'='*70}")
    print(f"TEST: {test_name}")
    print('='*70)


def print_success(message: str):
    """Print success message."""
    print(f"✓ {message}")


def print_error(message: str):
    """Print error message."""
    print(f"✗ {message}")


def test_scope_formatting():
    """Test scope formatting functions."""
    print_test_header("Scope Formatting")

    # Test file scope
    result = format_file_scope("/tmp/test.txt")
    expected = "file:/tmp/test.txt"
    assert result == expected, f"Expected {expected}, got {result}"
    print_success(f"format_file_scope('/tmp/test.txt') = '{result}'")

    # Test command scope
    result = format_command_scope("rm -rf /tmp")
    expected = "command:rm -rf /tmp"
    assert result == expected, f"Expected {expected}, got {result}"
    print_success(f"format_command_scope('rm -rf /tmp') = '{result}'")

    # Test parse_scope
    scope_type, scope_value = parse_scope("file:/tmp/test.txt")
    assert scope_type == "file" and scope_value == "/tmp/test.txt"
    print_success(f"parse_scope('file:/tmp/test.txt') = ('{scope_type}', '{scope_value}')")

    scope_type, scope_value = parse_scope("all")
    assert scope_type == "all" and scope_value == ""
    print_success(f"parse_scope('all') = ('{scope_type}', '{scope_value}')")


def test_storage():
    """Test TokenStorage class."""
    print_test_header("Token Storage")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        storage = TokenStorage(project_dir)

        # Check that .auto-claude directory was created
        auto_claude_dir = project_dir / ".auto-claude"
        assert auto_claude_dir.exists(), ".auto-claude directory not created"
        print_success(f"Created .auto-claude directory at {auto_claude_dir}")

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
        storage.add_token(token)
        print_success(f"Added token: {token.token_id}")

        # Save tokens
        storage.save_tokens()
        print_success("Saved tokens to file")

        # Load tokens in new storage instance
        new_storage = TokenStorage(project_dir)
        loaded_tokens = new_storage.load_tokens()
        assert len(loaded_tokens) == 1, f"Expected 1 token, got {len(loaded_tokens)}"
        print_success(f"Loaded {len(loaded_tokens)} token(s)")

        # Get token
        retrieved = new_storage.get_token("test-token-1")
        assert retrieved is not None, "Failed to retrieve token"
        assert retrieved.rule_id == "bash-rm-rf"
        print_success(f"Retrieved token with rule_id: {retrieved.rule_id}")

        # Remove token
        removed = new_storage.remove_token("test-token-1")
        assert removed is True, "Failed to remove token"
        print_success("Removed token")

        # Verify removal
        retrieved = new_storage.get_token("test-token-1")
        assert retrieved is None, "Token still exists after removal"
        print_success("Verified token was removed")


def test_manager():
    """Test OverrideTokenManager class."""
    print_test_header("Override Token Manager")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        manager = OverrideTokenManager(project_dir)

        # Generate token with defaults
        token = manager.generate_token(rule_id="bash-rm-rf")
        print_success(f"Generated token: {token.token_id}")

        # Check default values
        assert token.scope == "all", f"Expected scope 'all', got {token.scope}"
        assert token.max_uses == 1, f"Expected max_uses 1, got {token.max_uses}"
        assert token.use_count == 0, f"Expected use_count 0, got {token.use_count}"
        assert token.creator == "user", f"Expected creator 'user', got {token.creator}"
        print_success("Default values correct")

        # Validate token
        is_valid = manager.validate_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf",
        )
        assert is_valid is True, "Token validation failed"
        print_success("Token is valid")

        # Use token
        used = manager.use_token(token.token_id)
        assert used is True, "Failed to use token"
        print_success("Token used successfully")

        # Verify usage count
        assert token.use_count == 1, f"Expected use_count 1, got {token.use_count}"
        print_success(f"Usage count incremented to {token.use_count}")

        # Try to use again (should fail - exhausted)
        used = manager.use_token(token.token_id)
        assert used is False, "Token should be exhausted"
        print_success("Token correctly exhausted after max_uses")


def test_manager_with_custom_params():
    """Test OverrideTokenManager with custom parameters."""
    print_test_header("Override Token Manager (Custom Params)")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        manager = OverrideTokenManager(project_dir)

        # Generate token with custom params
        token = manager.generate_token(
            rule_id="bash-rm-rf",
            scope="file:/tmp/test.txt",
            expiry_minutes=30,
            max_uses=5,
            reason="Testing file cleanup",
            creator="test-user",
        )
        print_success(f"Generated token with custom params: {token.token_id}")

        # Check values
        assert token.scope == "file:/tmp/test.txt", f"Expected scope 'file:/tmp/test.txt', got {token.scope}"
        assert token.max_uses == 5, f"Expected max_uses 5, got {token.max_uses}"
        assert token.reason == "Testing file cleanup", f"Expected reason 'Testing file cleanup', got {token.reason}"
        assert token.creator == "test-user", f"Expected creator 'test-user', got {token.creator}"
        print_success("Custom parameters correct")

        # Validate with matching context
        is_valid = manager.validate_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf",
            context="file:/tmp/test.txt",
        )
        assert is_valid is True, "Token should be valid for matching context"
        print_success("Token valid for matching context")

        # Validate with different context
        is_valid = manager.validate_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf",
            context="file:/tmp/other.txt",
        )
        assert is_valid is False, "Token should not be valid for different context"
        print_success("Token invalid for different context")


def test_validate_and_use():
    """Test validate_and_use_token method."""
    print_test_header("Validate and Use Token")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        manager = OverrideTokenManager(project_dir)

        token = manager.generate_token(
            rule_id="bash-rm-rf",
            scope="file:/tmp/test.txt",
        )
        print_success(f"Generated token: {token.token_id}")

        # Validate and use with correct context
        result = manager.validate_and_use_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf",
            context="file:/tmp/test.txt",
        )
        assert result is True, "validate_and_use_token should succeed"
        assert token.use_count == 1, "Usage count should be 1"
        print_success("validate_and_use_token succeeded")

        # Try with wrong rule_id
        result = manager.validate_and_use_token(
            token_id=token.token_id,
            rule_id="wrong-rule",
            context="file:/tmp/test.txt",
        )
        assert result is False, "Should fail with wrong rule_id"
        assert token.use_count == 1, "Usage count should not increment"
        print_success("validate_and_use_token failed for wrong rule_id")


def test_token_revocation():
    """Test token revocation."""
    print_test_header("Token Revocation")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        manager = OverrideTokenManager(project_dir)

        token = manager.generate_token(rule_id="bash-rm-rf")
        print_success(f"Generated token: {token.token_id}")

        # Revoke token
        revoked = manager.revoke_token(token.token_id)
        assert revoked is True, "Failed to revoke token"
        print_success("Token revoked")

        # Verify token is no longer valid
        is_valid = manager.validate_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf",
        )
        assert is_valid is False, "Revoked token should not be valid"
        print_success("Revoked token is invalid")


def test_token_persistence():
    """Test token persistence across manager instances."""
    print_test_header("Token Persistence")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create token with first manager
        manager1 = OverrideTokenManager(project_dir)
        token = manager1.generate_token(rule_id="bash-rm-rf")
        print_success(f"Generated token with manager1: {token.token_id}")

        # Load with second manager
        manager2 = OverrideTokenManager(project_dir)
        is_valid = manager2.validate_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf",
        )
        assert is_valid is True, "Token should persist across manager instances"
        print_success("Token persisted to new manager instance")


def test_list_tokens():
    """Test listing tokens."""
    print_test_header("List Tokens")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        manager = OverrideTokenManager(project_dir)

        # Generate multiple tokens
        token1 = manager.generate_token(rule_id="bash-rm-rf")
        token2 = manager.generate_token(rule_id="file-write-system")
        token3 = manager.generate_token(rule_id="bash-rm-rf")
        print_success("Generated 3 tokens")

        # List all
        all_tokens = manager.list_tokens()
        assert len(all_tokens) == 3, f"Expected 3 tokens, got {len(all_tokens)}"
        print_success(f"Listed {len(all_tokens)} tokens")

        # Filter by rule_id
        filtered = manager.list_tokens(rule_id="bash-rm-rf")
        assert len(filtered) == 2, f"Expected 2 tokens for bash-rm-rf, got {len(filtered)}"
        print_success(f"Filtered to {len(filtered)} tokens with rule_id 'bash-rm-rf'")


def test_cleanup_expired():
    """Test cleanup of expired tokens."""
    print_test_header("Cleanup Expired Tokens")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        manager = OverrideTokenManager(project_dir)

        # Generate token with no expiry
        token = manager.generate_token(
            rule_id="bash-rm-rf",
            expiry_minutes=0,
            max_uses=0,
        )
        print_success(f"Generated token: {token.token_id}")

        # Manually mark as expired
        manager.storage.load_tokens()
        loaded_token = manager.storage.tokens[token.token_id]
        loaded_token.expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        manager.storage.save_tokens()
        print_success("Marked token as expired")

        # Cleanup
        count = manager.cleanup_expired()
        assert count >= 1, f"Expected at least 1 cleaned up token, got {count}"
        print_success(f"Cleaned up {count} expired token(s)")

        # Verify token is gone
        is_valid = manager.validate_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf",
        )
        assert is_valid is False, "Expired token should not be valid"
        print_success("Expired token is no longer valid")


def test_convenience_functions():
    """Test convenience functions."""
    print_test_header("Convenience Functions")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # generate_override_token
        token = generate_override_token(
            rule_id="bash-rm-rf",
            project_dir=project_dir,
            scope="file:/tmp/test.txt",
            expiry_minutes=30,
            max_uses=2,  # Set to 2 so we can use it once and still have it valid
            reason="Test",
        )
        print_success(f"generate_override_token() created: {token.token_id}")

        # validate_override_token
        is_valid = validate_override_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf",
            project_dir=project_dir,
        )
        assert is_valid is True, "Token should be valid"
        print_success("validate_override_token() returned True")

        # use_override_token
        used = use_override_token(
            token_id=token.token_id,
            project_dir=project_dir,
        )
        assert used is True, "Token should be used"
        print_success("use_override_token() returned True")

        # revoke_override_token (revoke before exhausting the token)
        revoked = revoke_override_token(
            token_id=token.token_id,
            project_dir=project_dir,
        )
        assert revoked is True, "Token should be revoked"
        print_success("revoke_override_token() returned True")

        # list_override_tokens
        tokens = list_override_tokens(project_dir)
        assert len(tokens) == 0, "Token list should be empty after revocation"
        print_success("list_override_tokens() returned empty list")


def test_json_format():
    """Test JSON file format."""
    print_test_header("JSON File Format")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        manager = OverrideTokenManager(project_dir)

        token = manager.generate_token(
            rule_id="bash-rm-rf",
            scope="file:/tmp/test.txt",
            expiry_minutes=30,
            max_uses=5,
            reason="Test token",
            creator="test-user",
        )
        print_success(f"Generated token: {token.token_id}")

        # Load JSON file
        tokens_file = project_dir / ".auto-claude" / "override-tokens.json"
        with open(tokens_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print_success("Loaded JSON file")

        # Verify structure
        assert "tokens" in data, "JSON should have 'tokens' key"
        assert len(data["tokens"]) == 1, "Should have 1 token"
        print_success("JSON structure correct")

        # Verify token data
        token_data = data["tokens"][0]
        assert token_data["token_id"] == token.token_id
        assert token_data["rule_id"] == "bash-rm-rf"
        assert token_data["scope"] == "file:/tmp/test.txt"
        assert token_data["max_uses"] == 5
        assert token_data["reason"] == "Test token"
        assert token_data["creator"] == "test-user"
        print_success("Token data in JSON is correct")


def test_edge_cases():
    """Test edge cases."""
    print_test_header("Edge Cases")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        manager = OverrideTokenManager(project_dir)

        # Test unlimited uses (max_uses=0)
        token = manager.generate_token(
            rule_id="bash-rm-rf",
            max_uses=0,  # Unlimited
        )
        print_success("Generated token with unlimited uses")

        # Should be able to use many times
        for i in range(10):
            used = manager.use_token(token.token_id)
            assert used is True, f"Use {i+1} should succeed"
        print_success("Used token 10 times (unlimited)")

        # Token should still be valid
        is_valid = manager.validate_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf",
        )
        assert is_valid is True, "Token should still be valid"
        print_success("Token still valid after many uses")

        # Test no expiry (expiry_minutes=0)
        token2 = manager.generate_token(
            rule_id="bash-rm-rf",
            expiry_minutes=0,  # No expiry
        )
        assert token2.expires_at == "", "Token should have no expiry"
        print_success("Generated token with no expiry")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("OVERRIDE TOKEN MANAGEMENT TEST SUITE")
    print("="*70)

    tests = [
        test_scope_formatting,
        test_storage,
        test_manager,
        test_manager_with_custom_params,
        test_validate_and_use,
        test_token_revocation,
        test_token_persistence,
        test_list_tokens,
        test_cleanup_expired,
        test_convenience_functions,
        test_json_format,
        test_edge_cases,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print_error(f"Assertion failed: {e}")
            failed += 1
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            failed += 1

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Total tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed == 0:
        print("\n✓ ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n✗ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
