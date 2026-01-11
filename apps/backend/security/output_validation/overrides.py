"""
Override Token Management
=========================

System for generating and managing override tokens that allow users to bypass
specific validation rules for a limited time or scope.

Override tokens provide a safety mechanism for legitimate operations that
trigger validation rules but are known to be safe. Tokens can be:
- Time-limited (expire after a specified duration)
- Scope-limited (apply only to specific files or commands)
- Usage-limited (can only be used a specified number of times)

This module provides:
- OverrideTokenManager: Main class for token management
- generate_override_token(): Create a new override token
- validate_override_token(): Check if a token is valid and applies
- revoke_override_token(): Revoke a token before it expires
- list_override_tokens(): List all active tokens
- File-based persistence in .auto-claude/override-tokens.json

Usage:
    from security.output_validation.overrides import (
        OverrideTokenManager,
        generate_override_token,
        validate_override_token,
    )
    from pathlib import Path

    # Generate a token
    token = generate_override_token(
        rule_id="bash-rm-rf",
        project_dir=Path("/my/project"),
        scope="file:/tmp/test-file.txt",
        expiry_minutes=30,
        reason="Testing file cleanup script",
    )

    # Validate a token
    is_valid = validate_override_token(
        token_id=token.token_id,
        rule_id="bash-rm-rf",
        context="file:/tmp/test-file.txt",
        project_dir=Path("/my/project"),
    )

    # Or use the manager class for more control
    manager = OverrideTokenManager(project_dir=Path("/my/project"))
    token = manager.generate_token(
        rule_id="bash-rm-rf",
        scope="file:/tmp/test-file.txt",
        expiry_minutes=30,
        reason="Testing file cleanup",
    )
    manager.use_token(token.token_id, "file:/tmp/test-file.txt")
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Literal, Optional

from .models import OverrideToken


# =============================================================================
# LOGGER
# =============================================================================

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_EXPIRY_MINUTES = 60
DEFAULT_MAX_USES = 1
TOKENS_FILENAME = "override-tokens.json"
AUTO_CLAUDE_DIR = ".auto-claude"


# =============================================================================
# SCOPE FORMATTING
# =============================================================================

def format_file_scope(file_path: str) -> str:
    """
    Format a file path as a scope string.

    Args:
        file_path: Path to the file

    Returns:
        Scope string like "file:/path/to/file"
    """
    return f"file:{file_path}"


def format_command_scope(command_pattern: str) -> str:
    """
    Format a command pattern as a scope string.

    Args:
        command_pattern: Command or pattern

    Returns:
        Scope string like "command:pattern"
    """
    return f"command:{command_pattern}"


def parse_scope(scope: str) -> tuple[str, str]:
    """
    Parse a scope string into type and value.

    Args:
        scope: Scope string like "file:/path" or "command:pattern"

    Returns:
        Tuple of (scope_type, scope_value)
        - scope_type: "all", "file", or "command"
        - scope_value: The path/pattern (empty for "all")

    Example:
        >>> parse_scope("file:/tmp/test.txt")
        ('file', '/tmp/test.txt')
        >>> parse_scope("command:rm -rf")
        ('command', 'rm -rf')
        >>> parse_scope("all")
        ('all', '')
    """
    if scope == "all":
        return ("all", "")

    if ":" in scope:
        scope_type, scope_value = scope.split(":", 1)
        return (scope_type, scope_value)

    # Invalid scope format
    return ("unknown", scope)


# =============================================================================
# TOKEN STORAGE
# =============================================================================

class TokenStorage:
    """
    Handles file-based storage of override tokens.

    Manages reading and writing tokens to .auto-claude/override-tokens.json.
    Provides thread-safe access and automatic cleanup of expired tokens.

    Attributes:
        tokens_file: Path to the tokens JSON file
        tokens: Dict mapping token_id -> OverrideToken

    Example:
        >>> storage = TokenStorage(project_dir=Path("/my/project"))
        >>> storage.load_tokens()
        >>> token = OverrideToken(token_id="123", rule_id="bash-rm-rf")
        >>> storage.add_token(token)
        >>> storage.save_tokens()
    """

    def __init__(self, project_dir: Path):
        """
        Initialize token storage.

        Args:
            project_dir: Root directory of the project
        """
        self.project_dir = Path(project_dir).resolve()
        self.tokens_file = self._get_tokens_file()
        self.tokens: dict[str, OverrideToken] = {}

    def _get_tokens_file(self) -> Path:
        """
        Get the path to the tokens file.

        Creates .auto-claude directory if it doesn't exist.

        Returns:
            Path to override-tokens.json
        """
        auto_claude_dir = self.project_dir / AUTO_CLAUDE_DIR
        auto_claude_dir.mkdir(parents=True, exist_ok=True)
        return auto_claude_dir / TOKENS_FILENAME

    def load_tokens(self) -> dict[str, OverrideToken]:
        """
        Load tokens from file.

        Returns:
            Dict mapping token_id -> OverrideToken
        """
        if not self.tokens_file.exists():
            logger.debug(f"Tokens file does not exist: {self.tokens_file}")
            return {}

        try:
            with open(self.tokens_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse tokens and filter out expired ones
            tokens = {}
            now = datetime.now(timezone.utc)

            for token_data in data.get("tokens", []):
                token = OverrideToken.from_dict(token_data)

                # Skip expired or exhausted tokens
                if not token.is_valid():
                    logger.debug(
                        f"Skipping expired/exhausted token: {token.token_id}"
                    )
                    continue

                tokens[token.token_id] = token

            self.tokens = tokens
            logger.info(f"Loaded {len(tokens)} valid override tokens")

            return tokens

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse tokens file: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error loading tokens: {e}")
            return {}

    def save_tokens(self) -> bool:
        """
        Save tokens to file.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert tokens to dict
            tokens_data = [
                token.to_dict() for token in self.tokens.values()
            ]

            # Write to file with atomic update
            temp_file = self.tokens_file.with_suffix(".tmp")

            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(
                    {"tokens": tokens_data},
                    f,
                    indent=2,
                    sort_keys=True,
                )

            # Atomic rename
            temp_file.replace(self.tokens_file)

            logger.debug(f"Saved {len(tokens_data)} tokens to {self.tokens_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            return False

    def add_token(self, token: OverrideToken) -> None:
        """
        Add a token to storage.

        Args:
            token: Token to add
        """
        self.tokens[token.token_id] = token
        logger.debug(f"Added token: {token.token_id}")

    def get_token(self, token_id: str) -> OverrideToken | None:
        """
        Get a token by ID.

        Args:
            token_id: Token identifier

        Returns:
            OverrideToken if found and valid, None otherwise
        """
        token = self.tokens.get(token_id)

        if token and token.is_valid():
            return token

        return None

    def remove_token(self, token_id: str) -> bool:
        """
        Remove a token from storage.

        Args:
            token_id: Token identifier

        Returns:
            True if token was removed, False if not found
        """
        if token_id in self.tokens:
            del self.tokens[token_id]
            logger.debug(f"Removed token: {token_id}")
            return True

        return False

    def cleanup_expired(self) -> int:
        """
        Remove expired and exhausted tokens.

        Returns:
            Number of tokens cleaned up
        """
        cleanup_count = 0
        expired_tokens = []

        for token_id, token in self.tokens.items():
            if not token.is_valid():
                expired_tokens.append(token_id)

        for token_id in expired_tokens:
            del self.tokens[token_id]
            cleanup_count += 1

        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} expired tokens")

        return cleanup_count

    def list_tokens(
        self,
        rule_id: str | None = None,
    ) -> list[OverrideToken]:
        """
        List all valid tokens, optionally filtered by rule_id.

        Args:
            rule_id: Optional rule ID to filter by

        Returns:
            List of valid OverrideToken objects
        """
        tokens = [
            token for token in self.tokens.values()
            if token.is_valid()
        ]

        if rule_id:
            tokens = [t for t in tokens if t.rule_id == rule_id]

        return tokens


