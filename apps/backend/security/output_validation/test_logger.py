"""
Tests for Validation Event Logger
==================================

Comprehensive test suite for the structured logging system.
Tests event logging, filtering, statistics, file persistence, and sanitization.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ..models import (
    OutputValidationConfig,
    SeverityLevel,
    ToolType,
    ValidationEvent,
    ValidationResult,
)
from ..logger import (
    ValidationEventLogger,
    get_validation_logger,
    reset_validation_logger,
    log_blocked_operation,
    log_warning,
    log_override_used,
    log_path_bypassed,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def config():
    """Create a test validation configuration."""
    return OutputValidationConfig(
        enabled=True,
        strict_mode=False,
        log_all_validations=True,
    )


@pytest.fixture
def validation_result_blocked():
    """Create a blocked ValidationResult for testing."""
    return ValidationResult(
        is_blocked=True,
        rule_id="bash-rm-rf-root",
        severity=SeverityLevel.CRITICAL,
        reason="This command would recursively delete all files",
        suggestions=["Use a more specific path"],
        matched_pattern="rm -rf /",
        tool_name="Bash",
        tool_input={"command": "rm -rf /"},
        can_override=False,
    )


@pytest.fixture
def validation_result_warning():
    """Create a warning ValidationResult for testing."""
    return ValidationResult(
        is_blocked=False,
        rule_id="bash-deprecated-cmd",
        severity=SeverityLevel.LOW,
        reason="This command is deprecated",
        suggestions=["Use the modern equivalent"],
        matched_pattern="ftp",
        tool_name="Bash",
        tool_input={"command": "ftp example.com"},
        can_override=True,
    )


@pytest.fixture
def logger(temp_project_dir, config):
    """Create a ValidationEventLogger for testing."""
    return ValidationEventLogger(
        project_dir=temp_project_dir,
        config=config,
    )


# =============================================================================
# VALIDATIONEVENTLOGGER INITIALIZATION
# =============================================================================

def test_logger_initialization(temp_project_dir, config):
    """Test logger initialization with project directory."""
    logger = ValidationEventLogger(
        project_dir=temp_project_dir,
        config=config,
    )

    assert logger.project_dir == temp_project_dir
    assert logger.config == config
    assert logger.events == []
    assert logger.log_file_path is not None
    assert logger.log_file_path.parent == temp_project_dir / ".auto-claude" / "validation-logs"


def test_logger_initialization_no_project():
    """Test logger initialization without project directory."""
    logger = ValidationEventLogger(project_dir=None, config=None)

    assert logger.project_dir is None
    assert logger.config is not None
    assert logger.events == []
    assert logger.log_file_path is None


def test_session_id_generation(logger):
    """Test that session IDs are generated correctly."""
    session_id = logger._session_id()

    # Should be in format YYYYMMDD-HHMMSS
    assert len(session_id) == 17
    assert "-" in session_id


# =============================================================================
# LOGGING BLOCKED OPERATIONS
# =============================================================================

def test_log_blocked_operation(logger, validation_result_blocked):
    """Test logging a blocked operation."""
    event = logger.log_blocked(
        tool_name="Bash",
        rule_id="bash-rm-rf-root",
        result=validation_result_blocked,
    )

    # Check event properties
    assert event.tool_name == "Bash"
    assert event.rule_id == "bash-rm-rf-root"
    assert event.decision == "blocked"
    assert event.severity == SeverityLevel.CRITICAL
    assert "recursively delete" in event.reason
    assert event.was_overridden is False

    # Check event is in memory
    assert len(logger.events) == 1
    assert logger.events[0] == event


def test_log_blocked_with_tool_input(logger, validation_result_blocked):
    """Test logging blocked operation with tool input."""
    tool_input = {"command": "rm -rf /important/data"}

    event = logger.log_blocked(
        tool_name="Bash",
        rule_id="bash-rm-rf-root",
        result=validation_result_blocked,
        tool_input=tool_input,
    )

    assert event.tool_input_summary == tool_input


def test_log_blocked_sanitizes_sensitive_data(logger, validation_result_blocked):
    """Test that sensitive data in tool input is sanitized."""
    tool_input = {
        "command": "deploy",
        "api_key": "secret-key-123",
        "password": "my-password",
        "normal_field": "safe data",
    }

    event = logger.log_blocked(
        tool_name="Bash",
        rule_id="test-rule",
        result=validation_result_blocked,
        tool_input=tool_input,
    )

    # Sensitive fields should be redacted
    assert event.tool_input_summary["api_key"] == "[REDACTED]"
    assert event.tool_input_summary["password"] == "[REDACTED]"
    assert event.tool_input_summary["normal_field"] == "safe data"


# =============================================================================
# LOGGING WARNINGS
# =============================================================================

def test_log_warning(logger, validation_result_warning):
    """Test logging a warning."""
    event = logger.log_warning(
        tool_name="Bash",
        rule_id="bash-deprecated-cmd",
        result=validation_result_warning,
    )

    # Check event properties
    assert event.tool_name == "Bash"
    assert event.rule_id == "bash-deprecated-cmd"
    assert event.decision == "warning"
    assert event.severity == SeverityLevel.LOW
    assert "deprecated" in event.reason

    # Check event is in memory
    assert len(logger.events) == 1
    assert logger.events[0] == event


# =============================================================================
# LOGGING ALLOWED OPERATIONS
# =============================================================================

def test_log_allowed_when_enabled(logger):
    """Test logging allowed operations when log_all_validations is enabled."""
    event = logger.log_allowed(
        tool_name="Bash",
        tool_input={"command": "ls -la"},
    )

    assert event is not None
    assert event.tool_name == "Bash"
    assert event.decision == "allowed"
    assert event.rule_id is None
    assert event.severity is None


def test_log_allowed_when_disabled(temp_project_dir):
    """Test that allowed operations are not logged when disabled."""
    config = OutputValidationConfig(log_all_validations=False)
    logger = ValidationEventLogger(
        project_dir=temp_project_dir,
        config=config,
    )

    event = logger.log_allowed(
        tool_name="Bash",
        tool_input={"command": "ls -la"},
    )

    assert event is None
    assert len(logger.events) == 0


# =============================================================================
# LOGGING OVERRIDE USAGE
# =============================================================================

def test_log_override_used(logger, validation_result_blocked):
    """Test logging override token usage."""
    event = logger.log_override_used(
        tool_name="Bash",
        rule_id="bash-rm-rf-root",
        override_token_id="token-abc-123",
        result=validation_result_blocked,
    )

    # Check event properties
    assert event.tool_name == "Bash"
    assert event.rule_id == "bash-rm-rf-root"
    assert event.decision == "allowed"  # Override allows the operation
    assert event.was_overridden is True
    assert event.override_token_id == "token-abc-123"
    assert "Override token used" in event.reason


def test_log_override_used_without_result(logger):
    """Test logging override usage without ValidationResult."""
    event = logger.log_override_used(
        tool_name="Write",
        rule_id="write-system-file",
        override_token_id="token-xyz-789",
    )

    assert event.tool_name == "Write"
    assert event.rule_id == "write-system-file"
    assert event.decision == "allowed"
    assert event.was_overridden is True
    assert event.override_token_id == "token-xyz-789"
    assert event.severity is None  # No result provided


# =============================================================================
# LOGGING PATH BYPASSED
# =============================================================================

def test_log_path_bypassed(logger):
    """Test logging when path bypasses validation."""
    event = logger.log_path_bypassed(
        tool_name="Write",
        file_path="tests/test_foo.py",
    )

    assert event.tool_name == "Write"
    assert event.decision == "allowed"
    assert event.rule_id is None
    assert "tests/test_foo.py" in event.reason
    assert "allowed_paths" in event.reason


# =============================================================================
# GETTING AND FILTERING EVENTS
# =============================================================================

def test_get_all_events(logger):
    """Test getting all events."""
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-1",
        result=ValidationResult(is_blocked=True, rule_id="rule-1"),
    )
    logger.log_warning(
        tool_name="Write",
        rule_id="rule-2",
        result=ValidationResult(is_blocked=False, rule_id="rule-2"),
    )
    logger.log_allowed(tool_name="Edit", tool_input={})

    events = logger.get_events()
    assert len(events) == 3


def test_get_events_filtered_by_decision(logger):
    """Test filtering events by decision type."""
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-1",
        result=ValidationResult(is_blocked=True, rule_id="rule-1"),
    )
    logger.log_warning(
        tool_name="Write",
        rule_id="rule-2",
        result=ValidationResult(is_blocked=False, rule_id="rule-2"),
    )
    logger.log_allowed(tool_name="Edit", tool_input={})

    blocked = logger.get_events(decision="blocked")
    warnings = logger.get_events(decision="warning")
    allowed = logger.get_events(decision="allowed")

    assert len(blocked) == 1
    assert blocked[0].rule_id == "rule-1"

    assert len(warnings) == 1
    assert warnings[0].rule_id == "rule-2"

    assert len(allowed) == 1


def test_get_events_filtered_by_tool(logger):
    """Test filtering events by tool name."""
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-1",
        result=ValidationResult(is_blocked=True, rule_id="rule-1"),
    )
    logger.log_blocked(
        tool_name="Write",
        rule_id="rule-2",
        result=ValidationResult(is_blocked=True, rule_id="rule-2"),
    )
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-3",
        result=ValidationResult(is_blocked=True, rule_id="rule-3"),
    )

    bash_events = logger.get_events(tool_name="Bash")
    write_events = logger.get_events(tool_name="Write")

    assert len(bash_events) == 2
    assert len(write_events) == 1


def test_get_events_filtered_by_rule(logger):
    """Test filtering events by rule ID."""
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-1",
        result=ValidationResult(is_blocked=True, rule_id="rule-1"),
    )
    logger.log_blocked(
        tool_name="Write",
        rule_id="rule-1",
        result=ValidationResult(is_blocked=True, rule_id="rule-1"),
    )
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-2",
        result=ValidationResult(is_blocked=True, rule_id="rule-2"),
    )

    rule1_events = logger.get_events(rule_id="rule-1")
    rule2_events = logger.get_events(rule_id="rule-2")

    assert len(rule1_events) == 2
    assert len(rule2_events) == 1


def test_get_blocked_events(logger):
    """Test getting only blocked events."""
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-1",
        result=ValidationResult(is_blocked=True, rule_id="rule-1"),
    )
    logger.log_warning(
        tool_name="Write",
        rule_id="rule-2",
        result=ValidationResult(is_blocked=False, rule_id="rule-2"),
    )
    logger.log_allowed(tool_name="Edit", tool_input={})

    blocked = logger.get_blocked_events()
    assert len(blocked) == 1
    assert blocked[0].decision == "blocked"


def test_get_warning_events(logger):
    """Test getting only warning events."""
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-1",
        result=ValidationResult(is_blocked=True, rule_id="rule-1"),
    )
    logger.log_warning(
        tool_name="Write",
        rule_id="rule-2",
        result=ValidationResult(is_blocked=False, rule_id="rule-2"),
    )
    logger.log_allowed(tool_name="Edit", tool_input={})

    warnings = logger.get_warning_events()
    assert len(warnings) == 1
    assert warnings[0].decision == "warning"


def test_get_override_events(logger, validation_result_blocked):
    """Test getting events where override was used."""
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-1",
        result=validation_result_blocked,
    )
    logger.log_override_used(
        tool_name="Write",
        rule_id="rule-2",
        override_token_id="token-123",
    )
    logger.log_allowed(tool_name="Edit", tool_input={})

    overrides = logger.get_override_events()
    assert len(overrides) == 1
    assert overrides[0].was_overridden is True
    assert overrides[0].override_token_id == "token-123"


# =============================================================================
# STATISTICS
# =============================================================================

def test_get_statistics(logger):
    """Test getting event statistics."""
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-1",
        result=ValidationResult(
            is_blocked=True,
            rule_id="rule-1",
            severity=SeverityLevel.CRITICAL,
        ),
    )
    logger.log_blocked(
        tool_name="Write",
        rule_id="rule-2",
        result=ValidationResult(
            is_blocked=True,
            rule_id="rule-2",
            severity=SeverityLevel.HIGH,
        ),
    )
    logger.log_warning(
        tool_name="Edit",
        rule_id="rule-3",
        result=ValidationResult(
            is_blocked=False,
            rule_id="rule-3",
            severity=SeverityLevel.LOW,
        ),
    )
    logger.log_allowed(tool_name="Bash", tool_input={})

    stats = logger.get_statistics()

    assert stats["total_validations"] == 4
    assert stats["blocked"] == 2
    assert stats["warnings"] == 1
    assert stats["allowed"] == 1
    assert stats["overrides_used"] == 0
    assert stats["by_tool"] == {"Bash": 2, "Write": 1, "Edit": 1}
    assert stats["by_severity"] == {"critical": 1, "high": 1}


def test_get_statistics_with_overrides(logger, validation_result_blocked):
    """Test statistics include override usage."""
    logger.log_override_used(
        tool_name="Bash",
        rule_id="rule-1",
        override_token_id="token-123",
        result=validation_result_blocked,
    )

    stats = logger.get_statistics()

    assert stats["overrides_used"] == 1


# =============================================================================
# FILE PERSISTENCE
# =============================================================================

def test_save_to_file(logger, validation_result_blocked):
    """Test saving events to a JSON file."""
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-1",
        result=validation_result_blocked,
    )

    file_path = logger.save_to_file()

    # Check file exists
    assert file_path.exists()
    assert file_path == logger.log_file_path

    # Check file contents
    with open(file_path) as f:
        data = json.load(f)

    assert "session_id" in data
    assert "timestamp" in data
    assert "statistics" in data
    assert "events" in data
    assert len(data["events"]) == 1
    assert data["events"][0]["tool_name"] == "Bash"
    assert data["events"][0]["decision"] == "blocked"


def test_save_to_custom_path(logger, validation_result_blocked):
    """Test saving events to a custom path."""
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-1",
        result=validation_result_blocked,
    )

    custom_path = logger.project_dir / "custom-log.json"
    file_path = logger.save_to_file(path=custom_path)

    assert file_path == custom_path
    assert custom_path.exists()


def test_save_to_file_no_path():
    """Test that saving without a path raises an error."""
    logger = ValidationEventLogger(project_dir=None, config=None)

    with pytest.raises(ValueError, match="No log file path available"):
        logger.save_to_file()


def test_clear_events(logger):
    """Test clearing events from memory."""
    logger.log_blocked(
        tool_name="Bash",
        rule_id="rule-1",
        result=ValidationResult(is_blocked=True, rule_id="rule-1"),
    )

    assert len(logger.events) == 1

    logger.clear()

    assert len(logger.events) == 0


# =============================================================================
# GLOBAL LOGGER INSTANCE
# =============================================================================

def test_get_validation_logger(temp_project_dir, config):
    """Test getting or creating a global logger instance."""
    logger1 = get_validation_logger(temp_project_dir, config)
    logger2 = get_validation_logger(temp_project_dir, config)

    # Should return the same instance
    assert logger1 is logger2


def test_get_validation_logger_no_project():
    """Test getting a logger without a project directory."""
    logger = get_validation_logger(project_dir=None, config=None)

    assert logger is not None
    assert logger.project_dir is None
    assert logger.log_file_path is None


def test_reset_validation_logger(temp_project_dir, config):
    """Test resetting a validation logger."""
    logger1 = get_validation_logger(temp_project_dir, config)
    logger1.log_blocked(
        tool_name="Bash",
        rule_id="rule-1",
        result=ValidationResult(is_blocked=True, rule_id="rule-1"),
    )

    # Reset the logger
    reset_validation_logger(temp_project_dir)

    # Get a new instance - should be fresh
    logger2 = get_validation_logger(temp_project_dir, config)
    assert logger2 is not logger1
    assert len(logger2.events) == 0


def test_reset_all_validation_loggers(temp_project_dir, config):
    """Test resetting all validation loggers."""
    project1 = temp_project_dir / "project1"
    project2 = temp_project_dir / "project2"
    project1.mkdir()
    project2.mkdir()

    logger1 = get_validation_logger(project1, config)
    logger2 = get_validation_logger(project2, config)

    # Reset all
    reset_validation_logger()

    # Should get new instances
    logger1_new = get_validation_logger(project1, config)
    logger2_new = get_validation_logger(project2, config)

    assert logger1_new is not logger1
    assert logger2_new is not logger2


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def test_log_blocked_operation_convenience(temp_project_dir, config, validation_result_blocked):
    """Test the convenience function for logging blocked operations."""
    event = log_blocked_operation(
        tool_name="Bash",
        rule_id="rule-1",
        result=validation_result_blocked,
        project_dir=temp_project_dir,
        config=config,
    )

    assert event.tool_name == "Bash"
    assert event.decision == "blocked"

    # Check it's in the global logger
    logger = get_validation_logger(temp_project_dir)
    assert len(logger.events) == 1


def test_log_warning_convenience(temp_project_dir, config, validation_result_warning):
    """Test the convenience function for logging warnings."""
    event = log_warning(
        tool_name="Bash",
        rule_id="rule-2",
        result=validation_result_warning,
        project_dir=temp_project_dir,
        config=config,
    )

    assert event.tool_name == "Bash"
    assert event.decision == "warning"


def test_log_override_used_convenience(temp_project_dir, config):
    """Test the convenience function for logging override usage."""
    event = log_override_used(
        tool_name="Write",
        rule_id="rule-3",
        override_token_id="token-123",
        project_dir=temp_project_dir,
        config=config,
    )

    assert event.tool_name == "Write"
    assert event.was_overridden is True
    assert event.override_token_id == "token-123"


def test_log_path_bypassed_convenience(temp_project_dir, config):
    """Test the convenience function for logging path bypass."""
    event = log_path_bypassed(
        tool_name="Write",
        file_path="tests/test.py",
        project_dir=temp_project_dir,
        config=config,
    )

    assert event.tool_name == "Write"
    assert "tests/test.py" in event.reason


# =============================================================================
# TOOL INPUT SANITIZATION
# =============================================================================

def test_sanitize_tool_input_redacts_secrets(logger):
    """Test that sensitive keys are redacted."""
    tool_input = {
        "api_key": "secret-123",
        "secret": "password",
        "token": "auth-token",
        "normal": "safe",
    }

    sanitized = logger._sanitize_tool_input(tool_input)

    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["secret"] == "[REDACTED]"
    assert sanitized["token"] == "[REDACTED]"
    assert sanitized["normal"] == "safe"


def test_sanitize_tool_input_truncates_long_strings(logger):
    """Test that long strings are truncated."""
    tool_input = {
        "short": "abc",
        "long": "a" * 300,
    }

    sanitized = logger._sanitize_tool_input(tool_input)

    assert sanitized["short"] == "abc"
    assert len(sanitized["long"]) == 215  # 200 + " ... [TRUNCATED]"
    assert "[TRUNCATED]" in sanitized["long"]


def test_sanitize_tool_input_truncates_long_lists(logger):
    """Test that long lists are truncated."""
    tool_input = {
        "short_list": [1, 2, 3],
        "long_list": list(range(20)),
    }

    sanitized = logger._sanitize_tool_input(tool_input)

    assert sanitized["short_list"] == [1, 2, 3]
    assert len(sanitized["long_list"]) == 11  # 10 + ["... [TRUNCATED]"]
    assert "[TRUNCATED]" in str(sanitized["long_list"][-1])


def test_sanitize_tool_input_handles_nested_dicts(logger):
    """Test that nested dicts are sanitized recursively."""
    tool_input = {
        "outer": {
            "inner_api_key": "secret",
            "inner_normal": "safe",
        }
    }

    sanitized = logger._sanitize_tool_input(tool_input)

    assert sanitized["outer"]["inner_api_key"] == "[REDACTED]"
    assert sanitized["outer"]["inner_normal"] == "safe"


# =============================================================================
# VALIDATION EVENT SERIALIZATION
# =============================================================================

def test_validation_event_to_dict(logger):
    """Test converting ValidationEvent to dict."""
    event = ValidationEvent(
        tool_name="Bash",
        rule_id="rule-1",
        decision="blocked",
        severity=SeverityLevel.CRITICAL,
        reason="Test reason",
        tool_input_summary={"command": "test"},
    )

    event_dict = event.to_dict()

    assert event_dict["tool_name"] == "Bash"
    assert event_dict["rule_id"] == "rule-1"
    assert event_dict["decision"] == "blocked"
    assert event_dict["severity"] == "critical"
    assert event_dict["reason"] == "Test reason"
    assert event_dict["tool_input_summary"] == {"command": "test"}


def test_validation_event_from_dict():
    """Test loading ValidationEvent from dict."""
    event_dict = {
        "timestamp": "2024-01-01T00:00:00Z",
        "tool_name": "Bash",
        "rule_id": "rule-1",
        "decision": "blocked",
        "severity": "critical",
        "reason": "Test reason",
        "was_overridden": False,
        "override_token_id": "",
        "tool_input_summary": {"command": "test"},
    }

    event = ValidationEvent.from_dict(event_dict)

    assert event.tool_name == "Bash"
    assert event.rule_id == "rule-1"
    assert event.decision == "blocked"
    assert event.severity == SeverityLevel.CRITICAL
    assert event.reason == "Test reason"


def test_validation_event_timestamp_auto_generated():
    """Test that timestamp is auto-generated if not provided."""
    event = ValidationEvent(
        tool_name="Bash",
        decision="allowed",
    )

    assert event.timestamp != ""
    assert "T" in event.timestamp  # ISO format
