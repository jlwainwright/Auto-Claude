#!/usr/bin/env python3
"""
Screening Messages Module
==========================

Provides user-friendly messages for input screening results.

This module generates clear, helpful messages that explain why input was
rejected without revealing detection mechanisms or security patterns.

Key principles:
- Messages are informative but don't leak pattern details
- Suggestions provided for how to rephrase input
- Contact info for false positive reports
- UI formatting for terminal and Electron interfaces

Usage:
    from security.screening_messages import (
        get_rejection_message,
        format_for_terminal,
        format_for_ui,
    )

    # Get a user-friendly rejection message
    message = get_rejection_message(
        verdict="rejected",
        category="instruction_override",
        confidence=0.95
    )

    # Format for terminal output
    print(format_for_terminal(message))

    # Format for UI (structured data)
    ui_message = format_for_ui(message)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal


# =============================================================================
# TYPES AND MODELS
# =============================================================================


class MessageCategory(str, Enum):
    """Categories of rejection messages for different threat types."""

    INSTRUCTION_OVERRIDE = "instruction_override"
    """Attempts to override or ignore previous instructions."""

    ROLE_HIJACKING = "role_hijacking"
    """Attempts to change the AI's role or persona."""

    CONTEXT_MANIPULATION = "context_manipulation"
    """Attempts to manipulate the conversation context."""

    SHELL_INJECTION = "shell_injection"
    """Suspicious command execution patterns."""

    ENCODING_ATTACK = "encoding_attack"
    """Encoded or obfuscated content."""

    DELIMITER_ATTACK = "delimiter_attack"
    """Delimiter-based injection attempts."""

    GENERAL = "general"
    """General security concerns without specific category."""


class OutputFormat(str, Enum):
    """Output format types for messages."""

    TERMINAL = "terminal"
    """Plain text with ANSI colors for terminal display."""

    PLAIN = "plain"
    """Plain text without formatting."""

    UI = "ui"
    """Structured dictionary for UI rendering."""


@dataclass
class RejectionMessage:
    """User-friendly rejection message.

    Attributes:
        title: Short, clear title explaining the rejection
        explanation: Detailed explanation without revealing patterns
        suggestions: List of suggestions for rephrasing the input
        contact_info: Information for reporting false positives
        category: Message category for determining content
        severity: Severity level for UI display (low, medium, high, critical)
    """

    title: str
    """Short, clear title explaining the rejection."""

    explanation: str
    """Detailed explanation without revealing patterns."""

    suggestions: list[str]
    """List of suggestions for rephrasing the input."""

    contact_info: str
    """Information for reporting false positives."""

    category: MessageCategory
    """Message category for determining content."""

    severity: Literal["low", "medium", "high", "critical"]
    """Severity level for UI display."""


# =============================================================================
# MESSAGE CONTENT
# =============================================================================


