"""
Output Validation System
========================

Inspects agent-generated tool calls before execution to catch potentially
harmful operations that slip through the allowlist.

This package provides:
- Data models for validation rules and results
- Pattern detection engine for dangerous operations
- Tool-specific validators (Bash, Write, Edit, etc.)
- Per-project configuration system
- Override mechanism for user bypasses
- Logging and reporting

Main exports:
- SeverityLevel: Severity levels for rules
- RulePriority: Priority levels for rule evaluation
- ToolType: Tool types that can be validated
- ValidationRule: Pattern-based validation rule
- ValidationResult: Result of validation check
- OutputValidationConfig: Per-project configuration
- OverrideToken: User bypass token
- ValidationEvent: Log entry for validation events
"""

# Data models
from .models import (
    OverrideToken,
    OutputValidationConfig,
    RulePriority,
    SeverityLevel,
    ToolType,
    ValidationEvent,
    ValidationRule,
    ValidationResult,
)

# Pattern detection engine
from .pattern_detector import PatternDetector, PatternMatchResult, create_pattern_detector

# Default validation rules
from .rules import (
    ALL_DEFAULT_RULES,
    BASH_RULES,
    FILE_PATH_RULES,
    FILE_WRITE_RULES,
    WEB_RULES,
    get_default_rules,
    get_rule_by_id,
    list_rule_categories,
    list_rule_ids,
)

# Main validation hook
from .hook import output_validation_hook, reset_hook

# Configuration loading
from .config import (
    ValidationConfigLoader,
    clear_config_cache,
    get_config_file_path,
    get_validation_config,
    is_yaml_available,
    load_validation_config,
)

# Custom rules support
from .custom_rules import (
    CustomRuleError,
    apply_config_overrides,
    get_active_rules,
    get_custom_rule_ids,
    load_custom_rules,
    merge_with_defaults,
    validate_pattern_safety,
)

# Allowed paths support
from .allowed_paths import (
    AllowedPathsChecker,
    compile_glob_patterns,
    get_allowed_paths,
    is_path_allowed,
    normalize_pattern,
    pattern_to_regex,
)

# Override token management
from .overrides import (
    OverrideTokenManager,
    TokenStorage,
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

# Validation event logging
from .logger import (
    ValidationEventLogger,
    get_validation_logger,
    reset_validation_logger,
    log_blocked_operation,
    log_warning,
    log_override_used,
    log_path_bypassed,
)

__all__ = [
    # Enums
    "SeverityLevel",
    "RulePriority",
    "ToolType",
    # Core models
    "ValidationRule",
    "ValidationResult",
    "OutputValidationConfig",
    "OverrideToken",
    "ValidationEvent",
    # Pattern detection
    "PatternDetector",
    "PatternMatchResult",
    "create_pattern_detector",
    # Default rules
    "ALL_DEFAULT_RULES",
    "BASH_RULES",
    "FILE_WRITE_RULES",
    "FILE_PATH_RULES",
    "WEB_RULES",
    "get_default_rules",
    "get_rule_by_id",
    "list_rule_categories",
    "list_rule_ids",
    # Main hook
    "output_validation_hook",
    "reset_hook",
    # Configuration loading
    "ValidationConfigLoader",
    "load_validation_config",
    "get_validation_config",
    "clear_config_cache",
    "get_config_file_path",
    "is_yaml_available",
    # Custom rules support
    "CustomRuleError",
    "load_custom_rules",
    "merge_with_defaults",
    "apply_config_overrides",
    "validate_pattern_safety",
    "get_custom_rule_ids",
    "get_active_rules",
    # Allowed paths support
    "AllowedPathsChecker",
    "is_path_allowed",
    "get_allowed_paths",
    "compile_glob_patterns",
    "normalize_pattern",
    "pattern_to_regex",
    # Override token management
    "OverrideTokenManager",
    "TokenStorage",
    "generate_override_token",
    "validate_override_token",
    "use_override_token",
    "validate_and_use_override_token",
    "revoke_override_token",
    "list_override_tokens",
    "cleanup_expired_tokens",
    "format_file_scope",
    "format_command_scope",
    "parse_scope",
    # Validation event logging
    "ValidationEventLogger",
    "get_validation_logger",
    "reset_validation_logger",
    "log_blocked_operation",
    "log_warning",
    "log_override_used",
    "log_path_bypassed",
]