# =============================================================================
# OVERRIDE TOKEN MANAGER
# =============================================================================

class OverrideTokenManager:
    """
    Manages override token lifecycle.

    This class provides a high-level API for creating, validating, using,
    and revoking override tokens. It handles persistence, cleanup, and
    validation logic.

    Attributes:
        project_dir: Root directory of the project
        storage: TokenStorage instance for persistence

    Example:
        >>> manager = OverrideTokenManager(project_dir=Path("/my/project"))
        >>>
        >>> # Create a token
        >>> token = manager.generate_token(
        ...     rule_id="bash-rm-rf",
        ...     scope="file:/tmp/test.txt",
        ...     expiry_minutes=30,
        ...     reason="Testing cleanup script",
        ... )
        >>>
        >>> # Use the token
        >>> if manager.validate_and_use_token(
        ...     token_id=token.token_id,
        ...     rule_id="bash-rm-rf",
        ...     context="file:/tmp/test.txt",
        ... ):
        ...     print("Token validated and used")
        >>>
        >>> # Revoke when done
        >>> manager.revoke_token(token.token_id)
    """

    def __init__(self, project_dir: Path):
        """
        Initialize override token manager.

        Args:
            project_dir: Root directory of the project
        """
        self.project_dir = Path(project_dir).resolve()
        self.storage = TokenStorage(self.project_dir)

    def _ensure_loaded(self) -> None:
        """Ensure tokens are loaded from storage."""
        if not self.storage.tokens:
            self.storage.load_tokens()

    def generate_token(
        self,
        rule_id: str,
        scope: str = "all",
        expiry_minutes: int = DEFAULT_EXPIRY_MINUTES,
        max_uses: int = DEFAULT_MAX_USES,
        reason: str = "",
        creator: str = "user",
    ) -> OverrideToken:
        """
        Generate a new override token.

        Args:
            rule_id: ID of the rule this token overrides
            scope: Scope of override ("all", "file:/path", "command:pattern")
            expiry_minutes: Token expiry time in minutes (0 = no expiry)
            max_uses: Maximum number of uses (0 = unlimited)
            reason: User-provided reason for the override
            creator: Identifier for who created the token

        Returns:
            OverrideToken object

        Raises:
            ValueError: If parameters are invalid
        """
        # Validate inputs
        if not rule_id or not isinstance(rule_id, str):
            raise ValueError("rule_id must be a non-empty string")

        if expiry_minutes < 0:
            raise ValueError("expiry_minutes must be >= 0")

        if max_uses < 0:
            raise ValueError("max_uses must be >= 0")

        # Calculate expiry
        expires_at = ""
        if expiry_minutes > 0:
            expiry_time = datetime.now(timezone.utc) + timedelta(
                minutes=expiry_minutes
            )
            expires_at = expiry_time.isoformat()

        # Create token
        token = OverrideToken(
            token_id=str(uuid.uuid4()),
            rule_id=rule_id,
            scope=scope,
            expires_at=expires_at,
            max_uses=max_uses,
            use_count=0,
            reason=reason,
            creator=creator,
        )

        # Save to storage
        self._ensure_loaded()
        self.storage.add_token(token)
        self.storage.save_tokens()

        logger.info(
            f"Generated override token: {token.token_id} "
            f"for rule {rule_id}, scope={scope}, "
            f"expires={expiry_minutes}min, max_uses={max_uses}"
        )

        return token

    def validate_token(
        self,
        token_id: str,
        rule_id: str,
        context: str = "",
    ) -> bool:
        """
        Check if a token is valid and applies to the given context.

        Args:
            token_id: Token identifier
            rule_id: Rule ID that the token should override
            context: Context string (e.g., "file:/path" or "command:pattern")

        Returns:
            True if token is valid and applies, False otherwise
        """
        self._ensure_loaded()

        token = self.storage.get_token(token_id)

        if not token:
            logger.debug(f"Token not found or invalid: {token_id}")
            return False

        # Check rule ID match
        if token.rule_id != rule_id:
            logger.debug(
                f"Token {token_id} is for rule {token.rule_id}, "
                f"not {rule_id}"
            )
            return False

        # Check scope
        if context and not token.applies_to(context):
            logger.debug(
                f"Token {token_id} scope ({token.scope}) "
                f"does not match context ({context})"
            )
            return False

        logger.debug(f"Token {token_id} is valid for {rule_id}")
        return True

    def use_token(
        self,
        token_id: str,
        context: str = "",
    ) -> bool:
        """
        Use a token (increment usage count).

        Args:
            token_id: Token identifier
            context: Context string for logging

        Returns:
            True if token was used, False if exhausted/invalid
        """
        self._ensure_loaded()

        token = self.storage.get_token(token_id)

        if not token:
            return False

        # Increment usage count
        if token.use_token():
            self.storage.save_tokens()
            logger.info(
                f"Used override token: {token_id}, "
                f"context={context}, "
                f"use_count={token.use_count}/{token.max_uses}"
            )
            return True

        logger.debug(f"Token {token_id} is exhausted")
        return False

    def validate_and_use_token(
        self,
        token_id: str,
        rule_id: str,
        context: str = "",
    ) -> bool:
        """
        Validate and use a token in one operation.

        This is the most common operation when checking overrides:
        first validate the token applies to the rule/context, then use it.

        Args:
            token_id: Token identifier
            rule_id: Rule ID that the token should override
            context: Context string (e.g., "file:/path" or "command:pattern")

        Returns:
            True if token was valid and used, False otherwise
        """
        if not self.validate_token(token_id, rule_id, context):
            return False

        return self.use_token(token_id, context)

    def revoke_token(self, token_id: str) -> bool:
        """
        Revoke a token before it expires.

        Args:
            token_id: Token identifier

        Returns:
            True if token was revoked, False if not found
        """
        self._ensure_loaded()

        if self.storage.remove_token(token_id):
            self.storage.save_tokens()
            logger.info(f"Revoked override token: {token_id}")
            return True

        return False

    def list_tokens(
        self,
        rule_id: str | None = None,
        include_expired: bool = False,
    ) -> list[OverrideToken]:
        """
        List tokens, optionally filtered by rule_id.

        Args:
            rule_id: Optional rule ID to filter by
            include_expired: If True, include expired/exhausted tokens

        Returns:
            List of OverrideToken objects
        """
        self._ensure_loaded()

        if include_expired:
            # Return all tokens
            tokens = list(self.storage.tokens.values())
        else:
            # Return only valid tokens
            tokens = self.storage.list_tokens(rule_id=rule_id)

        if rule_id and include_expired:
            tokens = [t for t in tokens if t.rule_id == rule_id]

        return tokens

    def cleanup_expired(self) -> int:
        """
        Remove expired and exhausted tokens from storage.

        Returns:
            Number of tokens cleaned up
        """
        self._ensure_loaded()

        cleanup_count = self.storage.cleanup_expired()

        if cleanup_count > 0:
            self.storage.save_tokens()

        return cleanup_count


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_override_token(
    rule_id: str,
    project_dir: Path,
    scope: str = "all",
    expiry_minutes: int = DEFAULT_EXPIRY_MINUTES,
    max_uses: int = DEFAULT_MAX_USES,
    reason: str = "",
    creator: str = "user",
) -> OverrideToken:
    """
    Generate a new override token.

    Convenience function that creates a manager and generates a token.

    Args:
        rule_id: ID of the rule this token overrides
        project_dir: Root directory of the project
        scope: Scope of override ("all", "file:/path", "command:pattern")
        expiry_minutes: Token expiry time in minutes (default: 60)
        max_uses: Maximum number of uses (default: 1)
        reason: User-provided reason for the override
        creator: Identifier for who created the token

    Returns:
        OverrideToken object

    Example:
        >>> from pathlib import Path
        >>> token = generate_override_token(
        ...     rule_id="bash-rm-rf",
        ...     project_dir=Path("/my/project"),
        ...     scope="file:/tmp/test.txt",
        ...     expiry_minutes=30,
        ...     reason="Testing cleanup script",
        ... )
        >>> print(f"Token ID: {token.token_id}")
        >>> print(f"Expires: {token.expires_at}")
    """
    manager = OverrideTokenManager(project_dir)
    return manager.generate_token(
        rule_id=rule_id,
        scope=scope,
        expiry_minutes=expiry_minutes,
        max_uses=max_uses,
        reason=reason,
        creator=creator,
    )


