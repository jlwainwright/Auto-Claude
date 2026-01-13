"""
Test Generation Module
======================

Automatically generates unit tests for new code using AI-powered analysis.
Supports multiple test frameworks: pytest, jest, vitest, mocha.

Usage:
    from test_generation import TestGenerator
    
    generator = TestGenerator(project_dir)
    tests = generator.generate_tests(file_path, functions=["my_function"])
"""

from .generator import TestGenerator
from .models import (
    FunctionInfo,
    TestCase,
    TestGenerationConfig,
    TestGenerationResult,
)

__all__ = [
    "TestGenerator",
    "FunctionInfo",
    "TestCase",
    "TestGenerationConfig",
    "TestGenerationResult",
]
