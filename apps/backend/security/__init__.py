"""
Security Module for Auto-Build Framework
=========================================

Provides security validation for bash commands using dynamic allowlists
based on project analysis, plus comprehensive output validation for all
agent tool calls.

The security system has multiple layers:
1. Base commands - Always allowed (core shell utilities)
2. Stack commands - Detected from project structure (frameworks, languages)
3. Custom commands - User-defined allowlist
4. Output validation - Pattern-based detection of dangerous operations

Public API
----------
Bash command validation:
- bash_security_hook: Pre-tool-use hook for command validation
- validate_command: Standalone validation function for testing
- get_security_profile: Get or create security profile for a project
- reset_profile_cache: Reset cached security profile

Output validation:
- output_validation_hook: Pre-tool-use hook for all tool output validation
- get_validation_config: Load validation configuration for a project
- generate_override_token: Create override token for bypassing rules
- validate_override_token: Check if an override token is valid
- use_override_token: Use an override token
- revoke_override_token: Revoke an override token
- list_override_tokens: List all override tokens

Command parsing:
- extract_commands: Extract command names from shell strings
- split_command_segments: Split compound commands into segments

Validators:
- All validators are available via the VALIDATORS dict
"""

# Core hooks
# Re-export from project_analyzer for convenience
from project_analyzer import (
    BASE_COMMANDS,
    SecurityProfile,
    is_command_allowed,
    needs_validation,
)

from .hooks import bash_security_hook, validate_command

# Command parsing utilities
from .parser import (
    extract_commands,
    get_command_for_validation,
    split_command_segments,
)

# Profile management
from .profile import (
    get_security_profile,
    reset_profile_cache,
)

# Tool input validation
from .tool_input_validator import (
    get_safe_tool_input,
    validate_tool_input,
)

# Output validation system
from .output_validation import (
    # Main hook
    output_validation_hook,
    # Configuration loading
    get_validation_config,
    load_validation_config,
    clear_config_cache,
    get_config_file_path,
    # Override token management
    generate_override_token,
    validate_override_token,
    use_override_token,
    validate_and_use_override_token,
    revoke_override_token,
    list_override_tokens,
    cleanup_expired_tokens,
    # Enums and models
    SeverityLevel,
    ValidationResult,
    ValidationRule,
    OutputValidationConfig,
    OverrideToken,
    # Event logging
    log_blocked_operation,
    log_warning,
    log_override_used,
    # Report generation
    generate_validation_report,
    generate_and_save_report,
    print_validation_summary,
    # Message formatting
    format_block_message,
    format_short_block_message,
)

# Validators (for advanced usage)
from .validator import (
    VALIDATORS,
    validate_chmod_command,
    validate_dropdb_command,
    validate_dropuser_command,
    validate_git_command,
    validate_git_commit,
    validate_git_config,
    validate_init_script,
    validate_kill_command,
    validate_killall_command,
    validate_mongosh_command,
    validate_mysql_command,
    validate_mysqladmin_command,
    validate_pkill_command,
    validate_psql_command,
    validate_redis_cli_command,
    validate_rm_command,
)

__all__ = [
    # Main API - Bash security
    "bash_security_hook",
    "validate_command",
    "get_security_profile",
    "reset_profile_cache",
    # Main API - Output validation
    "output_validation_hook",
    "get_validation_config",
    "load_validation_config",
    "clear_config_cache",
    "get_config_file_path",
    # Override token management
    "generate_override_token",
    "validate_override_token",
    "use_override_token",
    "validate_and_use_override_token",
    "revoke_override_token",
    "list_override_tokens",
    "cleanup_expired_tokens",
    # Parsing utilities
    "extract_commands",
    "split_command_segments",
    "get_command_for_validation",
    # Validators
    "VALIDATORS",
    "validate_pkill_command",
    "validate_kill_command",
    "validate_killall_command",
    "validate_chmod_command",
    "validate_rm_command",
    "validate_init_script",
    "validate_git_command",
    "validate_git_commit",
    "validate_git_config",
    "validate_dropdb_command",
    "validate_dropuser_command",
    "validate_psql_command",
    "validate_mysql_command",
    "validate_redis_cli_command",
    "validate_mongosh_command",
    "validate_mysqladmin_command",
    # From project_analyzer
    "SecurityProfile",
    "is_command_allowed",
    "needs_validation",
    "BASE_COMMANDS",
    # Tool input validation
    "validate_tool_input",
    "get_safe_tool_input",
    # Output validation - Enums and models
    "SeverityLevel",
    "ValidationResult",
    "ValidationRule",
    "OutputValidationConfig",
    "OverrideToken",
    # Output validation - Event logging
    "log_blocked_operation",
    "log_warning",
    "log_override_used",
    # Output validation - Report generation
    "generate_validation_report",
    "generate_and_save_report",
    "print_validation_summary",
    # Output validation - Message formatting
    "format_block_message",
    "format_short_block_message",
]
