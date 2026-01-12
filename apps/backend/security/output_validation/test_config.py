"""
Tests for Output Validation Configuration Loader
=================================================

Tests configuration loading from .auto-claude directory with JSON and YAML formats.
"""

import json
from pathlib import Path

import pytest

# Import the module under test
from security.output_validation.config import (
    CONFIG_FILENAMES,
    ValidationConfigLoader,
    clear_config_cache,
    get_config_file_path,
    get_validation_config,
    is_yaml_available,
    load_validation_config,
)
from security.output_validation.models import SeverityLevel


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory with .auto-claude folder."""
    auto_claude_dir = tmp_path / ".auto-claude"
    auto_claude_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def valid_json_config(temp_project_dir: Path) -> Path:
    """Create a valid JSON config file."""
    config_path = temp_project_dir / ".auto-claude" / "output-validation.json"
    config_data = {
        "enabled": True,
        "strict_mode": False,
        "disabled_rules": ["bash-rm-rf-root"],
        "severity_overrides": {"bash-chmod-777": "low"},
        "allowed_paths": ["tests/**", "build/**"],
        "log_all_validations": True,
        "version": "1.0",
    }
    with open(config_path, "w") as f:
        json.dump(config_data, f)
    return config_path


@pytest.fixture
def valid_custom_rules_config(temp_project_dir: Path) -> Path:
    """Create a config with custom rules."""
    config_path = temp_project_dir / ".auto-claude" / "output-validation.json"
    config_data = {
        "enabled": True,
        "custom_rules": [
            {
                "rule_id": "custom-test-rule",
                "name": "Custom Test Rule",
                "description": "A custom validation rule",
                "pattern": "test-pattern",
                "pattern_type": "regex",
                "severity": "high",
                "priority": "p1",
                "tool_types": ["Bash", "Write"],
                "context": "command",
                "message": "This matches test pattern",
                "suggestions": ["Use alternative pattern"],
                "enabled": True,
                "category": "custom",
            }
        ],
    }
    with open(config_path, "w") as f:
        json.dump(config_data, f)
    return config_path


@pytest.fixture
def invalid_json_config(temp_project_dir: Path) -> Path:
    """Create an invalid JSON config file."""
    config_path = temp_project_dir / ".auto-claude" / "output-validation.json"
    with open(config_path, "w") as f:
        f.write("{ invalid json }")
    return config_path


@pytest.fixture
def invalid_schema_config(temp_project_dir: Path) -> Path:
    """Create a config with schema validation errors."""
    config_path = temp_project_dir / ".auto-claude" / "output-validation.json"
    config_data = {
        "enabled": "not-a-boolean",  # Should be boolean
        "disabled_rules": ["rule1", 123],  # Should all be strings
        "severity_overrides": {"rule1": "invalid-severity"},
        "unknown_key": "should-not-be-here",
    }
    with open(config_path, "w") as f:
        json.dump(config_data, f)
    return config_path


@pytest.fixture
def invalid_custom_rule_config(temp_project_dir: Path) -> Path:
    """Create a config with invalid custom rule."""
    config_path = temp_project_dir / ".auto-claude" / "output-validation.json"
    config_data = {
        "custom_rules": [
            {
                "rule_id": "invalid-rule",
                # Missing required fields: name, description, pattern
                "severity": "invalid-severity",
                "priority": "invalid-priority",
                "tool_types": ["InvalidTool"],
                "context": "invalid-context",
            }
        ],
    }
    with open(config_path, "w") as f:
        json.dump(config_data, f)
    return config_path


@pytest.fixture
def valid_yaml_config(temp_project_dir: Path) -> Path:
    """Create a valid YAML config file (if YAML is available)."""
    if not is_yaml_available():
        pytest.skip("PyYAML not installed")

    config_path = temp_project_dir / ".auto-claude" / "output-validation.yaml"
    config_content = """
enabled: true
strict_mode: false
disabled_rules:
  - bash-rm-rf-root
severity_overrides:
  bash-chmod-777: low
