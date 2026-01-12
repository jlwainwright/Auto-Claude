"""
Tests for User-Friendly Block Messages
=======================================

Tests for the message formatting module that creates actionable,
user-friendly block messages for validation results.
"""

import pytest

from security.output_validation.messages import (
    format_block_message,
    format_override_instruction,
    format_short_block_message,
    format_validation_summary,
    format_tool_description,
    get_documentation_url,
    get_rule_documentation_link,
)
from security.output_validation.models import (
    SeverityLevel,
    ToolType,
    ValidationResult,
    ValidationRule,
)


class TestFormatBlockMessage:
    """Tests for format_block_message function."""

    def test_basic_block_message(self):
        """Test basic block message formatting."""
        rule = ValidationRule(
            rule_id="test-rule",
            name="Test Rule",
            description="This is a test rule",
            pattern="test",
            severity=SeverityLevel.HIGH,
            tool_types=[ToolType.BASH],
        )

        result = ValidationResult.blocked(
            rule=rule,
            reason="This operation is dangerous",
            tool_name="Bash",
            tool_input={"command": "dangerous command"},
        )

        message = format_block_message(result, rule)

        assert "High-Risk Operation Blocked" in message
        assert "What was blocked:" in message
        assert "Why it was blocked:" in message
        assert "This operation is dangerous" in message
        assert "Suggestions:" not in message  # No suggestions
        assert "To override this block:" in message
        assert "github.com" in message

    def test_block_message_with_suggestions(self):
        """Test block message with suggestions."""
        rule = ValidationRule(
            rule_id="test-rule",
            name="Test Rule",
            description="This is a test rule",
            pattern="test",
            severity=SeverityLevel.HIGH,
            tool_types=[ToolType.BASH],
            suggestions=["Use safer alternative", "Review the command"],
        )

        result = ValidationResult.blocked(
            rule=rule,
            reason="This operation is dangerous",
            tool_name="Bash",
            tool_input={"command": "dangerous command"},
        )

        message = format_block_message(result, rule)

        assert "Suggestions:" in message
        assert "1. Use safer alternative" in message
        assert "2. Review the command" in message

    def test_critical_severity_message(self):
        """Test critical severity message includes warning."""
        rule = ValidationRule(
            rule_id="critical-rule",
            name="Critical Rule",
            description="Critical rule",
            pattern="critical",
            severity=SeverityLevel.CRITICAL,
            tool_types=[ToolType.BASH],
        )

        result = ValidationResult.blocked(
            rule=rule,
            reason="This is critical",
            tool_name="Bash",
            tool_input={"command": "rm -rf /"},
        )

        message = format_block_message(result, rule)

        assert "🚨 Critical Security Block" in message
        assert "⚠️ WARNING: This is a critical security rule" in message

    def test_bash_command_blocking(self):
        """Test block message for Bash command."""
        rule = ValidationRule(
            rule_id="bash-dangerous",
            name="Dangerous Command",
            description="Dangerous bash command",
            pattern=r"rm -rf",
            severity=SeverityLevel.HIGH,
            tool_types=[ToolType.BASH],
            suggestions=[
                "Review the command",
                "Use absolute paths",
                "Consider --preserve-root flag",
            ],
        )

        result = ValidationResult.blocked(
            rule=rule,
            reason="This command would delete critical files",
            matched_pattern="rm -rf /important",
            tool_name="Bash",
            tool_input={"command": "rm -rf /important/data"},
        )

        message = format_block_message(result, rule)

        assert "command execution" in message
        assert "rm -rf /important/data" in message
        assert "Matched pattern: rm -rf /important" in message
        assert "1. Review the command" in message
        assert "2. Use absolute paths" in message
        assert "3. Consider --preserve-root flag" in message

    def test_write_operation_blocking(self):
        """Test block message for Write operation."""
        rule = ValidationRule(
            rule_id="write-system-file",
            name="System File Write",
            description="Writing to system files",
            pattern=r"^/etc/",
            severity=SeverityLevel.CRITICAL,
            tool_types=[ToolType.WRITE],
        )

        result = ValidationResult.blocked(
            rule=rule,
            reason="Writing to system directories can break your OS",
            tool_name="Write",
            tool_input={"file_path": "/etc/passwd", "content": "malicious"},
        )

        message = format_block_message(result, rule)

        assert "file write" in message
        assert "/etc/passwd" in message
        assert "Writing to system directories can break your OS" in message

    def test_web_fetch_blocking(self):
        """Test block message for WebFetch operation."""
        rule = ValidationRule(
            rule_id="web-internal-ip",
            name="Internal IP Access",
            description="Accessing internal IP",
            pattern=r"192\.168\.",
            severity=SeverityLevel.MEDIUM,
            tool_types=[ToolType.WEB_FETCH],
        )

        result = ValidationResult.blocked(
            rule=rule,
            reason="This targets an internal IP address",
            tool_name="WebFetch",
            tool_input={"url": "http://192.168.1.1/admin"},
        )

        message = format_block_message(result, rule)

        assert "web request" in message
        assert "http://192.168.1.1/admin" in message
        assert "Potentially Dangerous Operation" in message

    def test_long_command_truncation(self):
        """Test that very long commands are truncated."""
        rule = ValidationRule(
            rule_id="long-cmd",
            name="Long Command",
            description="Long command",
            pattern="test",
            severity=SeverityLevel.HIGH,
            tool_types=[ToolType.BASH],
        )

        long_command = "rm -rf / " + "very-long-path" * 50  # > 200 chars
        result = ValidationResult.blocked(
            rule=rule,
            reason="Long command",
            tool_name="Bash",
            tool_input={"command": long_command},
        )

        message = format_block_message(result, rule)

        # Should truncate with ellipsis
        assert "..." in message
        # Command in message should be shorter than original
        assert len([l for l in message.split("\n") if "Command:" in l][0]) < len(
            long_command
        )

    def test_without_override_instructions(self):
        """Test message without override instructions."""
        rule = ValidationRule(
            rule_id="no-override",
            name="No Override",
            description="No override allowed",
            pattern="test",
            severity=SeverityLevel.CRITICAL,
            tool_types=[ToolType.BASH],
        )

        result = ValidationResult.blocked(
            rule=rule,
            reason="Cannot override",
            tool_name="Bash",
            tool_input={"command": "test"},
        )

        # Include override instructions
        message_with = format_block_message(result, rule, include_override=True)
        assert "To override this block:" in message_with

        # Exclude override instructions
        message_without = format_block_message(result, rule, include_override=False)
        assert "To override this block:" not in message_without

    def test_critical_no_override(self):
        """Test that critical blocks show override warning."""
        rule = ValidationRule(
            rule_id="critical-no-override",
            name="Critical",
            description="Critical",
            pattern="test",
            severity=SeverityLevel.CRITICAL,
            tool_types=[ToolType.BASH],
        )

        result = ValidationResult.blocked(
            rule=rule,
            reason="Critical operation",
            tool_name="Bash",
            tool_input={"command": "test"},
        )

        message = format_block_message(result, rule)

        # Should show override warning even for critical
        assert "To override this block:" in message
        assert "⚠️ WARNING: This is a critical security rule" in message


