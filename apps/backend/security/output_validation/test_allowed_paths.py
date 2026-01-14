"""
Tests for Allowed Paths Configuration
======================================

Tests path allowlist functionality that bypasses validation for configured patterns.
"""

from pathlib import Path

import pytest

from security.output_validation.allowed_paths import (
    AllowedPathsChecker,
    compile_glob_patterns,
    get_allowed_paths,
    is_path_allowed,
    normalize_pattern,
    pattern_to_regex,
)
from security.output_validation.models import OutputValidationConfig


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def empty_config() -> OutputValidationConfig:
    """Config with no allowed paths."""
    return OutputValidationConfig(allowed_paths=[])


@pytest.fixture
def test_config() -> OutputValidationConfig:
    """Config with test and build allowed paths."""
    return OutputValidationConfig(
        allowed_paths=[
            "tests/**",
            "test_*.py",
            "build/**",
            "dist/**",
            ".git/**",
            "__pycache__/**",
            "*.egg-info/**",
        ]
    )


@pytest.fixture
def complex_config() -> OutputValidationConfig:
    """Config with complex patterns."""
    return OutputValidationConfig(
        allowed_paths=[
            # Directory patterns
            "tests/**",
            "tests/integration/**",
            "build/**",
            "dist/**",
            # File patterns
            "test_*.py",
            "*_test.py",
            "*.tmp",
            # Hidden directories
            ".git/**",
            ".vscode/**",
            "__pycache__/**",
            "node_modules/**",
            # Specific paths
            "generated/code/**",
            "assets/dist/**",
        ]
    )


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()
    return project_dir


# =============================================================================
# AllowedPathsChecker Tests
# =============================================================================

