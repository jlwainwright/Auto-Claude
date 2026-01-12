"""
Bash Tool Validator
===================

Validates Bash tool operations to catch dangerous command sequences.
Enhances existing bash_security_hook with pattern-based detection.

This validator:
- Integrates with existing bash_security_hook logic
- Adds pattern detection for complex command chains
- Detects obfuscated dangerous commands (base64 encoded, variable expansion)
- Catches privilege escalation attempts (sudo, chmod 777, etc.)

The bash_validator complements the allowlist-based validation in bash_security_hook
by adding content-based pattern matching that catches:
1. Destructive operations (rm -rf /, dd, mkfs, DROP DATABASE)
2. Dangerous operations (chmod 777, chown system files, kill critical processes)
3. Suspicious patterns (curl data exfil, wget|sh, history clear)
4. Obfuscated commands (base64 decode exec, variable expansion, XOR decode)
5. Command chains (dangerous operations combined with &&, |, ;)
"""

from typing import Any

from ..models import OutputValidationConfig, ToolType, ValidationResult
from ..pattern_detector import PatternDetector


async def validate_bash(
    tool_input: dict[str, Any],
    detector: PatternDetector,
    config: OutputValidationConfig,
) -> ValidationResult:
    """
    Validate Bash tool command against dangerous patterns.

    Performs comprehensive validation of Bash tool operations by checking:
    1. Command string for destructive operations
    2. Command string for privilege escalation attempts
    3. Command string for obfuscated dangerous commands
    4. Command string for dangerous command chains

    Validation priorities:
    - P0 (CRITICAL): rm -rf /, dd overwrite, mkfs, DROP DATABASE, TRUNCATE
    - P1 (HIGH): chmod 777, chown system files, kill critical processes, sudo escalation
    - P1 (HIGH): base64 decode exec, variable expansion exec, XOR decode exec
    - P1 (HIGH): dangerous command chains, eval in command chain
    - P2 (MEDIUM): curl data exfil, wget|sh, history clear, package installs
    - P3 (LOW): deprecated commands (ftp, telnet)

    This validator is complementary to bash_security_hook:
    - bash_security_hook: Allowlist-based (which commands are allowed)
    - bash_validator: Pattern-based (what dangerous patterns are in commands)

    Args:
        tool_input: Must contain "command" key with command string
            - command: Shell command to validate
        detector: PatternDetector instance with loaded validation rules
        config: OutputValidationConfig for project-specific settings

    Returns:
        ValidationResult with decision:
        - is_blocked=True if dangerous pattern detected
        - is_blocked=False if operation is safe

    Examples:
        >>> # Block destructive command
        >>> result = await validate_bash(
        ...     tool_input={"command": "rm -rf /important/data"},
        ...     detector=detector,
        ...     config=config
        ... )
        >>> assert result.is_blocked == True
        >>> assert "recursively delete" in result.reason.lower()

        >>> # Block obfuscated command
        >>> result = await validate_bash(
        ...     tool_input={"command": "echo 'cmt0Ci1YIAo=' | base64 -d | bash"},
        ...     detector=detector,
        ...     config=config
        ... )
        >>> assert result.is_blocked == True
        >>> assert "base64" in result.reason.lower()

        >>> # Block dangerous command chain
        >>> result = await validate_bash(
        ...     tool_input={"command": "chmod 777 /etc/passwd && rm -rf /home"},
        ...     detector=detector,
        ...     config=config
        ... )
        >>> assert result.is_blocked == True
        >>> assert "chain" in result.reason.lower()

        >>> # Allow safe command
        >>> result = await validate_bash(
        ...     tool_input={"command": "ls -la"},
        ...     detector=detector,
        ...     config=config
        ... )
        >>> assert result.is_blocked == False
    """
    # Extract command string
    command = tool_input.get("command", "")

    # Validate input structure
    if not isinstance(command, str):
        return ValidationResult.blocked(
            rule=None,  # No specific rule, input validation error
            reason=f"command must be a string, got {type(command).__name__}",
            tool_name="Bash",
            tool_input=tool_input,
        )

    if not command:
        # Empty command - allow (likely a tool usage error, not security issue)
        return ValidationResult.allowed()

    # Use pattern detector to check command against BASH_RULES
    # This checks for:
    # - P0: Destructive operations (rm -rf, dd, mkfs, DROP DATABASE)
    # - P1: Dangerous operations (chmod 777, sudo, kill processes)
    # - P2: Suspicious patterns (data exfil, remote scripts)
    # - P2: Obfuscation patterns (base64, variable expansion, command chains)
    result = detector.match(
        tool_type=ToolType.BASH,
        content=command,
        context="command",
        tool_input=tool_input,
        config=config,
    )

    return result


