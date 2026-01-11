"""
Write Tool Validator
====================

Validates Write tool operations to catch dangerous file writes.
Checks file paths for system directories and content for secrets/malware patterns.

This validator:
- Blocks writes to system directories (/etc, /usr, /bin, etc.)
- Blocks writes to authentication files (.ssh/authorized_keys, /etc/passwd)
- Detects and warns on potential secret exposure in file content
- Blocks writes that would overwrite critical config files
"""

from typing import Any

from ..models import OutputValidationConfig, ToolType, ValidationResult
from ..pattern_detector import PatternDetector


async def validate_write(
    tool_input: dict[str, Any],
    detector: PatternDetector,
    config: OutputValidationConfig,
) -> ValidationResult:
    """
    Validate Write tool operation against dangerous patterns.

    Performs comprehensive validation of Write tool operations by checking:
    1. File path validation: Blocks writes to system directories, sensitive files
    2. File content validation: Detects secrets, malware indicators, code injection

    Validation priorities:
    - P0 (CRITICAL): System directories, /etc/passwd, /etc/shadow, sudoers, SSH keys
    - P0 (CRITICAL): API keys, AWS keys, private keys in content
    - P1 (HIGH): SSH config, crontab, /etc/hosts, eval/exec patterns
    - P1 (HIGH): Base64 decode exec, reverse shells
    - P2 (MEDIUM): .env files, crypto miners

    Args:
        tool_input: Must contain "file_path" and optionally "content" keys
            - file_path: Absolute or relative path to file being written
            - content: Content being written to the file (optional)
        detector: PatternDetector instance with loaded validation rules
        config: OutputValidationConfig for project-specific settings

    Returns:
        ValidationResult with decision:
        - is_blocked=True if dangerous pattern detected
        - is_blocked=False if operation is safe

    Examples:
        >>> # Block write to system directory
        >>> result = await validate_write(
        ...     tool_input={"file_path": "/etc/passwd", "content": "..."},
        ...     detector=detector,
        ...     config=config
        ... )
        >>> assert result.is_blocked == True
        >>> assert "system" in result.reason.lower()

        >>> # Block write with API key
        >>> result = await validate_write(
        ...     tool_input={
        ...         "file_path": "/app/config.py",
        ...         "content": "API_KEY=sk-1234567890abcdef"
        ...     },
        ...     detector=detector,
        ...     config=config
        ... )
        >>> assert result.is_blocked == True
        >>> assert "api key" in result.reason.lower()

        >>> # Allow safe write
        >>> result = await validate_write(
        ...     tool_input={
        ...         "file_path": "/app/README.md",
        ...         "content": "# My Project"
        ...     },
        ...     detector=detector,
        ...     config=config
        ... )
        >>> assert result.is_blocked == False
    """
    # Extract file path and content
    file_path = tool_input.get("file_path", "")
    content = tool_input.get("content", "")

    # Validate input structure
    if not isinstance(file_path, str):
        return ValidationResult.blocked(
            rule=None,  # No specific rule, input validation error
            reason=f"file_path must be a string, got {type(file_path).__name__}",
            tool_name="Write",
            tool_input=tool_input,
        )

    if not file_path:
        # Empty file path - allow (likely a tool usage error, not security issue)
        return ValidationResult.allowed()

    if content is not None and not isinstance(content, str):
        return ValidationResult.blocked(
            rule=None,
            reason=f"content must be a string, got {type(content).__name__}",
            tool_name="Write",
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

    # Step 2: Validate file content (if provided)
    # Check for secrets, malware indicators, code injection
    if content:
        content_result = await _validate_file_content(
            content=content,
            file_path=file_path,
            detector=detector,
            config=config,
            tool_input=tool_input,
        )

        if content_result.is_blocked:
            # File content is dangerous
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

    Checks if the file path indicates a write to:
    - System directories (/etc, /usr, /bin, /sbin, /lib, /boot, /sys, /proc)
    - Critical system files (/etc/passwd, /etc/shadow, /etc/sudoers)
    - SSH authorization files (~/.ssh/authorized_keys, ~/.ssh/config)
    - System cron files (/etc/crontab, /etc/cron.*)
    - Other user home directories (potential privilege escalation)

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
        tool_type=ToolType.WRITE,
        content=file_path,
        context="file_path",
        tool_input=tool_input,
        config=config,
    )

    return result


async def _validate_file_content(
    content: str,
    file_path: str,
    detector: PatternDetector,
    config: OutputValidationConfig,
    tool_input: dict[str, Any],
) -> ValidationResult:
    """
    Validate file content for dangerous patterns.

    Checks if the content contains:
    - Secrets: API keys, AWS keys, private keys, passwords
    - Malware indicators: eval/exec, base64 decode exec, reverse shells
    - Resource abuse: Crypto miners, browser mining scripts
    - Code injection patterns

    Args:
        content: File content to validate
        file_path: Associated file path (for context)
        detector: PatternDetector instance
        config: Validation configuration
        tool_input: Original tool input (for logging)

    Returns:
        ValidationResult with decision
    """
    # Use pattern detector to check content against FILE_WRITE_RULES
    result = detector.match(
        tool_type=ToolType.WRITE,
        content=content,
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
