"""
Security Module for Auto-Build Framework
=========================================

Provides security validation for bash commands using dynamic allowlists
based on project analysis, plus input harmlessness screening for prompt
injection detection.

The security system has multiple layers:
1. Base commands - Always allowed (core shell utilities)
2. Stack commands - Detected from project structure (frameworks, languages)
3. Custom commands - User-defined allowlist
4. Input screening - Prompt injection and malicious pattern detection

Public API
----------
Main functions:
- bash_security_hook: Pre-tool-use hook for command validation
- validate_command: Standalone validation function for testing
- get_security_profile: Get or create security profile for a project
- reset_profile_cache: Reset cached security profile
- screen_input: Screen user input for prompt injection attacks
- is_input_safe: Quick check if input is safe

Command parsing:
- extract_commands: Extract command names from shell strings
- split_command_segments: Split compound commands into segments

Validators:
- All validators are available via the VALIDATORS dict

Input screening:
- InputScreener: Main screening class
- ScreeningResult: Result dataclass with verdict and patterns
- ScreeningVerdict: Enum of possible verdicts (safe/suspicious/rejected)
- ScreeningLevel: Enum of screening strictness levels
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

# Input harmlessness screening
from .input_screener import (
    DetectedPattern,
    InputScreener,
    ScreeningLevel,
    ScreeningResult,
    ScreeningVerdict,
    is_input_safe,
    screen_input,
)

# Screening user messages
from .screening_messages import (
    MessageCategory,
    OutputFormat,
    format_for_plain,
    format_for_terminal,
    format_for_ui,
    get_rejection_message,
    get_suggestions_for_category,
    get_user_friendly_rejection,
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
    # Main API
    "bash_security_hook",
    "validate_command",
    "get_security_profile",
    "reset_profile_cache",
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
    # Input harmlessness screening
    "InputScreener",
    "screen_input",
    "is_input_safe",
    "ScreeningResult",
    "ScreeningVerdict",
    "ScreeningLevel",
    "DetectedPattern",
    # Screening user messages
    "MessageCategory",
    "OutputFormat",
    "get_rejection_message",
    "get_user_friendly_rejection",
    "get_suggestions_for_category",
    "format_for_terminal",
    "format_for_plain",
    "format_for_ui",
]