class TestFormatOverrideInstruction:
    """Tests for format_override_instruction function."""

    def test_basic_override_instruction(self):
        """Test basic override instruction formatting."""
        instruction = format_override_instruction("test-rule")

        assert "create an override token:" in instruction
        assert "auto-claude override create --rule test-rule" in instruction
        assert "⚠️ WARNING" not in instruction

    def test_critical_override_instruction(self):
        """Test override instruction for critical rule."""
        instruction = format_override_instruction(
            "critical-rule", severity=SeverityLevel.CRITICAL
        )

        assert "auto-claude override create --rule critical-rule" in instruction
        assert "⚠️ WARNING: This is a critical security rule" in instruction
        assert "fully understand the risks" in instruction

    def test_medium_severity_override(self):
        """Test override instruction for medium severity."""
        instruction = format_override_instruction(
            "medium-rule", severity=SeverityLevel.MEDIUM
        )

        assert "auto-claude override create --rule medium-rule" in instruction
        assert "⚠️ WARNING" not in instruction


class TestFormatToolDescription:
    """Tests for format_tool_description function."""

    def test_bash_tool_description(self):
        """Test Bash tool description."""
        desc = format_tool_description("Bash")
        assert desc == "command execution"

    def test_write_tool_description(self):
        """Test Write tool description."""
        desc = format_tool_description("Write")
        assert desc == "file write"

    def test_edit_tool_description(self):
        """Test Edit tool description."""
        desc = format_tool_description("Edit")
        assert desc == "file edit"

    def test_unknown_tool_description(self):
        """Test unknown tool description."""
        desc = format_tool_description("UnknownTool")
        assert desc == "unknowntool"

    def test_none_tool_description(self):
        """Test None tool description."""
        desc = format_tool_description(None)
        assert desc == "operation"


