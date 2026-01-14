"""
Output Validation Configuration Loader
========================================

Loads and manages validation configuration from project's .auto-claude directory.
Supports JSON and YAML config formats with schema validation.

Configuration files searched in order:
1. .auto-claude/output-validation.json
2. .auto-claude/output-validation.yaml
3. .auto-claude/output-validation.yml

Project configuration merges with defaults, with project settings
taking precedence.

Usage:
    from security.output_validation.config import (
        load_validation_config,
        get_validation_config,
        ValidationConfigLoader,
    )

    # Load config for a project
    config = load_validation_config(project_dir=Path("/path/to/project"))

    # Get cached config
    config = get_validation_config(project_dir=Path("/path/to/project"))

    # Check if validation is enabled
    if config.enabled:
        print(f"Strict mode: {config.strict_mode}")
        print(f"Disabled rules: {config.disabled_rules}")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

# Optional YAML support (follows pattern from analysis/ci_discovery.py)
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .models import OutputValidationConfig, SeverityLevel, ToolType, ValidationRule


# =============================================================================
# CONFIG FILE NAMES
# =============================================================================

CONFIG_FILENAMES = [
    "output-validation.json",
    "output-validation.yaml",
    "output-validation.yml",
]

AUTO_CLAUDE_DIR = ".auto-claude"


# =============================================================================
# CONFIG SCHEMA DEFINITION
# =============================================================================

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "strict_mode": {"type": "boolean"},
        "disabled_rules": {"type": "array", "items": {"type": "string"}},
        "severity_overrides": {
            "type": "object",
            "patternProperties": {
                # Rule ID maps to severity level
                ".*": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
            },
        },
        "allowed_paths": {"type": "array", "items": {"type": "string"}},
        "custom_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["rule_id", "name", "description", "pattern"],
                "properties": {
                    "rule_id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "pattern": {"type": "string"},
                    "pattern_type": {"type": "string", "enum": ["regex", "literal"]},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "priority": {"type": "string", "enum": ["p0", "p1", "p2", "p3"]},
                    "tool_types": {"type": "array", "items": {"type": "string"}},
                    "context": {"type": "string", "enum": ["command", "file_content", "file_path", "all"]},
                    "message": {"type": "string"},
                    "suggestions": {"type": "array", "items": {"type": "string"}},
                    "enabled": {"type": "boolean"},
                    "category": {"type": "string"},
                },
            },
        },
        "log_all_validations": {"type": "boolean"},
        "version": {"type": "string"},
    },
    "additionalProperties": False,
}


# =============================================================================
# CONFIG LOADER
# =============================================================================

class ValidationConfigLoader:
    """
    Loads and caches validation configuration from project directory.

    Configuration is loaded from .auto-claude/output-validation.{json,yaml,yml}
    and merged with default values.

    Attributes:
        project_dir: Root directory of the project
        config_dir: Path to .auto-claude directory
        config_file: Path to the config file (if found)
        config: Loaded configuration (OutputValidationConfig)
    """

    def __init__(self, project_dir: Path):
        """
        Initialize config loader.

        Args:
            project_dir: Root directory of the project
        """
        self.project_dir = Path(project_dir).resolve()
        self.config_dir = self.project_dir / AUTO_CLAUDE_DIR
        self.config_file: Path | None = None
        self.config: OutputValidationConfig | None = None
        self._load_errors: list[str] = []

    def load(self) -> OutputValidationConfig:
        """
        Load configuration from .auto-claude directory.

        Searches for config files in order:
        1. output-validation.json
        2. output-validation.yaml
        3. output-validation.yml

        Returns:
            OutputValidationConfig with defaults merged with project config

        Raises:
            ValueError: If config file has validation errors
        """
        # Find config file
        self.config_file = self._find_config_file()

        if self.config_file is None:
            # No config file found, use defaults
            self.config = OutputValidationConfig()
            return self.config

        # Load and parse config file
        try:
            config_data = self._read_config_file(self.config_file)
        except Exception as e:
            # Log error but use defaults
            self._load_errors.append(f"Failed to read config file: {e}")
            self.config = OutputValidationConfig()
            return self.config

        # Validate config
        validation_errors = self._validate_config(config_data)
        if validation_errors:
            error_msg = f"Config validation errors in {self.config_file.name}:\n"
            error_msg += "\n".join(f"  - {err}" for err in validation_errors)
            raise ValueError(error_msg)

        # Create config object
        self.config = OutputValidationConfig.from_dict(config_data)
        return self.config

    def _find_config_file(self) -> Path | None:
        """Find the first existing config file."""
        if not self.config_dir.exists():
            return None

        for filename in CONFIG_FILENAMES:
            config_path = self.config_dir / filename
            if config_path.exists():
                return config_path

        return None

    def _read_config_file(self, config_path: Path) -> dict:
        """
        Read and parse config file based on extension.

        Args:
            config_path: Path to config file

        Returns:
            Parsed config data as dict

        Raises:
            ValueError: If file format is not supported or parsing fails
        """
        suffix = config_path.suffix.lower()

        try:
            with open(config_path, "r") as f:
                if suffix == ".json":
                    return json.load(f)
                elif suffix in (".yaml", ".yml"):
                    if not HAS_YAML:
                        raise ValueError(
                            "YAML format requires PyYAML package. "
                            "Install with: pip install pyyaml"
                        )
                    return yaml.safe_load(f) or {}
                else:
                    raise ValueError(f"Unsupported config file format: {suffix}")
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Invalid {suffix.upper()} in {config_path.name}: {e}")
        except OSError as e:
            raise ValueError(f"Failed to read {config_path.name}: {e}")

    def _validate_config(self, config_data: dict) -> list[str]:
        """
        Validate config data against schema.

        Args:
            config_data: Parsed config data

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check for unknown top-level keys
        valid_keys = set(CONFIG_SCHEMA["properties"].keys())
        unknown_keys = set(config_data.keys()) - valid_keys
        if unknown_keys:
            errors.append(f"Unknown keys: {', '.join(sorted(unknown_keys))}")

        # Validate enabled
        if "enabled" in config_data and not isinstance(config_data["enabled"], bool):
            errors.append("'enabled' must be a boolean")

        # Validate strict_mode
        if "strict_mode" in config_data and not isinstance(
            config_data["strict_mode"], bool
        ):
            errors.append("'strict_mode' must be a boolean")

        # Validate disabled_rules
        if "disabled_rules" in config_data:
            if not isinstance(config_data["disabled_rules"], list):
                errors.append("'disabled_rules' must be a list")
            else:
                for i, rule_id in enumerate(config_data["disabled_rules"]):
                    if not isinstance(rule_id, str):
                        errors.append(f"'disabled_rules[{i}]' must be a string")

        # Validate severity_overrides
        if "severity_overrides" in config_data:
            if not isinstance(config_data["severity_overrides"], dict):
                errors.append("'severity_overrides' must be an object")
            else:
                valid_severities = {"critical", "high", "medium", "low"}
                for rule_id, severity in config_data["severity_overrides"].items():
                    if not isinstance(rule_id, str):
                        errors.append(f"'severity_overrides' key must be string: {rule_id}")
                    if severity not in valid_severities:
                        errors.append(
                            f"Invalid severity for rule '{rule_id}': {severity}. "
                            f"Must be one of: {', '.join(sorted(valid_severities))}"
                        )

        # Validate allowed_paths
        if "allowed_paths" in config_data:
            if not isinstance(config_data["allowed_paths"], list):
                errors.append("'allowed_paths' must be a list")
            else:
                for i, path in enumerate(config_data["allowed_paths"]):
                    if not isinstance(path, str):
                        errors.append(f"'allowed_paths[{i}]' must be a string")

        # Validate custom_rules
        if "custom_rules" in config_data:
            if not isinstance(config_data["custom_rules"], list):
                errors.append("'custom_rules' must be a list")
            else:
                for i, rule_data in enumerate(config_data["custom_rules"]):
                    rule_errors = self._validate_custom_rule(rule_data, i)
                    errors.extend(rule_errors)

        # Validate log_all_validations
        if "log_all_validations" in config_data and not isinstance(
            config_data["log_all_validations"], bool
        ):
            errors.append("'log_all_validations' must be a boolean")

        # Validate version
        if "version" in config_data and not isinstance(config_data["version"], str):
            errors.append("'version' must be a string")

        return errors

    def _validate_custom_rule(self, rule_data: dict, index: int) -> list[str]:
        """
        Validate a single custom rule.

        Args:
            rule_data: Rule configuration
            index: Index in custom_rules list (for error messages)

        Returns:
            List of validation error messages
        """
        errors = []
        prefix = f"'custom_rules[{index}]'"

        # Required fields
        required_fields = ["rule_id", "name", "description", "pattern"]
        for field in required_fields:
            if field not in rule_data:
                errors.append(f"{prefix}: Missing required field '{field}'")
            elif not isinstance(rule_data[field], str):
                errors.append(f"{prefix}: Field '{field}' must be a string")

        # Optional fields with validation
        if "pattern_type" in rule_data:
            if rule_data["pattern_type"] not in ("regex", "literal"):
                errors.append(
                    f"{prefix}: 'pattern_type' must be 'regex' or 'literal', "
                    f"got '{rule_data['pattern_type']}'"
                )

        if "severity" in rule_data:
            valid_severities = {"critical", "high", "medium", "low"}
            if rule_data["severity"] not in valid_severities:
                errors.append(
                    f"{prefix}: 'severity' must be one of: {', '.join(sorted(valid_severities))}"
                )

        if "priority" in rule_data:
            valid_priorities = {"p0", "p1", "p2", "p3"}
            if rule_data["priority"] not in valid_priorities:
                errors.append(
                    f"{prefix}: 'priority' must be one of: {', '.join(sorted(valid_priorities))}"
                )

        if "tool_types" in rule_data:
            if not isinstance(rule_data["tool_types"], list):
                errors.append(f"{prefix}: 'tool_types' must be a list")
            else:
                valid_tools = {t.value for t in ToolType}
                for j, tool in enumerate(rule_data["tool_types"]):
                    if tool not in valid_tools:
                        errors.append(
                            f"{prefix}: 'tool_types[{j}]' invalid tool '{tool}'. "
                            f"Must be one of: {', '.join(sorted(valid_tools))}"
                        )

        if "context" in rule_data:
            valid_contexts = {"command", "file_content", "file_path", "all"}
            if rule_data["context"] not in valid_contexts:
                errors.append(
                    f"{prefix}: 'context' must be one of: {', '.join(sorted(valid_contexts))}"
                )

        if "enabled" in rule_data and not isinstance(rule_data["enabled"], bool):
            errors.append(f"{prefix}: 'enabled' must be a boolean")

        if "suggestions" in rule_data:
            if not isinstance(rule_data["suggestions"], list):
                errors.append(f"{prefix}: 'suggestions' must be a list")

        return errors

    def get_load_errors(self) -> list[str]:
        """Get list of errors encountered during loading."""
        return self._load_errors.copy()

    def has_config_file(self) -> bool:
        """Check if a config file exists."""
        return self.config_file is not None