def validate_override_token(
    token_id: str,
    rule_id: str,
    project_dir: Path,
    context: str = "",
) -> bool:
    """
    Check if an override token is valid and applies to the given context.

    Convenience function that creates a manager and validates a token.

    Args:
        token_id: Token identifier
        rule_id: Rule ID that the token should override
        project_dir: Root directory of the project
        context: Context string (e.g., "file:/path" or "command:pattern")

    Returns:
        True if token is valid and applies, False otherwise

    Example:
        >>> from pathlib import Path
        >>> is_valid = validate_override_token(
        ...     token_id="123e4567-e89b-12d3-a456-426614174000",
        ...     rule_id="bash-rm-rf",
        ...     project_dir=Path("/my/project"),
        ...     context="file:/tmp/test.txt",
        ... )
        >>> if is_valid:
        ...     print("Token is valid")
    """
    manager = OverrideTokenManager(project_dir)
    return manager.validate_token(token_id, rule_id, context)


def use_override_token(
    token_id: str,
    project_dir: Path,
    context: str = "",
) -> bool:
    """
    Use an override token (increment usage count).

    Convenience function that creates a manager and uses a token.

    Args:
        token_id: Token identifier
        project_dir: Root directory of the project
        context: Context string for logging

    Returns:
        True if token was used, False if exhausted/invalid

    Example:
        >>> from pathlib import Path
        >>> success = use_override_token(
        ...     token_id="123e4567-e89b-12d3-a456-426614174000",
        ...     project_dir=Path("/my/project"),
        ...     context="file:/tmp/test.txt",
        ... )
        >>> if success:
        ...     print("Token used successfully")
    """
    manager = OverrideTokenManager(project_dir)
    return manager.use_token(token_id, context)