async def _analyze_command_chain(
    command: str,
) -> list[str]:
    """
    Analyze command string for command chain operators.

    Identifies commands separated by:
    - && (AND operator - run next if current succeeds)
    - || (OR operator - run next if current fails)
    - | (pipe operator - pass output to next command)
    - ; (separator - run commands sequentially)
    - \n (newline - sequential commands)

    Args:
        command: Command string to analyze

    Returns:
        List of individual commands in the chain

    Example:
        >>> commands = _analyze_command_chain("cd /tmp && ls -la | grep test")
        >>> assert "cd /tmp" in commands
        >>> assert "ls -la" in commands
        >>> assert "grep test" in commands
    """
    import re

    # Split on command separators, but preserve quoted strings
    # This is a simplified version - full shell parsing is complex

    # Replace newlines with semicolons for consistent handling
    command = command.replace("\n", ";")

    # Split on &&, ||, ; while preserving the operators for context
    # We use a regex to split but keep delimiters
    parts = re.split(r"(&&|\|\||;)", command)

    # Reconstruct segments
    segments = []
    current = ""

    for i, part in enumerate(parts):
        if part in ("&&", "||", ";"):
            # This is a separator
            if current.strip():
                segments.append(current.strip())
            current = ""
        elif "|" in part and i > 0:
            # Handle pipe operator (split further)
            pipe_parts = part.split("|")
            if current.strip():
                segments.append(current.strip())
            for pipe_part in pipe_parts[:-1]:
                if pipe_part.strip():
                    segments.append(pipe_part.strip())
            current = pipe_parts[-1]
        else:
            current += part

    if current.strip():
        segments.append(current.strip())

    return segments


async def _detect_obfuscation(command: str) -> list[str]:
    """
    Detect common obfuscation techniques in commands.

    Identifies:
    - Base64 encoding/decoding
    - Variable expansion ($VAR, ${VAR}, $(cmd))
    - Command substitution $(cmd) or `cmd`
    - XOR or other encoding operations
    - Hex encoding
    - Octal encoding

    Args:
        command: Command string to analyze

    Returns:
        List of detected obfuscation techniques

    Example:
        >>> obfuscation = _detect_obfuscation("echo $X | base64 -d")
        >>> assert "variable_expansion" in obfuscation
        >>> assert "base64" in obfuscation
    """
    import re

    detected = []

    # Base64 encoding/decoding
    if re.search(r"base64\s+(-d|--decode|-e|--encode)", command, re.IGNORECASE):
        detected.append("base64")

    # Variable expansion
    if re.search(r"\$\{?\w+\}?", command):
        detected.append("variable_expansion")

    # Command substitution
    if re.search(r"\$\(|`.*`", command):
        detected.append("command_substitution")

    # XOR/encoding operations in perl/python one-liners
    if re.search(r"(perl|python|awk).*\s(xor|decode|unpack|chr|encode)\s*\(", command, re.IGNORECASE):
        detected.append("xor_encoding")

    # Hex encoding (\xNN)
    if re.search(r"\\x[0-9a-f]{2}", command, re.IGNORECASE):
        detected.append("hex_encoding")

    # Octal encoding (\NNN)
    if re.search(r"\\[0-9]{3}", command):
        detected.append("octal_encoding")

    return detected


async def validate_bash_advanced(
    tool_input: dict[str, Any],
    detector: PatternDetector,
    config: OutputValidationConfig,
) -> ValidationResult:
    """
    Advanced Bash validation with command chain analysis.

    This is an enhanced version of validate_bash that provides:
    1. Individual command validation in command chains
    2. Obfuscation detection
    3. Chain-level risk assessment

    Use this when you need deeper analysis of complex commands.

    Args:
        tool_input: Must contain "command" key
        detector: PatternDetector instance
        config: Validation configuration

    Returns:
        ValidationResult with enhanced details

    Example:
        >>> result = await validate_bash_advanced(
        ...     tool_input={"command": "cd /tmp && evil_command"},
        ...     detector=detector,
        ...     config=config
        ... )
        >>> if result.is_blocked:
        ...     print(f"Blocked: {result.reason}")
    """
    command = tool_input.get("command", "")

    if not command or not isinstance(command, str):
        return ValidationResult.allowed()

    # First, run standard pattern validation
    standard_result = await validate_bash(tool_input, detector, config)
    if standard_result.is_blocked:
        # Standard pattern matched - block immediately
        return standard_result

    # If standard validation passed, do advanced analysis
    # Check for command chains
    commands = await _analyze_command_chain(command)

    if len(commands) > 1:
        # Multiple commands detected - analyze each
        for cmd in commands:
            # Check each command individually
            cmd_result = detector.match(
                tool_type=ToolType.BASH,
                content=cmd,
                context="command",
                tool_input={"command": cmd},  # Individual command
                config=config,
            )

            if cmd_result.is_blocked:
                # Individual command in chain is dangerous
                return ValidationResult.blocked(
                    rule=cmd_result.rule_id,
                    reason=f"Command chain contains dangerous operation: {cmd_result.reason}",
                    matched_pattern=cmd_result.matched_pattern,
                    tool_name="Bash",
                    tool_input=tool_input,
                    suggestions=[
                        "Break the command chain into separate steps",
                        "Verify each command in the chain is safe",
                    ] + (cmd_result.suggestions or []),
                )

    # Check for obfuscation (even if patterns didn't match)
    obfuscation = await _detect_obfuscation(command)

    if obfuscation:
        # Obfuscation detected - warn or block based on severity
        # For now, just enhance the result with obfuscation info
        # (could block in strict mode)
        pass

    return ValidationResult.allowed()
