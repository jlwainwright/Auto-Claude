"""
Tests for Validation Report Generator
======================================

Comprehensive pytest test suite for the validation report generation module.
"""

from pathlib import Path
from datetime import datetime, timezone

import pytest

from security.output_validation.report import (
    ValidationReportGenerator,
    generate_validation_report,
    generate_and_save_report,
    print_validation_summary,
)
from security.output_validation.logger import ValidationEventLogger
from security.output_validation.models import (
    ValidationResult,
    SeverityLevel,
    OutputValidationConfig,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def logger():
    """Create a ValidationEventLogger for testing."""
    return ValidationEventLogger(
        project_dir=Path("/test/project"),
        config=OutputValidationConfig()
    )


@pytest.fixture
def report_gen(logger):
    """Create a ValidationReportGenerator for testing."""
    return ValidationReportGenerator(
        logger=logger,
        spec_dir=Path("/test/project/.auto-claude/specs/001")
    )


@pytest.fixture
def logger_with_events(logger):
    """Create a logger with sample events."""
    # Add blocked event
    blocked_result = ValidationResult(
        is_blocked=True,
        rule_id="bash-rm-rf-root",
        severity=SeverityLevel.CRITICAL,
        reason="Attempted to remove root directory",
        tool_name="Bash",
        tool_input={"command": "rm -rf /"}
    )
    logger.log_blocked(
        tool_name="Bash",
        rule_id="bash-rm-rf-root",
        result=blocked_result
    )

    # Add warning event
    warning_result = ValidationResult(
        is_blocked=False,
        rule_id="bash-sudo",
        severity=SeverityLevel.HIGH,
        reason="Sudo command detected",
        tool_name="Bash",
        tool_input={"command": "sudo apt install"}
    )
    logger.log_warning(
        tool_name="Bash",
        rule_id="bash-sudo",
        result=warning_result
    )

    # Add override event
    logger.log_override_used(
        tool_name="Write",
        rule_id="write-system-file",
        override_token_id="token-123",
        result=ValidationResult(
            is_blocked=True,
            rule_id="write-system-file",
            severity=SeverityLevel.HIGH,
            reason="Attempted to write to system file"
        ),
        tool_input={"file_path": "/etc/config.json"}
    )

    # Add allowed event
    logger.log_allowed(
        tool_name="Read",
        tool_input={"file_path": "README.md"}
    )

    return logger


# =============================================================================
# TESTS: REPORT GENERATION
# =============================================================================

def test_report_generator_init(report_gen):
    """Test report generator initialization."""
    assert report_gen.logger is not None
    assert report_gen.spec_dir == Path("/test/project/.auto-claude/specs/001")


def test_report_generator_init_without_spec_dir(logger):
    """Test report generator initialization without spec dir."""
    report_gen = ValidationReportGenerator(logger=logger, spec_dir=None)
    assert report_gen.logger is not None
    assert report_gen.spec_dir is None


def test_generate_markdown_with_no_events(report_gen):
    """Test markdown generation with no events."""
    markdown = report_gen.generate_markdown()

    assert "# Output Validation Report" in markdown
    assert "## Summary" in markdown
    assert "| **Total Validations** | 0 |" in markdown
    assert "## Blocked Operations" not in markdown
    assert "## Warnings" not in markdown


def test_generate_markdown_with_events(logger_with_events):
    """Test markdown generation with events."""
    report_gen = ValidationReportGenerator(
        logger=logger_with_events,
        spec_dir=Path("/test/spec")
    )
    markdown = report_gen.generate_markdown()

    # Check header
    assert "# Output Validation Report" in markdown
    assert "**Project:**" in markdown
    assert "**Spec Directory:**" in markdown

    # Check summary
    assert "## Summary" in markdown
    assert "| **Total Validations** | 4 |" in markdown
    assert "| 🔴 **Blocked** | 1 |" in markdown
    assert "| ⚠️  **Warnings** | 1 |" in markdown
    assert "| ✅ **Allowed** | 1 |" in markdown
    assert "| 🔑 **Overrides Used** | 1 |" in markdown

    # Check blocked section
    assert "## Blocked Operations" in markdown
    assert "### bash-rm-rf-root" in markdown
    assert "🔴 **Severity:** critical" in markdown
    assert "Attempted to remove root directory" in markdown

    # Check warnings section
    assert "## Warnings" in markdown
    assert "### bash-sudo" in markdown
    assert "🟠 **Severity:** high" in markdown

    # Check overrides section
    assert "## Override Tokens Used" in markdown
    assert "`token-123`" in markdown
    assert "write-system-file" in markdown


def test_generate_header(report_gen):
    """Test header generation."""
    header = report_gen._generate_header()

    assert "# Output Validation Report" in header
    assert "**Generated:**" in header
    assert "**Project:**" in header


def test_generate_summary_section(logger_with_events):
    """Test summary section generation."""
    report_gen = ValidationReportGenerator(logger=logger_with_events)
    summary = report_gen._generate_summary_section()

    assert "## Summary" in summary
    assert "| Metric | Count |" in summary
    assert "| **Total Validations** | 4 |" in summary


def test_generate_blocked_section(logger_with_events):
    """Test blocked operations section generation."""
    report_gen = ValidationReportGenerator(logger_with_events)
    blocked = logger_with_events.get_blocked_events()
    section = report_gen._generate_blocked_section(blocked)

    assert "## Blocked Operations" in section
    assert "### bash-rm-rf-root" in section
    assert "🔴 **Severity:** critical" in section
    assert "**Reason:**" in section
    assert "**Occurrences:** 1" in section
    assert "**Examples:**" in section


def test_generate_blocked_section_multiple_same_rule(logger):
    """Test blocked section with multiple violations of same rule."""
    # Add multiple blocked events for same rule
    for i in range(5):
        result = ValidationResult(
            is_blocked=True,
            rule_id="bash-rm-rf",
            severity=SeverityLevel.HIGH,
            reason=f"Dangerous rm command {i}",
            tool_name="Bash",
            tool_input={"command": f"rm -rf /dir{i}"}
        )
        logger.log_blocked(
            tool_name="Bash",
            rule_id="bash-rm-rf",
            result=result
        )

    report_gen = ValidationReportGenerator(logger)
    blocked = logger.get_blocked_events()
    section = report_gen._generate_blocked_section(blocked)

    assert "## Blocked Operations" in section
    assert "### bash-rm-rf" in section
    assert "**Occurrences:** 5" in section
    assert "**Examples:**" in section
    # Should show max 3 examples
    assert "4. **Bash**" not in section
    assert "*... and 2 more*" in section


def test_generate_warning_section(logger_with_events):
    """Test warnings section generation."""
    report_gen = ValidationReportGenerator(logger_with_events)
    warnings = logger_with_events.get_warning_events()
    section = report_gen._generate_warning_section(warnings)

    assert "## Warnings" in section
    assert "### bash-sudo" in section
    assert "🟠 **Severity:** high" in section
    assert "**Reason:**" in section
    assert "**Occurrences:** 1" in section


def test_generate_override_section(logger_with_events):
    """Test override section generation."""
    report_gen = ValidationReportGenerator(logger_with_events)
    overrides = logger_with_events.get_override_events()
    section = report_gen._generate_override_section(overrides)

    assert "## Override Tokens Used" in section
    assert "`token-123`" in markdown_escape(section)
    assert "**Rule:** write-system-file" in section
    assert "**Tool:** Write" in section


def test_generate_tool_statistics(logger_with_events):
    """Test tool statistics section generation."""
    report_gen = ValidationReportGenerator(logger_with_events)
    section = report_gen._generate_tool_statistics()

    assert "## Statistics by Tool" in section
    assert "| Tool | Validations |" in section
    assert "| Bash |" in section
    assert "| Write |" in section
    assert "| Read |" in section


def test_generate_severity_breakdown(logger_with_events):
    """Test severity breakdown section generation."""
    report_gen = ValidationReportGenerator(logger_with_events)
    section = report_gen._generate_severity_breakdown()

    assert "## Blocked Operations by Severity" in section
    assert "| Severity | Count |" in section
    assert "🔴 CRITICAL" in section


def test_generate_footer(report_gen):
    """Test footer generation."""
    footer = report_gen._generate_footer()

    assert "---" in footer
    assert "*This report was generated by" in footer
    assert "Auto Claude Output Validation System" in footer


def test_severity_icon(report_gen):
    """Test severity icon mapping."""
    assert report_gen._severity_icon(SeverityLevel.CRITICAL) == "🔴"
    assert report_gen._severity_icon(SeverityLevel.HIGH) == "🟠"
    assert report_gen._severity_icon(SeverityLevel.MEDIUM) == "🟡"
    assert report_gen._severity_icon(SeverityLevel.LOW) == "🔵"
    assert report_gen._severity_icon(None) == "⚪"


def test_severity_icon_text(report_gen):
    """Test severity icon text mapping."""
    assert report_gen._severity_icon_text("critical") == "🔴"
    assert report_gen._severity_icon_text("high") == "🟠"
    assert report_gen._severity_icon_text("medium") == "🟡"
    assert report_gen._severity_icon_text("low") == "🔵"
    assert report_gen._severity_icon_text("unknown") == "⚪"


def test_format_tool_input_empty(report_gen):
    """Test formatting empty tool input."""
    formatted = report_gen._format_tool_input({})
    assert formatted == "*No details available*"


def test_format_tool_input_command(report_gen):
    """Test formatting tool input with command."""
    formatted = report_gen._format_tool_input({"command": "rm -rf /"})
    assert "`rm -rf /`" in formatted


def test_format_tool_input_long_command(report_gen):
    """Test formatting tool input with long command (truncation)."""
    long_cmd = "a" * 200
    formatted = report_gen._format_tool_input({"command": long_cmd})
    assert "..." in formatted
    assert len(formatted) < 300


def test_format_tool_input_file_path(report_gen):
    """Test formatting tool input with file path."""
    formatted = report_gen._format_tool_input({"file_path": "/etc/config.json"})
    assert "File: `/etc/config.json`" in formatted


def test_format_tool_input_multiple_fields(report_gen):
    """Test formatting tool input with multiple fields."""
    formatted = report_gen._format_tool_input({
        "command": "ls -la",
        "file_path": "/home/user",
        "tool_name": "Bash"
    })
    assert "`ls -la`" in formatted
    assert "File: `/home/user`" in formatted
    assert "Tool: Bash" in formatted


# =============================================================================
# TESTS: SAVE FUNCTIONALITY
# =============================================================================

def test_save_to_file_with_path(tmp_path, logger_with_events):
    """Test saving report to specific path."""
    report_gen = ValidationReportGenerator(
        logger=logger_with_events,
        spec_dir=Path("/test/spec")
    )
    report_path = tmp_path / "custom-report.md"

    result_path = report_gen.save_to_file(report_path)

    assert result_path == report_path
    assert report_path.exists()
    content = report_path.read_text()
    assert "# Output Validation Report" in content


def test_save_to_file_without_path(tmp_path, logger_with_events):
    """Test saving report to default path (spec_dir)."""
    spec_dir = tmp_path / "specs" / "001"
    spec_dir.mkdir(parents=True)

    report_gen = ValidationReportGenerator(
        logger=logger_with_events,
        spec_dir=spec_dir
    )

    result_path = report_gen.save_to_file()

    expected_path = spec_dir / "validation-report.md"
    assert result_path == expected_path
    assert expected_path.exists()


def test_save_to_file_no_path_available(logger):
    """Test save to file when no path is available."""
    report_gen = ValidationReportGenerator(logger=logger, spec_dir=None)

    with pytest.raises(ValueError, match="No path available"):
        report_gen.save_to_file()


# =============================================================================
# TESTS: PRINT SUMMARY
# =============================================================================

def test_print_summary(capsys, logger_with_events):
    """Test printing summary to console."""
    report_gen = ValidationReportGenerator(logger=logger_with_events)
    report_gen.print_summary()

    captured = capsys.readouterr()
    output = captured.out

    assert "OUTPUT VALIDATION SUMMARY" in output
    assert "Total Validations: 4" in output
    assert "Blocked: 1" in output
    assert "Warnings: 1" in output
    assert "Allowed: 1" in output
    assert "Overrides Used: 1" in output


# =============================================================================
# TESTS: CONVENIENCE FUNCTIONS
# =============================================================================

def test_generate_validation_report():
    """Test convenience function to create report generator."""
    report_gen = generate_validation_report(
        project_dir=Path("/test/project"),
        spec_dir=Path("/test/spec")
    )

    assert isinstance(report_gen, ValidationReportGenerator)
    assert report_gen.logger is not None
    assert report_gen.spec_dir == Path("/test/spec")


def test_generate_and_save_report(tmp_path):
    """Test convenience function to generate and save report."""
    logger = ValidationEventLogger(project_dir=Path("/test"))

    # Add some events
    logger.log_blocked(
        tool_name="Bash",
        rule_id="test-rule",
        result=ValidationResult(
            is_blocked=True,
            rule_id="test-rule",
            severity=SeverityLevel.HIGH,
            reason="Test block"
        )
    )

    # Generate report using convenience function
    spec_dir = tmp_path / "specs" / "001"
    spec_dir.mkdir(parents=True)

    report_path = generate_and_save_report(
        project_dir=Path("/test/project"),
        spec_dir=spec_dir
    )

    expected_path = spec_dir / "validation-report.md"
    assert report_path == expected_path
    assert expected_path.exists()


def test_generate_and_save_report_custom_path(tmp_path):
    """Test generating and saving report to custom path."""
    logger = ValidationEventLogger(project_dir=Path("/test"))
    logger.log_blocked(
        tool_name="Bash",
        rule_id="test",
        result=ValidationResult(is_blocked=True, rule_id="test")
    )

    custom_path = tmp_path / "custom" / "report.md"
    report_path = generate_and_save_report(
        project_dir=Path("/test"),
        report_path=custom_path
    )

    assert report_path == custom_path
    assert custom_path.exists()


def test_print_validation_summary(capsys):
    """Test convenience function to print summary."""
    logger = ValidationEventLogger(project_dir=Path("/test"))
    logger.log_blocked(
        tool_name="Bash",
        rule_id="test",
        result=ValidationResult(is_blocked=True, rule_id="test")
    )

    print_validation_summary(Path("/test"))

    captured = capsys.readouterr()
    assert "OUTPUT VALIDATION SUMMARY" in captured.out


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def markdown_escape(text: str) -> str:
    """Helper to escape backticks for comparison."""
    return text.replace("`", "\\`")
