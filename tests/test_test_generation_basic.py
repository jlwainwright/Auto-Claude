"""
Basic tests for test generation module.

Tests the core TestGenerator functionality for parsing Python files.
"""

import tempfile
from pathlib import Path

import pytest

from test_generation import TestGenerator, FunctionInfo


def test_test_generator_initialization(tmp_path: Path):
    """Test that TestGenerator can be initialized."""
    generator = TestGenerator(tmp_path)
    assert generator.project_dir == tmp_path.resolve()
    assert generator.test_discovery is not None


def test_parse_simple_python_file(tmp_path: Path):
    """Test parsing a simple Python file with functions."""
    # Create a test Python file
    test_file = tmp_path / "test_module.py"
    test_file.write_text("""
def hello(name: str) -> str:
    \"\"\"Say hello to someone.\"\"\"
    return f"Hello, {name}!"

def add(a: int, b: int) -> int:
    return a + b

class Calculator:
    def multiply(self, x: float, y: float) -> float:
        return x * y
""")
    
    generator = TestGenerator(tmp_path)
    functions = generator.parse_file(test_file)
    
    assert len(functions) >= 3
    
    # Check hello function
    hello_func = next((f for f in functions if f.name == "hello"), None)
    assert hello_func is not None
    assert hello_func.parameters == ["name"]
    assert hello_func.parameter_types.get("name") == "str"
    assert hello_func.return_type == "str"
    assert hello_func.docstring is not None
    assert "hello" in hello_func.docstring.lower()
    assert not hello_func.is_method
    
    # Check add function
    add_func = next((f for f in functions if f.name == "add"), None)
    assert add_func is not None
    assert add_func.parameters == ["a", "b"]
    assert not add_func.is_method
    
    # Check multiply method
    multiply_func = next((f for f in functions if f.name == "multiply"), None)
    assert multiply_func is not None
    assert multiply_func.is_method
    assert multiply_func.class_name == "Calculator"


def test_identify_functions_needing_tests(tmp_path: Path):
    """Test identifying functions that need tests."""
    test_file = tmp_path / "module.py"
    test_file.write_text("""
def public_function():
    pass

def _private_function():
    pass

def test_something():
    pass
""")
    
    generator = TestGenerator(tmp_path)
    functions = generator.identify_functions_needing_tests(test_file)
    
    # Should include public_function but not _private_function or test_something
    function_names = [f.name for f in functions]
    assert "public_function" in function_names
    assert "_private_function" not in function_names
    assert "test_something" not in function_names


def test_discover_framework(tmp_path: Path):
    """Test framework discovery."""
    # Create a pytest.ini to trigger pytest detection
    pytest_ini = tmp_path / "pytest.ini"
    pytest_ini.write_text("[pytest]\n")
    
    generator = TestGenerator(tmp_path)
    result = generator.discover_framework()
    
    # Should detect pytest
    assert len(result.frameworks) > 0
    assert any(f.name == "pytest" for f in result.frameworks)
