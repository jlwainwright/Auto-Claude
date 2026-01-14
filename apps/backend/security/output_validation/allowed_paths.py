"""
Allowed Paths Configuration
============================

Module for managing and checking allowed paths that bypass certain validation rules.
Projects can define path patterns that are excluded from validation checks, useful for:
- Test directories (tests/**, test_*.py)
- Build outputs (build/**, dist/**, *.egg-info/)
- Generated files (.git/**, node_modules/**, __pycache__/**)
- Temporary directories (tmp/**, temp/**)

This module provides:
- AllowedPathsChecker: Main class for checking path allowlist
- is_path_allowed(): Check if a path matches allowed patterns
- get_allowed_paths(): Get resolved list of allowed path patterns
- compile_glob_patterns(): Pre-compile glob patterns for efficient matching

Allowed paths are checked BEFORE pattern detection, providing a fast-path
for known safe directories.

Usage:
    from security.output_validation.allowed_paths import (
        AllowedPathsChecker,
        is_path_allowed,
    )
    from security.output_validation.config import load_validation_config

    # Load config
    config = load_validation_config(project_dir=Path("/project"))

    # Check if a path is allowed
    if is_path_allowed(
        file_path="tests/test_foo.py",
        project_dir=Path("/project"),
        config=config
    ):
        print("Path is in allowlist - skipping validation")

    # Or use the checker class for repeated checks
    checker = AllowedPathsChecker(project_dir=Path("/project"), config=config)
    if checker.is_allowed("tests/test_foo.py"):
        print("Path allowed")
"""

from __future__ import annotations

import logging
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

from .config import OutputValidationConfig

# =============================================================================
# LOGGER
# =============================================================================

logger = logging.getLogger(__name__)


# =============================================================================
# ALLOWED PATHS CHECKER
# =============================================================================

class AllowedPathsChecker:
    """
    Checks if file paths match allowed path patterns from project config.

    This class provides efficient path matching against glob patterns
    defined in the project's validation configuration. Paths matching
    allowed patterns bypass validation checks.

    Attributes:
        project_dir: Root directory of the project
        config: Validation configuration with allowed_paths list
        allowed_patterns: List of compiled glob patterns

    Example:
        >>> config = OutputValidationConfig(
        ...     allowed_paths=["tests/**", "build/**", ".git/**"]
        ... )
        >>> checker = AllowedPathsChecker(
        ...     project_dir=Path("/my/project"),
        ...     config=config
        ... )
        >>> checker.is_allowed("tests/test_api.py")
        True
        >>> checker.is_allowed("/etc/passwd")
        False
    """

    def __init__(
        self,
        project_dir: Path,
        config: OutputValidationConfig,
    ):
        """
        Initialize allowed paths checker.

        Args:
            project_dir: Root directory of the project
            config: Validation configuration containing allowed_paths
        """
        self.project_dir = Path(project_dir).resolve()
        self.config = config
        self.allowed_patterns = self._compile_patterns()

    def _compile_patterns(self) -> list[str]:
        """
        Compile glob patterns from config.

        Resolves relative paths against project directory and prepares
        patterns for matching.

        Returns:
            List of glob patterns ready for fnmatch
        """
        patterns = []

        for pattern in self.config.allowed_paths:
            if not isinstance(pattern, str):
                # Skip invalid patterns
                logger.warning(
                    f"Invalid allowed_paths pattern (not a string): {pattern}"
                )
                continue

            # Resolve relative patterns against project directory
            if not Path(pattern).is_absolute():
                # For relative patterns, we'll match against relative paths
                # No need to resolve to absolute
                patterns.append(pattern)
            else:
                # Keep absolute patterns as-is
                patterns.append(pattern)

        return patterns

    def is_allowed(self, file_path: str) -> bool:
        """
        Check if a file path matches any allowed path pattern.

        This function checks the given file path against all configured
        allowed path patterns. If a match is found, the path bypasses
        validation checks.

        Matching logic:
        - Patterns support Unix shell-style wildcards (*, ?, [seq], [!seq])
        - ** matches any directory level
        - Relative patterns are matched against relative paths
        - Absolute patterns are matched against absolute paths

        Args:
            file_path: File path to check (can be relative or absolute)

        Returns:
            True if path matches an allowed pattern, False otherwise

        Examples:
            >>> config = OutputValidationConfig(
            ...     allowed_paths=["tests/**", "*.tmp", "build/"]
            ... )
            >>> checker = AllowedPathsChecker(Path("/project"), config)
            >>> checker.is_allowed("tests/test_api.py")
            True
            >>> checker.is_allowed("tests/integration/test_user.py")
            True
            >>> checker.is_allowed("build/output.js")
            True
            >>> checker.is_allowed("src/main.py")
            False
            >>> checker.is_allowed("file.tmp")
            True
        """
        if not self.allowed_patterns:
            # No allowed paths configured
            return False

        # Convert to Path object for easier manipulation
        path_obj = Path(file_path)

        # Try matching against both relative and absolute paths
        paths_to_check = self._get_paths_to_check(path_obj)

        # Check each pattern
        for pattern in self.allowed_patterns:
            for check_path in paths_to_check:
                if self._matches_pattern(check_path, pattern):
                    # Log the allowlist usage
                    logger.debug(
                        f"Path '{file_path}' matched allowed pattern '{pattern}' - "
                        "bypassing validation"
                    )
                    return True

        # No match found
        return False

    def _get_paths_to_check(self, path_obj: Path) -> list[str]:
        """
        Get list of path variations to check against patterns.

        This handles the complexity of relative vs absolute paths and
        ensures we match patterns appropriately.

        Args:
            path_obj: Path object to check

        Returns:
            List of path strings to check against patterns
        """
        paths_to_check = []

        # Original path as provided
        paths_to_check.append(str(path_obj))

        # Relative path from project directory (if applicable)
        try:
            if path_obj.is_absolute():
                rel_path = path_obj.relative_to(self.project_dir)
                paths_to_check.append(str(rel_path))
            else:
                # Already relative, try resolving to absolute
                abs_path = (self.project_dir / path_obj).resolve()
                paths_to_check.append(str(abs_path))
        except ValueError:
            # Path is not relative to project directory
            pass

        return paths_to_check

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """
        Check if a path matches a glob pattern.

        Handles complex patterns including:
        - ** for matching multiple directory levels
        - * for matching within a single path component
        - Standard shell glob patterns

        Args:
            path: Path string to check
            pattern: Glob pattern to match against

        Returns:
            True if path matches pattern, False otherwise
        """
        # Handle ** patterns specially
        if "**" in pattern:
            # Convert ** to a regex-like pattern
            # **/ means "zero or more directories"
            # /** means "zero or more directories at end"
            # We'll use fnmatch which handles ** in most implementations
            return fnmatch(path, pattern)

        # Standard glob matching
        return fnmatch(path, pattern)

    def get_allowed_patterns(self) -> list[str]:
        """
        Get the list of allowed path patterns.

        Returns:
            Copy of the allowed patterns list
        """
        return self.allowed_patterns.copy()

    def has_allowed_paths(self) -> bool:
        """
        Check if any allowed paths are configured.

        Returns:
            True if allowed_paths is non-empty, False otherwise
        """
        return len(self.allowed_patterns) > 0


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def is_path_allowed(
    file_path: str,
    project_dir: Path,
    config: OutputValidationConfig,
) -> bool:
    """
    Check if a file path matches allowed path patterns from config.

    This is a convenience function that creates a temporary checker
    instance and performs the check. For repeated checks, use the
    AllowedPathsChecker class directly.

    Args:
        file_path: File path to check
        project_dir: Root directory of the project
        config: Validation configuration

    Returns:
        True if path matches allowed patterns, False otherwise

    Examples:
        >>> config = load_validation_config(project_dir)
        >>> if is_path_allowed("tests/test.py", project_dir, config):
        ...     print("Path is allowed - skip validation")
    """
    checker = AllowedPathsChecker(project_dir, config)
    return checker.is_allowed(file_path)


