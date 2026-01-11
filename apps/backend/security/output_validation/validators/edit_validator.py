"""
Edit Tool Validator
===================

Validates Edit tool operations to catch dangerous file modifications.
Checks file paths for system directories and new content for malicious patterns.

This validator:
- Blocks edits to system directories (/etc, /usr, /bin, etc.)
- Detects code injection patterns (eval, exec, __import__)
- Blocks changes that would disable security features
- Warns on changes to security-sensitive files (.env, config.json)
"""

from typing import Any

from ..models import OutputValidationConfig, ToolType, ValidationResult
from ..pattern_detector import PatternDetector


async def validate_edit(
    tool_input: dict[str, Any],
    detector: PatternDetector,
    config: OutputValidationConfig,
) -> ValidationResult:
    """
    Validate Edit tool operation against dangerous patterns.

    Performs comprehensive validation of Edit tool operations by checking:
    1. File path validation: Blocks edits to system directories, sensitive files
    2. New content validation: Detects secrets, code injection, security disabling

    Validation priorities:
    - P0 (CRITICAL): System directories, /etc/passwd, sudoers, SSH keys
    - P0 (CRITICAL): API keys, AWS keys, private keys in new_string
    - P1 (HIGH): Security disabling patterns, eval/exec in new_string
    - P1 (HIGH): Base64 decode exec, reverse shells
    - P2 (MEDIUM): .env files, crypto miners

    Args:
        tool_input: Must contain "file_path" and "new_string" keys
            - file_path: Absolute or relative path to file being edited
            - old_string: The string to be replaced (optional)
            - new_string: The replacement content
            - replace_all: Whether to replace all occurrences (optional)
        detector: PatternDetector instance with loaded validation rules
        config: OutputValidationConfig for project-specific settings

    Returns:
        ValidationResult with decision:
        - is_blocked=True if dangerous pattern detected
        - is_blocked=False if operation is safe

    Examples:
        >>> # Block edit to system file
        >>> result = await validate_edit(
        ...     tool_input={"file_path": "/etc/passwd", "new_string": "..."},
        ...     detector=detector,
        ...     config=config
        ... )
        >>> assert result.is_blocked == True
        >>> assert "system" in result.reason.lower()

        >>> # Block edit injecting eval
        >>> result = await validate_edit(
        ...     tool_input={
        ...         "file_path": "/app/config.py",
        ...         "old_string": "safe_code",
        ...         "new_string": "eval(malicious_code)"
        ...     },
        ...     detector=detector,
        ...     config=config
        ... )
        >>> assert result.is_blocked == True
        >>> assert "eval" in result.reason.lower()

        >>> # Allow safe edit
        >>> result = await validate_edit(
        ...     tool_input={
        ...         "file_path": "/app/README.md",
        ...         "old_string": "Old text",
        ...         "new_string": "New text"
        ...     },
        ...     detector=detector,
        ...     config=config
        ... )
        >>> assert result.is_blocked == False
    """
    # Extract file path and new content
    file_path = tool_input.get("file_path", "")
    new_string = tool_input.get("new_string", "")
    old_string = tool_input.get("old_string", "")

    # Validate input structure
    if not isinstance(file_path, str):
        return ValidationResult.blocked(
            rule=None,  # No specific rule, input validation error
            reason=f"file_path must be a string, got {type(file_path).__name__}",
            tool_name="Edit",
            tool_input=tool_input,
        )

    if not file_path:
        # Empty file path - allow (likely a tool usage error, not security issue)
        return ValidationResult.allowed()

    if new_string is not None and not isinstance(new_string, str):
        return ValidationResult.blocked(
            rule=None,
            reason=f"new_string must be a string, got {type(new_string).__name__}",
            tool_name="Edit",
            tool_input=tool_input,
        )

    # Step 1: Validate file path (P0 rules - system directories and critical files)
    path_result = await _validate_file_path(
        file_path=file_path,
        detector=detector,
        config=config,
        tool_input=tool_input,
    )

    if path_result.is_blocked:
        # File path is dangerous - block immediately
        return path_result

    # Step 2: Validate new content (if provided)
    # Check for secrets, code injection, security disabling
    if new_string:
        content_result = await _validate_new_content(
            new_string=new_string,
            file_path=file_path,
            old_string=old_string,
            detector=detector,
            config=config,
            tool_input=tool_input,
        )

        if content_result.is_blocked:
            # New content is dangerous
            return content_result

    # All checks passed - allow the operation
    return ValidationResult.allowed()


async def _validate_file_path(
    file_path: str,
    detector: PatternDetector,
    config: OutputValidationConfig,
    tool_input: dict[str, Any],
) -> ValidationResult:
    """
    Validate file path for dangerous patterns.

    Checks if the file path indicates an edit to:
    - System directories (/etc, /usr, /bin, /sbin, /lib, /boot, /sys, /proc)
    - Critical system files (/etc/passwd, /etc/shadow, /etc/sudoers)
    - SSH authorization files (~/.ssh/authorized_keys, ~/.ssh/config)
    - System cron files (/etc/crontab, /etc/cron.*)
    - Security-sensitive files (.env, config.json)

    Args:
        file_path: File path to validate
        detector: PatternDetector instance
        config: Validation configuration
        tool_input: Original tool input (for logging)

    Returns:
        ValidationResult with decision
    """
    # Use pattern detector to check file path against FILE_PATH_RULES
    result = detector.match(
        tool_type=ToolType.EDIT,
        content=file_path,
        context="file_path",
        tool_input=tool_input,
        config=config,
    )

    return result


async def _validate_new_content(
    new_string: str,
    file_path: str,
    old_string: str,
    detector: PatternDetector,
    config: OutputValidationConfig,
    tool_input: dict[str, Any],
) -> ValidationResult:
    """
    Validate new content for dangerous patterns.

    Checks if the new_string contains:
    - Secrets: API keys, AWS keys, private keys, passwords
    - Code injection: eval/exec/__import__ patterns
    - Security disabling: Patterns that disable validations or security features
    - Malware indicators: base64 decode exec, reverse shells
    - Resource abuse: Crypto miners, browser mining scripts

    Args:
        new_string: New content being added
        file_path: Associated file path (for context)
        old_string: Old string being replaced (for context)
        detector: PatternDetector instance
        config: Validation configuration
        tool_input: Original tool input (for logging)

    Returns:
        ValidationResult with decision
    """
    # Use pattern detector to check content against FILE_WRITE_RULES
    # (which include rules for Edit operations)
    result = detector.match(
        tool_type=ToolType.EDIT,
        content=new_string,
        context="file_content",
        tool_input=tool_input,
        config=config,
    )

    # If blocked, enhance the reason with file path context
    if result.is_blocked:
        # The result already has a good reason from the rule
        # We could enhance it here with file path info if needed
        pass

    return result
