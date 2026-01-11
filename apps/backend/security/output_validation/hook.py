"""
Output Validation Hook
======================

Pre-tool-use hook that validates tool outputs against dangerous patterns.
This is the main entry point for the output validation system.

This hook:
- Validates tool outputs before execution
- Routes to tool-specific validators
- Returns block decision with clear reason when dangerous pattern detected
- Integrates with existing bash_security_hook (extends, doesn't replace)
"""

import logging
from pathlib import Path
from typing import Any

from .models import (
    OutputValidationConfig,
    SeverityLevel,
    ToolType,
    ValidationResult,
)
from .overrides import (
    OverrideTokenManager,
    format_file_scope,
    format_command_scope,
    list_override_tokens,
)
from .pattern_detector import create_pattern_detector
from .rules import get_default_rules


# =============================================================================
# LOGGER
# =============================================================================

logger = logging.getLogger(__name__)


# Global pattern detector instance (lazy loaded)
_detector = None
_config = None


def _get_detector():
    """Get or create the global pattern detector instance."""
    global _detector
    if _detector is None:
        _detector = create_pattern_detector()
        # Load default rules
        _detector.add_rules(get_default_rules())
    return _detector


def _get_config(project_dir: Path | None = None) -> OutputValidationConfig:
    """
    Get validation configuration for the project.

    TODO: In phase 3, this will load from .auto-claude/output-validation.json
    For now, returns default configuration.

    Args:
        project_dir: Optional project directory path

    Returns:
        OutputValidationConfig instance
    """
    global _config
    if _config is None:
        # Use default config for now
        _config = OutputValidationConfig(
            enabled=True,
            strict_mode=False,
        )
    return _config


def _get_override_context(
    tool_type: ToolType,
    tool_input: dict[str, Any],
) -> str | None:
    """
    Get the context string for override token matching.

    Args:
        tool_type: Type of tool being validated
        tool_input: Tool input parameters

    Returns:
        Context string (e.g., "file:/path", "command:pattern") or None
    """
    if tool_type == ToolType.WRITE or tool_type == ToolType.EDIT:
        file_path = tool_input.get("file_path", "")
        if file_path:
            return format_file_scope(file_path)

    elif tool_type == ToolType.BASH:
        command = tool_input.get("command", "")
        if command:
            return format_command_scope(command)

    # For other tool types, return None (context-agnostic tokens only)
    return None


def _check_override_tokens(
    rule_id: str,
    tool_type: ToolType,
    tool_input: dict[str, Any],
    project_dir: Path | None,
) -> tuple[bool, str | None]:
    """
    Check if there's a valid override token for the blocked operation.

    Args:
        rule_id: ID of the rule that was triggered
        tool_type: Type of tool being validated
        tool_input: Tool input parameters
        project_dir: Project directory path

    Returns:
        Tuple of (should_allow, token_id_used)
        - should_allow: True if valid token found and used
        - token_id_used: ID of the token used (or None)
    """
    if not project_dir:
        # No project directory, can't check tokens
        return False, None

    try:
        # Get context for token matching
        context = _get_override_context(tool_type, tool_input)

        # List all valid tokens for this rule
        tokens = list_override_tokens(
            project_dir=project_dir,
            rule_id=rule_id,
            include_expired=False,
        )

        if not tokens:
            logger.debug(f"No override tokens found for rule: {rule_id}")
            return False, None

        # Try to find a token that applies to this context
        manager = OverrideTokenManager(project_dir)

        for token in tokens:
            # Check if token applies to the context
            if context and not token.applies_to(context):
                logger.debug(
                    f"Token {token.token_id} does not apply to context: {context}"
                )
                continue

            # Token applies - use it
            if manager.validate_and_use_token(
                token_id=token.token_id,
                rule_id=rule_id,
                context=context or "",
            ):
                logger.info(
                    f"Override token used: {token.token_id} "
                    f"for rule {rule_id}, "
                    f"context={context or 'all'}, "
                    f"reason={token.reason or 'N/A'}"
                )
                return True, token.token_id

        # No applicable token found
        logger.debug(f"No applicable override token for rule: {rule_id}, context: {context}")
        return False, None

    except Exception as e:
        # If override checking fails, fail safe by blocking
        logger.error(f"Error checking override tokens: {e}")
        return False, None


