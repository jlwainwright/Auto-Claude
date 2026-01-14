#!/usr/bin/env python3
"""
Manual test script for output validation configuration loader.
Tests basic functionality without requiring pytest.
"""

import json
import tempfile
from pathlib import Path

from security.output_validation.config import (
    ValidationConfigLoader,
    clear_config_cache,
    get_config_file_path,
    load_validation_config,
)


def test_no_config_file():
    """Test loading when no config file exists."""
    print("\n=== Test 1: No config file ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        loader = ValidationConfigLoader(project_dir)
        config = loader.load()

        print(f"✓ Config loaded: {config is not None}")
        print(f"✓ Default enabled: {config.enabled}")
        print(f"✓ Has config file: {loader.has_config_file()}")
        assert config.enabled is True  # Default value


def test_valid_json_config():
    """Test loading a valid JSON config file."""
    print("\n=== Test 2: Valid JSON config ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        auto_claude_dir = project_dir / ".auto-claude"
        auto_claude_dir.mkdir()

        config_path = auto_claude_dir / "output-validation.json"
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

        loader = ValidationConfigLoader(project_dir)
        config = loader.load()

        print(f"✓ Config loaded: {config is not None}")
        print(f"✓ Enabled: {config.enabled}")
        print(f"✓ Strict mode: {config.strict_mode}")
        print(f"✓ Disabled rules: {config.disabled_rules}")
        print(f"✓ Severity overrides: {config.severity_overrides}")
        print(f"✓ Allowed paths: {config.allowed_paths}")
        print(f"✓ Log all validations: {config.log_all_validations}")
        print(f"✓ Version: {config.version}")

        assert config.enabled is True
        assert config.strict_mode is False
        assert config.disabled_rules == ["bash-rm-rf-root"]
        assert config.severity_overrides == {"bash-chmod-777": "low"}
        assert config.allowed_paths == ["tests/**", "build/**"]


def test_invalid_schema_config():
    """Test loading a config with schema validation errors."""
    print("\n=== Test 3: Invalid schema config ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        auto_claude_dir = project_dir / ".auto-claude"
        auto_claude_dir.mkdir()

        config_path = auto_claude_dir / "output-validation.json"
        config_data = {
            "enabled": "not-a-boolean",  # Should be boolean
            "disabled_rules": ["rule1", 123],  # Should all be strings
            "unknown_key": "should-not-be-here",
        }
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        loader = ValidationConfigLoader(project_dir)

        try:
            loader.load()
            print("✗ Should have raised ValueError")
            assert False
        except ValueError as e:
            error_msg = str(e)
            print(f"✓ Raised ValueError as expected")
            print(f"✓ Error message: {error_msg[:200]}...")
            assert "Config validation errors" in error_msg
            assert "'enabled' must be a boolean" in error_msg


def test_custom_rules_config():
    """Test loading a config with custom rules."""
    print("\n=== Test 4: Custom rules config ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        auto_claude_dir = project_dir / ".auto-claude"
        auto_claude_dir.mkdir()

        config_path = auto_claude_dir / "output-validation.json"
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

        loader = ValidationConfigLoader(project_dir)
        config = loader.load()

        print(f"✓ Config loaded with custom rules")
        print(f"✓ Number of custom rules: {len(config.custom_rules)}")
        print(f"✓ Custom rule ID: {config.custom_rules[0]['rule_id']}")
        assert len(config.custom_rules) == 1
        assert config.custom_rules[0]["rule_id"] == "custom-test-rule"


def test_yaml_config():
    """Test loading a YAML config file."""
    print("\n=== Test 5: YAML config ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        auto_claude_dir = project_dir / ".auto-claude"
        auto_claude_dir.mkdir()

        config_path = auto_claude_dir / "output-validation.yaml"
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

        loader = ValidationConfigLoader(project_dir)
        config = loader.load()

        print(f"✓ YAML config loaded successfully")
        print(f"✓ Enabled: {config.enabled}")
        print(f"✓ Disabled rules: {config.disabled_rules}")

        assert config.enabled is True
        assert config.disabled_rules == ["bash-rm-rf-root"]


def test_config_caching():
    """Test configuration caching."""
    print("\n=== Test 6: Config caching ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        auto_claude_dir = project_dir / ".auto-claude"
        auto_claude_dir.mkdir()

        config_path = auto_claude_dir / "output-validation.json"
        config_data = {"enabled": False}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        # Clear cache first
        clear_config_cache(project_dir)

        # Load config
        config1 = load_validation_config(project_dir)
        config2 = load_validation_config(project_dir)

        print(f"✓ Config caching working: {config1 is config2}")
        assert config1 is config2

        # Clear cache and verify
        clear_config_cache(project_dir)
        config3 = load_validation_config(project_dir)

        print(f"✓ Cache cleared: {config1 is not config3}")
        assert config1 is not config3


def test_get_config_file_path():
    """Test getting config file path."""
    print("\n=== Test 7: Get config file path ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # No config file
        path = get_config_file_path(project_dir)
        print(f"✓ No config file: {path is None}")
        assert path is None

        # Create config file
        auto_claude_dir = project_dir / ".auto-claude"
        auto_claude_dir.mkdir()
        config_path = auto_claude_dir / "output-validation.json"
        config_path.write_text("{}")

        path = get_config_file_path(project_dir)
        print(f"✓ Config file path: {path}")
        print(f"✓ Expected path: {config_path}")
        print(f"✓ Path resolved: {config_path.resolve()}")
        assert path == config_path.resolve() or path == config_path


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Output Validation Configuration Loader")
    print("=" * 60)

    try:
        test_no_config_file()
        test_valid_json_config()
        test_invalid_schema_config()
        test_custom_rules_config()
        test_yaml_config()
        test_config_caching()
        test_get_config_file_path()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
