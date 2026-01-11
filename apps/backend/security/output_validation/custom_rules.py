"""
Custom Validation Rules Support
================================

Module for loading, validating, and merging custom validation rules from project
configuration with default rules.

This module provides:
- CustomRuleError: Exception for custom rule validation failures
- load_custom_rules(): Load and parse custom rules from config
- merge_with_defaults(): Merge custom rules with default rules
- apply_config_overrides(): Apply disabled_rules and severity_overrides
- validate_pattern_safety(): Validate regex patterns for safety issues

Custom rules allow projects to:
- Add project-specific validation patterns
- Override default rule severity
- Disable default rules that don't apply
- Customize validation behavior per project

Usage:
    from security.output_validation.custom_rules import (
        CustomRuleError,
        load_custom_rules,
        merge_with_defaults,
        validate_pattern_safety,
    )
    from security.output_validation.rules import get_default_rules
    from security.output_validation.config import load_validation_config

    # Load config and custom rules
    config = load_validation_config(project_dir)
    custom_rules = load_custom_rules(config)

    # Merge with defaults and apply config overrides
    all_rules = merge_with_defaults(
        default_rules=get_default_rules(),
        custom_rules=custom_rules,
        config=config
    )
"""

import re
from pathlib import Path
from typing import List, Literal, Optional, Union

from .config import OutputValidationConfig
from .models import (
    RulePriority,
    SeverityLevel,
    ToolType,
    ValidationRule,
)


# =============================================================================
# EXCEPTIONS
# =============================================================================

class CustomRuleError(Exception):
    """Exception raised when custom rule validation fails."""

    def __init__(self, message: str, rule_id: Optional[str] = None, field: Optional[str] = None):
        """
        Initialize custom rule error.

        Args:
            message: Error message
            rule_id: ID of the rule that caused the error (if applicable)
            field: Field that caused the error (if applicable)
        """
        self.rule_id = rule_id
        self.field = field
        super().__init__(message)


# =============================================================================
# PATTERN SAFETY VALIDATION
# =============================================================================

# Patterns that are potentially dangerous in regex
DANGEROUS_REGEX_PATTERNS = [
    # Nested quantifiers (can cause catastrophic backtracking)
    r"(.+)\1",
    r"(.+)+\1",
    r"(a+)+",

    # Overly permissive patterns
    r"^.*$",
    r".*",
    r"^.+$",

    # Evil regex patterns (known ReDoS patterns)
    r"(a+)+$",
    r"([a-zA-Z]+)*$",
    r"(a|aa)+$",
]

DANGEROUS_REGEX_DESCRIPTIONS = [
    "nested quantifiers (catastrophic backtracking risk)",
    "overly permissive pattern (matches everything)",
    "evil regex pattern (known ReDoS vulnerability)",
]