class TestGetDocumentationUrl:
    """Tests for documentation URL functions."""

    def test_documentation_url_without_rule_id(self):
        """Test documentation URL without rule ID."""
        url = get_documentation_url()
        assert url == "https://github.com/AndyMik90/Auto-Claude/docs/output-validation.md"

    def test_documentation_url_with_rule_id(self):
        """Test documentation URL with rule ID."""
        url = get_documentation_url("bash-rm-rf-root")
        assert url.endswith("#bash-rm-rf-root")

    def test_rule_documentation_link(self):
        """Test rule documentation link."""
        rule = ValidationRule(
            rule_id="test-rule",
            name="Test Rule",
            description="Test",
            pattern="test",
            tool_types=[ToolType.BASH],
        )

        link = get_rule_documentation_link(rule)
        assert "Learn more about this rule:" in link
        assert "#test-rule" in link


class TestFormatShortBlockMessage:
    """Tests for format_short_block_message function."""

    def test_short_message_for_bash(self):
        """Test short message for Bash command."""
        result = ValidationResult(
            is_blocked=True,
            rule_id="bash-test",
            severity=SeverityLevel.HIGH,
            reason="Test",
            tool_name="Bash",
            tool_input={"command": "rm -rf /data"},
        )

        message = format_short_block_message(result)

        assert message == "Blocked command execution 'rm -rf /data' (rule: bash-test, severity: high)"

    def test_short_message_for_write(self):
        """Test short message for Write operation."""
        result = ValidationResult(
            is_blocked=True,
            rule_id="write-test",
            severity=SeverityLevel.CRITICAL,
            reason="Test",
            tool_name="Write",
            tool_input={"file_path": "/etc/passwd"},
        )

        message = format_short_block_message(result)

        assert message == "Blocked file write '/etc/passwd' (rule: write-test, severity: critical)"

    def test_short_message_for_web_fetch(self):
        """Test short message for WebFetch operation."""
        result = ValidationResult(
            is_blocked=True,
            rule_id="web-test",
            severity=SeverityLevel.MEDIUM,
            reason="Test",
            tool_name="WebFetch",
            tool_input={"url": "http://example.com"},
        )

        message = format_short_block_message(result)

        assert message == "Blocked web request 'http://example.com' (rule: web-test, severity: medium)"

    def test_short_message_truncates_long_content(self):
        """Test that short message truncates long content."""
        result = ValidationResult(
            is_blocked=True,
            rule_id="test",
            severity=SeverityLevel.HIGH,
            reason="Test",
            tool_name="Bash",
            tool_input={"command": "a" * 100},
        )

        message = format_short_block_message(result)

        # Should be truncated
        assert len(message) < 200
        assert "..." in message or "'aaaaaaaaaaaaaaaa" in message