def get_allowed_paths(
    project_dir: Path,
    config: OutputValidationConfig,
) -> list[str]:
    """
    Get list of allowed path patterns for a project.

    Args:
        project_dir: Root directory of the project
        config: Validation configuration

    Returns:
        List of allowed path patterns
    """
    checker = AllowedPathsChecker(project_dir, config)
    return checker.get_allowed_patterns()


def compile_glob_patterns(patterns: list[str]) -> list[str]:
    """
    Compile and validate glob patterns.

    This function validates that patterns are strings and returns
    a clean list of patterns.

    Args:
        patterns: List of glob patterns to compile

    Returns:
        List of validated patterns

    Raises:
        TypeError: If any pattern is not a string
    """
    compiled = []

    for pattern in patterns:
        if not isinstance(pattern, str):
            raise TypeError(
                f"Allowed path pattern must be string, got {type(pattern).__name__}: {pattern}"
            )

        # Basic pattern validation
        if not pattern or pattern.isspace():
            logger.warning(f"Skipping empty or whitespace pattern: '{pattern}'")
            continue

        compiled.append(pattern)

    return compiled


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def normalize_pattern(pattern: str) -> str:
    """
    Normalize a glob pattern for consistent matching.

    This ensures patterns use forward slashes and removes redundant
    separators.

    Args:
        pattern: Glob pattern to normalize

    Returns:
        Normalized pattern string

    Examples:
        >>> normalize_pattern("tests\\\\**")
        'tests/**'
        >>> normalize_pattern("build//output")
        'build/output'
    """
    # Convert backslashes to forward slashes
    normalized = pattern.replace("\\", "/")

    # Remove duplicate slashes
    while "//" in normalized:
        normalized = normalized.replace("//", "/")

    return normalized


def pattern_to_regex(pattern: str) -> str:
    """
    Convert a glob pattern to a regex pattern (for advanced use cases).

    This is provided for compatibility with regex-based validation systems.
    Most users should use fnmatch-based matching instead.

    Args:
        pattern: Glob pattern to convert

    Returns:
        Regex pattern string

    Examples:
        >>> pattern_to_regex("tests/**/*.py")
        'tests/.*\\.py'
        >>> pattern_to_regex("build/*.js")
        'build/[^/]*\\.js'
    """
    import re

    # First, replace ** with a placeholder (must do this before *)
    # Use a unique placeholder that won't appear in normal paths
    pattern = pattern.replace("**", "\x00DOUBLESTAR\x00")

    # Then replace single * with placeholder
    pattern = pattern.replace("*", "\x00STAR\x00")

    # Replace ? with placeholder
    pattern = pattern.replace("?", "\x00QUESTION\x00")

    # Now escape special regex characters
    regex = re.escape(pattern)

    # Replace placeholders with regex equivalents (in reverse order to avoid partial matches)
    regex = regex.replace("\x00QUESTION\x00", "[^/]")  # ? -> [^/]
    regex = regex.replace("\x00STAR\x00", "[^/]*")  # * -> [^/]*
    regex = regex.replace("\x00DOUBLESTAR\x00", ".*")  # ** -> .*

    return regex
