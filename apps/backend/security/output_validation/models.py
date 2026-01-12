"""
Data Models for Output Validation System
=========================================

Defines the core data structures for the output validation framework that
inspects agent-generated tool calls before execution.

This module provides:
- Enums for severity levels and priorities
- ValidationRule: Pattern-based validation rule definition
- ValidationResult: Result of validation check (block/warn/allow)
- OutputValidationConfig: Per-project configuration
- OverrideToken: User bypass mechanism
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal


class SeverityLevel(str, Enum):
    """
    Severity levels for validation rules.

    Attributes:
        CRITICAL: Operation is always blocked (e.g., rm -rf /)
        HIGH: Blocked by default, override available (e.g., chmod 777)
        MEDIUM: Warning with block option (e.g., potential secret exposure)
        LOW: Informational warning only (e.g., deprecated command)
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RulePriority(str, Enum):
    """
    Priority levels for rule matching order.

    Higher priority rules are evaluated first. If a high-priority rule
    matches, lower-priority rules are skipped for that tool call.

    Attributes:
        P0: Highest priority - security-critical patterns
        P1: High priority - dangerous operations
        P2: Medium priority - suspicious patterns
        P3: Low priority - informational checks
    """

    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"


class ToolType(str, Enum):
    """
    Tool types that can be validated.

    Maps to Claude SDK tool names.
    """

    BASH = "Bash"
    WRITE = "Write"
    EDIT = "Edit"
    READ = "Read"
    WEB_FETCH = "WebFetch"
    WEB_SEARCH = "WebSearch"


@dataclass
class ValidationRule:
    """
    A validation rule that detects dangerous patterns in tool outputs.

    Attributes:
        rule_id: Unique identifier (e.g., "bash-rm-rf-root")
        name: Human-readable name
        description: What this rule detects and why
        pattern: Regex pattern to match (or literal string for exact matches)
        pattern_type: Type of pattern matching ("regex" or "literal")
        severity: Severity level for violations
        priority: Evaluation priority (P0 = highest)
        tool_types: List of tools this rule applies to
        context: Where to apply pattern ("command", "file_content", "file_path")
        message: User-facing message when rule triggers
        suggestions: List of suggested alternatives or fixes
        enabled: Whether rule is active (can be disabled in config)
        category: Rule category for organization (e.g., "filesystem", "database")
    """

    rule_id: str
    name: str
    description: str
    pattern: str
    pattern_type: Literal["regex", "literal"] = "regex"
    severity: SeverityLevel = SeverityLevel.MEDIUM
    priority: RulePriority = RulePriority.P2
    tool_types: list[ToolType] = field(default_factory=list)
    context: Literal["command", "file_content", "file_path", "all"] = "all"
    message: str = ""
    suggestions: list[str] = field(default_factory=list)
    enabled: bool = True
    category: str = "general"

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "pattern": self.pattern,
            "pattern_type": self.pattern_type,
            "severity": self.severity.value,
            "priority": self.priority.value,
            "tool_types": [t.value for t in self.tool_types],
            "context": self.context,
            "message": self.message,
            "suggestions": self.suggestions,
            "enabled": self.enabled,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationRule":
        """Load from dict."""
        # Handle tool_types conversion
        tool_types = [
            ToolType(t) if isinstance(t, str) else t for t in data.get("tool_types", [])
        ]

        # Handle enum conversions
        severity = SeverityLevel(data.get("severity", "medium"))
        priority = RulePriority(data.get("priority", "p2"))

        return cls(
            rule_id=data["rule_id"],
            name=data["name"],
            description=data["description"],
            pattern=data["pattern"],
            pattern_type=data.get("pattern_type", "regex"),
            severity=severity,
            priority=priority,
            tool_types=tool_types,
            context=data.get("context", "all"),
            message=data.get("message", ""),
            suggestions=data.get("suggestions", []),
            enabled=data.get("enabled", True),
            category=data.get("category", "general"),
        )


