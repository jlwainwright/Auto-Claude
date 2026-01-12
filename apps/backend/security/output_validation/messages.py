"""
User-Friendly Block Messages
============================

Formats validation results into clear, actionable messages for users.
Includes what was blocked, why, and how to proceed.

This module provides:
- format_block_message(): Format ValidationResult into comprehensive message
- format_override_instruction(): Show how to use override tokens
- get_documentation_url(): Generate documentation links for rules
- format_tool_description(): Get user-friendly tool descriptions
"""

from .models import ValidationResult, ValidationRule, SeverityLevel, ToolType


# ============================================================================
# MESSAGE TEMPLATES
# ============================================================================

# Severity-level headers
SEVERITY_HEADERS = {
    SeverityLevel.CRITICAL: "🚨 Critical Security Block",
    SeverityLevel.HIGH: "⚠️ High-Risk Operation Blocked",
    SeverityLevel.MEDIUM: "⚡ Potentially Dangerous Operation",
    SeverityLevel.LOW: "ℹ️ Warning",
}

# Tool type descriptions (user-friendly)
TOOL_DESCRIPTIONS = {
    ToolType.BASH: "command execution",
    ToolType.WRITE: "file write",
    ToolType.EDIT: "file edit",
    ToolType.READ: "file read",
    ToolType.WEB_FETCH: "web request",
    ToolType.WEB_SEARCH: "web search",
}

# Documentation base URL
DOC_BASE_URL = "https://github.com/AndyMik90/Auto-Claude/docs/output-validation.md"


# ============================================================================
# MAIN MESSAGE FORMATTING
# ============================================================================

def format_block_message(
    result: ValidationResult,
    rule: ValidationRule | None = None,
    include_override: bool = True,
) -> str:
    """
    Format a ValidationResult into a comprehensive, user-friendly block message.

    The message includes:
    - Clear header with severity level
    - What operation was blocked
    - Why it was blocked (rule-specific reason)
    - Actionable suggestions
    - How to override (if applicable)
    - Link to documentation

    Args:
        result: ValidationResult from validation check
        rule: Optional ValidationRule (looked up by result.rule_id if not provided)
        include_override: Whether to include override instructions

    Returns:
        Formatted multi-line message string

    Example:
        >>> result = ValidationResult.blocked(
        ...     rule=dangerous_rule,
        ...     reason="This would delete system files",
        ...     tool_name="Bash",
        ...     tool_input={"command": "rm -rf /"}
        ... )
        >>> message = format_block_message(result)
        >>> print(message)
        🚨 Critical Security Block

        This command execution has been blocked because it violates security rules.

        What was blocked:
        • Command: rm -rf /
        • Type: command execution

        Why it was blocked:
        This command would recursively delete critical system directories,
        which would destroy your operating system.

        Suggestions:
        • Review the command and ensure you're targeting the correct directory
        • Use absolute paths to avoid ambiguity
        • Consider using --preserve-root flag with rm

        To override this block:
        If you're sure this operation is safe, you can create an override token:
        $ auto-claude override create --rule bash-rm-rf-root

        Learn more:
        https://github.com/AndyMik90/Auto-Claude/docs/output-validation.md#bash-rm-rf-root
    """
    # Get severity for header
    severity = result.severity or SeverityLevel.MEDIUM
    header = SEVERITY_HEADERS.get(severity, "⚠️ Operation Blocked")

    # Build message sections
    sections = []

    # Header
    sections.append(f"{header}\n")

    # Summary line
    tool_desc = format_tool_description(result.tool_name)
    summary = f"This {tool_desc} has been blocked because it violates security rules."
    sections.append(f"{summary}\n")

    # What was blocked
    sections.append(_format_what_was_blocked(result))
    sections.append("")

    # Why it was blocked
    sections.append(_format_why_blocked(result, rule))
    sections.append("")

    # Suggestions (if available)
    if result.suggestions:
        sections.append(_format_suggestions(result.suggestions))
        sections.append("")

    # Override instructions (if applicable and requested)
    if include_override and result.can_override and result.rule_id:
        sections.append(_format_override_instructions(result.rule_id, severity))
        sections.append("")

    # Documentation link
    doc_link = get_documentation_url(result.rule_id)
    if doc_link:
        sections.append(f"Learn more:\n{doc_link}")

    return "\n".join(sections)