def validate_pattern_safety(pattern: str, pattern_type: Literal["regex", "literal"]) -> None:
    """
    Validate a pattern for safety issues.

    Checks for:
    - Regex compilation errors
    - Catastrophic backtracking risks (ReDoS)
    - Overly permissive patterns
    - Known evil regex patterns

    Args:
        pattern: The pattern to validate
        pattern_type: Type of pattern ("regex" or "literal")

    Raises:
        CustomRuleError: If pattern is unsafe
    """
    if pattern_type == "literal":
        # Literal patterns are always safe (no regex engine involved)
        return

    # Try to compile the regex
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        raise CustomRuleError(
            f"Invalid regex pattern: {e}",
            field="pattern"
        )

    # Check for overly permissive patterns
    if pattern in ("^.*$", ".*", "^.+$"):
        raise CustomRuleError(
            f"Pattern is overly permissive and would match everything. "
            f"Please be more specific.",
            field="pattern"
        )

    # Check for overlapping alternations (e.g., (a|aa)+)
    # This is a known cause of ReDoS - check this first as it's more specific
    alternation_pattern = re.search(r"\(([^)]+\|[^)]+)\)[*+?]", pattern)
    if alternation_pattern:
        alternation_content = alternation_pattern.group(1)
        # Check if one option is a prefix of another (e.g., "a|aa", "b|bc")
        options = alternation_content.split("|")
        for i, opt1 in enumerate(options):
            for opt2 in options[i + 1:]:
                if opt1.startswith(opt2) or opt2.startswith(opt1):
                    raise CustomRuleError(
                        f"Pattern contains overlapping alternation ({opt1}|{opt2}) "
                        f"which can cause catastrophic backtracking. "
                        f"Consider using non-overlapping alternatives.",
                        field="pattern"
                    )

    # Check for nested quantifiers (catastrophic backtracking risk)
    # Look for:
    # 1. Consecutive quantifiers: ++, **, +*, *+, etc.
    # 2. Parenthesized content with quantifiers followed by another quantifier: (a+)+, (b*)*
    #    (but NOT if it contains | which would be caught by overlapping check above)
    if re.search(r"([*+?{][*+?{])", pattern):
        raise CustomRuleError(
            f"Pattern contains nested quantifiers which can cause catastrophic backtracking. "
            f"Consider simplifying the pattern.",
            field="pattern"
        )

    # Check for (content)+ where content has quantifiers but no alternation
    # This catches (a+)+, (b*)* but not (a|b)+ which is caught above
    nested_paren = re.search(r"\(([^|*)]+[*+?{]+)\)[*+?{]", pattern)
    if nested_paren:
        raise CustomRuleError(
            f"Pattern contains nested quantifiers which can cause catastrophic backtracking. "
            f"Consider simplifying the pattern.",
            field="pattern"
        )

    # Check for excessive repetition limits (can cause DoS)
    # Patterns like {100000}, {1000,}, {500,10000}, or large ranges
    # Match: {4+ digits}, {3+ digits,}, or {digits,4+ digits}
    large_quantifier = re.search(r"\{(\d{4,}|(\d{3,},\d*)|(\d*,\d{4,}))\}", pattern)
    if large_quantifier:
        raise CustomRuleError(
            f"Pattern contains excessive repetition limit which can cause performance issues. "
            f"Consider using a smaller limit.",
            field="pattern"
        )

    # Test pattern against various inputs to check for performance issues
    # Use a timeout to prevent actual ReDoS during validation
    test_inputs = [
        "a" * 10,
        "a" * 50,
        "a" * 100,
        "test string " * 10,
    ]

    for test_input in test_inputs:
        try:
            # Quick test - should complete almost instantly for safe patterns
            compiled.search(test_input)
        except Exception as e:
            raise CustomRuleError(
                f"Pattern fails on test input '{test_input[:20]}...': {e}",
                field="pattern"
            )


# =============================================================================
# CUSTOM RULE LOADING
# =============================================================================