@dataclass
class ValidationResult:
    """
    Result of validating a tool call against a rule.

    Attributes:
        is_blocked: Whether the operation should be blocked
        rule_id: ID of the rule that triggered (if any)
        severity: Severity level of the violation
        reason: Clear explanation of why operation was blocked/warned
        suggestions: List of suggested alternatives
        matched_pattern: The specific pattern that matched
        tool_name: Name of the tool being validated
        tool_input: The input that was validated (for logging)
        can_override: Whether an override token can bypass this block
    """

    is_blocked: bool
    rule_id: str | None = None
    severity: SeverityLevel | None = None
    reason: str = ""
    suggestions: list[str] = field(default_factory=list)
    matched_pattern: str = ""
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    can_override: bool = False

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "is_blocked": self.is_blocked,
            "rule_id": self.rule_id,
            "severity": self.severity.value if self.severity else None,
            "reason": self.reason,
            "suggestions": self.suggestions,
            "matched_pattern": self.matched_pattern,
            "tool_name": self.tool_name,
            "can_override": self.can_override,
        }

    @classmethod
    def allowed(cls) -> "ValidationResult":
        """Create a result that allows the operation."""
        return cls(is_blocked=False)

    @classmethod
    def blocked(
        cls,
        rule: ValidationRule,
        reason: str,
        matched_pattern: str = "",
        tool_name: str = "",
        tool_input: dict | None = None,
    ) -> "ValidationResult":
        """Create a result that blocks the operation."""
        return cls(
            is_blocked=True,
            rule_id=rule.rule_id,
            severity=rule.severity,
            reason=reason,
            suggestions=rule.suggestions.copy(),
            matched_pattern=matched_pattern,
            tool_name=tool_name,
            tool_input=tool_input or {},
            can_override=(rule.severity != SeverityLevel.CRITICAL),
        )


@dataclass
class OutputValidationConfig:
    """
    Configuration for output validation system.

    Loaded from .auto-claude/output-validation.json or equivalent.

    Attributes:
        enabled: Whether validation is enabled
        strict_mode: If True, all MEDIUM+ severity rules block (not just warn)
        disabled_rules: List of rule IDs to disable
        severity_overrides: Map of rule_id -> custom severity level
        allowed_paths: Paths that bypass certain validations
        custom_rules: Additional rules defined by the project
        log_all_validations: If True, log all validation checks (not just blocks)
        version: Config schema version for migration
    """

    enabled: bool = True
    strict_mode: bool = False
    disabled_rules: list[str] = field(default_factory=list)
    severity_overrides: dict[str, str] = field(default_factory=dict)
    allowed_paths: list[str] = field(default_factory=list)
    custom_rules: list[dict] = field(default_factory=list)
    log_all_validations: bool = False
    version: str = "1.0"

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "enabled": self.enabled,
            "strict_mode": self.strict_mode,
            "disabled_rules": self.disabled_rules,
            "severity_overrides": self.severity_overrides,
            "allowed_paths": self.allowed_paths,
            "custom_rules": self.custom_rules,
            "log_all_validations": self.log_all_validations,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OutputValidationConfig":
        """Load from dict."""
        return cls(
            enabled=data.get("enabled", True),
            strict_mode=data.get("strict_mode", False),
            disabled_rules=data.get("disabled_rules", []),
            severity_overrides=data.get("severity_overrides", {}),
            allowed_paths=data.get("allowed_paths", []),
            custom_rules=data.get("custom_rules", []),
            log_all_validations=data.get("log_all_validations", False),
            version=data.get("version", "1.0"),
        )

    def get_severity_override(self, rule_id: str) -> SeverityLevel | None:
        """Get custom severity for a rule, if configured."""
        if rule_id in self.severity_overrides:
            try:
                return SeverityLevel(self.severity_overrides[rule_id])
            except ValueError:
                return None
        return None

    def is_rule_disabled(self, rule_id: str) -> bool:
        """Check if a rule is disabled."""
        return rule_id in self.disabled_rules