async def output_validation_hook(
    input_data: dict[str, Any],
    tool_use_id: str | None = None,
    context: Any | None = None,
) -> dict[str, Any]:
    """
    Pre-tool-use hook that validates tool outputs against dangerous patterns.

    This hook runs before tool execution and blocks operations that match
    dangerous patterns defined in the validation rules.

    Hook signature matches Claude Agent SDK PreToolUse hook requirements:
    - Takes input_data with tool_name and tool_input
    - Returns {} to allow, or {"decision": "block", "reason": "..."} to block

    Integration with bash_security_hook:
    - This hook runs BEFORE bash_security_hook for Bash commands
    - bash_security_hook handles allowlist validation
    - This hook handles pattern-based validation (complementary)

    Args:
        input_data: Dict containing tool_name and tool_input
            - tool_name: Name of the tool being called (e.g., "Bash", "Write")
            - tool_input: Dict of input parameters for the tool
            - cwd: Optional current working directory
        tool_use_id: Optional tool use ID from SDK
        context: Optional context (can contain project_dir, spec_dir, etc.)

    Returns:
        Empty dict {} to allow the operation, or
        {"decision": "block", "reason": "...", "rule_id": "..."} to block

    Example:
        # Block dangerous command
        result = await output_validation_hook({
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"}
        })
        # Returns: {"decision": "block", "reason": "This command would..."}

        # Allow safe command
        result = await output_validation_hook({
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"}
        })
        # Returns: {}
    """
    # Extract tool information
    tool_name = input_data.get("tool_name")
    tool_input = input_data.get("tool_input")

    # Validate tool_input structure
    if not isinstance(tool_input, dict):
        return {
            "decision": "block",
            "reason": f"tool_input must be dict, got {type(tool_input).__name__}",
        }

    # Get project directory from context or input
    project_dir = None
    if context and hasattr(context, "project_dir"):
        project_dir = context.project_dir
    elif context and isinstance(context, dict):
        project_dir = context.get("project_dir")

    # Also check input_data for cwd (current working directory)
    # The SDK passes this when client is created with cwd parameter
    if not project_dir:
        project_dir = input_data.get("cwd")

    if project_dir and isinstance(project_dir, str):
        project_dir = Path(project_dir)

    # Get validation configuration
    config = _get_config(project_dir)

    # Check if validation is enabled
    if not config.enabled:
        return {}

    # Get pattern detector
    detector = _get_detector()

    # Route to tool-specific validator
    try:
        tool_type = _get_tool_type(tool_name)
        if tool_type is None:
            # Tool not supported by validation - allow
            return {}

        # Validate based on tool type
        result = await _validate_tool(
            tool_type=tool_type,
            tool_name=tool_name,
            tool_input=tool_input,
            detector=detector,
            config=config,
        )

        if result.is_blocked:
            # Check for override tokens before blocking
            should_allow, token_id = _check_override_tokens(
                rule_id=result.rule_id or "",
                tool_type=tool_type,
                tool_input=tool_input,
                project_dir=project_dir,
            )

            if should_allow:
                # Override token found and used - allow the operation
                logger.info(
                    f"Operation allowed via override token: {token_id} "
                    f"for rule {result.rule_id}"
                )
                return {}

            # No override token - block the operation
            return {
                "decision": "block",
                "reason": result.reason,
                "rule_id": result.rule_id,
                "severity": result.severity.value if result.severity else None,
                "suggestions": result.suggestions,
            }

        # Allow the operation
        return {}

    except Exception as e:
        # If validation fails, fail safe by blocking
        # This ensures that errors don't bypass security
        return {
            "decision": "block",
            "reason": f"Validation error: {str(e)}",
        }


def _get_tool_type(tool_name: str | None) -> ToolType | None:
    """
    Convert SDK tool name to ToolType enum.

    Args:
        tool_name: Tool name from SDK (e.g., "Bash", "Write", "Edit")

    Returns:
        ToolType enum value, or None if tool not supported
    """
    if tool_name is None:
        return None

    tool_name_map = {
        "Bash": ToolType.BASH,
        "Write": ToolType.WRITE,
        "Edit": ToolType.EDIT,
        "Read": ToolType.READ,
        "WebFetch": ToolType.WEB_FETCH,
        "WebSearch": ToolType.WEB_SEARCH,
    }

    return tool_name_map.get(tool_name)


async def _validate_tool(
    tool_type: ToolType,
    tool_name: str,
    tool_input: dict[str, Any],
    detector,
    config: OutputValidationConfig,
) -> ValidationResult:
    """
    Validate a tool call against dangerous patterns.

    Routes to tool-specific validation logic based on tool type.

    TODO: In phase 2, this will route to dedicated validators:
    - validators/bash_validator.py
    - validators/write_validator.py
    - validators/edit_validator.py

    For now, implements inline validation using pattern_detector.

    Args:
        tool_type: Type of tool being validated
        tool_name: Name of the tool from SDK
        tool_input: Tool input parameters
        detector: PatternDetector instance
        config: Validation configuration

    Returns:
        ValidationResult with decision
    """
    # Route to tool-specific validation
    if tool_type == ToolType.BASH:
        return await _validate_bash(tool_input, detector, config)
    elif tool_type == ToolType.WRITE:
        return await _validate_write(tool_input, detector, config)
    elif tool_type == ToolType.EDIT:
        return await _validate_edit(tool_input, detector, config)
    elif tool_type == ToolType.WEB_FETCH:
        return await _validate_web_fetch(tool_input, detector, config)
    elif tool_type == ToolType.WEB_SEARCH:
        return await _validate_web_search(tool_input, detector, config)
    else:
        # Tool type not supported for validation
        return ValidationResult.allowed()


