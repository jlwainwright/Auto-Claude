"""
Smoke Tests for Validation Report Generator
============================================

Manual test script for the validation report generation module.
Run with: python apps/backend/security/output_validation/test_report_smoke.py

No pytest required.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

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


def test_basic_report_generation():
    """Test 1: Basic report generation with no events."""
    print("\n" + "=" * 60)
    print("TEST 1: Basic Report Generation (No Events)")
    print("=" * 60)

    logger = ValidationEventLogger(
        project_dir=Path("/test/project"),
        config=OutputValidationConfig()
    )

    report_gen = ValidationReportGenerator(logger)
    markdown = report_gen.generate_markdown()

    assert "# Output Validation Report" in markdown
    assert "## Summary" in markdown
    assert "| **Total Validations** | 0 |" in markdown

    print("✅ Report with no events generated successfully")
    print(f"   Report length: {len(markdown)} characters")


def test_report_with_events():
    """Test 2: Report generation with various events."""
    print("\n" + "=" * 60)
    print("TEST 2: Report Generation With Events")
    print("=" * 60)

    # Create a fresh logger instance to avoid picking up events from other tests
    logger = ValidationEventLogger(
        project_dir=Path("/test/project"),
        config=OutputValidationConfig()
    )
    # Clear any pre-existing events
    logger.clear()

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
        tool_input={"command": "sudo apt install package"}
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
        override_token_id="token-abc-123",
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

    # Generate report
    report_gen = ValidationReportGenerator(logger)
    markdown = report_gen.generate_markdown()

    # Debug: print actual event count
    stats = logger.get_statistics()
    print(f"   Actual event count: {stats['total_validations']}")

    # Verify sections
    try:
        assert "# Output Validation Report" in markdown
        assert "## Summary" in markdown
        assert "## Blocked Operations" in markdown
        assert "## Warnings" in markdown
        assert "## Override Tokens Used" in markdown
        assert "## Statistics by Tool" in markdown
        assert "## Blocked Operations by Severity" in markdown
    except AssertionError as e:
        print(f"   ❌ Section check failed: {e}")
        print(f"   First 500 chars of markdown:")
        print(f"   {markdown[:500]}")
        raise

    # Verify statistics - use flexible matching
    stats_checks = [
        ("| **Total Validations** |", "Total Validations"),
        ("| 🔴 **Blocked** |", "Blocked"),
        ("| ⚠️  **Warnings** |", "Warnings"),
        ("| ✅ **Allowed** |", "Allowed"),
        ("| 🔑 **Overrides Used** |", "Overrides Used"),
    ]

    for check_str, desc in stats_checks:
        if check_str not in markdown:
            print(f"   ❌ Missing: {desc}")
            print(f"      Looking for: {repr(check_str)}")
            print(f"      Actual stats line:")
            # Find the stats table
            idx = markdown.find("| Metric | Count |")
            if idx > 0:
                print(f"      {markdown[idx:idx+300]}")
            raise AssertionError(f"{desc} not found in report")

    # Verify details
    checks = [
        ("### bash-rm-rf-root", "bash-rm-rf-root section"),
        ("🔴 **Severity:** critical", "critical severity"),
        ("### bash-sudo", "bash-sudo section"),
        ("🟠 **Severity:** high", "high severity"),
        ("token-abc-123", "override token"),
    ]

    for check_str, desc in checks:
        if check_str not in markdown:
            print(f"   ❌ Missing: {desc}")
            print(f"      Looking for: {repr(check_str)}")
            raise AssertionError(f"{desc} not found in report")

    print("✅ Report with events generated successfully")
    print(f"   Report length: {len(markdown)} characters")
    print("   All sections present and verified")


def test_multiple_same_rule():
    """Test 3: Report with multiple violations of same rule."""
    print("\n" + "=" * 60)
    print("TEST 3: Multiple Violations of Same Rule")
    print("=" * 60)

    logger = ValidationEventLogger(
        project_dir=Path("/test/project"),
        config=OutputValidationConfig()
    )

    # Add 5 blocked events for same rule
    for i in range(5):
        result = ValidationResult(
            is_blocked=True,
            rule_id="bash-dangerous",
            severity=SeverityLevel.HIGH,
            reason=f"Dangerous command #{i+1}",
            tool_name="Bash",
            tool_input={"command": f"rm -rf /dir{i}"}
        )
        logger.log_blocked(
            tool_name="Bash",
            rule_id="bash-dangerous",
            result=result
        )

    report_gen = ValidationReportGenerator(logger)
    markdown = report_gen.generate_markdown()

    # Verify occurrences are grouped
    assert "**Occurrences:** 5" in markdown

    # Verify examples are limited to 3
    assert "**Examples:**" in markdown
    # Should have examples 1, 2, 3 but not 4 or 5
    assert "1. **Bash**" in markdown
    assert "*... and 2 more*" in markdown

    print("✅ Multiple violations grouped correctly")
    print("   5 violations detected")
    print("   Examples limited to 3")


def test_severity_icons():
    """Test 4: Severity icon mapping."""
    print("\n" + "=" * 60)
    print("TEST 4: Severity Icon Mapping")
    print("=" * 60)

    logger = ValidationEventLogger()
    report_gen = ValidationReportGenerator(logger)

    # Test all severity levels
    icons = {
        SeverityLevel.CRITICAL: "🔴",
        SeverityLevel.HIGH: "🟠",
        SeverityLevel.MEDIUM: "🟡",
        SeverityLevel.LOW: "🔵",
    }

    for severity, expected_icon in icons.items():
        actual_icon = report_gen._severity_icon(severity)
        assert actual_icon == expected_icon, f"Expected {expected_icon} for {severity}, got {actual_icon}"
        print(f"   {severity.value}: {actual_icon} ✓")

    # Test None
    none_icon = report_gen._severity_icon(None)
    assert none_icon == "⚪"
    print(f"   None: {none_icon} ✓")

    print("✅ All severity icons mapped correctly")


def test_tool_input_formatting():
    """Test 5: Tool input formatting."""
    print("\n" + "=" * 60)
    print("TEST 5: Tool Input Formatting")
    print("=" * 60)

    logger = ValidationEventLogger()
    report_gen = ValidationReportGenerator(logger)

    # Test empty input
    formatted = report_gen._format_tool_input({})
    assert formatted == "*No details available*"
    print("   Empty input: *No details available* ✓")

    # Test command
    formatted = report_gen._format_tool_input({"command": "ls -la"})
    assert "`ls -la`" in formatted
    print("   Command: `ls -la` ✓")

    # Test long command truncation
    long_cmd = "a" * 200
    formatted = report_gen._format_tool_input({"command": long_cmd})
    assert "..." in formatted
    assert len(formatted) < 300
    print(f"   Long command: Truncated to < 300 chars ✓")

    # Test file path
    formatted = report_gen._format_tool_input({"file_path": "/etc/config.json"})
    assert "File: `/etc/config.json`" in formatted
    print("   File path: File: `/etc/config.json` ✓")

    # Test multiple fields
    formatted = report_gen._format_tool_input({
        "command": "npm install",
        "file_path": "/home/user/package.json",
    })
    assert "`npm install`" in formatted
    assert "File:" in formatted
    print("   Multiple fields: Combined correctly ✓")

    print("✅ All tool input formatting tests passed")


def test_save_to_file():
    """Test 6: Save report to file."""
    print("\n" + "=" * 60)
    print("TEST 6: Save Report to File")
    print("=" * 60)

    import tempfile

    # Create logger with events
    logger = ValidationEventLogger(project_dir=Path("/test"))
    logger.log_blocked(
        tool_name="Bash",
        rule_id="test-rule",
        result=ValidationResult(
            is_blocked=True,
            rule_id="test-rule",
            severity=SeverityLevel.HIGH,
            reason="Test"
        )
    )

    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_dir = Path(tmpdir) / "specs" / "001"
        spec_dir.mkdir(parents=True)

        report_gen = ValidationReportGenerator(logger, spec_dir)
        report_path = report_gen.save_to_file()

        # Verify file exists
        assert report_path.exists()
        assert report_path.name == "validation-report.md"

        # Verify content
        content = report_path.read_text()
        assert "# Output Validation Report" in content
        assert "## Summary" in content

        print(f"   Report saved to: {report_path}")
        print(f"   File size: {len(content)} bytes")
        print("   Content verified ✓")

    print("✅ Report saved to file successfully")


def test_print_summary():
    """Test 7: Print summary to console."""
    print("\n" + "=" * 60)
    print("TEST 7: Print Summary to Console")
    print("=" * 60)

    logger = ValidationEventLogger(project_dir=Path("/test"))

    # Add various events
    logger.log_blocked(
        tool_name="Bash",
        rule_id="test-1",
        result=ValidationResult(is_blocked=True, rule_id="test-1")
    )
    logger.log_warning(
        tool_name="Write",
        rule_id="test-2",
        result=ValidationResult(is_blocked=False, rule_id="test-2")
    )
    logger.log_allowed(tool_name="Read", tool_input={"file_path": "test.txt"})

    report_gen = ValidationReportGenerator(logger)

    print("\n--- Output from print_summary(): ---\n")
    report_gen.print_summary()
    print("\n--- End output ---\n")

    print("✅ Summary printed to console")


def test_convenience_functions():
    """Test 8: Convenience functions."""
    print("\n" + "=" * 60)
    print("TEST 8: Convenience Functions")
    print("=" * 60)

    # Test generate_validation_report
    report_gen = generate_validation_report(Path("/test"))
    assert isinstance(report_gen, ValidationReportGenerator)
    print("   generate_validation_report() ✓")

    # Test print_validation_summary
    print("\n   Output from print_validation_summary():")
    print("   ---")
    print_validation_summary(Path("/test"))
    print("   ---")

    print("✅ All convenience functions work")


def test_full_report_example():
    """Test 9: Full report example with realistic data."""
    print("\n" + "=" * 60)
    print("TEST 9: Full Report Example (Realistic)")
    print("=" * 60)

    logger = ValidationEventLogger(
        project_dir=Path("/my/project"),
        config=OutputValidationConfig()
    )

    # Add realistic blocked operations
    logger.log_blocked(
        tool_name="Bash",
        rule_id="bash-rm-rf-root",
        result=ValidationResult(
            is_blocked=True,
            rule_id="bash-rm-rf-root",
            severity=SeverityLevel.CRITICAL,
            reason="Attempted to remove root filesystem",
            tool_name="Bash",
            tool_input={"command": "rm -rf /"}
        )
    )

    logger.log_blocked(
        tool_name="Write",
        rule_id="write-system-file",
        result=ValidationResult(
            is_blocked=True,
            rule_id="write-system-file",
            severity=SeverityLevel.HIGH,
            reason="Attempted to write to system directory",
            tool_name="Write",
            tool_input={"file_path": "/etc/config.json", "content": "..."}
        )
    )

    # Add warnings
    logger.log_warning(
        tool_name="Bash",
        rule_id="bash-sudo",
        result=ValidationResult(
            is_blocked=False,
            rule_id="bash-sudo",
            severity=SeverityLevel.HIGH,
            reason="Sudo command detected - requires elevated privileges",
            tool_name="Bash",
            tool_input={"command": "sudo apt install package"}
        )
    )

    # Add override usage
    logger.log_override_used(
        tool_name="Bash",
        rule_id="bash-rm-rf",
        override_token_id="550e8400-e29b-41d4-a716-446655440000",
        result=ValidationResult(
            is_blocked=True,
            rule_id="bash-rm-rf",
            severity=SeverityLevel.HIGH,
            reason="Dangerous rm command"
        ),
        tool_input={"command": "rm -rf /tmp/test"}
    )

    # Generate and print report
    report_gen = ValidationReportGenerator(logger)
    markdown = report_gen.generate_markdown()

    print("\n" + "-" * 60)
    print("Generated Report Preview (first 1000 chars):")
    print("-" * 60)
    print(markdown[:1000])
    print("..." if len(markdown) > 1000 else "")
    print("-" * 60)

    # Verify structure
    assert "# Output Validation Report" in markdown
    assert "**Project:** `/my/project`" in markdown
    assert "## Summary" in markdown
    assert "## Blocked Operations" in markdown
    assert "## Warnings" in markdown
    assert "## Override Tokens Used" in markdown

    print("\n✅ Full realistic report generated successfully")
    print(f"   Total report length: {len(markdown)} characters")


def run_all_tests():
    """Run all smoke tests."""
    print("\n" + "=" * 60)
    print("VALIDATION REPORT GENERATOR - SMOKE TESTS")
    print("=" * 60)

    tests = [
        test_basic_report_generation,
        test_report_with_events,
        test_multiple_same_rule,
        test_severity_icons,
        test_tool_input_formatting,
        test_save_to_file,
        test_print_summary,
        test_convenience_functions,
        test_full_report_example,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ FAILED: {test.__name__}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR: {test.__name__}")
            print(f"   Error: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("✅ All smoke tests passed!")
        return 0
    else:
        print(f"❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