class TestFormatValidationSummary:
    """Tests for format_validation_summary function."""

    def test_basic_summary(self):
        """Test basic validation summary."""
        summary = format_validation_summary(
            blocked_count=5, warning_count=3, allowed_count=100
        )

        assert "Validation Summary (108 operations checked):" in summary
        assert "✅ Allowed: 100" in summary
        assert "⚡ Warnings: 3" in summary
        assert "🚫 Blocked: 5" in summary
        assert "🔓 Overrides used:" not in summary

    def test_summary_with_overrides(self):
        """Test summary with overrides used."""
        summary = format_validation_summary(
            blocked_count=5, warning_count=3, allowed_count=100, has_overrides=True
        )

        assert "🔓 Overrides used: Yes" in summary

    def test_summary_with_no_blocks(self):
        """Test summary with no blocks."""
        summary = format_validation_summary(
            blocked_count=0, warning_count=0, allowed_count=50
        )

        assert "Validation Summary (50 operations checked):" in summary
        assert "✅ Allowed: 50" in summary
        assert "⚡ Warnings:" not in summary
        assert "🚫 Blocked:" not in summary

    def test_summary_with_only_warnings(self):
        """Test summary with only warnings."""
        summary = format_validation_summary(
            blocked_count=0, warning_count=10, allowed_count=40
        )

        assert "⚡ Warnings: 10" in summary
        assert "🚫 Blocked:" not in summary


class TestMessageFormattingIntegration:
    """Integration tests for message formatting."""

    def test_full_block_message_structure(self):
        """Test that full block message has all expected sections."""
        rule = ValidationRule(
            rule_id="integration-test",
            name="Integration Test Rule",
            description="This is an integration test rule with detailed description",
            pattern="test",
            severity=SeverityLevel.HIGH,
            tool_types=[ToolType.BASH],
            suggestions=[
                "First suggestion",
                "Second suggestion",
                "Third suggestion",
            ],
        )

        result = ValidationResult.blocked(
            rule=rule,
            reason="This is the reason for the block",
            matched_pattern="test-pattern",
            tool_name="Bash",
            tool_input={"command": "test command"},
        )

        message = format_block_message(result, rule)

        # Verify all sections are present
        sections = [
            "High-Risk Operation Blocked",
            "What was blocked:",
            "Why it was blocked:",
            "Suggestions:",
            "To override this block:",
            "Learn more:",
        ]

        for section in sections:
            assert section in message, f"Missing section: {section}"

        # Verify suggestions are numbered
        assert "1. First suggestion" in message
        assert "2. Second suggestion" in message
        assert "3. Third suggestion" in message

        # Verify documentation link includes rule ID
        assert "#integration-test" in message

    def test_message_without_suggestions(self):
        """Test message without suggestions still looks good."""
        rule = ValidationRule(
            rule_id="no-suggestions",
            name="No Suggestions Rule",
            description="No suggestions",
            pattern="test",
            severity=SeverityLevel.MEDIUM,
            tool_types=[ToolType.BASH],
            suggestions=[],  # No suggestions
        )

        result = ValidationResult.blocked(
            rule=rule,
            reason="Blocked without suggestions",
            tool_name="Bash",
            tool_input={"command": "test"},
        )

        message = format_block_message(result, rule)

        # Should not have suggestions section
        assert "Suggestions:" not in message

        # Should still have other sections
        assert "What was blocked:" in message
        assert "Why it was blocked:" in message

    def test_message_with_multiline_reason(self):
        """Test message with multiline reason is formatted correctly."""
        rule = ValidationRule(
            rule_id="multiline-reason",
            name="Multiline Reason",
            description="Test",
            pattern="test",
            severity=SeverityLevel.HIGH,
            tool_types=[ToolType.BASH],
        )

        result = ValidationResult.blocked(
            rule=rule,
            reason="First reason. Second reason. Third reason.",
            tool_name="Bash",
            tool_input={"command": "test"},
        )

        message = format_block_message(result, rule)

        # All reasons should be present
        assert "First reason" in message
        assert "Second reason" in message
        assert "Third reason" in message