def _format_what_was_blocked(result: ValidationResult) -> str:
    """Format the 'What was blocked' section."""
    lines = ["What was blocked:"]
    indent = "• "

    # Add tool name
    tool_desc = format_tool_description(result.tool_name)
    lines.append(f"{indent}{tool_desc.capitalize()}")

    # Add relevant details based on tool type
    if result.tool_input:
        # Extract relevant info based on tool
        if result.tool_name == "Bash":
            command = result.tool_input.get("command", "")
            if command:
                # Truncate very long commands
                display_cmd = command[:200] + "..." if len(command) > 200 else command
                lines.append(f"{indent}Command: {display_cmd}")

        elif result.tool_name in ("Write", "Edit"):
            file_path = result.tool_input.get("file_path", "")
            if file_path:
                lines.append(f"{indent}File: {file_path}")

        elif result.tool_name == "WebFetch":
            url = result.tool_input.get("url", "")
            if url:
                lines.append(f"{indent}URL: {url}")

        elif result.tool_name == "WebSearch":
            query = result.tool_input.get("query", "")
            if query:
                lines.append(f"{indent}Query: {query}")

    return "\n".join(lines)


def _format_why_blocked(
    result: ValidationResult,
    rule: ValidationRule | None = None,
) -> str:
    """Format the 'Why it was blocked' section."""
    lines = ["Why it was blocked:"]

    # Use result.reason as the primary explanation
    reason = result.reason.strip()

    # If we have the rule object, we can provide more context
    if rule:
        # Add rule name for clarity
        if rule.name and rule.name != rule.description:
            lines.append(f"Rule: {rule.name}")
            lines.append("")

        # Format the reason with proper indentation
        for line in reason.split(". "):
            line = line.strip()
            if line:
                lines.append(f"{line}")

        # Add rule description if different from reason
        if rule.description and rule.description != result.reason:
            lines.append("")
            lines.append(f"Details: {rule.description}")
    else:
        # Just use the reason
        for line in reason.split(". "):
            line = line.strip()
            if line:
                lines.append(f"{line}")

    # Add matched pattern if available
    if result.matched_pattern:
        lines.append("")
        lines.append(f"Matched pattern: {result.matched_pattern}")

    return "\n".join(lines)


def _format_suggestions(suggestions: list[str]) -> str:
    """Format the suggestions section."""
    if not suggestions:
        return ""

    lines = ["Suggestions:"]
    for i, suggestion in enumerate(suggestions, 1):
        lines.append(f"{i}. {suggestion}")

    return "\n".join(lines)


def _format_override_instructions(rule_id: str, severity: SeverityLevel) -> str:
    """Format the override instructions section."""
    lines = ["To override this block:"]

    # Warnings for critical severity
    if severity == SeverityLevel.CRITICAL:
        lines.append("")
        lines.append("⚠️ WARNING: This is a critical security rule.")
        lines.append("Overriding it could cause serious damage to your system.")
        lines.append("")

    # Instructions
    lines.append("If you're sure this operation is safe, you can create an override token:")
    lines.append(f"  $ auto-claude override create --rule {rule_id}")
    lines.append("")
    lines.append("This will generate a time-limited token that allows this specific operation.")
    lines.append("")
    lines.append("To list active override tokens:")
    lines.append("  $ auto-claude override list")
    lines.append("")
    lines.append("To revoke an override token:")
    lines.append("  $ auto-claude override revoke <token-id>")

    return "\n".join(lines)


# ============================================================================
# OVERRIDE INSTRUCTIONS
# ============================================================================

