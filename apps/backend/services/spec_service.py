#!/usr/bin/env python3
"""
Spec Service Module
===================

Provides a structured API for spec creation with input screening.
This service layer wraps the screening logic and returns structured
responses suitable for API endpoints and programmatic use.

This ensures that all spec creation paths (CLI, orchestrator, future REST API)
consistently apply harmlessness screening before processing.

Usage:
    from services.spec_service import SpecService, SpecCreationError
    from pathlib import Path

    service = SpecService(project_dir=Path("/path/to/project"))

    # Validate input before creating spec
    result = service.validate_input(task_description)
    if not result.is_valid:
        print(f"Invalid: {result.error.reason}")

    # Or create a spec with automatic screening
    try:
        spec_info = service.create_spec(
            task_description="Add user authentication",
            metadata={"complexity": "standard"}
        )
    except SpecCreationError as e:
        print(f"Failed: {e.reason} (code: {e.error_code})")

The service integrates with the existing InputScreener module and provides
structured error responses that can be used by:
- CLI commands (spec_runner.py, spec_commands.py)
- Electron frontend (via subprocess output parsing)
- Future REST API endpoints
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from security.input_screener import InputScreener, ScreeningResult, ScreeningVerdict


# =============================================================================
# ERROR CODES
# =============================================================================


class SpecErrorCode(str, Enum):
    """Error codes for spec creation failures."""

    # Security-related errors
    INPUT_REJECTED = "INPUT_REJECTED"
    INPUT_SUSPICIOUS = "INPUT_SUSPICIOUS"
    SCREENING_ERROR = "SCREENING_ERROR"

    # Validation errors
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"

    # General errors
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ValidationError:
    """Detailed validation error information.

    Attributes:
        code: Error code for programmatic handling
        reason: Human-readable error message
        verdict: Screening verdict that caused the error
        detected_patterns: List of patterns that were detected
        confidence: Confidence score of the screening result
        suggestions: List of suggestions for fixing the input
    """

    code: str
    reason: str
    verdict: ScreeningVerdict | None = None
    detected_patterns: list[Any] = field(default_factory=list)
    confidence: float = 0.0
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "code": self.code,
            "reason": self.reason,
            "verdict": self.verdict.value if self.verdict else None,
            "detected_patterns": [
                {
                    "name": p.name,
                    "severity": p.severity,
                    "category": p.category,
                    "confidence": p.confidence,
                }
                for p in self.detected_patterns
            ],
            "confidence": self.confidence,
            "suggestions": self.suggestions,
        }


@dataclass
class ValidationResult:
    """Result of input validation.

    Attributes:
        is_valid: Whether the input passed validation
        error: Validation error details (if validation failed)
        screening_result: Full screening result for reference
    """

    is_valid: bool
    error: ValidationError | None = None
    screening_result: ScreeningResult | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {"is_valid": self.is_valid}

        if self.error:
            result["error"] = self.error.to_dict()

        if self.screening_result:
            result["screening"] = {
                "verdict": self.screening_result.verdict.value,
                "confidence": self.screening_result.confidence,
                "screening_time_ms": self.screening_result.screening_time_ms,
            }

        return result


@dataclass
class SpecInfo:
    """Information about a created spec.

    Attributes:
        spec_id: Spec identifier (e.g., "001-feature-name")
        spec_dir: Full path to spec directory
        spec_file: Full path to spec.md file
        created: Whether the spec was newly created or already existed
    """

    spec_id: str
    spec_dir: Path
    spec_file: Path
    created: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "spec_id": self.spec_id,
            "spec_dir": str(self.spec_dir),
            "spec_file": str(self.spec_file),
            "created": self.created,
        }


# =============================================================================
# EXCEPTIONS
# =============================================================================


class SpecCreationError(Exception):
    """Exception raised when spec creation fails.

    Attributes:
        message: Human-readable error message
        error_code: Error code for programmatic handling
        reason: Detailed reason for the error
        details: Additional error details from screening
    """

    def __init__(
        self,
        message: str,
        error_code: SpecErrorCode,
        reason: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.reason = reason
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error_code": self.error_code.value,
            "reason": self.reason,
            "message": str(self),
            "details": self.details,
        }


# =============================================================================
# SPEC SERVICE
# =============================================================================


class SpecService:
    """
    Service layer for spec creation with input screening.

    This service provides a structured API for validating and creating specs,
    ensuring all inputs pass through harmlessness screening before processing.

    The service is designed to be used by:
    - CLI commands (spec_runner.py, input_handlers.py)
    - Electron frontend (via subprocess calls with structured output)
    - Future REST API endpoints
    - Direct Python imports

    Attributes:
        project_dir: Root directory of the project
        screener: InputScreener instance for validation
    """

    def __init__(self, project_dir: Path | str):
        """
        Initialize the spec service.

        Args:
            project_dir: Root directory of the project
        """
        self.project_dir = Path(project_dir).resolve()
        self.screener = InputScreener(project_dir=str(self.project_dir))

    def validate_input(
        self, task_description: str, screening_level: str | None = None
    ) -> ValidationResult:
        """
        Validate task description through harmlessness screening.

        This method screens the input for potential prompt injection attacks
        and returns a structured validation result.

        Args:
            task_description: The task description to validate
            screening_level: Optional screening level (permissive/normal/strict)

        Returns:
            ValidationResult with validation status and error details if failed

        Examples:
            >>> service = SpecService(project_dir=Path("/project"))
            >>> result = service.validate_input("Add user login")
            >>> if result.is_valid:
            ...     print("Input is safe")
            ... else:
            ...     print(f"Rejected: {result.error.reason}")
        """
        if not task_description or not task_description.strip():
            return ValidationResult(
                is_valid=False,
                error=ValidationError(
                    code=SpecErrorCode.MISSING_REQUIRED_FIELD.value,
                    reason="Task description is required",
                    suggestions=["Provide a clear task description"],
                ),
            )

        try:
            # Override screening level if specified
            if screening_level:
                from security.input_screener import ScreeningLevel

                try:
                    original_level = self.screener.level
                    self.screener.level = ScreeningLevel(screening_level)
                    result = self.screener.screen_input(task_description)
                    self.screener.level = original_level
                except ValueError:
                    return ValidationResult(
                        is_valid=False,
                        error=ValidationError(
                            code=SpecErrorCode.INVALID_INPUT.value,
                            reason=f"Invalid screening level: {screening_level}",
                            suggestions=[
                                "Use one of: permissive, normal, strict"
                            ],
                        ),
                    )
            else:
                result = self.screener.screen_input(task_description)

            # Check if input is safe
            if not result.is_safe:
                # Build detailed error
                error_code = (
                    SpecErrorCode.INPUT_REJECTED
                    if result.verdict == ScreeningVerdict.REJECTED
                    else SpecErrorCode.INPUT_SUSPICIOUS
                )

                # Generate suggestions based on detected patterns
                suggestions = self._generate_suggestions(result)

                return ValidationResult(
                    is_valid=False,
                    error=ValidationError(
                        code=error_code.value,
                        reason=result.reason,
                        verdict=result.verdict,
                        detected_patterns=result.detected_patterns,
                        confidence=result.confidence,
                        suggestions=suggestions,
                    ),
                    screening_result=result,
                )

            # Input is safe
            return ValidationResult(is_valid=True, screening_result=result)

        except Exception as e:
            # Screening error - fail open for reliability
            return ValidationResult(
                is_valid=False,
                error=ValidationError(
                    code=SpecErrorCode.SCREENING_ERROR.value,
                    reason=f"Screening failed: {str(e)}",
                    suggestions=[
                        "Try again with a simpler description",
                        "Report this issue if it persists",
                    ],
                ),
            )

    def create_spec(
        self,
        task_description: str,
        metadata: dict[str, Any] | None = None,
        screening_level: str | None = None,
    ) -> SpecInfo:
        """
        Create a spec with automatic screening validation.

        This method validates the input through screening and then creates
        the spec directory structure. Raises SpecCreationError if validation fails.

        Args:
            task_description: The task description for the spec
            metadata: Optional metadata for the spec
            screening_level: Optional screening level override

        Returns:
            SpecInfo with spec details

        Raises:
            SpecCreationError: If validation fails or spec creation errors

        Examples:
            >>> service = SpecService(project_dir=Path("/project"))
            >>> try:
            ...     spec = service.create_spec("Add user authentication")
            ...     print(f"Created: {spec.spec_id}")
            ... except SpecCreationError as e:
            ...     print(f"Failed: {e.reason}")
        """
        # Validate input first
        validation = self.validate_input(task_description, screening_level)

        if not validation.is_valid:
            raise SpecCreationError(
                message=f"Input validation failed: {validation.error.reason}",
                error_code=SpecErrorCode(validation.error.code),
                reason=validation.error.reason,
                details=validation.error.to_dict(),
            )

        # Input is safe - proceed with spec creation
        # Import here to avoid circular dependency
        from spec.pipeline.models import create_spec_dir, get_specs_dir

        specs_dir = get_specs_dir(self.project_dir)
        spec_dir = create_spec_dir(specs_dir, task_description)

        # Return spec info
        spec_file = spec_dir / "spec.md"

        return SpecInfo(
            spec_id=spec_dir.name,
            spec_dir=spec_dir,
            spec_file=spec_file,
            created=not spec_file.exists(),
        )

    def _generate_suggestions(self, result: ScreeningResult) -> list[str]:
        """
        Generate helpful suggestions based on screening result.

        Args:
            result: The screening result

        Returns:
            List of suggestions for the user
        """
        suggestions = []

        if not result.detected_patterns:
            return suggestions

        # Analyze patterns to provide specific suggestions
        pattern_categories = {p.category for p in result.detected_patterns}

        if "instruction_override" in pattern_categories:
            suggestions.append("Avoid instructions that try to override system prompts")

        if "role_hijacking" in pattern_categories:
            suggestions.append("Don't ask the AI to change roles or assume new personas")

        if "context_manipulation" in pattern_categories:
            suggestions.append("Avoid using system-level formatting or commands")

        if "delimiter_attack" in pattern_categories:
            suggestions.append("Use natural language instead of special delimiters")

        if "encoding_attack" in pattern_categories:
            suggestions.append("Provide input directly without encoding")

        if "shell_injection" in pattern_categories:
            suggestions.append("Describe what you want clearly without shell commands")

        # Add general suggestion
        if not suggestions:
            suggestions.append("Rephrase your request using clear, natural language")

        # Add false positive reporting
        suggestions.append(
            "If this is a false positive, report it at: "
            "https://github.com/Andymik90/auto-claude/issues"
        )

        return suggestions


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def validate_spec_input(
    task_description: str,
    project_dir: Path | str,
    screening_level: str | None = None,
) -> ValidationResult:
    """
    Convenience function to validate spec input.

    Args:
        task_description: The task description to validate
        project_dir: Root directory of the project
        screening_level: Optional screening level override

    Returns:
        ValidationResult with validation status

    Examples:
        >>> result = validate_spec_input("Add login", "/project")
        >>> if result.is_valid:
        ...     print("Safe to proceed")
    """
    service = SpecService(project_dir=project_dir)
    return service.validate_input(task_description, screening_level)


def create_validated_spec(
    task_description: str,
    project_dir: Path | str,
    metadata: dict[str, Any] | None = None,
    screening_level: str | None = None,
) -> SpecInfo:
    """
    Convenience function to create a spec with validation.

    Args:
        task_description: The task description for the spec
        project_dir: Root directory of the project
        metadata: Optional metadata for the spec
        screening_level: Optional screening level override

    Returns:
        SpecInfo with spec details

    Raises:
        SpecCreationError: If validation fails

    Examples:
        >>> try:
        ...     spec = create_validated_spec("Add login", "/project")
        ...     print(f"Created: {spec.spec_id}")
        ... except SpecCreationError as e:
        ...     print(f"Failed: {e.reason}")
    """
    service = SpecService(project_dir=project_dir)
    return service.create_spec(task_description, metadata, screening_level)