@dataclass
class OverrideToken:
    """
    Token that allows bypassing specific validation rules.

    Generated by users to temporarily allow operations that would
    normally be blocked.

    Attributes:
        token_id: Unique token identifier (UUID)
        rule_id: ID of the rule this token overrides
        scope: Scope of override ("all", "file:/path/to/file", "command:pattern")
        created_at: Timestamp when token was created
        expires_at: Timestamp when token expires (optional)
        max_uses: Maximum number of times token can be used (0 = unlimited)
        use_count: Current usage count
        reason: User-provided reason for creating the override
        creator: Identifier for who created the token (user, process)
    """

    token_id: str
    rule_id: str
    scope: str = "all"
    created_at: str = ""
    expires_at: str = ""
    max_uses: int = 1
    use_count: int = 0
    reason: str = ""
    creator: str = "user"

    def __post_init__(self):
        """Set created_at if not provided."""
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "token_id": self.token_id,
            "rule_id": self.rule_id,
            "scope": self.scope,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "max_uses": self.max_uses,
            "use_count": self.use_count,
            "reason": self.reason,
            "creator": self.creator,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OverrideToken":
        """Load from dict."""
        return cls(
            token_id=data["token_id"],
            rule_id=data["rule_id"],
            scope=data.get("scope", "all"),
            created_at=data.get("created_at", ""),
            expires_at=data.get("expires_at", ""),
            max_uses=data.get("max_uses", 1),
            use_count=data.get("use_count", 0),
            reason=data.get("reason", ""),
            creator=data.get("creator", "user"),
        )

    def is_valid(self) -> bool:
        """Check if token is still valid (not expired or used up)."""
        # Check usage count
        if self.max_uses > 0 and self.use_count >= self.max_uses:
            return False

        # Check expiry
        if self.expires_at:
            try:
                expires = datetime.fromisoformat(self.expires_at)
                if datetime.now(timezone.utc) > expires:
                    return False
            except ValueError:
                # Invalid expiry format - treat as expired
                return False

        return True

    def applies_to(self, context: str) -> bool:
        """Check if token applies to a given context."""
        if self.scope == "all":
            return True

        # Check scope prefix matching
        if context.startswith(self.scope):
            return True

        return False

    def use_token(self) -> bool:
        """Increment usage count. Returns False if token is exhausted."""
        if not self.is_valid():
            return False

        self.use_count += 1
        return True


@dataclass
class ValidationEvent:
    """
    Log entry for a validation event.

    Attributes:
        timestamp: When the validation occurred
        tool_name: Tool being validated
        rule_id: Rule that triggered (if any)
        decision: "allowed", "blocked", or "warning"
        severity: Severity level of the rule
        reason: Explanation of the decision
        was_overridden: Whether an override token was used
        override_token_id: ID of override token used (if any)
        tool_input_summary: Summary of the tool input (sanitized)
    """

    timestamp: str = ""
    tool_name: str = ""
    rule_id: str | None = None
    decision: Literal["allowed", "blocked", "warning"] = "allowed"
    severity: SeverityLevel | None = None
    reason: str = ""
    was_overridden: bool = False
    override_token_id: str = ""
    tool_input_summary: dict = field(default_factory=dict)

    def __post_init__(self):
        """Set timestamp if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "timestamp": self.timestamp,
            "tool_name": self.tool_name,
            "rule_id": self.rule_id,
            "decision": self.decision,
            "severity": self.severity.value if self.severity else None,
            "reason": self.reason,
            "was_overridden": self.was_overridden,
            "override_token_id": self.override_token_id,
            "tool_input_summary": self.tool_input_summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationEvent":
        """Load from dict."""
        severity = None
        if data.get("severity"):
            try:
                severity = SeverityLevel(data["severity"])
            except ValueError:
                pass

        return cls(
            timestamp=data.get("timestamp", ""),
            tool_name=data["tool_name"],
            rule_id=data.get("rule_id"),
            decision=data.get("decision", "allowed"),
            severity=severity,
            reason=data.get("reason", ""),
            was_overridden=data.get("was_overridden", False),
            override_token_id=data.get("override_token_id", ""),
            tool_input_summary=data.get("tool_input_summary", {}),
        )
