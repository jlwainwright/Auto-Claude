"""
Override Commands
=================

CLI commands for managing validation override tokens.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

# Ensure parent directory is in path for imports (before other imports)
_PARENT_DIR = Path(__file__).parent.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

from security.output_validation.overrides import (
    OverrideTokenManager,
    format_command_scope,
    format_file_scope,
)
from ui import Icons, icon, success, warning, error as ui_error


def handle_override_create_command(
    project_dir: Path,
    rule_id: str,
    scope: str = "all",
    expiry_minutes: int = 60,
    max_uses: int = 1,
    reason: str = "",
) -> None:
    """
    Handle the override create command.

    Args:
        project_dir: Project root directory
        rule_id: ID of the rule to override
        scope: Override scope ("all", "file:<path>", "command:<pattern>")
        expiry_minutes: Token expiry time in minutes (0 = no expiry)
        max_uses: Maximum number of uses (0 = unlimited)
        reason: User-provided reason for the override
    """
    # Validate scope format
    valid_scopes = ["all"]
    if scope.startswith("file:"):
        valid_scopes.append(scope)
    elif scope.startswith("command:"):
        valid_scopes.append(scope)
    elif scope != "all":
        print(
            ui_error(
                f"{icon(Icons.ERROR)} Invalid scope format. "
                f"Use: all, file:<path>, or command:<pattern>"
            )
        )
        sys.exit(1)

    # Validate numeric parameters
    if expiry_minutes < 0:
        print(ui_error(f"{icon(Icons.ERROR)} expiry_minutes must be >= 0"))
        sys.exit(1)

    if max_uses < 0:
        print(ui_error(f"{icon(Icons.ERROR)} max_uses must be >= 0"))
        sys.exit(1)

    # Create the token
    manager = OverrideTokenManager(project_dir)

    try:
        token = manager.generate_token(
            rule_id=rule_id,
            scope=scope,
            expiry_minutes=expiry_minutes,
            max_uses=max_uses,
            reason=reason,
            creator="cli",
        )
    except ValueError as e:
        print(ui_error(f"{icon(Icons.ERROR)} Failed to create token: {e}"))
        sys.exit(1)

    # Display token details
    print("\n" + "=" * 70)
    print("  OVERRIDE TOKEN CREATED")
    print("=" * 70)
    print()
    print(f"  Token ID:     {token.token_id}")
    print(f"  Rule ID:      {token.rule_id}")
    print(f"  Scope:        {token.scope}")
    print(f"  Created:      {token.created_at}")
    print(f"  Expires:      {token.expires_at or 'Never'}")
    print(f"  Max Uses:     {token.max_uses if token.max_uses > 0 else 'Unlimited'}")
    print(f"  Reason:       {token.reason or '(none)'}")
    print()

    # Show usage hints
    print("=" * 70)
    print("  USAGE")
    print("=" * 70)
    print()
    print(f"  The token will be automatically used when validation triggers.")
    print(f"  No additional action needed - the agent will check for valid tokens.")
    print()
    print(f"  To revoke this token:")
    print(f"    python auto-claude/run.py --override revoke {token.token_id}")
    print()

    # Show security warning if scope is "all"
    if scope == "all":
        print(
            warning(
                f"{icon(Icons.WARNING)} Security Warning: "
                f"This token overrides ALL validations for rule '{rule_id}'."
            )
        )
        print()
    elif expiry_minutes == 0:
        print(
            warning(
                f"{icon(Icons.WARNING)} Security Warning: "
                f"This token NEVER expires. Use with caution."
            )
        )
        print()
    elif max_uses == 0:
        print(
            warning(
                f"{icon(Icons.WARNING)} Security Warning: "
                f"This token has UNLIMITED uses. Use with caution."
            )
        )
        print()

    print(success(f"{icon(Icons.SUCCESS)} Override token created successfully"))
    print()


def handle_override_list_command(
    project_dir: Path,
    rule_id: str | None = None,
    include_expired: bool = False,
) -> None:
    """
    Handle the override list command.

    Args:
        project_dir: Project root directory
        rule_id: Optional rule ID to filter by
        include_expired: If True, include expired/exhausted tokens
    """
    manager = OverrideTokenManager(project_dir)
    tokens = manager.list_tokens(rule_id=rule_id, include_expired=include_expired)

    print("\n" + "=" * 70)
    print("  OVERRIDE TOKENS")
    print("=" * 70)
    print()

    # Filter info
    if rule_id:
        print(f"  Filtered by rule: {rule_id}")
    if include_expired:
        print(f"  Including expired/exhausted tokens")
    print()

    if not tokens:
        print("  No override tokens found.")
        print()
        print("  To create a token:")
        print("    python auto-claude/run.py --override create <rule-id>")
        print()
        return

    # Sort by creation date (newest first)
    tokens_sorted = sorted(tokens, key=lambda t: t.created_at, reverse=True)

    # Display tokens
    for i, token in enumerate(tokens_sorted, 1):
        # Check token status
        now = datetime.now(timezone.utc)
        is_expired = token.expires_at and datetime.fromisoformat(
            token.expires_at
        ) < now
        is_exhausted = token.max_uses > 0 and token.use_count >= token.max_uses
        is_valid = not (is_expired or is_exhausted)

        # Status indicator
        if not is_valid:
            status = "[EXPIRED/EXHAUSTED]"
            status_icon = icon(Icons.WARNING)
        else:
            status = "[ACTIVE]"
            status_icon = icon(Icons.SUCCESS)

        print(f"  {i}. {status_icon} {token.token_id}")
        print(f"     Status:        {status}")
        print(f"     Rule ID:       {token.rule_id}")
        print(f"     Scope:         {token.scope}")
        print(f"     Created:       {token.created_at}")

        if token.expires_at:
            # Calculate remaining time
            expiry_dt = datetime.fromisoformat(token.expires_at)
            if is_expired:
                remaining = "Expired"
            else:
                delta = expiry_dt - now
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                remaining = f"{hours}h {minutes}m"
            print(f"     Expires:       {token.expires_at} ({remaining})")
        else:
            print(f"     Expires:       Never")

        # Usage
        if token.max_uses > 0:
            uses_str = f"{token.use_count}/{token.max_uses}"
            if is_exhausted:
                uses_str += " (exhausted)"
            print(f"     Uses:          {uses_str}")
        else:
            print(f"     Uses:          {token.use_count} (unlimited)")

        if token.reason:
            print(f"     Reason:        {token.reason}")

        print()

    # Summary
    active_count = sum(1 for t in tokens if t.is_valid())
    expired_count = len(tokens) - active_count

    print("-" * 70)
    print(f"  Total: {len(tokens)} tokens ({active_count} active, {expired_count} expired)")
    print()

    # Show usage hints
    if active_count > 0:
        print("  To revoke a token:")
        print("    python auto-claude/run.py --override revoke <token-id>")
        print()
    if expired_count > 0 and not include_expired:
        print("  To include expired tokens:")
        print("    python auto-claude/run.py --override list --include-expired")
        print()


def handle_override_revoke_command(project_dir: Path, token_id: str) -> None:
    """
    Handle the override revoke command.

    Args:
        project_dir: Project root directory
        token_id: Token ID to revoke
    """
    # Validate token ID format (basic check for UUID)
    if len(token_id.split("-")) != 5:
        print(
            ui_error(
                f"{icon(Icons.ERROR)} Invalid token ID format. "
                f"Token IDs should be UUIDs."
            )
        )
        print()
        print("To list available tokens:")
        print("  python auto-claude/run.py --override list")
        sys.exit(1)

    manager = OverrideTokenManager(project_dir)

    # Check if token exists before revoking
    tokens = manager.list_tokens(include_expired=True)
    token_exists = any(t.token_id == token_id for t in tokens)

    if not token_exists:
        print(
            warning(
                f"{icon(Icons.WARNING)} Token '{token_id}' not found. "
                f"It may have already expired or been revoked."
            )
        )
        print()

        # Show available tokens
        handle_override_list_command(project_dir, include_expired=False)
        return

    # Revoke the token
    success_revoked = manager.revoke_token(token_id)

    if success_revoked:
        print()
        print(success(f"{icon(Icons.SUCCESS)} Token revoked successfully"))
        print()
        print(f"  Token ID: {token_id}")
        print()

        print("  The token will no longer bypass validation rules.")
        print()
    else:
        print(
            ui_error(
                f"{icon(Icons.ERROR)} Failed to revoke token '{token_id}'. "
                f"It may have already been revoked."
            )
        )
        sys.exit(1)


def print_override_help() -> None:
    """Print help information for override commands."""
    print("\n" + "=" * 70)
    print("  OVERRIDE COMMANDS")
    print("=" * 70)
    print()
    print("Override commands allow you to manage validation override tokens.")
    print("Tokens temporarily bypass specific validation rules when needed.")
    print()
    print("=" * 70)
    print("  CREATE TOKEN")
    print("=" * 70)
    print()
    print("  python auto-claude/run.py --override create <rule-id> [options]")
    print()
    print("  Arguments:")
    print("    <rule-id>              ID of the validation rule to override")
    print()
    print("  Options:")
    print("    --scope <scope>        Override scope (default: all)")
    print("                           - all: Override all validations for this rule")
    print("                           - file:<path>: Override for specific file")
    print("                           - command:<pattern>: Override for command pattern")
    print("    --expiry <minutes>     Token expiry time in minutes (default: 60)")
    print("                           Use 0 for no expiry")
    print("    --max-uses <count>     Maximum uses (default: 1)")
    print("                           Use 0 for unlimited uses")
    print("    --reason <text>        Reason for the override (for audit trail)")
    print()
    print("  Examples:")
    print("    # Create token for bash-rm-rf rule (1 hour, single use)")
    print("    python auto-claude/run.py --override create bash-rm-rf")
    print()
    print("    # Create token for specific file")
    print("    python auto-claude/run.py --override create bash-rm-rf \\")
    print("      --scope file:/tmp/test.txt --reason 'Testing cleanup script'")
    print()
    print("    # Create unlimited use token for 24 hours")
    print("    python auto-claude/run.py --override create bash-rm-rf \\")
    print("      --expiry 1440 --max-uses 0")
    print()
    print("=" * 70)
    print("  LIST TOKENS")
    print("=" * 70)
    print()
    print("  python auto-claude/run.py --override list [options]")
    print()
    print("  Options:")
    print("    --rule <rule-id>       Filter by rule ID")
    print("    --include-expired      Include expired/exhausted tokens")
    print()
    print("  Examples:")
    print("    # List all active tokens")
    print("    python auto-claude/run.py --override list")
    print()
    print("    # List tokens for a specific rule")
    print("    python auto-claude/run.py --override list --rule bash-rm-rf")
    print()
    print("    # Include expired tokens")
    print("    python auto-claude/run.py --override list --include-expired")
    print()
    print("=" * 70)
    print("  REVOKE TOKEN")
    print("=" * 70)
    print()
    print("  python auto-claude/run.py --override revoke <token-id>")
    print()
    print("  Arguments:")
    print("    <token-id>             Token ID to revoke (get from list command)")
    print()
    print("  Examples:")
    print("    python auto-claude/run.py --override revoke 123e4567-e89b-12d3-a456-426614174000")
    print()
    print("=" * 70)
    print("  SECURITY NOTES")
    print("=" * 70)
    print()
    print("  • Tokens are stored in .auto-claude/override-tokens.json")
    print("  • Use the most restrictive scope possible (file: > command: > all)")
    print("  • Set appropriate expiry times (shorter is better)")
    print("  • Limit usage count when possible (default: 1)")
    print("  • Always provide a reason for audit purposes")
    print("  • Review active tokens regularly with --override list")
    print("  • Revoke tokens when no longer needed")
    print()
