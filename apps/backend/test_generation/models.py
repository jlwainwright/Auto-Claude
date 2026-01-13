"""
Test Generation Models
======================

Data models for test generation functionality.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FunctionInfo:
    """
    Information about a function/method extracted from code.
    
    Attributes:
        name: Function name
        file_path: Path to the file containing the function
        line_start: Starting line number
        line_end: Ending line number
        parameters: List of parameter names
        parameter_types: Optional type hints for parameters
        return_type: Optional return type hint
        docstring: Function docstring if present
        is_method: Whether this is a method (vs standalone function)
        class_name: Class name if this is a method
        is_async: Whether the function is async
        decorators: List of decorator names
    """
    
    name: str
    file_path: Path
    line_start: int
    line_end: int
    parameters: list[str] = field(default_factory=list)
    parameter_types: dict[str, str] = field(default_factory=dict)
    return_type: str | None = None
    docstring: str | None = None
    is_method: bool = False
    class_name: str | None = None
    is_async: bool = False
    decorators: list[str] = field(default_factory=list)


@dataclass
class TestCase:
    """
    A test case specification.
    
    Attributes:
        name: Test case name/description
        inputs: Dictionary of input values for the test
        expected_output: Expected return value
        expected_exception: Expected exception type if any
        description: Human-readable description of what this test verifies
    """
    
    name: str
    inputs: dict[str, Any] = field(default_factory=dict)
    expected_output: Any = None
    expected_exception: type[Exception] | None = None
    description: str = ""


@dataclass
class TestGenerationConfig:
    """
    Configuration for test generation.
    
    Attributes:
        coverage_target: Target coverage percentage (default 80)
        framework: Test framework to use (auto-detected if None)
        test_directory: Directory where tests should be created
        follow_conventions: Whether to follow existing test conventions
        include_edge_cases: Whether to generate edge case tests
        include_error_cases: Whether to generate error/exception tests
    """
    
    coverage_target: float = 80.0
    framework: str | None = None
    test_directory: str | None = None
    follow_conventions: bool = True
    include_edge_cases: bool = True
    include_error_cases: bool = True


@dataclass
class TestGenerationResult:
    """
    Result of test generation.
    
    Attributes:
        success: Whether generation was successful
        test_code: Generated test code
        test_file_path: Path where test should be written
        functions_tested: List of function names that were tested
        coverage_estimate: Estimated coverage percentage
        warnings: List of warning messages
        errors: List of error messages
    """
    
    success: bool
    test_code: str = ""
    test_file_path: Path | None = None
    functions_tested: list[str] = field(default_factory=list)
    coverage_estimate: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
