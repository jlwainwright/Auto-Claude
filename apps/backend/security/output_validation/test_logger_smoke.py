#!/usr/bin/env python3
"""
Smoke test for Validation Event Logger
=======================================

Simple verification that the logger module works correctly without requiring pytest.
"""

import sys
import json
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Now we can import from the backend package
from security.output_validation.logger import (
    ValidationEventLogger,
    get_validation_logger,
    reset_validation_logger,
)
from security.output_validation.models import (
    OutputValidationConfig,
    SeverityLevel,
    ValidationResult,
    ValidationEvent,
)


def test_logger_initialization():
    """Test basic logger initialization."""
    print("✓ Testing logger initialization...")

    config = OutputValidationConfig(
        enabled=True,
        log_all_validations=True,
    )

    logger = ValidationEventLogger(project_dir=None, config=config)

    assert logger.config == config
    assert logger.events == []
    assert logger.log_file_path is None

    print("  ✓ Logger initialized successfully")


def test_log_blocked():
    """Test logging a blocked operation."""
    print("✓ Testing log_blocked...")

    logger = ValidationEventLogger(project_dir=None, config=None)

    result = ValidationResult(
        is_blocked=True,
        rule_id="bash-rm-rf-root",
        severity=SeverityLevel.CRITICAL,
        reason="This command would delete all files",
        tool_name="Bash",
        tool_input={"command": "rm -rf /"},
    )

    event = logger.log_blocked(
        tool_name="Bash",
        rule_id="bash-rm-rf-root",
        result=result,
    )

    assert event.tool_name == "Bash"
    assert event.rule_id == "bash-rm-rf-root"
    assert event.decision == "blocked"
    assert event.severity == SeverityLevel.CRITICAL
    assert len(logger.events) == 1

    print("  ✓ Blocked operation logged successfully")


def test_log_warning():
    """Test logging a warning."""
    print("✓ Testing log_warning...")

    logger = ValidationEventLogger(project_dir=None, config=None)

    result = ValidationResult(
        is_blocked=False,
        rule_id="bash-deprecated",
        severity=SeverityLevel.LOW,
        reason="This command is deprecated",
        tool_name="Bash",
        tool_input={"command": "ftp example.com"},
    )

    event = logger.log_warning(
        tool_name="Bash",
        rule_id="bash-deprecated",
        result=result,
    )

    assert event.tool_name == "Bash"
    assert event.decision == "warning"
    assert event.severity == SeverityLevel.LOW

    print("  ✓ Warning logged successfully")


def test_log_override():
    """Test logging override usage."""
    print("✓ Testing log_override_used...")

    logger = ValidationEventLogger(project_dir=None, config=None)

    result = ValidationResult(
        is_blocked=True,
        rule_id="bash-rm-rf-root",
        severity=SeverityLevel.CRITICAL,
        reason="This command would delete all files",
        tool_name="Bash",
    )

    event = logger.log_override_used(
        tool_name="Bash",
        rule_id="bash-rm-rf-root",
        override_token_id="token-abc-123",
        result=result,
    )

    assert event.tool_name == "Bash"
    assert event.decision == "allowed"  # Override allows the operation
    assert event.was_overridden is True
    assert event.override_token_id == "token-abc-123"

    print("  ✓ Override usage logged successfully")


def test_get_events():
    """Test getting events from logger."""
    print("✓ Testing get_events...")

    logger = ValidationEventLogger(project_dir=None, config=None)

    result = ValidationResult(
        is_blocked=True,
        rule_id="test-rule",
        severity=SeverityLevel.HIGH,
        reason="Test reason",
        tool_name="Bash",
    )

    logger.log_blocked(tool_name="Bash", rule_id="rule-1", result=result)
    logger.log_blocked(tool_name="Write", rule_id="rule-2", result=result)
    logger.log_warning(tool_name="Edit", rule_id="rule-3", result=result)

    # Get all events
    all_events = logger.get_events()
    assert len(all_events) == 3

    # Filter by decision
    blocked = logger.get_events(decision="blocked")
    assert len(blocked) == 2

    # Filter by tool
    bash_events = logger.get_events(tool_name="Bash")
    assert len(bash_events) == 1

    print("  ✓ Event filtering works correctly")