def validate_and_use_override_token(
    token_id: str,
    rule_id: str,
    project_dir: Path,
    context: str = "",
) -> bool:
    """
    Validate and use an override token in one operation.

    This is the most common convenience function for checking overrides.
    It validates that the token applies to the rule/context, then uses it.

    Args:
        token_id: Token identifier
        rule_id: Rule ID that the token should override
        project_dir: Root directory of the project
        context: Context string (e.g., "file:/path" or "command:pattern")

    Returns:
        True if token was valid and used, False otherwise

    Example:
        >>> from pathlib import Path
        >>> if validate_and_use_override_token(
        ...     token_id="123e4567-e89b-12d3-a456-426614174000",
        ...     rule_id="bash-rm-rf",
        ...     project_dir=Path("/my/project"),
        ...     context="file:/tmp/test.txt",
        ... ):
        ...     print("Override allowed")
        ... else:
        ...     print("Invalid or exhausted token")
    """
    manager = OverrideTokenManager(project_dir)
    return manager.validate_and_use_token(token_id, rule_id, context)


def revoke_override_token(
    token_id: str,
    project_dir: Path,
) -> bool:
    """
    Revoke an override token before it expires.

    Convenience function that creates a manager and revokes a token.

    Args:
        token_id: Token identifier
        project_dir: Root directory of the project

    Returns:
        True if token was revoked, False if not found

    Example:
        >>> from pathlib import Path
        >>> if revoke_override_token(
        ...     token_id="123e4567-e89b-12d3-a456-426614174000",
        ...     project_dir=Path("/my/project"),
        ... ):
        ...     print("Token revoked")
    """
    manager = OverrideTokenManager(project_dir)
    return manager.revoke_token(token_id)


