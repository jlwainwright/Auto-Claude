"""
Validation Report Generator
===========================

Generates human-readable summary reports of validation events per build session.
Reports show what was blocked, warnings issued, and provides statistics.

This module provides:
- ValidationReportGenerator: Main report generator class
- Markdown report generation with formatted statistics
- Per-session validation summaries
- Detailed event listings grouped by decision type
- Save functionality for spec directories

Usage:
    from security.output_validation.report import (
        ValidationReportGenerator,
        generate_validation_report,
        generate_and_save_report,
    )

    # Generate a report from logger
    logger = get_validation_logger(project_dir)
    report_gen = ValidationReportGenerator(logger)
    markdown = report_gen.generate_markdown()

    # Or use convenience function
    report_path = generate_and_save_report(
        project_dir=Path("/project"),
        spec_dir=Path("/project/.auto-claude/specs/001")
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .logger import ValidationEventLogger, get_validation_logger
from .models import SeverityLevel


# =============================================================================
# LOGGER
# =============================================================================

module_logger = logging.getLogger(__name__)


# =============================================================================
# VALIDATION REPORT GENERATOR
# =============================================================================

class ValidationReportGenerator:
    """
    Generates human-readable reports from validation events.

    Creates markdown-formatted reports showing:
    - Summary statistics (total, blocked, warnings, allowed, overrides)
    - Blocked operations with explanations
    - Warning events
    - Override token usage
    - Events grouped by tool and rule

    Attributes:
        logger: ValidationEventLogger with events to report
        spec_dir: Optional spec directory for report context

    Example:
        >>> logger = get_validation_logger(project_dir)
        >>> report_gen = ValidationReportGenerator(logger)
        >>> markdown = report_gen.generate_markdown()
        >>> report_gen.save_to_file(spec_dir / "validation-report.md")
    """

    def __init__(
        self,
        logger: ValidationEventLogger,
        spec_dir: Path | None = None,
    ):
        """
        Initialize the report generator.

        Args:
            logger: ValidationEventLogger with events to report
            spec_dir: Optional spec directory for context
        """
        self.logger = logger
        self.spec_dir = spec_dir

    def generate_markdown(self) -> str:
        """
        Generate a markdown-formatted validation report.

        Returns:
            Markdown string containing the full report
        """
        sections = []

        # Title and metadata
        sections.append(self._generate_header())
        sections.append("")

        # Summary statistics
        sections.append(self._generate_summary_section())
        sections.append("")

        # Blocked operations
        blocked = self.logger.get_blocked_events()
        if blocked:
            sections.append(self._generate_blocked_section(blocked))
            sections.append("")

        # Warnings
        warnings = self.logger.get_warning_events()
        if warnings:
            sections.append(self._generate_warning_section(warnings))
            sections.append("")

        # Override usage
        overrides = self.logger.get_override_events()
        if overrides:
            sections.append(self._generate_override_section(overrides))
            sections.append("")

        # Statistics by tool
        sections.append(self._generate_tool_statistics())
        sections.append("")

        # Severity breakdown
        sections.append(self._generate_severity_breakdown())
        sections.append("")

        # Footer
        sections.append(self._generate_footer())

        return "\n".join(sections)

    def _generate_header(self) -> str:
        """Generate report header with metadata."""
        stats = self.logger.get_statistics()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = [
            "# Output Validation Report",
            "",
            f"**Generated:** {timestamp}",
        ]

        if self.logger.project_dir:
            lines.append(f"**Project:** `{self.logger.project_dir}`")

        if self.spec_dir:
            lines.append(f"**Spec Directory:** `{self.spec_dir}`")

        lines.append(f"**Total Validations:** {stats['total_validations']}")

        return "\n".join(lines)

    def _generate_summary_section(self) -> str:
        """Generate summary statistics section."""
        stats = self.logger.get_statistics()

        lines = [
            "## Summary",
            "",
            "| Metric | Count |",
            "|--------|-------|",
            f"| **Total Validations** | {stats['total_validations']} |",
            f"| 🔴 **Blocked** | {stats['blocked']} |",
            f"| ⚠️  **Warnings** | {stats['warnings']} |",
            f"| ✅ **Allowed** | {stats['allowed']} |",
            f"| 🔑 **Overrides Used** | {stats['overrides_used']} |",
        ]

        return "\n".join(lines)

    def _generate_blocked_section(self, blocked: list) -> str:
        """Generate blocked operations section."""
        lines = [
            "## Blocked Operations",
            "",
            f"The following {len(blocked)} operations were blocked by validation rules:",
            "",
        ]

        # Group by rule ID
        by_rule: dict[str, list] = {}
        for event in blocked:
            rule_id = event.rule_id or "unknown"
            if rule_id not in by_rule:
                by_rule[rule_id] = []
            by_rule[rule_id].append(event)

        # List each rule's violations
        for rule_id, events in sorted(by_rule.items()):
            lines.append(f"### {rule_id}")

            # Get first event's details
            first_event = events[0]
            severity_icon = self._severity_icon(first_event.severity)
            lines.append(f"{severity_icon} **Severity:** {first_event.severity.value if first_event.severity else 'unknown'}")
            lines.append(f"**Reason:** {first_event.reason}")
            lines.append(f"**Occurrences:** {len(events)}")
            lines.append("")

            # Show examples (max 3)
            lines.append("**Examples:**")
            for i, event in enumerate(events[:3], 1):
                lines.append(f"{i}. **{event.tool_name}** - {self._format_tool_input(event.tool_input_summary)}")

            if len(events) > 3:
                lines.append(f"   *... and {len(events) - 3} more*")

            lines.append("")

        return "\n".join(lines)

    def _generate_warning_section(self, warnings: list) -> str:
        """Generate warnings section."""
        lines = [
            "## Warnings",
            "",
            f"The following {len(warnings)} warnings were issued:",
            "",
        ]

        # Group by rule ID
        by_rule: dict[str, list] = {}
        for event in warnings:
            rule_id = event.rule_id or "unknown"
            if rule_id not in by_rule:
                by_rule[rule_id] = []
            by_rule[rule_id].append(event)

        # List each rule's warnings
        for rule_id, events in sorted(by_rule.items()):
            lines.append(f"### {rule_id}")

            first_event = events[0]
            severity_icon = self._severity_icon(first_event.severity)
            lines.append(f"{severity_icon} **Severity:** {first_event.severity.value if first_event.severity else 'unknown'}")
            lines.append(f"**Reason:** {first_event.reason}")
            lines.append(f"**Occurrences:** {len(events)}")
            lines.append("")

            # Show examples (max 3)
            lines.append("**Examples:**")
            for i, event in enumerate(events[:3], 1):
                lines.append(f"{i}. **{event.tool_name}** - {self._format_tool_input(event.tool_input_summary)}")

            if len(events) > 3:
                lines.append(f"   *... and {len(events) - 3} more*")

            lines.append("")

        return "\n".join(lines)

    def _generate_override_section(self, overrides: list) -> str:
        """Generate override usage section."""
        lines = [
            "## Override Tokens Used",
            "",
            f"The following {len(overrides)} override tokens were used to bypass validation:",
            "",
        ]

        for i, event in enumerate(overrides, 1):
            token_id = event.override_token_id or "unknown"
            lines.append(f"{i}. **Token:** `{token_id}`")
            lines.append(f"   - **Rule:** {event.rule_id}")
            lines.append(f"   - **Tool:** {event.tool_name}")
            lines.append(f"   - **Reason:** {event.reason}")
            lines.append("")

        return "\n".join(lines)

    def _generate_tool_statistics(self) -> str:
        """Generate statistics by tool section."""
        stats = self.logger.get_statistics()
        by_tool = stats.get("by_tool", {})

        if not by_tool:
            return ""

        lines = [
            "## Statistics by Tool",
            "",
            "| Tool | Validations |",
            "|------|-------------|",
        ]

        for tool, count in sorted(by_tool.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| {tool} | {count} |")

        return "\n".join(lines)

    def _generate_severity_breakdown(self) -> str:
        """Generate severity breakdown section."""
        stats = self.logger.get_statistics()
        by_severity = stats.get("by_severity", {})

        if not by_severity:
            return ""

        lines = [
            "## Blocked Operations by Severity",
            "",
            "| Severity | Count |",
            "|----------|-------|",
        ]

        # Order by severity level (critical first)
        severity_order = ["critical", "high", "medium", "low"]
        for severity in severity_order:
            if severity in by_severity:
                icon = self._severity_icon_text(severity)
                lines.append(f"| {icon} {severity.upper()} | {by_severity[severity]} |")

        return "\n".join(lines)

    def _generate_footer(self) -> str:
        """Generate report footer."""
        lines = [
            "---",
            "",
            "*This report was generated by the Auto Claude Output Validation System.*",
            "",
            "For more information about validation rules and configuration, see the documentation.",
        ]

        return "\n".join(lines)

    def _severity_icon(self, severity: SeverityLevel | None) -> str:
        """Get emoji icon for severity level."""
        if not severity:
            return "⚪"

        icons = {
            SeverityLevel.CRITICAL: "🔴",
            SeverityLevel.HIGH: "🟠",
            SeverityLevel.MEDIUM: "🟡",
            SeverityLevel.LOW: "🔵",
        }
        return icons.get(severity, "⚪")

    def _severity_icon_text(self, severity: str) -> str:
        """Get emoji icon for severity string."""
        icons = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🔵",
        }
        return icons.get(severity, "⚪")

    def _format_tool_input(self, tool_input: dict[str, Any]) -> str:
        """
        Format tool input for display.

        Args:
            tool_input: Sanitized tool input dict

        Returns:
            Formatted string representation
        """
        if not tool_input:
            return "*No details available*"

        # Extract key fields for display
        parts = []

        # Handle different tool types
        if "command" in tool_input:
            command = tool_input["command"]
            if len(command) > 100:
                command = command[:100] + "..."
            parts.append(f"`{command}`")

        if "file_path" in tool_input:
            parts.append(f"File: `{tool_input['file_path']}`")

        if "tool_name" in tool_input:
            parts.append(f"Tool: {tool_input['tool_name']}")

        return " | ".join(parts) if parts else str(tool_input)

    def save_to_file(self, path: Path | None = None) -> Path:
        """
        Save the generated report to a file.

        Args:
            path: Optional path to save to (defaults to spec_dir/validation-report.md)

        Returns:
            Path to the saved file

        Raises:
            ValueError: If no path is available
        """
        if path:
            report_path = path
        elif self.spec_dir:
            report_path = self.spec_dir / "validation-report.md"
        else:
            raise ValueError("No path available for saving report")

        # Ensure parent directory exists
        report_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate markdown
        markdown = self.generate_markdown()

        # Write to file
        with open(report_path, "w") as f:
            f.write(markdown)

        module_logger.info(f"Validation report saved to {report_path}")

        return report_path

    def print_summary(self) -> None:
        """Print a brief summary to console."""
        stats = self.logger.get_statistics()

        print("\n" + "=" * 60)
        print("OUTPUT VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Total Validations: {stats['total_validations']}")
        print(f"🔴 Blocked: {stats['blocked']}")
        print(f"⚠️  Warnings: {stats['warnings']}")
        print(f"✅ Allowed: {stats['allowed']}")
        print(f"🔑 Overrides Used: {stats['overrides_used']}")
        print("=" * 60 + "\n")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_validation_report(
    project_dir: Path | None = None,
    spec_dir: Path | None = None,
) -> ValidationReportGenerator:
    """
    Create a ValidationReportGenerator for the project.

    Args:
        project_dir: Project directory path
        spec_dir: Optional spec directory for context

    Returns:
        ValidationReportGenerator instance
    """
    logger = get_validation_logger(project_dir)
    return ValidationReportGenerator(logger, spec_dir)


def generate_and_save_report(
    project_dir: Path | None = None,
    spec_dir: Path | None = None,
    report_path: Path | None = None,
) -> Path:
    """
    Generate and save a validation report.

    Args:
        project_dir: Project directory path
        spec_dir: Optional spec directory for context
        report_path: Optional custom path for the report

    Returns:
        Path to the saved report file
    """
    report_gen = generate_validation_report(project_dir, spec_dir)
    return report_gen.save_to_file(report_path)


def print_validation_summary(
    project_dir: Path | None = None,
) -> None:
    """
    Print a brief validation summary to console.

    Args:
        project_dir: Project directory path
    """
    report_gen = generate_validation_report(project_dir)
    report_gen.print_summary()
