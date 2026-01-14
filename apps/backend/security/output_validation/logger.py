"""
Validation Event Logger
=======================

Structured logging for all validation events in the output validation system.
Provides comprehensive audit trail of blocked operations, warnings, and override usage.

This module provides:
- ValidationEventLogger: Main logger class for validation events
- Structured JSON logging with full context
- In-memory event storage for session analysis
- Optional file-based persistence
- Integration with Python's logging module

Usage:
    from security.output_validation.logger import (
        ValidationEventLogger,
        get_validation_logger,
        log_blocked_operation,
        log_warning,
        log_override_used,
    )

    # Log a blocked operation
    log_blocked_operation(
        tool_name="Bash",
        rule_id="bash-rm-rf-root",
        result=validation_result,
        project_dir=Path("/project")
    )

    # Log override usage
    log_override_used(
        tool_name="Write",
        rule_id="write-system-file",
        override_token_id="abc123",
        project_dir=Path("/project")
    )

    # Get all events for the session
    logger = get_validation_logger(Path("/project"))
    events = logger.get_events()
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .models import (
    OutputValidationConfig,
    SeverityLevel,
    ToolType,
    ValidationEvent,
    ValidationResult,
)


# =============================================================================
# LOGGER
# =============================================================================

module_logger = logging.getLogger(__name__)


# =============================================================================
# VALIDATION EVENT LOGGER
# =============================================================================

class ValidationEventLogger:
    """
    Structured logger for validation events.

    Provides comprehensive logging of all validation events including:
    - Blocked operations (with full context)
    - Warnings for suspicious but allowed operations
    - Override token usage
    - Allowed operations (when log_all_validations is enabled)

    Events are stored in memory and optionally written to a JSON log file
    for audit trails and debugging.

    Attributes:
        project_dir: Project directory path
        config: Validation configuration (controls logging behavior)
        events: List of validation events in memory
        log_file_path: Optional path to JSON log file

    Example:
        >>> logger = ValidationEventLogger(
        ...     project_dir=Path("/my/project"),
        ...     config=config
        ... )
        >>> logger.log_blocked(
        ...     tool_name="Bash",
        ...     rule_id="bash-rm-rf-root",
        ...     result=validation_result
        ... )
        >>> events = logger.get_events()
        >>> logger.save_to_file()
    """

    def __init__(
        self,
        project_dir: Path | None = None,
        config: OutputValidationConfig | None = None,
    ):
        """
        Initialize the validation event logger.

        Args:
            project_dir: Optional project directory path
            config: Optional validation configuration
        """
        self.project_dir = project_dir
        self.config = config or OutputValidationConfig()
        self.events: list[ValidationEvent] = []

        # Set up log file path if project_dir is provided
        self.log_file_path: Path | None = None
        if project_dir:
            log_dir = project_dir / ".auto-claude" / "validation-logs"
            self.log_file_path = log_dir / f"validation-{self._session_id()}.json"

    def _session_id(self) -> str:
        """
        Generate a unique session ID for this logging session.

        Returns:
            Session ID string (timestamp-based)
        """
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    def log_blocked(
        self,
        tool_name: str,
        rule_id: str,
        result: ValidationResult,
        tool_input: dict[str, Any] | None = None,
    ) -> ValidationEvent:
        """
        Log a blocked operation.

        Args:
            tool_name: Name of the tool being validated
            rule_id: ID of the rule that triggered the block
            result: ValidationResult with block details
            tool_input: Optional tool input data for context

        Returns:
            ValidationEvent that was logged
        """
        event = ValidationEvent(
            tool_name=tool_name,
            rule_id=rule_id,
            decision="blocked",
            severity=result.severity,
            reason=result.reason,
            tool_input_summary=self._sanitize_tool_input(tool_input or result.tool_input),
        )

        self._add_event(event)

        # Log to Python logging
        module_logger.warning(
            f"Blocked {tool_name} operation: {rule_id} - {result.reason}"
        )

        return event

    def log_warning(
        self,
        tool_name: str,
        rule_id: str,
        result: ValidationResult,
        tool_input: dict[str, Any] | None = None,
    ) -> ValidationEvent:
        """
        Log a warning for suspicious but allowed operation.

        Args:
            tool_name: Name of the tool being validated
            rule_id: ID of the rule that triggered the warning
            result: ValidationResult with warning details
            tool_input: Optional tool input data for context

        Returns:
            ValidationEvent that was logged
        """
        event = ValidationEvent(
            tool_name=tool_name,
            rule_id=rule_id,
            decision="warning",
            severity=result.severity,
            reason=result.reason,
            tool_input_summary=self._sanitize_tool_input(tool_input or result.tool_input),
        )

        self._add_event(event)

        # Log to Python logging
        module_logger.info(
            f"Warning for {tool_name} operation: {rule_id} - {result.reason}"
        )

        return event

    def log_allowed(
        self,
        tool_name: str,
        tool_input: dict[str, Any] | None = None,
    ) -> ValidationEvent | None:
        """
        Log an allowed operation (only if log_all_validations is enabled).

        Args:
            tool_name: Name of the tool being validated
            tool_input: Optional tool input data for context

        Returns:
            ValidationEvent if logged, None if logging disabled
        """
        if not self.config.log_all_validations:
            return None

        event = ValidationEvent(
            tool_name=tool_name,
            rule_id=None,
            decision="allowed",
            severity=None,
            reason="Operation passed validation",
            tool_input_summary=self._sanitize_tool_input(tool_input or {}),
        )

        self._add_event(event)

        # Log to Python logging (debug level)
        module_logger.debug(f"Allowed {tool_name} operation")

        return event

    def log_override_used(
        self,
        tool_name: str,
        rule_id: str,
        override_token_id: str,
        result: ValidationResult | None = None,
        tool_input: dict[str, Any] | None = None,
    ) -> ValidationEvent:
        """
        Log when an override token is used to bypass validation.

        Args:
            tool_name: Name of the tool being validated
            rule_id: ID of the rule being overridden
            override_token_id: ID of the override token used
            result: Optional ValidationResult that was overridden
            tool_input: Optional tool input data for context

        Returns:
            ValidationEvent that was logged
        """
        reason = f"Override token used: {override_token_id}"
        if result and result.reason:
            reason += f" (original: {result.reason})"

        event = ValidationEvent(
            tool_name=tool_name,
            rule_id=rule_id,
            decision="allowed",
            severity=result.severity if result else None,
            reason=reason,
            was_overridden=True,
            override_token_id=override_token_id,
            tool_input_summary=self._sanitize_tool_input(tool_input or {}),
        )

        self._add_event(event)

        # Log to Python logging (warning level - overrides are significant)
        module_logger.warning(
            f"Override token used for {tool_name}: rule={rule_id}, "
            f"token={override_token_id}"
        )

        return event

    def log_path_bypassed(
        self,
        tool_name: str,
        file_path: str,
        tool_input: dict[str, Any] | None = None,
    ) -> ValidationEvent:
        """
        Log when a path bypasses validation due to allowed_paths config.

        Args:
            tool_name: Name of the tool being validated
            file_path: Path that bypassed validation
            tool_input: Optional tool input data for context

        Returns:
            ValidationEvent that was logged
        """
        event = ValidationEvent(
            tool_name=tool_name,
            rule_id=None,
            decision="allowed",
            severity=None,
            reason=f"Path bypassed validation (allowed_paths): {file_path}",
            tool_input_summary=self._sanitize_tool_input(tool_input or {}),
        )

        self._add_event(event)

        # Log to Python logging (debug level)
        module_logger.debug(
            f"Path bypassed validation for {tool_name}: {file_path}"
        )

        return event

    def _add_event(self, event: ValidationEvent) -> None:
        """
        Add an event to the in-memory store.

        Args:
            event: ValidationEvent to add
        """
        self.events.append(event)

        # Optionally write to file immediately
        if self.log_file_path and self.config.log_all_validations:
            self._append_to_file(event)

    def _sanitize_tool_input(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """
        Sanitize tool input for logging (remove sensitive data).

        Args:
            tool_input: Raw tool input data

        Returns:
            Sanitized tool input dict
        """
        if not tool_input:
            return {}

        sanitized = {}

        # Define sensitive keys to redact
        sensitive_keys = {
            "api_key", "apikey", "secret", "password", "token",
            "authorization", "auth", "credential", "private_key",
        }

        for key, value in tool_input.items():
            # Check if key is sensitive
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str):
                # Truncate long strings
                if len(value) > 200:
                    sanitized[key] = value[:200] + "... [TRUNCATED]"
                else:
                    sanitized[key] = value
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_tool_input(value)
            elif isinstance(value, list):
                # Truncate long lists
                if len(value) > 10:
                    sanitized[key] = value[:10] + ["... [TRUNCATED]"]
                else:
                    sanitized[key] = value
            else:
                sanitized[key] = value

        return sanitized

    def get_events(
        self,
        decision: Literal["blocked", "warning", "allowed"] | None = None,
        tool_name: str | None = None,
        rule_id: str | None = None,
    ) -> list[ValidationEvent]:
        """
        Get events from the log, optionally filtered.

        Args:
            decision: Optional filter by decision type
            tool_name: Optional filter by tool name
            rule_id: Optional filter by rule ID

        Returns:
            List of ValidationEvent matching filters
        """
        events = self.events

        if decision:
            events = [e for e in events if e.decision == decision]

        if tool_name:
            events = [e for e in events if e.tool_name == tool_name]

        if rule_id:
            events = [e for e in events if e.rule_id == rule_id]

        return events

    def get_blocked_events(self) -> list[ValidationEvent]:
        """Get all blocked operation events."""
        return self.get_events(decision="blocked")

    def get_warning_events(self) -> list[ValidationEvent]:
        """Get all warning events."""
        return self.get_events(decision="warning")

    def get_override_events(self) -> list[ValidationEvent]:
        """Get all events where override was used."""
        return [e for e in self.events if e.was_overridden]

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about validation events.

        Returns:
            Dict with statistics:
            - total_validations: Total number of validations
            - blocked: Number of blocked operations
            - warnings: Number of warnings
            - allowed: Number of allowed operations
            - overrides_used: Number of override tokens used
            - by_tool: Dict of tool_name -> event count
            - by_severity: Dict of severity -> event count (for blocked)
        """
        blocked = self.get_blocked_events()
        warnings = self.get_warning_events()
        overrides = self.get_override_events()

        # Count by tool
        by_tool: dict[str, int] = {}
        for event in self.events:
            by_tool[event.tool_name] = by_tool.get(event.tool_name, 0) + 1

        # Count by severity (for blocked events)
        by_severity: dict[str, int] = {}
        for event in blocked:
            if event.severity:
                severity = event.severity.value
                by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            "total_validations": len(self.events),
            "blocked": len(blocked),
            "warnings": len(warnings),
            "allowed": len(self.events) - len(blocked) - len(warnings),
            "overrides_used": len(overrides),
            "by_tool": by_tool,
            "by_severity": by_severity,
        }

    def save_to_file(self, path: Path | None = None) -> Path:
        """
        Save all events to a JSON file.

        Args:
            path: Optional path to save to (defaults to log_file_path)

        Returns:
            Path to the saved file

        Raises:
            ValueError: If no path is available
        """
        file_path = path or self.log_file_path

        if not file_path:
            raise ValueError("No log file path available")

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write events to JSON
        data = {
            "session_id": self._session_id(),
            "project_dir": str(self.project_dir) if self.project_dir else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "statistics": self.get_statistics(),
            "events": [event.to_dict() for event in self.events],
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        module_logger.info(f"Validation events saved to {file_path}")

        return file_path

    def _append_to_file(self, event: ValidationEvent) -> None:
        """
        Append a single event to the log file.

        Args:
            event: ValidationEvent to append
        """
        if not self.log_file_path:
            return

        # Ensure parent directory exists
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Append event as JSON line
        with open(self.log_file_path, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    def clear(self) -> None:
        """Clear all events from memory."""
        self.events.clear()


# =============================================================================
# GLOBAL LOGGER INSTANCE
# =============================================================================

_loggers: dict[Path, ValidationEventLogger] = {}


def get_validation_logger(
    project_dir: Path | None = None,
    config: OutputValidationConfig | None = None,
) -> ValidationEventLogger:
    """
    Get or create a ValidationEventLogger for the project.

    Args:
        project_dir: Project directory path
        config: Optional validation configuration

    Returns:
        ValidationEventLogger instance
    """
    if project_dir is None:
        # Create a temporary logger without persistence
        return ValidationEventLogger(project_dir=None, config=config)

    # Normalize path for consistent key
    project_dir = project_dir.resolve()

    if project_dir not in _loggers:
        _loggers[project_dir] = ValidationEventLogger(
            project_dir=project_dir,
            config=config,
        )

    return _loggers[project_dir]


def reset_validation_logger(project_dir: Path | None = None) -> None:
    """
    Reset the validation logger for a project.

    Args:
        project_dir: Project directory path (resets all if None)
    """
    if project_dir is None:
        _loggers.clear()
    else:
        project_dir = project_dir.resolve()
        if project_dir in _loggers:
            del _loggers[project_dir]


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def log_blocked_operation(
    tool_name: str,
    rule_id: str,
    result: ValidationResult,
    project_dir: Path | None = None,
    config: OutputValidationConfig | None = None,
    tool_input: dict[str, Any] | None = None,
) -> ValidationEvent:
    """
    Convenience function to log a blocked operation.

    Args:
        tool_name: Name of the tool being validated
        rule_id: ID of the rule that triggered the block
        result: ValidationResult with block details
        project_dir: Optional project directory path
        config: Optional validation configuration
        tool_input: Optional tool input data for context

    Returns:
        ValidationEvent that was logged
    """
    logger = get_validation_logger(project_dir, config)
    return logger.log_blocked(tool_name, rule_id, result, tool_input)


def log_warning(
    tool_name: str,
    rule_id: str,
    result: ValidationResult,
    project_dir: Path | None = None,
    config: OutputValidationConfig | None = None,
    tool_input: dict[str, Any] | None = None,
) -> ValidationEvent:
    """
    Convenience function to log a warning.

    Args:
        tool_name: Name of the tool being validated
        rule_id: ID of the rule that triggered the warning
        result: ValidationResult with warning details
        project_dir: Optional project directory path
        config: Optional validation configuration
        tool_input: Optional tool input data for context

    Returns:
        ValidationEvent that was logged
    """
    logger = get_validation_logger(project_dir, config)
    return logger.log_warning(tool_name, rule_id, result, tool_input)


def log_override_used(
    tool_name: str,
    rule_id: str,
    override_token_id: str,
    project_dir: Path | None = None,
    config: OutputValidationConfig | None = None,
    result: ValidationResult | None = None,
    tool_input: dict[str, Any] | None = None,
) -> ValidationEvent:
    """
    Convenience function to log override token usage.

    Args:
        tool_name: Name of the tool being validated
        rule_id: ID of the rule being overridden
        override_token_id: ID of the override token used
        project_dir: Optional project directory path
        config: Optional validation configuration
        result: Optional ValidationResult that was overridden
        tool_input: Optional tool input data for context

    Returns:
        ValidationEvent that was logged
    """
    logger = get_validation_logger(project_dir, config)
    return logger.log_override_used(tool_name, rule_id, override_token_id, result, tool_input)


def log_path_bypassed(
    tool_name: str,
    file_path: str,
    project_dir: Path | None = None,
    config: OutputValidationConfig | None = None,
    tool_input: dict[str, Any] | None = None,
) -> ValidationEvent:
    """
    Convenience function to log path bypass via allowed_paths.

    Args:
        tool_name: Name of the tool being validated
        file_path: Path that bypassed validation
        project_dir: Optional project directory path
        config: Optional validation configuration
        tool_input: Optional tool input data for context

    Returns:
        ValidationEvent that was logged
    """
    logger = get_validation_logger(project_dir, config)
    return logger.log_path_bypassed(tool_name, file_path, tool_input)
