"""
Tool-Specific Validators
========================

This package contains validators for specific tool types that need
output validation. Each validator is responsible for validating
tool inputs against dangerous patterns.

Built-in Validators:
- write_validator: Validate Write tool operations (file paths and content)
- edit_validator: Validate Edit tool operations (file paths and edits)
- bash_validator: Validate Bash tool operations (commands)

Validator Registry:
This module provides a central registry that maps tool names to their
validators, with support for:
- Lookup validators by tool name
- Unified validation interface
- Custom validator registration
- Iteration over all validators

Example:
    >>> # Get validator for a tool
    >>> validator = get_validator("Bash")
    >>> result = await validator(tool_input, detector, config)
    >>>
    >>> # Or use the unified interface
    >>> result = await validate_tool_output("Bash", tool_input, detector, config)
    >>>
    >>> # Register custom validator
    >>> register_validator("CustomTool", my_validator_function)
"""

from typing import Any, Callable

from ..models import OutputValidationConfig, ToolType, ValidationResult
from ..pattern_detector import PatternDetector
from .bash_validator import validate_bash, validate_bash_advanced
from .edit_validator import validate_edit
from .write_validator import validate_write

# Type alias for validator functions
ValidatorFunc = Callable[
    [dict[str, Any], PatternDetector, OutputValidationConfig],
    ValidationResult,
]

# Central registry mapping tool names to their validators
# Uses ToolType enum values as keys for consistency
TOOL_VALIDATORS: dict[str, ValidatorFunc] = {
    ToolType.BASH.value: validate_bash,
    ToolType.WRITE.value: validate_write,
    ToolType.EDIT.value: validate_edit,
}


def get_validator(tool_name: str) -> ValidatorFunc | None:
    """
    Get validator function for a given tool name.

    Args:
        tool_name: Name of the tool (e.g., "Bash", "Write", "Edit")
            Must match the ToolType enum value

    Returns:
        Validator function if found, None otherwise

    Examples:
        >>> # Get Bash validator
        >>> validator = get_validator("Bash")
        >>> if validator:
        ...     result = await validator(tool_input, detector, config)

        >>> # Get unknown validator (returns None)
        >>> validator = get_validator("UnknownTool")
        >>> assert validator is None
    """
    return TOOL_VALIDATORS.get(tool_name)


def register_validator(
    tool_name: str,
    validator: ValidatorFunc,
    override: bool = False,
) -> None:
    """
    Register a custom validator for a tool.

    This allows projects to add their own validators for custom tools
    or override built-in validators.

    Args:
        tool_name: Name of the tool (must be unique)
        validator: Async validator function with signature:
            (tool_input, detector, config) -> ValidationResult
        override: If True, allow overriding existing validators.
            If False, raises ValueError if tool_name already registered

    Raises:
        ValueError: If tool_name already registered and override=False

    Examples:
        >>> # Register custom validator
        >>> async def my_validator(tool_input, detector, config):
        ...     return ValidationResult.allowed()
        >>>
        >>> register_validator("MyTool", my_validator)
        >>>
        >>> # Override built-in validator (use with caution)
        >>> register_validator("Bash", my_custom_bash_validator, override=True)
    """
    if tool_name in TOOL_VALIDATORS and not override:
        raise ValueError(
            f"Validator for '{tool_name}' already registered. "
            f"Use override=True to replace built-in validators."
        )

    TOOL_VALIDATORS[tool_name] = validator


def unregister_validator(tool_name: str) -> bool:
    """
    Unregister a validator for a tool.

    This is primarily used for testing or to remove custom validators.
    Built-in validators can be unregistered but will be restored on
    process restart.

    Args:
        tool_name: Name of the tool to unregister

    Returns:
        True if validator was removed, False if tool_name not found

    Examples:
        >>> # Remove custom validator
        >>> success = unregister_validator("MyTool")
        >>> assert success == True

        >>> # Try to remove non-existent validator
        >>> success = unregister_validator("UnknownTool")
        >>> assert success == False
    """
    if tool_name in TOOL_VALIDATORS:
        del TOOL_VALIDATORS[tool_name]
        return True
    return False


async def validate_tool_output(
    tool_name: str,
    tool_input: dict[str, Any],
    detector: PatternDetector,
    config: OutputValidationConfig,
) -> ValidationResult:
    """
    Unified interface for validating tool outputs.

    This is the main entry point for tool validation. It looks up the
    appropriate validator for the tool and executes it.

    Args:
        tool_name: Name of the tool being validated (e.g., "Bash", "Write")
        tool_input: Tool input parameters (command, file_path, content, etc.)
        detector: PatternDetector instance with loaded validation rules
        config: OutputValidationConfig for project-specific settings

    Returns:
        ValidationResult with decision:
        - is_blocked=True if dangerous pattern detected
        - is_blocked=False if operation is safe

    Raises:
        ValueError: If no validator found for tool_name

    Examples:
        >>> # Validate Bash command
        >>> result = await validate_tool_output(
        ...     tool_name="Bash",
        ...     tool_input={"command": "rm -rf /data"},
        ...     detector=detector,
        ...     config=config
        ... )
        >>> if result.is_blocked:
        ...     print(f"Blocked: {result.reason}")

        >>> # Validate Write operation
        >>> result = await validate_tool_output(
        ...     tool_name="Write",
        ...     tool_input={"file_path": "/etc/passwd", "content": "..."},
        ...     detector=detector,
        ...     config=config
        ... )
        >>> assert result.is_blocked == True
    """
    validator = get_validator(tool_name)

    if validator is None:
        # No validator found - this could mean:
        # 1. Tool doesn't need validation (e.g., Read tool)
        # 2. Tool is unknown/unregistered
        #
        # For now, allow unknown tools (they're not in our threat model)
        # TODO: Could log a warning for unknown tools
        return ValidationResult.allowed()

    # Execute the validator
    return await validator(tool_input, detector, config)


def list_validators() -> list[str]:
    """
    Get list of all registered tool names.

    Returns:
        List of tool names that have registered validators

    Examples:
        >>> tools = list_validators()
        >>> assert "Bash" in tools
        >>> assert "Write" in tools
        >>> assert "Edit" in tools
    """
    return list(TOOL_VALIDATORS.keys())


def has_validator(tool_name: str) -> bool:
    """
    Check if a validator is registered for a tool.

    Args:
        tool_name: Name of the tool to check

    Returns:
        True if validator is registered, False otherwise

    Examples:
        >>> assert has_validator("Bash") == True
        >>> assert has_validator("Write") == True
        >>> assert has_validator("UnknownTool") == False
    """
    return tool_name in TOOL_VALIDATORS


__all__ = [
    # Built-in validators
    "validate_bash",
    "validate_bash_advanced",
    "validate_edit",
    "validate_write",
    # Registry functions
    "get_validator",
    "register_validator",
    "unregister_validator",
    "validate_tool_output",
    "list_validators",
    "has_validator",
    # Type alias
    "ValidatorFunc",
    # Registry dict (for direct access if needed)
    "TOOL_VALIDATORS",
]