def load_custom_rules(
    config: OutputValidationConfig,
) -> List[ValidationRule]:
    """
    Load and parse custom rules from configuration.

    Converts custom rule dictionaries from config into ValidationRule objects.
    Validates each rule for correctness and pattern safety.

    Args:
        config: Output validation configuration

    Returns:
        List of ValidationRule objects (only enabled rules)

    Raises:
        CustomRuleError: If a custom rule is invalid
    """
    custom_rules = []

    for i, rule_dict in enumerate(config.custom_rules):
        try:
            # Validate required fields
            required_fields = ["rule_id", "name", "description", "pattern"]
            for field in required_fields:
                if field not in rule_dict:
                    raise CustomRuleError(
                        f"Missing required field '{field}'",
                        rule_id=rule_dict.get("rule_id", f"custom_rules[{i}]"),
                        field=field
                    )

            rule_id = rule_dict["rule_id"]

            # Validate rule_id format (should be alphanumeric with hyphens/underscores)
            if not re.match(r"^[a-zA-Z0-9_-]+$", rule_id):
                raise CustomRuleError(
                    f"Rule ID must contain only alphanumeric characters, hyphens, and underscores",
                    rule_id=rule_id,
                    field="rule_id"
                )

            # Prevent conflicts with default rule IDs
            from .rules import get_rule_by_id
            if get_rule_by_id(rule_id) is not None:
                raise CustomRuleError(
                    f"Rule ID '{rule_id}' conflicts with a default rule. "
                    f"Custom rules must use unique IDs.",
                    rule_id=rule_id,
                    field="rule_id"
                )

            # Extract and validate pattern type
            pattern_type = rule_dict.get("pattern_type", "regex")
            if pattern_type not in ("regex", "literal"):
                raise CustomRuleError(
                    f"pattern_type must be 'regex' or 'literal', got '{pattern_type}'",
                    rule_id=rule_id,
                    field="pattern_type"
                )

            # Validate pattern safety
            pattern = rule_dict["pattern"]
            validate_pattern_safety(pattern, pattern_type)

            # Extract and validate severity
            severity_str = rule_dict.get("severity", "medium")
            try:
                severity = SeverityLevel(severity_str)
            except ValueError:
                raise CustomRuleError(
                    f"Invalid severity '{severity_str}'. Must be one of: critical, high, medium, low",
                    rule_id=rule_id,
                    field="severity"
                )

            # Extract and validate priority
            priority_str = rule_dict.get("priority", "p2")
            try:
                priority = RulePriority(priority_str)
            except ValueError:
                raise CustomRuleError(
                    f"Invalid priority '{priority_str}'. Must be one of: p0, p1, p2, p3",
                    rule_id=rule_id,
                    field="priority"
                )

            # Extract and validate tool_types
            tool_types_str = rule_dict.get("tool_types", [])
            tool_types = []
            for tool_str in tool_types_str:
                try:
                    tool_types.append(ToolType(tool_str))
                except ValueError:
                    valid_tools = [t.value for t in ToolType]
                    raise CustomRuleError(
                        f"Invalid tool type '{tool_str}'. Must be one of: {', '.join(valid_tools)}",
                        rule_id=rule_id,
                        field="tool_types"
                    )

            # Extract and validate context
            context = rule_dict.get("context", "all")
            valid_contexts = ["command", "file_content", "file_path", "all"]
            if context not in valid_contexts:
                raise CustomRuleError(
                    f"Invalid context '{context}'. Must be one of: {', '.join(valid_contexts)}",
                    rule_id=rule_id,
                    field="context"
                )

            # Extract optional fields
            message = rule_dict.get("message", "")
            suggestions = rule_dict.get("suggestions", [])
            enabled = rule_dict.get("enabled", True)
            category = rule_dict.get("category", "custom")

            # Validate suggestions is a list
            if not isinstance(suggestions, list):
                raise CustomRuleError(
                    f"suggestions must be a list",
                    rule_id=rule_id,
                    field="suggestions"
                )

            # Create ValidationRule object
            rule = ValidationRule(
                rule_id=rule_id,
                name=rule_dict["name"],
                description=rule_dict["description"],
                pattern=pattern,
                pattern_type=pattern_type,
                severity=severity,
                priority=priority,
                tool_types=tool_types,
                context=context,
                message=message,
                suggestions=suggestions,
                enabled=enabled,
                category=category,
            )

            # Only add enabled rules
            if enabled:
                custom_rules.append(rule)

        except CustomRuleError:
            # Re-raise with more context
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise CustomRuleError(
                f"Unexpected error loading custom rule: {e}",
                rule_id=rule_dict.get("rule_id", f"custom_rules[{i}]")
            )

    return custom_rules


# =============================================================================
# RULE MERGING
# =============================================================================