class TestAllowedPathsChecker:
    """Tests for AllowedPathsChecker class."""

    def test_init_empty_config(self, temp_project_dir, empty_config):
        """Test initialization with empty config."""
        checker = AllowedPathsChecker(temp_project_dir, empty_config)

        assert checker.project_dir == temp_project_dir.resolve()
        assert checker.config == empty_config
        assert checker.allowed_patterns == []
        assert not checker.has_allowed_paths()

    def test_init_with_patterns(self, temp_project_dir, test_config):
        """Test initialization with patterns."""
        checker = AllowedPathsChecker(temp_project_dir, test_config)

        assert checker.has_allowed_paths()
        assert len(checker.allowed_patterns) == len(test_config.allowed_paths)
        assert checker.get_allowed_patterns() == test_config.allowed_paths

    def test_is_allowed_no_patterns(self, temp_project_dir, empty_config):
        """Test is_allowed returns False when no patterns configured."""
        checker = AllowedPathsChecker(temp_project_dir, empty_config)

        assert not checker.is_allowed("tests/test.py")
        assert not checker.is_allowed("any/path/file.txt")

    def test_is_allowed_tests_directory(self, temp_project_dir, test_config):
        """Test matching files in tests directory."""
        checker = AllowedPathsChecker(temp_project_dir, test_config)

        # Test files in tests/
        assert checker.is_allowed("tests/test_api.py")
        assert checker.is_allowed("tests/integration/test_user.py")
        assert checker.is_allowed("tests/unit/test_utils.py")
        assert checker.is_allowed("tests/fixtures/data.json")

        # Test nested tests
        assert checker.is_allowed("tests/integration/auth/test_login.py")
        assert checker.is_allowed("tests/unit/modules/test_database.py")

    def test_is_allowed_wildcard_patterns(self, temp_project_dir, test_config):
        """Test wildcard file patterns."""
        checker = AllowedPathsChecker(temp_project_dir, test_config)

        # test_*.py pattern
        assert checker.is_allowed("test_api.py")
        assert checker.is_allowed("test_utils.py")
        assert checker.is_allowed("test_database_connection.py")
        assert not checker.is_allowed("test.py")  # No underscore
        assert not checker.is_allowed("api_test.py")  # Wrong order

    def test_is_allowed_build_directories(self, temp_project_dir, test_config):
        """Test build and dist directories."""
        checker = AllowedPathsChecker(temp_project_dir, test_config)

        # build/**
        assert checker.is_allowed("build/app.js")
        assert checker.is_allowed("build/static/main.js")
        assert checker.is_allowed("build/css/style.css")

        # dist/**
        assert checker.is_allowed("dist/package.tar.gz")
        assert checker.is_allowed("dist/windows/myapp.exe")

    def test_is_allowed_hidden_directories(self, temp_project_dir, test_config):
        """Test hidden directory patterns."""
        checker = AllowedPathsChecker(temp_project_dir, test_config)

        # .git/**
        assert checker.is_allowed(".git/config")
        assert checker.is_allowed(".git/refs/heads/main")
        assert checker.is_allowed(".git/hooks/pre-commit")

        # __pycache__/**
        assert checker.is_allowed("__pycache__/module.cpython-39.pyc")
        assert checker.is_allowed("__pycache__/utils.cpython-39.pyc")

        # *.egg-info/**
        assert checker.is_allowed("mypackage-1.0.egg-info/PKG-INFO")
        assert checker.is_allowed("project-2.3.egg-info/requires.txt")

    def test_is_allowed_rejections(self, temp_project_dir, test_config):
        """Test paths that should NOT be allowed."""
        checker = AllowedPathsChecker(temp_project_dir, test_config)

        # Source code
        assert not checker.is_allowed("src/main.py")
        assert not checker.is_allowed("src/utils/helpers.py")

        # Config files
        assert not checker.is_allowed("config.py")
        assert not checker.is_allowed(".env")
        assert not checker.is_allowed("package.json")

        # System files
        assert not checker.is_allowed("/etc/passwd")
        assert not checker.is_allowed("/usr/bin/python")

    def test_is_allowed_complex_patterns(self, temp_project_dir, complex_config):
        """Test complex glob patterns."""
        checker = AllowedPathsChecker(temp_project_dir, complex_config)

        # Specific nested patterns
        assert checker.is_allowed("tests/integration/api/test.py")
        assert checker.is_allowed("generated/code/client.ts")
        assert checker.is_allowed("assets/dist/bundle.js")

        # Multiple test patterns
        assert checker.is_allowed("test_api.py")
        assert checker.is_allowed("utils_test.py")
        assert not checker.is_allowed("api_tests.py")  # Wrong suffix

        # node_modules
        assert checker.is_allowed("node_modules/react/index.js")
        assert checker.is_allowed("node_modules/.bin/webpack")

    def test_is_allowed_absolute_vs_relative(self, temp_project_dir, test_config):
        """Test handling of absolute and relative paths."""
        checker = AllowedPathsChecker(temp_project_dir, test_config)

        # Relative paths should match
        assert checker.is_allowed("tests/test.py")
        assert checker.is_allowed("build/output.js")

        # Absolute paths outside project should not match
        assert not checker.is_allowed("/etc/passwd")
        assert not checker.is_allowed("/usr/local/bin/script")

    def test_is_allowed_case_sensitive(self, temp_project_dir, test_config):
        """Test that matching is case-sensitive."""
        checker = AllowedPathsChecker(temp_project_dir, test_config)

        # Should match exact case
        assert checker.is_allowed("tests/test.py")
        assert checker.is_allowed("build/app.js")

        # Should not match different case
        # Note: This depends on the filesystem, but fnmatch is case-sensitive
        assert not checker.is_allowed("Tests/test.py")  # Capital T
        assert not checker.is_allowed("BUILD/app.js")  # All caps

    def test_get_allowed_patterns(self, temp_project_dir, test_config):
        """Test get_allowed_patterns returns copy of patterns."""
        checker = AllowedPathsChecker(temp_project_dir, test_config)

        patterns = checker.get_allowed_patterns()
        assert patterns == test_config.allowed_paths

        # Verify it's a copy
        patterns.append("new-pattern")
        assert "new-pattern" not in checker.get_allowed_patterns()

    def test_has_allowed_paths(self, temp_project_dir):
        """Test has_allowed_paths method."""
        empty_checker = AllowedPathsChecker(
            temp_project_dir,
            OutputValidationConfig(allowed_paths=[])
        )
        assert not empty_checker.has_allowed_paths()

        config_checker = AllowedPathsChecker(
            temp_project_dir,
            OutputValidationConfig(allowed_paths=["tests/**"])
        )
        assert config_checker.has_allowed_paths()


