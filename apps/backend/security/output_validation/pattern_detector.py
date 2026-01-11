"""
Pattern Detection Engine
========================

Core pattern matching engine that detects dangerous operations in tool outputs.
Supports regex patterns, literal matches, and context-aware detection.

This module provides:
- PatternDetector: Main pattern matching class
- Context-aware matching (command, file_content, file_path)
- Support for regex and literal patterns
- Pattern priority handling
"""

import re
from typing import Any

from .models import RulePriority, SeverityLevel, ToolType, ValidationResult, ValidationRule


class PatternDetector:
    """
    Pattern matching engine for detecting dangerous operations.

    The PatternDetector is responsible for matching tool outputs against
    validation rules and determining if they should be blocked.

    Features:
    - Regex and literal pattern matching
    - Context-aware detection (command, file_content, file_path)
    - Priority-based rule evaluation
    - Efficient matching with early exit on high-priority hits

    Example:
        detector = PatternDetector()

        # Add rules
        detector.add_rule(dangerous_rm_rule)
        detector.add_rule(chmod_rule)

        # Check a command
        result = detector.match(
            tool_type=ToolType.BASH,
            content="rm -rf /important/data",
            context="command"
        )

        if result.is_blocked:
            print(f"Blocked: {result.reason}")
    """

    def __init__(self) -> None:
        """Initialize the pattern detector with empty rule sets."""
        # Rules organized by priority for efficient matching
        self._rules_by_priority: dict[RulePriority, list[ValidationRule]] = {
            RulePriority.P0: [],
            RulePriority.P1: [],
            RulePriority.P2: [],
            RulePriority.P3: [],
        }

        # Rules organized by tool type for quick filtering
        self._rules_by_tool: dict[ToolType, list[ValidationRule]] = {
            ToolType.BASH: [],
            ToolType.WRITE: [],
            ToolType.EDIT: [],
            ToolType.READ: [],
            ToolType.WEB_FETCH: [],
            ToolType.WEB_SEARCH: [],
        }

        # All rules for iteration
        self._all_rules: list[ValidationRule] = []

        # Compiled regex cache for performance
        self._compiled_patterns: dict[str, re.Pattern[str]] = {}

    def add_rule(self, rule: ValidationRule) -> None:
        """
        Add a validation rule to the detector.

        The rule is indexed by priority and tool type for efficient matching.

        Args:
            rule: ValidationRule to add
        """
        # Add to priority-indexed dict
        self._rules_by_priority[rule.priority].append(rule)

        # Add to tool-type-indexed dict
        for tool_type in rule.tool_types:
            self._rules_by_tool[tool_type].append(rule)

        # Add to all rules list
        self._all_rules.append(rule)

        # Compile regex pattern if needed
        if rule.pattern_type == "regex":
            try:
                self._compiled_patterns[rule.rule_id] = re.compile(rule.pattern)
            except re.error as e:
                # Invalid regex - log and disable the rule
                print(f"Warning: Invalid regex pattern for rule {rule.rule_id}: {e}")
                rule.enabled = False

    def add_rules(self, rules: list[ValidationRule]) -> None:
        """
        Add multiple validation rules at once.

        Args:
            rules: List of ValidationRule objects to add
        """
        for rule in rules:
            self.add_rule(rule)

    def match(
        self,
        tool_type: ToolType,
        content: str,
        context: str,
        tool_input: dict[str, Any] | None = None,
        config: Any | None = None,
    ) -> ValidationResult:
        """
        Match content against all applicable validation rules.

        Rules are evaluated in priority order (P0 → P1 → P2 → P3).
        If a high-priority rule matches and blocks, lower-priority rules
        are not evaluated.

        Args:
            tool_type: Type of tool being validated (Bash, Write, Edit, etc.)
            content: The content to validate (command, file content, file path, etc.)
            context: Context of validation ("command", "file_content", "file_path", "all")
            tool_input: Optional tool input data (for logging)
            config: Optional OutputValidationConfig for rule overrides

        Returns:
            ValidationResult indicating if operation should be blocked
        """
        # Get rules applicable to this tool type
        applicable_rules = self._rules_by_tool.get(tool_type, [])

        # If no rules apply, allow immediately
        if not applicable_rules:
            return ValidationResult.allowed()

        # Sort by priority (P0 first, P3 last)
        sorted_rules = sorted(
            applicable_rules,
            key=lambda r: (
                list(RulePriority).index(r.priority),
                r.rule_id,
            )
        )

        # Check each rule in priority order
        for rule in sorted_rules:
            # Skip disabled rules
            if not rule.enabled:
                continue

            # Check if rule is disabled in config
            if config and config.is_rule_disabled(rule.rule_id):
                continue

            # Check context filter
            if rule.context != "all" and rule.context != context:
                continue

            # Attempt to match the pattern
            match_result = self._match_pattern(rule, content)

            if match_result.is_match:
                # Pattern matched - create block result

                # Apply severity override if configured
                severity = rule.severity
                if config:
                    override = config.get_severity_override(rule.rule_id)
                    if override:
                        severity = override

                # Check if should block based on severity
                should_block = self._should_block_by_severity(severity, config)

                if should_block:
                    return ValidationResult.blocked(
                        rule=rule,
                        reason=rule.message or rule.description,
                        matched_pattern=match_result.matched_text,
                        tool_name=tool_type.value,
                        tool_input=tool_input or {},
                    )

        # No rules matched - allow the operation
        return ValidationResult.allowed()

    def _match_pattern(self, rule: ValidationRule, content: str) -> "PatternMatchResult":
        """
        Match a single rule's pattern against content.

        Args:
            rule: The validation rule to match
            content: The content to check

        Returns:
            PatternMatchResult with match status and details
        """
        if rule.pattern_type == "literal":
            # Literal string matching
            if rule.pattern in content:
                return PatternMatchResult(
                    is_match=True,
                    matched_text=rule.pattern,
                )
            return PatternMatchResult(is_match=False)

        elif rule.pattern_type == "regex":
            # Regex pattern matching
            compiled = self._compiled_patterns.get(rule.rule_id)

            if not compiled:
                # Pattern wasn't compiled (invalid regex)
                return PatternMatchResult(is_match=False)

            match = compiled.search(content)
            if match:
                # Extract matched text
                matched_text = match.group(0)

                # If pattern has named groups, include them in result
                groups = dict(match.groupdict()) if match.groupdict() else {}

                return PatternMatchResult(
                    is_match=True,
                    matched_text=matched_text,
                    groups=groups,
                )

            return PatternMatchResult(is_match=False)

        else:
            # Unknown pattern type - treat as no match
            return PatternMatchResult(is_match=False)

    def _should_block_by_severity(
        self,
        severity: SeverityLevel,
        config: Any | None,
    ) -> bool:
        """
        Determine if operation should be blocked based on severity.

        Args:
            severity: Severity level of the rule
            config: Optional OutputValidationConfig with strict_mode setting

        Returns:
            True if operation should be blocked, False otherwise
        """
        # CRITICAL and HIGH always block
        if severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH):
            return True

        # Check strict_mode config
        if config and getattr(config, "strict_mode", False):
            # In strict mode, MEDIUM+ blocks
            if severity == SeverityLevel.MEDIUM:
                return True

        # MEDIUM and LOW don't block by default (warning only)
        return False

    def get_rules(self, tool_type: ToolType | None = None) -> list[ValidationRule]:
        """
        Get all rules, optionally filtered by tool type.

        Args:
            tool_type: Optional tool type filter

        Returns:
            List of ValidationRule objects
        """
        if tool_type:
            return self._rules_by_tool.get(tool_type, []).copy()
        return self._all_rules.copy()

    def get_rule_by_id(self, rule_id: str) -> ValidationRule | None:
        """
        Get a specific rule by its ID.

        Args:
            rule_id: The rule ID to look up

        Returns:
            ValidationRule if found, None otherwise
        """
        for rule in self._all_rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    def clear_rules(self) -> None:
        """Clear all rules from the detector."""
        for priority in RulePriority:
            self._rules_by_priority[priority].clear()

        for tool_type in ToolType:
            self._rules_by_tool[tool_type].clear()

        self._all_rules.clear()
        self._compiled_patterns.clear()

    def remove_rule(self, rule_id: str) -> bool:
        """
        Remove a rule by ID.

        Args:
            rule_id: ID of the rule to remove

        Returns:
            True if rule was found and removed, False otherwise
        """
        # Find and remove from all rules
        rule_to_remove = None
        for rule in self._all_rules:
            if rule.rule_id == rule_id:
                rule_to_remove = rule
                break

        if not rule_to_remove:
            return False

        # Remove from all collections
        self._all_rules.remove(rule_to_remove)
        self._rules_by_priority[rule_to_remove.priority].remove(rule_to_remove)

        for tool_type in rule_to_remove.tool_types:
            if rule_to_remove in self._rules_by_tool[tool_type]:
                self._rules_by_tool[tool_type].remove(rule_to_remove)

        # Remove compiled pattern
        if rule_id in self._compiled_patterns:
            del self._compiled_patterns[rule_id]

        return True


class PatternMatchResult:
    """
    Result of matching a single pattern against content.

    Attributes:
        is_match: Whether the pattern matched
        matched_text: The specific text that matched
        groups: Named groups from regex pattern (if any)
    """

    def __init__(
        self,
        is_match: bool,
        matched_text: str = "",
        groups: dict[str, str] | None = None,
    ) -> None:
        self.is_match = is_match
        self.matched_text = matched_text
        self.groups = groups or {}


def create_pattern_detector() -> PatternDetector:
    """
    Factory function to create a PatternDetector instance.

    This is the preferred way to create a detector, as it allows
    for easier dependency injection and testing.

    Returns:
        New PatternDetector instance
    """
    return PatternDetector()