def test_get_statistics():
    """Test getting statistics."""
    print("✓ Testing get_statistics...")

    logger = ValidationEventLogger(project_dir=None, config=None)

    result = ValidationResult(
        is_blocked=True,
        rule_id="test-rule",
        severity=SeverityLevel.CRITICAL,
        reason="Test",
        tool_name="Bash",
    )

    logger.log_blocked(tool_name="Bash", rule_id="rule-1", result=result)
    logger.log_blocked(tool_name="Write", rule_id="rule-2", result=result)
    logger.log_warning(tool_name="Edit", rule_id="rule-3", result=result)

    stats = logger.get_statistics()

    assert stats["total_validations"] == 3
    assert stats["blocked"] == 2
    assert stats["warnings"] == 1
    assert stats["by_tool"] == {"Bash": 1, "Write": 1, "Edit": 1}
    assert stats["by_severity"] == {"critical": 2}

    print("  ✓ Statistics calculated correctly")


def test_sanitization():
    """Test tool input sanitization."""
    print("✓ Testing tool input sanitization...")

    logger = ValidationEventLogger(project_dir=None, config=None)

    tool_input = {
        "command": "deploy",
        "api_key": "secret-123",
        "password": "my-password",
        "normal_field": "safe data",
        "long_string": "a" * 300,
        "long_list": list(range(20)),
    }

    sanitized = logger._sanitize_tool_input(tool_input)

    # Check sensitive fields are redacted
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["normal_field"] == "safe data"

    # Check truncation
    assert len(sanitized["long_string"]) < 300
    assert "[TRUNCATED]" in sanitized["long_string"]
    assert len(sanitized["long_list"]) < 20

    print("  ✓ Tool input sanitization works correctly")


def test_global_logger():
    """Test global logger instance management."""
    print("✓ Testing global logger instance...")

    # Import the module to access _loggers
    from security.output_validation import logger as logger_module

    # Clear existing loggers
    logger_module._loggers.clear()

    config = OutputValidationConfig(enabled=True)

    logger1 = get_validation_logger(project_dir=None, config=config)
    logger2 = get_validation_logger(project_dir=None, config=config)

    # Should return same instance for same path
    assert logger1 is not logger2  # Different because project_dir is None

    # Reset
    reset_validation_logger()

    print("  ✓ Global logger management works correctly")


def test_serialization():
    """Test ValidationEvent serialization."""
    print("✓ Testing ValidationEvent serialization...")

    event = ValidationEvent(
        tool_name="Bash",
        rule_id="test-rule",
        decision="blocked",
        severity=SeverityLevel.HIGH,
        reason="Test reason",
        tool_input_summary={"command": "test"},
    )

    # Convert to dict
    event_dict = event.to_dict()

    assert event_dict["tool_name"] == "Bash"
    assert event_dict["rule_id"] == "test-rule"
    assert event_dict["decision"] == "blocked"
    assert event_dict["severity"] == "high"

    # Convert back from dict
    event2 = ValidationEvent.from_dict(event_dict)

    assert event2.tool_name == event.tool_name
    assert event2.rule_id == event.rule_id
    assert event2.decision == event.decision

    print("  ✓ Event serialization works correctly")


def main():
    """Run all smoke tests."""
    print("\n" + "="*60)
    print("Validation Event Logger - Smoke Tests")
    print("="*60 + "\n")

    try:
        test_logger_initialization()
        test_log_blocked()
        test_log_warning()
        test_log_override()
        test_get_events()
        test_get_statistics()
        test_sanitization()
        test_global_logger()
        test_serialization()

        print("\n" + "="*60)
        print("✓ All smoke tests passed!")
        print("="*60 + "\n")
        return 0

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