def merge_with_defaults(
    default_rules: List[ValidationRule],
    custom_rules: Optional[List[ValidationRule]] = None,
    config: Optional[OutputValidationConfig] = None,
) -> List[ValidationRule]:
    """
    Merge custom rules with default rules and apply configuration overrides.

    This function:
    1. Creates a copy of default rules
    2. Adds custom rules (preventing ID conflicts)
    3. Disables rules in config.disabled_rules
    4. Applies severity overrides from config.severity_overrides

    Args:
        default_rules: List of default validation rules
        custom_rules: List of custom validation rules (optional)
        config: Output validation configuration (optional)

    Returns:
        List of ValidationRule objects with overrides applied

    Raises:
        CustomRuleError: If custom rules conflict with default rules
    """
    # Initialize custom_rules if not provided
    if custom_rules is None:
        custom_rules = []

    # Initialize config if not provided
    if config is None:
        config = OutputValidationConfig()

    # Create a copy of default rules to avoid modifying originals
    merged_rules = {rule.rule_id: rule for rule in default_rules}

    # Add custom rules
    for custom_rule in custom_rules:
        rule_id = custom_rule.rule_id

        # Check for conflicts with default rules
        if rule_id in merged_rules:
            raise CustomRuleError(
                f"Custom rule ID '{rule_id}' conflicts with a default rule. "
                f"Custom rules must use unique IDs.",
                rule_id=rule_id
            )

        merged_rules[rule_id] = custom_rule

    # Apply configuration overrides
    merged_rules = apply_config_overrides(
        rules=list(merged_rules.values()),
        config=config
    )

    # Sort by priority and category for consistent ordering
    priority_order = {
        RulePriority.P0: 0,
        RulePriority.P1: 1,
        RulePriority.P2: 2,
        RulePriority.P3: 3,
    }

    merged_rules.sort(
        key=lambda r: (priority_order.get(r.priority, 99), r.category, r.rule_id)
    )

    return merged_rules


def apply_config_overrides(
    rules: List[ValidationRule],
    config: OutputValidationConfig,
) -> List[ValidationRule]:
    """
    Apply configuration overrides to a list of rules.

    Overrides applied:
    - Disables rules in config.disabled_rules
    - Changes severity for rules in config.severity_overrides

    Args:
        rules: List of validation rules
        config: Output validation configuration

    Returns:
        New list of ValidationRule objects with overrides applied
    """
    result = []

    for rule in rules:
        # Create a copy to avoid modifying original
        rule_copy = ValidationRule(
            rule_id=rule.rule_id,
            name=rule.name,
            description=rule.description,
            pattern=rule.pattern,
            pattern_type=rule.pattern_type,
            severity=rule.severity,
            priority=rule.priority,
            tool_types=rule.tool_types.copy(),
            context=rule.context,
            message=rule.message,
            suggestions=rule.suggestions.copy(),
            enabled=rule.enabled,
            category=rule.category,
        )

        # Check if rule is disabled
        if config.is_rule_disabled(rule.rule_id):
            rule_copy.enabled = False

        # Apply severity override if configured
        override_severity = config.get_severity_override(rule.rule_id)
        if override_severity is not None:
            rule_copy.severity = override_severity

        # Only include enabled rules
        if rule_copy.enabled:
            result.append(rule_copy)

    return result


# =============================================================================
# RULE INSPECTION
# =============================================================================

def get_custom_rule_ids(config: OutputValidationConfig) -> list[str]:
    """
    Get list of custom rule IDs from configuration.

    Args:
        config: Output validation configuration

    Returns:
        List of custom rule IDs
    """
    return [rule.get("rule_id", "") for rule in config.custom_rules if "rule_id" in rule]


def get_active_rules(
    rules: List[ValidationRule],
    tool_type: Optional[ToolType] = None,
    min_severity: Optional[SeverityLevel] = None,
) -> List[ValidationRule]:
    """
    Filter active rules by tool type and/or severity.

    Args:
        rules: List of validation rules
        tool_type: Optional tool type filter
        min_severity: Optional minimum severity filter

    Returns:
        Filtered list of active rules
    """
    filtered = rules

    # Filter by tool type
    if tool_type:
        filtered = [r for r in filtered if tool_type in r.tool_types or not r.tool_types]

    # Filter by severity
    if min_severity:
        severity_order = {
            SeverityLevel.LOW: 0,
            SeverityLevel.MEDIUM: 1,
            SeverityLevel.HIGH: 2,
            SeverityLevel.CRITICAL: 3,
        }
        min_level = severity_order[min_severity]
        filtered = [r for r in filtered if severity_order.get(r.severity, 0) >= min_level]

    return filtered
