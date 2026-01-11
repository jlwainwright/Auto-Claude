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
]