def format_override_instruction(
    rule_id: str,
    severity: SeverityLevel = SeverityLevel.MEDIUM,
    project_dir: str | None = None,
) -> str:
    """
    Format a concise override instruction message.

    Args:
        rule_id: ID of the rule to override
        severity: Severity level of the rule
        project_dir: Optional project directory for context

    Returns:
        Formatted instruction string
    """
    lines = [f"To override this block, create an override token:"]
    lines.append(f"  $ auto-claude override create --rule {rule_id}")

    if severity == SeverityLevel.CRITICAL:
        lines.append("")
        lines.append("⚠️ WARNING: This is a critical security rule.")
        lines.append("Only override if you fully understand the risks.")

    return "\n".join(lines)


# ============================================================================
# TOOL DESCRIPTIONS
# ============================================================================

def format_tool_description(tool_name: str | None) -> str:
    """
    Get a user-friendly description of a tool type.

    Args:
        tool_name: Tool name from SDK (e.g., "Bash", "Write")

    Returns:
        User-friendly description (e.g., "command execution")
    """
    if not tool_name:
        return "operation"

    try:
        tool_type = ToolType(tool_name)
        return TOOL_DESCRIPTIONS.get(tool_type, tool_name.lower())
    except ValueError:
        # Unknown tool type
        return tool_name.lower()


# ============================================================================
# DOCUMENTATION LINKS
# ============================================================================

def get_documentation_url(rule_id: str | None = None) -> str:
    """
    Generate a documentation URL for a validation rule.

    Args:
        rule_id: Optional rule ID to link to specific rule

    Returns:
        Full documentation URL
    """
    if rule_id:
        return f"{DOC_BASE_URL}#{rule_id}"
    return DOC_BASE_URL


def get_rule_documentation_link(rule: ValidationRule) -> str:
    """
    Get a documentation link for a specific rule.

    Args:
        rule: ValidationRule to generate link for

    Returns:
        Documentation URL with anchor to rule
    """
    url = get_documentation_url(rule.rule_id)
    return f"Learn more about this rule: {url}"


# ============================================================================
# COMPATIBILITY HELPERS
# ============================================================================

def format_short_block_message(result: ValidationResult) -> str:
    """
    Format a short, one-line block message for use in logs/summaries.

    Args:
        result: ValidationResult from validation check

    Returns:
        Short message string

    Example:
        "Blocked bash command 'rm -rf /' (rule: bash-rm-rf-root, severity: critical)"
    """
    tool_desc = format_tool_description(result.tool_name)
    severity = result.severity.value if result.severity else "unknown"

    # Get a brief description of what was blocked
    if result.tool_name == "Bash":
        command = result.tool_input.get("command", "")[:50]
        what = f"'{command}'"
    elif result.tool_name in ("Write", "Edit"):
        file_path = result.tool_input.get("file_path", "")[:50]
        what = f"'{file_path}'"
    elif result.tool_name == "WebFetch":
        url = result.tool_input.get("url", "")[:50]
        what = f"'{url}'"
    else:
        what = "operation"

    return f"Blocked {tool_desc} {what} (rule: {result.rule_id}, severity: {severity})"


def format_validation_summary(
    blocked_count: int,
    warning_count: int,
    allowed_count: int,
    has_overrides: bool = False,
) -> str:
    """
    Format a validation summary for reports.

    Args:
        blocked_count: Number of blocked operations
        warning_count: Number of warnings
        allowed_count: Number of allowed operations
        has_overrides: Whether any overrides were used

    Returns:
        Formatted summary string
    """
    total = blocked_count + warning_count + allowed_count

    lines = [f"Validation Summary ({total} operations checked):"]
    lines.append(f"  ✅ Allowed: {allowed_count}")

    if warning_count > 0:
        lines.append(f"  ⚡ Warnings: {warning_count}")

    if blocked_count > 0:
        lines.append(f"  🚫 Blocked: {blocked_count}")

    if has_overrides:
        lines.append(f"  🔓 Overrides used: Yes")

    return "\n".join(lines)