# =============================================================================
# Convenience Functions Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_is_path_allowed(self, temp_project_dir, test_config):
        """Test is_path_allowed convenience function."""
        assert is_path_allowed("tests/test.py", temp_project_dir, test_config)
        assert is_path_allowed("build/app.js", temp_project_dir, test_config)
        assert not is_path_allowed("src/main.py", temp_project_dir, test_config)

    def test_get_allowed_paths(self, temp_project_dir, test_config):
        """Test get_allowed_paths convenience function."""
        patterns = get_allowed_paths(temp_project_dir, test_config)

        assert patterns == test_config.allowed_paths
        assert len(patterns) > 0


# =============================================================================
# Pattern Compilation Tests
# =============================================================================

class TestPatternCompilation:
    """Tests for pattern compilation and validation."""

    def test_compile_glob_patterns_valid(self):
        """Test compiling valid glob patterns."""
        patterns = ["tests/**", "build/**", "*.tmp"]
        compiled = compile_glob_patterns(patterns)

        assert compiled == patterns

    def test_compile_glob_patterns_empty(self):
        """Test compiling empty patterns list."""
        compiled = compile_glob_patterns([])
        assert compiled == []

    def test_compile_glob_patterns_invalid_type(self):
        """Test compiling invalid pattern types."""
        with pytest.raises(TypeError):
            compile_glob_patterns(["tests/**", 123, "build/**"])

    def test_compile_glob_patterns_whitespace(self):
        """Test handling of whitespace patterns."""
        patterns = ["tests/**", "   ", "\t", "build/**"]
        compiled = compile_glob_patterns(patterns)

        # Whitespace patterns should be filtered out
        assert "   " not in compiled
        assert "\t" not in compiled
        assert len(compiled) == 2

    def test_normalize_pattern(self):
        """Test pattern normalization."""
        assert normalize_pattern("tests\\\\**") == "tests/**"
        assert normalize_pattern("build//output") == "build/output"
        assert normalize_pattern("dist///file") == "dist/file"

    def test_pattern_to_regex(self):
        """Test converting glob patterns to regex."""
        assert pattern_to_regex("tests/**/*.py") == "tests/.*\\.py"
        assert pattern_to_regex("build/*.js") == "build/[^/]*\\.js"
        assert pattern_to_regex("test_?") == "test_[^/]"


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_file_path(self, temp_project_dir, test_config):
        """Test checking empty file path."""
        checker = AllowedPathsChecker(temp_project_dir, test_config)

        # Empty path should not match
        assert not checker.is_allowed("")

    def test_dot_patterns(self, temp_project_dir):
        """Test dot file patterns."""
        config = OutputValidationConfig(allowed_paths=[".*", ".*/**"])
        checker = AllowedPathsChecker(temp_project_dir, config)

        assert checker.is_allowed(".gitignore")
        assert checker.is_allowed(".env")
        assert checker.is_allowed(".vscode/settings.json")
        assert not checker.is_allowed("regular_file.txt")

    def test_deeply_nested_directories(self, temp_project_dir):
        """Test deeply nested directory patterns."""
        config = OutputValidationConfig(allowed_paths=["a/**"])
        checker = AllowedPathsChecker(temp_project_dir, config)

        assert checker.is_allowed("a/b/c/d/e/file.txt")
        assert checker.is_allowed("a/very/deeply/nested/path/file.py")

    def test_single_star_pattern(self, temp_project_dir):
        """Test single star (not double star) patterns."""
        config = OutputValidationConfig(allowed_paths=["*.py", "test.*"])
        checker = AllowedPathsChecker(temp_project_dir, config)

        # *.py matches files in current directory only
        assert checker.is_allowed("module.py")
        assert checker.is_allowed("test.py")
        assert not checker.is_allowed("src/module.py")  # Not in current dir

        # test.* matches files with any extension
        assert checker.is_allowed("test.py")
        assert checker.is_allowed("test.js")
        assert checker.is_allowed("test.txt")

    def test_bracket_patterns(self, temp_project_dir):
        """Test bracket expressions in patterns."""
        config = OutputValidationConfig(allowed_paths=["test_[abc].py"])
        checker = AllowedPathsChecker(temp_project_dir, config)

        assert checker.is_allowed("test_a.py")
        assert checker.is_allowed("test_b.py")
        assert checker.is_allowed("test_c.py")
        assert not checker.is_allowed("test_d.py")
        assert not checker.is_allowed("test_ab.py")

    def test_invalid_pattern_types_in_config(self, temp_project_dir):
        """Test handling of invalid pattern types in config."""
        # Create config with non-string pattern (shouldn't happen in practice,
        # but test defensive coding)
        config = OutputValidationConfig(allowed_paths=["tests/**", 123, None])

        # Should handle gracefully
        checker = AllowedPathsChecker(temp_project_dir, config)

        # Valid pattern should still work
        assert checker.is_allowed("tests/test.py")

        # Invalid patterns should be skipped (logged as warning)
        assert len(checker.allowed_patterns) == 1  # Only the valid one

    def test_absolute_pattern_in_config(self, temp_project_dir):
        """Test absolute path patterns in config."""
        abs_path = str(temp_project_dir / "build")

        config = OutputValidationConfig(allowed_paths=[abs_path])
        checker = AllowedPathsChecker(temp_project_dir, config)

        # Should match absolute path
        assert checker.is_allowed(str(temp_project_dir / "build" / "app.js"))


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests with other components."""

    def test_allowed_paths_with_write_validator(self, temp_project_dir):
        """Test that allowed paths work in practice with file operations."""
        from security.output_validation.validators.write_validator import validate_write
        from security.output_validation.pattern_detector import PatternDetector

        # Create config that allows tests directory
        config = OutputValidationConfig(
            allowed_paths=["tests/**", "test_*.py"],
            enabled=True,
        )

        # Create pattern detector
        detector = PatternDetector(rules=[])

        # Test that writing to tests directory would bypass validation
        # (In real implementation, validator would check allowed_paths first)
        checker = AllowedPathsChecker(temp_project_dir, config)

        # These should be allowed
        assert checker.is_allowed("tests/test_api.py")
        assert checker.is_allowed("test_utils.py")

        # These should not be allowed
        assert not checker.is_allowed("src/main.py")
        assert not checker.is_allowed("config.py")

    def test_multiple_projects(self, tmp_path):
        """Test that different projects can have different allowed paths."""
        project1 = tmp_path / "project1"
        project2 = tmp_path / "project2"
        project1.mkdir()
        project2.mkdir()

        config1 = OutputValidationConfig(allowed_paths=["tests/**"])
        config2 = OutputValidationConfig(allowed_paths=["build/**"])

        checker1 = AllowedPathsChecker(project1, config1)
        checker2 = AllowedPathsChecker(project2, config2)

        # Each project should have its own rules
        assert checker1.is_allowed("tests/test.py")
        assert not checker1.is_allowed("build/app.js")

        assert checker2.is_allowed("build/app.js")
        assert not checker2.is_allowed("tests/test.py")


# =============================================================================
# Logging Tests
# =============================================================================

class TestLogging:
    """Tests for logging functionality."""

    def test_logging_on_match(self, temp_project_dir, test_config, caplog):
        """Test that matching paths are logged."""
        import logging

        # Enable debug logging
        with caplog.at_level(logging.DEBUG):
            checker = AllowedPathsChecker(temp_project_dir, test_config)
            checker.is_allowed("tests/test.py")

            # Check that debug log was written
            assert any("bypassing validation" in record.message for record in caplog.records)
            assert any("tests/test.py" in record.message for record in caplog.records)

    def test_no_logging_on_no_match(self, temp_project_dir, test_config, caplog):
        """Test that non-matching paths are not logged."""
        import logging

        with caplog.at_level(logging.DEBUG):
            checker = AllowedPathsChecker(temp_project_dir, test_config)
            checker.is_allowed("src/main.py")

            # No debug log about bypassing validation
            assert not any(
                "bypassing validation" in record.message
                for record in caplog.records
            )