# User-friendly message templates by category
# These messages explain the issue without revealing detection patterns
MESSAGE_TEMPLATES = {
    MessageCategory.INSTRUCTION_OVERRIDE: {
        "title": "Input Format Not Supported",
        "explanation": (
            "Your input contains formatting that is not compatible with our "
            "processing system. This helps maintain system integrity and "
            "prevents confusion in task understanding."
        ),
        "suggestions": [
            "Focus on describing what you want to accomplish",
            "Use straightforward language without special formatting",
            "Avoid phrases that attempt to modify system behavior",
            "Break complex tasks into separate, clear descriptions",
        ],
        "severity": "critical",
    },
    MessageCategory.ROLE_HIJACKING: {
        "title": "Invalid Role Specification",
        "explanation": (
            "Your input contains role or persona specifications that are not "
            "supported. Auto Claude operates as a development assistant and "
            "cannot adopt alternative personas or roles."
        ),
        "suggestions": [
            "Describe the task you need help with directly",
            "Focus on what needs to be done, not who should do it",
            "Use plain language to explain your requirements",
            "Avoid role-playing or persona adoption language",
        ],
        "severity": "critical",
    },
    MessageCategory.CONTEXT_MANIPULATION: {
        "title": "Input Structure Issue",
        "explanation": (
            "Your input uses formatting structures that are not compatible with "
            "our task processing system. Please use standard sentence and "
            "paragraph formatting."
        ),
        "suggestions": [
            "Use normal sentences and paragraphs",
            "Avoid unusual separators or special formatting",
            "Don't use system-like labels or markers",
            "Keep formatting simple and direct",
        ],
        "severity": "high",
    },
    MessageCategory.SHELL_INJECTION: {
        "title": "Command Syntax Not Allowed",
        "explanation": (
            "Your input contains command syntax that cannot be processed "
            "directly. If you need to execute commands, please describe what "
            "you want to accomplish instead of providing raw commands."
        ),
        "suggestions": [
            "Describe the outcome you want to achieve",
            "Explain what files or configurations you need changed",
            "Let the assistant determine the appropriate commands",
            "Break down complex operations into clear steps",
        ],
        "severity": "critical",
    },
    MessageCategory.ENCODING_ATTACK: {
        "title": "Encoded Content Found",
        "explanation": (
            "Your input contains content that cannot be safely processed. "
            "Please provide your task description in plain text format "
            "using normal characters."
        ),
        "suggestions": [
            "Use plain text instead of converted content",
            "Avoid character transformation or encoding schemes",
            "Write your task description directly in normal language",
            "Don't use character substitutions",
        ],
        "severity": "high",
    },
    MessageCategory.DELIMITER_ATTACK: {
        "title": "Formatting Not Compatible",
        "explanation": (
            "Your input contains formatting that is not compatible with our "
            "task processing system. Please use standard text formatting."
        ),
        "suggestions": [
            "Use normal sentences without special characters",
            "Avoid excessive dashes, equals signs, or asterisks",
            "Don't use code block markers unnecessarily",
            "Keep formatting simple and readable",
        ],
        "severity": "medium",
    },
    MessageCategory.GENERAL: {
        "title": "Input Cannot Be Processed",
        "explanation": (
            "Your input contains patterns that are not compatible with our "
            "task processing system. This may be due to formatting, content, "
            "or structural issues."
        ),
        "suggestions": [
            "Rephrase your request using clear, straightforward language",
            "Focus on describing what you want to accomplish",
            "Avoid technical jargon unless necessary",
            "Break complex tasks into simpler descriptions",
        ],
        "severity": "medium",
    },
}


# =============================================================================
# MESSAGE GENERATION
# =============================================================================


def get_rejection_message(
    category: str | MessageCategory = "general",
    severity: str | None = None,
    detected_count: int = 0,
) -> RejectionMessage:
    """
    Generate a user-friendly rejection message.

    Args:
        category: The category of the rejection (e.g., 'instruction_override')
        severity: Severity level (overrides default from template)
        detected_count: Number of patterns detected (for message variation)

    Returns:
        RejectionMessage with user-friendly content
    """
    # Normalize category to enum
    if isinstance(category, str):
        try:
            category = MessageCategory(category)
        except ValueError:
            # If category doesn't exist, use GENERAL
            category = MessageCategory.GENERAL

    # Get template for category
    template = MESSAGE_TEMPLATES.get(category, MESSAGE_TEMPLATES[MessageCategory.GENERAL])

    # Use provided severity or default from template
    final_severity = severity or template["severity"]

    # Build suggestions (can vary based on detected_count)
    suggestions = template["suggestions"].copy()
    if detected_count > 1:
        suggestions.append("Multiple issues were detected - review all suggestions above")

    return RejectionMessage(
        title=template["title"],
        explanation=template["explanation"],
        suggestions=suggestions,
        contact_info=_get_contact_info(),
        category=category,
        severity=final_severity,  # type: ignore
    )


def _get_contact_info() -> str:
    """
    Get contact information for false positive reports.

    Returns:
        Contact information string
    """
    return (
        "If you believe this is a false positive, please report it at:\n"
        "https://github.com/AndyMik90/Auto-Claude/issues\n"
        "Include your task description (redacted if sensitive) for analysis."
    )


# =============================================================================
# MESSAGE FORMATTING
# =============================================================================