# =============================================================================
# CONFIG CACHE
# =============================================================================

_config_cache: dict[str, OutputValidationConfig] = {}


def load_validation_config(project_dir: Path) -> OutputValidationConfig:
    """
    Load validation configuration for a project.

    Configuration is loaded from .auto-claude/output-validation.{json,yaml,yml}
    and merged with defaults. Results are cached by project directory.

    Args:
        project_dir: Root directory of the project

    Returns:
        OutputValidationConfig with defaults merged with project config

    Raises:
        ValueError: If config file has validation errors
    """
    project_dir = Path(project_dir).resolve()
    cache_key = str(project_dir)

    # Check cache
    if cache_key in _config_cache:
        return _config_cache[cache_key]

    # Load config
    loader = ValidationConfigLoader(project_dir)
    config = loader.load()

    # Cache result
    _config_cache[cache_key] = config
    return config


def get_validation_config(project_dir: Path) -> OutputValidationConfig | None:
    """
    Get cached validation configuration for a project.

    Returns None if configuration hasn't been loaded yet.

    Args:
        project_dir: Root directory of the project

    Returns:
        OutputValidationConfig if cached, None otherwise
    """
    project_dir = Path(project_dir).resolve()
    cache_key = str(project_dir)
    return _config_cache.get(cache_key)


def clear_config_cache(project_dir: Path | None = None) -> None:
    """
    Clear cached configuration.

    Args:
        project_dir: If provided, only clear cache for this project.
                     If None, clear all cached configurations.
    """
    global _config_cache

    if project_dir is None:
        _config_cache.clear()
    else:
        project_dir = Path(project_dir).resolve()
        cache_key = str(project_dir)
        _config_cache.pop(cache_key, None)


def get_config_file_path(project_dir: Path) -> Path | None:
    """
    Get the path to the config file for a project (if it exists).

    Args:
        project_dir: Root directory of the project

    Returns:
        Path to config file if found, None otherwise
    """
    loader = ValidationConfigLoader(project_dir)
    return loader._find_config_file()


def is_yaml_available() -> bool:
    """
    Check if YAML parsing is available.

    Returns:
        True if PyYAML is installed, False otherwise
    """
    return HAS_YAML