allowed_paths:
  - tests/**
  - build/**
log_all_validations: true
version: "1.0"
"""
    with open(config_path, "w") as f:
        f.write(config_content)
    return config_path


# =============================================================================
# TESTS: ValidationConfigLoader
# =============================================================================

class TestValidationConfigLoader:
    """Test ValidationConfigLoader class."""

    def test_load_with_no_config_file(self, temp_project_dir: Path):
        """Test loading when no config file exists."""
        loader = ValidationConfigLoader(temp_project_dir)
        config = loader.load()

        # Should return default config
        assert config is not None
        assert config.enabled is True  # Default value
        assert config.strict_mode is False
        assert len(config.disabled_rules) == 0
        assert loader.has_config_file() is False

    def test_load_with_valid_json_config(self, valid_json_config: Path):
        """Test loading a valid JSON config file."""
        loader = ValidationConfigLoader(valid_json_config.parent.parent)
        config = loader.load()

        assert config.enabled is True
        assert config.strict_mode is False
        assert config.disabled_rules == ["bash-rm-rf-root"]
        assert config.severity_overrides == {"bash-chmod-777": "low"}
        assert config.allowed_paths == ["tests/**", "build/**"]
        assert config.log_all_validations is True
        assert config.version == "1.0"
        assert loader.has_config_file() is True

    def test_load_with_valid_yaml_config(self, valid_yaml_config: Path):
        """Test loading a valid YAML config file."""
        loader = ValidationConfigLoader(valid_yaml_config.parent.parent)
        config = loader.load()

        assert config.enabled is True
        assert config.strict_mode is False
        assert config.disabled_rules == ["bash-rm-rf-root"]
        assert config.severity_overrides == {"bash-chmod-777": "low"}
        assert config.allowed_paths == ["tests/**", "build/**"]
        assert config.log_all_validations is True

    def test_load_with_invalid_json(self, invalid_json_config: Path):
        """Test loading an invalid JSON file."""
        loader = ValidationConfigLoader(invalid_json_config.parent.parent)
        config = loader.load()

        # Should fall back to defaults
        assert config.enabled is True
        assert len(loader.get_load_errors()) > 0
        assert "Failed to read config file" in loader.get_load_errors()[0]

    def test_load_with_invalid_schema(self, invalid_schema_config: Path):
        """Test loading a config with schema validation errors."""
        loader = ValidationConfigLoader(invalid_schema_config.parent.parent)

        with pytest.raises(ValueError) as exc_info:
            loader.load()

        error_msg = str(exc_info.value)
        assert "Config validation errors" in error_msg
        assert "'enabled' must be a boolean" in error_msg
        assert "'disabled_rules[1]' must be a string" in error_msg
        assert "Invalid severity for rule 'rule1'" in error_msg
        assert "Unknown keys: unknown_key" in error_msg

    def test_load_with_invalid_custom_rule(self, invalid_custom_rule_config: Path):
        """Test loading a config with invalid custom rule."""
        loader = ValidationConfigLoader(invalid_custom_rule_config.parent.parent)

        with pytest.raises(ValueError) as exc_info:
            loader.load()

        error_msg = str(exc_info.value)
        assert "Missing required field 'name'" in error_msg
        assert "Missing required field 'description'" in error_msg
        assert "Missing required field 'pattern'" in error_msg
        assert "'severity' must be one of" in error_msg
        assert "'priority' must be one of" in error_msg
        assert "invalid tool 'InvalidTool'" in error_msg

    def test_load_with_valid_custom_rules(self, valid_custom_rules_config: Path):
        """Test loading a config with valid custom rules."""
        loader = ValidationConfigLoader(valid_custom_rules_config.parent.parent)
        config = loader.load()

        assert len(config.custom_rules) == 1
        rule = config.custom_rules[0]
        assert rule["rule_id"] == "custom-test-rule"
        assert rule["name"] == "Custom Test Rule"
        assert rule["severity"] == "high"

    def test_find_config_file(self, temp_project_dir: Path):
        """Test finding config file in .auto-claude directory."""
        loader = ValidationConfigLoader(temp_project_dir)

        # No config file
        assert loader._find_config_file() is None

        # Create JSON config
        json_config = temp_project_dir / ".auto-claude" / "output-validation.json"
        json_config.write_text("{}")

        loader2 = ValidationConfigLoader(temp_project_dir)
        assert loader2._find_config_file() == json_config

    def test_config_file_priority(self, temp_project_dir: Path):
        """Test that JSON config takes priority over YAML."""
        loader = ValidationConfigLoader(temp_project_dir)
        auto_claude_dir = temp_project_dir / ".auto-claude"

        # Create both JSON and YAML configs
        json_config = auto_claude_dir / "output-validation.json"
        json_config.write_text('{"enabled": true}')

        if is_yaml_available():
            yaml_config = auto_claude_dir / "output-validation.yaml"
            yaml_config.write_text("enabled: false")

        # JSON should be found first (lower priority in list means checked first)
        loader2 = ValidationConfigLoader(temp_project_dir)
        found = loader2._find_config_file()

        assert found is not None
        assert found.suffix == ".json"


# =============================================================================
# TESTS: Module Functions
# =============================================================================

class TestModuleFunctions:
    """Test module-level functions."""

    def test_load_validation_config(self, valid_json_config: Path):
        """Test load_validation_config function."""
        project_dir = valid_json_config.parent.parent
        config = load_validation_config(project_dir)

        assert config.enabled is True
        assert config.disabled_rules == ["bash-rm-rf-root"]

    def test_load_validation_config_caching(self, valid_json_config: Path):
        """Test that load_validation_config caches results."""
        project_dir = valid_json_config.parent.parent

        # First load
        config1 = load_validation_config(project_dir)
        # Second load (should be cached)
        config2 = load_validation_config(project_dir)

        assert config1 is config2

    def test_get_validation_config(self, valid_json_config: Path):
        """Test get_validation_config function."""
        project_dir = valid_json_config.parent.parent

        # Not loaded yet
        config = get_validation_config(project_dir)
        assert config is None

        # Load it
        load_validation_config(project_dir)

        # Now it should be available
        config = get_validation_config(project_dir)
        assert config is not None
        assert config.enabled is True

    def test_clear_config_cache(self, valid_json_config: Path):
        """Test clear_config_cache function."""
        project_dir = valid_json_config.parent.parent

        # Load config
        load_validation_config(project_dir)
        assert get_validation_config(project_dir) is not None

        # Clear cache for this project
        clear_config_cache(project_dir)
        assert get_validation_config(project_dir) is None

    def test_clear_config_cache_all(self, valid_json_config: Path):
        """Test clearing all cached configs."""
        project_dir = valid_json_config.parent.parent

        # Load config
        load_validation_config(project_dir)
        assert get_validation_config(project_dir) is not None

        # Clear all cache
        clear_config_cache()
        assert get_validation_config(project_dir) is None

    def test_get_config_file_path(self, temp_project_dir: Path):
        """Test get_config_file_path function."""
        # No config file
        assert get_config_file_path(temp_project_dir) is None

        # Create config file
        config_path = temp_project_dir / ".auto-claude" / "output-validation.json"
        config_path.write_text("{}")

        assert get_config_file_path(temp_project_dir) == config_path

    def test_is_yaml_available(self):
        """Test is_yaml_available function."""
        # Should return a boolean
        assert isinstance(is_yaml_available(), bool)


# =============================================================================
# TESTS: Config Merging
# =============================================================================

class TestConfigMerging:
    """Test that project config merges with defaults correctly."""

    def test_partial_config_uses_defaults(self, temp_project_dir: Path):
        """Test that partial config uses defaults for missing fields."""
        config_path = temp_project_dir / ".auto-claude" / "output-validation.json"
        config_data = {
            "enabled": False,
            # All other fields missing - should use defaults
        }
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = load_validation_config(temp_project_dir)

        assert config.enabled is False  # From config
        assert config.strict_mode is False  # Default
        assert config.disabled_rules == []  # Default
        assert config.log_all_validations is False  # Default

    def test_empty_config_uses_all_defaults(self, temp_project_dir: Path):
        """Test that empty config file uses all defaults."""
        config_path = temp_project_dir / ".auto-claude" / "output-validation.json"
        with open(config_path, "w") as f:
            json.dump({}, f)

        config = load_validation_config(temp_project_dir)

        # All should be defaults
        assert config.enabled is True
        assert config.strict_mode is False
        assert len(config.disabled_rules) == 0
        assert len(config.severity_overrides) == 0
        assert len(config.allowed_paths) == 0
        assert config.log_all_validations is False
        assert config.version == "1.0"


# =============================================================================
# TESTS: Severity Overrides
# =============================================================================

class TestSeverityOverrides:
    """Test severity override functionality."""

    def test_get_severity_override(self, temp_project_dir: Path):
        """Test getting custom severity for a rule."""
        config_path = temp_project_dir / ".auto-claude" / "output-validation.json"
        config_data = {
            "severity_overrides": {
                "bash-rm-rf-root": "low",
                "bash-chmod-777": "medium",
            },
        }
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = load_validation_config(temp_project_dir)

        assert config.get_severity_override("bash-rm-rf-root") == SeverityLevel.LOW
        assert (
            config.get_severity_override("bash-chmod-777") == SeverityLevel.MEDIUM
        )
        assert config.get_severity_override("non-existent-rule") is None

    def test_invalid_severity_in_override(self, temp_project_dir: Path):
        """Test that invalid severity values are rejected."""
        config_path = temp_project_dir / ".auto-claude" / "output-validation.json"
        config_data = {
            "severity_overrides": {
                "bash-rm-rf-root": "invalid",
            },
        }
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        loader = ValidationConfigLoader(temp_project_dir)

        with pytest.raises(ValueError) as exc_info:
            loader.load()

        assert "Invalid severity for rule 'bash-rm-rf-root'" in str(exc_info.value)


# =============================================================================
# TESTS: Disabled Rules
# =============================================================================

class TestDisabledRules:
    """Test disabled rules functionality."""

    def test_is_rule_disabled(self, temp_project_dir: Path):
        """Test checking if a rule is disabled."""
        config_path = temp_project_dir / ".auto-claude" / "output-validation.json"
        config_data = {
            "disabled_rules": ["bash-rm-rf-root", "bash-chmod-777"],
        }
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = load_validation_config(temp_project_dir)

        assert config.is_rule_disabled("bash-rm-rf-root") is True
        assert config.is_rule_disabled("bash-chmod-777") is True
        assert config.is_rule_disabled("some-other-rule") is False

    def test_disabled_rules_with_non_string(self, temp_project_dir: Path):
        """Test that non-string rule IDs are rejected."""
        config_path = temp_project_dir / ".auto-claude" / "output-validation.json"
        config_data = {
            "disabled_rules": ["rule1", 123, {"key": "value"}],
        }
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        loader = ValidationConfigLoader(temp_project_dir)

        with pytest.raises(ValueError) as exc_info:
            loader.load()

        assert "'disabled_rules[1]' must be a string" in str(exc_info.value)
        assert "'disabled_rules[2]' must be a string" in str(exc_info.value)