def format_for_terminal(message: RejectionMessage, use_colors: bool = True) -> str:
    """
    Format rejection message for terminal output with ANSI colors.

    Args:
        message: The rejection message to format
        use_colors: Whether to use ANSI color codes (default: True)

    Returns:
        Formatted string for terminal display
    """
    lines = []

    # ANSI color codes
    if use_colors:
        RED = "\033[91m"
        YELLOW = "\033[93m"
        BOLD = "\033[1m"
        RESET = "\033[0m"
        DIM = "\033[2m"
    else:
        RED = ""
        YELLOW = ""
        BOLD = ""
        RESET = ""
        DIM = ""

    # Title (color based on severity)
    severity_colors = {
        "critical": RED,
        "high": RED,
        "medium": YELLOW,
        "low": YELLOW,
    }
    color = severity_colors.get(message.severity, YELLOW)

    lines.append(f"\n{color}{BOLD}⚠️  {message.title}{RESET}\n")
    lines.append(f"{DIM}{message.explanation}{RESET}\n")

    # Suggestions
    if message.suggestions:
        lines.append(f"{BOLD}Suggestions:{RESET}")
        for i, suggestion in enumerate(message.suggestions, 1):
            lines.append(f"  {i}. {suggestion}")
        lines.append("")

    # Contact info
    lines.append(f"{DIM}{message.contact_info}{RESET}")

    return "\n".join(lines)


def format_for_plain(message: RejectionMessage) -> str:
    """
    Format rejection message as plain text without formatting.

    Args:
        message: The rejection message to format

    Returns:
        Plain text string
    """
    lines = []

    lines.append(f"\n{message.title}\n")
    lines.append(f"{message.explanation}\n")

    if message.suggestions:
        lines.append("Suggestions:")
        for i, suggestion in enumerate(message.suggestions, 1):
            lines.append(f"  {i}. {suggestion}")
        lines.append("")

    lines.append(message.contact_info)

    return "\n".join(lines)


def format_for_ui(message: RejectionMessage) -> dict:
    """
    Format rejection message as structured data for UI rendering.

    Args:
        message: The rejection message to format

    Returns:
        Dictionary with structured message data
    """
    return {
        "title": message.title,
        "explanation": message.explanation,
        "suggestions": message.suggestions,
        "contact_info": message.contact_info,
        "category": message.category.value,
        "severity": message.severity,
        "display_style": _get_ui_display_style(message.severity),
    }


def _get_ui_display_style(severity: str) -> str:
    """
    Get the UI display style based on severity.

    Args:
        severity: Severity level

    Returns:
        UI display style string (error, warning, info)
    """
    severity_styles = {
        "critical": "error",
        "high": "error",
        "medium": "warning",
        "low": "info",
    }
    return severity_styles.get(severity, "info")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def get_user_friendly_rejection(
    category: str = "general",
    severity: str | None = None,
    output_format: OutputFormat = OutputFormat.TERMINAL,
    use_colors: bool = True,
) -> str | dict:
    """
    Get a formatted rejection message for user display.

    This is a convenience function that combines message generation
    and formatting in one call.

    Args:
        category: The category of rejection
        severity: Severity level (overrides default)
        output_format: How to format the output (terminal, plain, ui)
        use_colors: Whether to use colors in terminal format

    Returns:
        Formatted message (string or dict based on output_format)

    Example:
        >>> # Get terminal message
        >>> print(get_user_friendly_rejection("shell_injection"))

        >>> # Get UI structured message
        >>> ui_msg = get_user_friendly_rejection(
        ...     "instruction_override",
        ...     output_format="ui"
        ... )
    """
    message = get_rejection_message(category=category, severity=severity)

    if output_format == OutputFormat.TERMINAL:
        return format_for_terminal(message, use_colors=use_colors)
    elif output_format == OutputFormat.PLAIN:
        return format_for_plain(message)
    elif output_format == OutputFormat.UI:
        return format_for_ui(message)
    else:
        # Default to terminal
        return format_for_terminal(message, use_colors=use_colors)


def get_suggestions_for_category(category: str) -> list[str]:
    """
    Get suggestions for a specific category.

    Useful for displaying inline suggestions without full message.

    Args:
        category: The category to get suggestions for

    Returns:
        List of suggestion strings
    """
    try:
        cat_enum = MessageCategory(category)
    except ValueError:
        cat_enum = MessageCategory.GENERAL

    template = MESSAGE_TEMPLATES.get(cat_enum, MESSAGE_TEMPLATES[MessageCategory.GENERAL])
    return template["suggestions"].copy()