async def _validate_bash(
    tool_input: dict[str, Any],
    detector,
    config: OutputValidationConfig,
) -> ValidationResult:
    """
    Validate Bash tool command against dangerous patterns.

    Checks the command string for destructive operations, privilege escalation,
    data exfiltration, and other dangerous patterns.

    Args:
        tool_input: Must contain "command" key with command string
        detector: PatternDetector instance
        config: Validation configuration

    Returns:
        ValidationResult
    """
    command = tool_input.get("command", "")

    if not command:
        return ValidationResult.allowed()

    # Validate command against patterns
    result = detector.match(
        tool_type=ToolType.BASH,
        content=command,
        context="command",
        tool_input=tool_input,
        config=config,
    )

    return result


async def _validate_write(
    tool_input: dict[str, Any],
    detector,
    config: OutputValidationConfig,
) -> ValidationResult:
    """
    Validate Write tool operation against dangerous patterns.

    Checks both file path and file content for dangerous patterns:
    - File path: Writes to system directories, sensitive files
    - File content: Secrets, malware indicators, code injection

    Args:
        tool_input: Must contain "file_path" and "content" keys
        detector: PatternDetector instance
        config: Validation configuration

    Returns:
        ValidationResult
    """
    file_path = tool_input.get("file_path", "")
    content = tool_input.get("content", "")

    if not file_path:
        return ValidationResult.allowed()

    # Check file path first (P0 rules)
    path_result = detector.match(
        tool_type=ToolType.WRITE,
        content=file_path,
        context="file_path",
        tool_input=tool_input,
        config=config,
    )

    if path_result.is_blocked:
        return path_result

    # Check file content if provided
    if content:
        content_result = detector.match(
            tool_type=ToolType.WRITE,
            content=content,
            context="file_content",
            tool_input=tool_input,
            config=config,
        )

        if content_result.is_blocked:
            return content_result

    return ValidationResult.allowed()


async def _validate_edit(
    tool_input: dict[str, Any],
    detector,
    config: OutputValidationConfig,
) -> ValidationResult:
    """
    Validate Edit tool operation against dangerous patterns.

    Checks file path and both old_string/new_string content for:
    - System file modifications
    - Code injection patterns
    - Secret exposure

    Args:
        tool_input: Must contain "file_path", "old_string", "new_string" keys
        detector: PatternDetector instance
        config: Validation configuration

    Returns:
        ValidationResult
    """
    file_path = tool_input.get("file_path", "")
    old_string = tool_input.get("old_string", "")
    new_string = tool_input.get("new_string", "")

    if not file_path:
        return ValidationResult.allowed()

    # Check file path first
    path_result = detector.match(
        tool_type=ToolType.EDIT,
        content=file_path,
        context="file_path",
        tool_input=tool_input,
        config=config,
    )

    if path_result.is_blocked:
        return path_result

    # Check new_string for dangerous patterns (old_string is existing content)
    if new_string:
        content_result = detector.match(
            tool_type=ToolType.EDIT,
            content=new_string,
            context="file_content",
            tool_input=tool_input,
            config=config,
        )

        if content_result.is_blocked:
            return content_result

    return ValidationResult.allowed()


async def _validate_web_fetch(
    tool_input: dict[str, Any],
    detector,
    config: OutputValidationConfig,
) -> ValidationResult:
    """
    Validate WebFetch tool operation against dangerous patterns.

    Checks URL for:
    - Internal IP addresses (SSRF risk)
    - Local file inclusion attempts (file://)
    - Other security concerns

    Args:
        tool_input: Must contain "url" key
        detector: PatternDetector instance
        config: Validation configuration

    Returns:
        ValidationResult
    """
    url = tool_input.get("url", "")

    if not url:
        return ValidationResult.allowed()

    # Validate URL against patterns
    result = detector.match(
        tool_type=ToolType.WEB_FETCH,
        content=url,
        context="all",
        tool_input=tool_input,
        config=config,
    )

    return result


async def _validate_web_search(
    tool_input: dict[str, Any],
    detector,
    config: OutputValidationConfig,
) -> ValidationResult:
    """
    Validate WebSearch tool operation against dangerous patterns.

    Checks query for potential issues (currently minimal validation).

    Args:
        tool_input: Must contain "query" key
        detector: PatternDetector instance
        config: Validation configuration

    Returns:
        ValidationResult
    """
    query = tool_input.get("query", "")

    if not query:
        return ValidationResult.allowed()

    # Validate query against patterns
    result = detector.match(
        tool_type=ToolType.WEB_SEARCH,
        content=query,
        context="all",
        tool_input=tool_input,
        config=config,
    )

    return result


def reset_hook():
    """
    Reset the global hook state.

    Clears the pattern detector and config, allowing them to be reloaded.
    Useful for testing and configuration changes.
    """
    global _detector, _config
    _detector = None
    _config = None