def list_override_tokens(
    project_dir: Path,
    rule_id: str | None = None,
    include_expired: bool = False,
) -> list[OverrideToken]:
    """
    List override tokens.

    Convenience function that creates a manager and lists tokens.

    Args:
        project_dir: Root directory of the project
        rule_id: Optional rule ID to filter by
        include_expired: If True, include expired/exhausted tokens

    Returns:
        List of OverrideToken objects

    Example:
        >>> from pathlib import Path
        >>> tokens = list_override_tokens(
        ...     project_dir=Path("/my/project"),
        ...     rule_id="bash-rm-rf",
        ... )
        >>> for token in tokens:
        ...     print(f"{token.token_id}: {token.scope}")
    """
    manager = OverrideTokenManager(project_dir)
    return manager.list_tokens(rule_id=rule_id, include_expired=include_expired)


def cleanup_expired_tokens(project_dir: Path) -> int:
    """
    Remove expired and exhausted tokens from storage.

    Convenience function that creates a manager and cleans up tokens.

    Args:
        project_dir: Root directory of the project

    Returns:
        Number of tokens cleaned up

    Example:
        >>> from pathlib import Path
        >>> count = cleanup_expired_tokens(Path("/my/project"))
        >>> print(f"Cleaned up {count} expired tokens")
    """
    manager = OverrideTokenManager(project_dir)
    return manager.cleanup_expired()
