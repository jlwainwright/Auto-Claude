#!/usr/bin/env python3
"""Smoke test for allowed_paths module."""

import sys
from pathlib import Path

# Add apps/backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from security.output_validation.allowed_paths import (
    AllowedPathsChecker,
    is_path_allowed,
    compile_glob_patterns,
    normalize_pattern,
    pattern_to_regex,
)
from security.output_validation.models import OutputValidationConfig


def test_basic_functionality():
    """Test basic allowed paths functionality."""
    print("Testing allowed_paths module...")

    # Test 1: Create config with test and build patterns
    config = OutputValidationConfig(
        allowed_paths=[
            "tests/**",
            "test_*.py",
            "build/**",
            "dist/**",
            ".git/**",
        ]
    )

    checker = AllowedPathsChecker(Path("/tmp/project"), config)

    # Test 2: Check allowed paths
    assert checker.is_allowed("tests/test_api.py"), "tests/test_api.py should be allowed"
    assert checker.is_allowed("tests/integration/test_user.py"), "Nested test path should be allowed"
    assert checker.is_allowed("test_utils.py"), "test_*.py pattern should match"
    assert checker.is_allowed("build/app.js"), "build/** should match"
    assert checker.is_allowed(".git/config"), ".git/** should match"

    # Test 3: Check non-allowed paths
    assert not checker.is_allowed("src/main.py"), "src/main.py should not be allowed"
    assert not checker.is_allowed("config.py"), "config.py should not be allowed"
    assert not checker.is_allowed("/etc/passwd"), "System files should not be allowed"

    # Test 4: Empty config
    empty_config = OutputValidationConfig(allowed_paths=[])
    empty_checker = AllowedPathsChecker(Path("/tmp"), empty_config)
    assert not empty_checker.is_allowed("tests/test.py"), "Empty config should allow nothing"

    # Test 5: Convenience functions
    assert is_path_allowed("tests/test.py", Path("/tmp"), config), "is_path_allowed convenience function"
    patterns = compile_glob_patterns(["tests/**", "build/**"])
    assert patterns == ["tests/**", "build/**"], "compile_glob_patterns"

    # Test 6: Pattern utilities
    assert normalize_pattern("tests\\\\**") == "tests/**", "normalize_pattern"

    # Debug pattern_to_regex
    result = pattern_to_regex("tests/**/*.py")
    print(f"  pattern_to_regex('tests/**/*.py') = '{result}'")
    # The result should contain .* for ** and [^/]* for *
    assert ".*" in result and "\\.py" in result, f"pattern_to_regex failed, got: {result}"

    print("✓ All basic tests passed!")


def test_complex_patterns():
    """Test complex glob patterns."""
    print("Testing complex patterns...")

    config = OutputValidationConfig(
        allowed_paths=[
            "tests/**",
            "generated/code/**",
            "*.egg-info/**",
            "node_modules/**",
        ]
    )

    checker = AllowedPathsChecker(Path("/project"), config)

    # Deep nesting
    assert checker.is_allowed("tests/a/b/c/d/test.py"), "Deep nesting with **"
    assert checker.is_allowed("generated/code/client/src/generated.ts"), "Specific nested path"

    # Egg info
    assert checker.is_allowed("mypackage-1.0.egg-info/PKG-INFO"), "*.egg-info/**"

    # Node modules
    assert checker.is_allowed("node_modules/react/index.js"), "node_modules/**"

    print("✓ Complex pattern tests passed!")


def test_edge_cases():
    """Test edge cases."""
    print("Testing edge cases...")

    config = OutputValidationConfig(allowed_paths=["tests/**", "test_*.py"])
    checker = AllowedPathsChecker(Path("/project"), config)

    # Empty path
    assert not checker.is_allowed(""), "Empty path should not match"

    # Case sensitivity
    assert not checker.is_allowed("Tests/test.py"), "Case sensitive matching"

    # Wrong patterns
    assert not checker.is_allowed("test.py"), "No underscore in test.py"
    assert not checker.is_allowed("api_test.py"), "Wrong order for test pattern"

    print("✓ Edge case tests passed!")


if __name__ == "__main__":
    test_basic_functionality()
    test_complex_patterns()
    test_edge_cases()
    print("\n✅ All smoke tests passed!")
