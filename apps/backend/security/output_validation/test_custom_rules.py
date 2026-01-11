"""
Tests for Custom Validation Rules
==================================

Tests for loading, validating, and merging custom validation rules from
project configuration.
"""

import pytest

from security.output_validation.config import OutputValidationConfig
from security.output_validation.custom_rules import (
    CustomRuleError,
    apply_config_overrides,
    get_active_rules,
    get_custom_rule_ids,
    load_custom_rules,
    merge_with_defaults,
    validate_pattern_safety,
)
from security.output_validation.models import (
    RulePriority,
    SeverityLevel,
    ToolType,
    ValidationRule,
)
from security.output_validation.rules import get_default_rules, get_rule_by_id


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_custom_rule_dict() -> dict:
    """A valid custom rule dictionary."""
    return {
        "rule_id": "custom-test-rule",
        "name": "Custom Test Rule",
        "description": "A custom validation rule for testing",
        "pattern": r"test-dangerous-pattern",
        "pattern_type": "regex",
        "severity": "high",
        "priority": "p1",
        "tool_types": ["Bash", "Write"],
        "context": "command",
        "message": "This matches a test pattern",
        "suggestions": ["Use alternative pattern", "Review the command"],
        "enabled": True,
        "category": "custom",
    }


@pytest.fixture
def sample_config(sample_custom_rule_dict: dict) -> OutputValidationConfig:
    """A config with a custom rule."""
    return OutputValidationConfig(
        enabled=True,
        strict_mode=False,
        disabled_rules=["bash-rm-rf-root"],
        severity_overrides={"bash-chmod-777": "low"},
        custom_rules=[sample_custom_rule_dict],
    )


@pytest.fixture
def sample_custom_rule(sample_custom_rule_dict: dict) -> ValidationRule:
    """A ValidationRule object from the custom rule dict."""
    return ValidationRule(
        rule_id=sample_custom_rule_dict["rule_id"],
        name=sample_custom_rule_dict["name"],
        description=sample_custom_rule_dict["description"],
        pattern=sample_custom_rule_dict["pattern"],
        pattern_type=sample_custom_rule_dict["pattern_type"],
        severity=SeverityLevel(sample_custom_rule_dict["severity"]),
        priority=RulePriority(sample_custom_rule_dict["priority"]),
        tool_types=[ToolType(t) for t in sample_custom_rule_dict["tool_types"]],
        context=sample_custom_rule_dict["context"],
        message=sample_custom_rule_dict["message"],
        suggestions=sample_custom_rule_dict["suggestions"],
        enabled=sample_custom_rule_dict["enabled"],
        category=sample_custom_rule_dict["category"],
    )


# =============================================================================
# TESTS: Pattern Safety Validation
# =============================================================================

class TestPatternSafetyValidation:
    """Test pattern safety validation."""

    def test_safe_regex_pattern(self):
        """Test that safe regex patterns pass validation."""
        safe_patterns = [
            r"test-pattern",
            r"rm\s+-rf",
            r"(?i)drop\s+database",
            r"^/etc/passwd$",
            r"api_key\s*[=:]",
        ]

        for pattern in safe_patterns:
            # Should not raise
            validate_pattern_safety(pattern, "regex")

    def test_literal_pattern_always_safe(self):
        """Test that literal patterns are always considered safe."""
        validate_pattern_safety("any literal text", "literal")
        validate_pattern_safety(".*", "literal")  # Even regex-like strings

    def test_invalid_regex_pattern(self):
        """Test that invalid regex patterns are rejected."""
        invalid_patterns = [
            r"(?P<unclosed",
            r"*invalid",
            r"[unclosed",
            r"(?invalid)",
        ]

        for pattern in invalid_patterns:
            with pytest.raises(CustomRuleError) as exc_info:
                validate_pattern_safety(pattern, "regex")

            assert "Invalid regex pattern" in str(exc_info.value)
            assert exc_info.value.field == "pattern"

    def test_overly_permissive_patterns(self):
        """Test that overly permissive patterns are rejected."""
        overly_permissive = [
            r"^.*$",
            r".*",
            r"^.+$",
        ]

        for pattern in overly_permissive:
            with pytest.raises(CustomRuleError) as exc_info:
                validate_pattern_safety(pattern, "regex")

            assert "overly permissive" in str(exc_info.value).lower()

    def test_nested_quantifiers(self):
        """Test that nested quantifiers are rejected."""
        nested_quantifier_patterns = [
            r"(a+)+",
            r"(b*)*",
            r"c++",
        ]

        for pattern in nested_quantifier_patterns:
            with pytest.raises(CustomRuleError) as exc_info:
                validate_pattern_safety(pattern, "regex")

            assert "nested quantifiers" in str(exc_info.value).lower()

    def test_overlapping_alternations(self):
        """Test that overlapping alternations are rejected."""
        overlapping_patterns = [
            r"(a|aa)+",
            r"(test|testing)+",
            r"(b|bb|bbb)*",
        ]

        for pattern in overlapping_patterns:
            with pytest.raises(CustomRuleError) as exc_info:
                validate_pattern_safety(pattern, "regex")

            assert "overlapping alternation" in str(exc_info.value).lower()

    def test_excessive_repetition(self):
        """Test that excessive repetition limits are rejected."""
        excessive_patterns = [
            r"a{10000}",
            r"b{1000,}",
            r"c{500,10000}",
        ]

        for pattern in excessive_patterns:
            with pytest.raises(CustomRuleError) as exc_info:
                validate_pattern_safety(pattern, "regex")

            assert "excessive repetition" in str(exc_info.value).lower()


# =============================================================================
# TESTS: Load Custom Rules
# =============================================================================

class TestLoadCustomRules:
    """Test loading custom rules from configuration."""

    def test_load_valid_custom_rule(self, sample_config: OutputValidationConfig):
        """Test loading a valid custom rule."""
        rules = load_custom_rules(sample_config)

        assert len(rules) == 1
        rule = rules[0]
        assert rule.rule_id == "custom-test-rule"
        assert rule.name == "Custom Test Rule"
        assert rule.pattern == r"test-dangerous-pattern"
        assert rule.severity == SeverityLevel.HIGH
        assert rule.priority == RulePriority.P1
        assert ToolType.BASH in rule.tool_types
        assert ToolType.WRITE in rule.tool_types

    def test_load_custom_rule_with_defaults(self):
        """Test loading custom rule with default values."""
        config = OutputValidationConfig(
            custom_rules=[{
                "rule_id": "minimal-rule",
                "name": "Minimal Rule",
                "description": "A minimal rule",
                "pattern": "test",
            }]
        )

        rules = load_custom_rules(config)

        assert len(rules) == 1
        rule = rules[0]
        assert rule.pattern_type == "regex"  # Default
        assert rule.severity == SeverityLevel.MEDIUM  # Default
        assert rule.priority == RulePriority.P2  # Default
        assert rule.tool_types == []  # Default (empty list)
        assert rule.context == "all"  # Default
        assert rule.enabled is True  # Default
        assert rule.category == "custom"  # Default

    def test_load_multiple_custom_rules(self):
        """Test loading multiple custom rules."""
        config = OutputValidationConfig(
            custom_rules=[
                {
                    "rule_id": "rule-1",
                    "name": "Rule 1",
                    "description": "First rule",
                    "pattern": "pattern-1",
                },
                {
                    "rule_id": "rule-2",
                    "name": "Rule 2",
                    "description": "Second rule",
                    "pattern": "pattern-2",
                },
            ]
        )

        rules = load_custom_rules(config)

        assert len(rules) == 2
        assert rules[0].rule_id == "rule-1"
        assert rules[1].rule_id == "rule-2"

    def test_load_disabled_custom_rule(self):
        """Test that disabled custom rules are not loaded."""
        config = OutputValidationConfig(
            custom_rules=[{
                "rule_id": "disabled-rule",
                "name": "Disabled Rule",
                "description": "A disabled rule",
                "pattern": "test",
                "enabled": False,
            }]
        )

        rules = load_custom_rules(config)

        assert len(rules) == 0

    def test_load_custom_rule_missing_required_field(self):
        """Test that missing required fields are rejected."""
        required_fields = ["rule_id", "name", "description", "pattern"]

        for field in required_fields:
            rule_dict = {
                "rule_id": "test-rule",
                "name": "Test Rule",
                "description": "Test",
                "pattern": "test",
            }
            del rule_dict[field]

            config = OutputValidationConfig(custom_rules=[rule_dict])

            with pytest.raises(CustomRuleError) as exc_info:
                load_custom_rules(config)

            assert f"Missing required field '{field}'" in str(exc_info.value)

    def test_load_custom_rule_invalid_rule_id(self):
        """Test that invalid rule IDs are rejected."""
        invalid_ids = [
            "rule with spaces",
            "rule/with/slashes",
            "rule.with.dots",
            "rule@with@special",
        ]

        for rule_id in invalid_ids:
            config = OutputValidationConfig(
                custom_rules=[{
                    "rule_id": rule_id,
                    "name": "Invalid Rule",
                    "description": "Test",
                    "pattern": "test",
                }]
            )

            with pytest.raises(CustomRuleError) as exc_info:
                load_custom_rules(config)

            assert "alphanumeric" in str(exc_info.value).lower()

    def test_load_custom_rule_conflicts_with_default(self):
        """Test that custom rule IDs conflicting with defaults are rejected."""
        # Use a known default rule ID
        config = OutputValidationConfig(
            custom_rules=[{
                "rule_id": "bash-rm-rf-root",  # Default rule ID
                "name": "Conflicting Rule",
                "description": "Test",
                "pattern": "test",
            }]
        )

        with pytest.raises(CustomRuleError) as exc_info:
            load_custom_rules(config)

        assert "conflicts with a default rule" in str(exc_info.value).lower()

    def test_load_custom_rule_invalid_pattern_type(self):
        """Test that invalid pattern types are rejected."""
        config = OutputValidationConfig(
            custom_rules=[{
                "rule_id": "test-rule",
                "name": "Test",
                "description": "Test",
                "pattern": "test",
                "pattern_type": "invalid",
            }]
        )

        with pytest.raises(CustomRuleError) as exc_info:
            load_custom_rules(config)

        assert "pattern_type" in str(exc_info.value).lower()

    def test_load_custom_rule_unsafe_pattern(self):
        """Test that unsafe patterns are rejected."""
        config = OutputValidationConfig(
            custom_rules=[{
                "rule_id": "test-rule",
                "name": "Test",
                "description": "Test",
                "pattern": r"(a+)+",  # Nested quantifiers
            }]
        )

        with pytest.raises(CustomRuleError) as exc_info:
            load_custom_rules(config)

        assert "nested quantifiers" in str(exc_info.value).lower()

    def test_load_custom_rule_invalid_severity(self):
        """Test that invalid severity values are rejected."""
        config = OutputValidationConfig(
            custom_rules=[{
                "rule_id": "test-rule",
                "name": "Test",
                "description": "Test",
                "pattern": "test",
                "severity": "invalid",
            }]
        )

        with pytest.raises(CustomRuleError) as exc_info:
            load_custom_rules(config)

        assert "severity" in str(exc_info.value).lower()

    def test_load_custom_rule_invalid_priority(self):
        """Test that invalid priority values are rejected."""
        config = OutputValidationConfig(
            custom_rules=[{
                "rule_id": "test-rule",
                "name": "Test",
                "description": "Test",
                "pattern": "test",
                "priority": "invalid",
            }]
        )

        with pytest.raises(CustomRuleError) as exc_info:
            load_custom_rules(config)

        assert "priority" in str(exc_info.value).lower()

    def test_load_custom_rule_invalid_tool_type(self):
        """Test that invalid tool types are rejected."""
        config = OutputValidationConfig(
            custom_rules=[{
                "rule_id": "test-rule",
                "name": "Test",
                "description": "Test",
                "pattern": "test",
                "tool_types": ["InvalidTool"],
            }]
        )

        with pytest.raises(CustomRuleError) as exc_info:
            load_custom_rules(config)

        assert "tool type" in str(exc_info.value).lower()

    def test_load_custom_rule_invalid_context(self):
        """Test that invalid context values are rejected."""
        config = OutputValidationConfig(
            custom_rules=[{
                "rule_id": "test-rule",
                "name": "Test",
                "description": "Test",
                "pattern": "test",
                "context": "invalid",
            }]
        )

        with pytest.raises(CustomRuleError) as exc_info:
            load_custom_rules(config)

        assert "context" in str(exc_info.value).lower()

    def test_load_custom_rule_invalid_suggestions_type(self):
        """Test that non-list suggestions are rejected."""
        config = OutputValidationConfig(
            custom_rules=[{
                "rule_id": "test-rule",
                "name": "Test",
                "description": "Test",
                "pattern": "test",
                "suggestions": "not-a-list",
            }]
        )

        with pytest.raises(CustomRuleError) as exc_info:
            load_custom_rules(config)

        assert "suggestions" in str(exc_info.value).lower()


# =============================================================================
# TESTS: Merge with Defaults
# =============================================================================

class TestMergeWithDefaults:
    """Test merging custom rules with default rules."""

    def test_merge_with_no_custom_rules(self):
        """Test merging with no custom rules."""
        default_rules = get_default_rules()
        merged = merge_with_defaults(default_rules)

        # Should have same number of rules (all enabled)
        assert len(merged) == len(default_rules)

    def test_merge_with_custom_rules(self, sample_custom_rule: ValidationRule):
        """Test merging with custom rules."""
        default_rules = get_default_rules()
        merged = merge_with_defaults(
            default_rules=default_rules,
            custom_rules=[sample_custom_rule]
        )

        # Should have default rules + custom rule
        assert len(merged) == len(default_rules) + 1

        # Check custom rule is present
        custom_rule_ids = [r.rule_id for r in merged if r.category == "custom"]
        assert "custom-test-rule" in custom_rule_ids

    def test_merge_with_disabled_default_rules(self):
        """Test that disabled default rules are excluded."""
        default_rules = get_default_rules()
        config = OutputValidationConfig(
            disabled_rules=["bash-rm-rf-root", "bash-chmod-777"]
        )

        merged = merge_with_defaults(default_rules, config=config)

        # Disabled rules should not be in the merged list
        merged_rule_ids = [r.rule_id for r in merged]
        assert "bash-rm-rf-root" not in merged_rule_ids
        assert "bash-chmod-777" not in merged_rule_ids

    def test_merge_with_severity_overrides(self):
        """Test that severity overrides are applied."""
        default_rules = get_default_rules()
        config = OutputValidationConfig(
            severity_overrides={"bash-rm-rf-root": "low"}
        )

        merged = merge_with_defaults(default_rules, config=config)

        # Find the rule and check severity
        rm_rule = next((r for r in merged if r.rule_id == "bash-rm-rf-root"), None)
        assert rm_rule is not None
        assert rm_rule.severity == SeverityLevel.LOW

    def test_merge_custom_rule_conflict(self, sample_custom_rule_dict: dict):
        """Test that conflicting custom rule IDs are rejected."""
        # Use a default rule ID
        sample_custom_rule_dict["rule_id"] = "bash-rm-rf-root"
        custom_rule = ValidationRule(
            rule_id=sample_custom_rule_dict["rule_id"],
            name=sample_custom_rule_dict["name"],
            description=sample_custom_rule_dict["description"],
            pattern=sample_custom_rule_dict["pattern"],
            pattern_type=sample_custom_rule_dict["pattern_type"],
            severity=SeverityLevel(sample_custom_rule_dict["severity"]),
            priority=RulePriority(sample_custom_rule_dict["priority"]),
            tool_types=[ToolType(t) for t in sample_custom_rule_dict["tool_types"]],
            context=sample_custom_rule_dict["context"],
            message=sample_custom_rule_dict["message"],
            suggestions=sample_custom_rule_dict["suggestions"],
            enabled=sample_custom_rule_dict["enabled"],
            category=sample_custom_rule_dict["category"],
        )

        default_rules = get_default_rules()

        with pytest.raises(CustomRuleError) as exc_info:
            merge_with_defaults(
                default_rules=default_rules,
                custom_rules=[custom_rule]
            )

        assert "conflicts" in str(exc_info.value).lower()


# =============================================================================
# TESTS: Apply Config Overrides
# =============================================================================

class TestApplyConfigOverrides:
    """Test applying configuration overrides to rules."""

    def test_apply_disabled_rules(self):
        """Test applying disabled rules override."""
        rules = [
            ValidationRule(
                rule_id="rule-1",
                name="Rule 1",
                description="Test",
                pattern="test",
                enabled=True,
            ),
            ValidationRule(
                rule_id="rule-2",
                name="Rule 2",
                description="Test",
                pattern="test",
                enabled=True,
            ),
        ]

        config = OutputValidationConfig(
            disabled_rules=["rule-1"]
        )

        result = apply_config_overrides(rules, config)

        assert len(result) == 1
        assert result[0].rule_id == "rule-2"
        assert result[0].enabled is True

    def test_apply_severity_overrides(self):
        """Test applying severity overrides."""
        rules = [
            ValidationRule(
                rule_id="rule-1",
                name="Rule 1",
                description="Test",
                pattern="test",
                severity=SeverityLevel.HIGH,
            ),
        ]

        config = OutputValidationConfig(
            severity_overrides={"rule-1": "low"}
        )

        result = apply_config_overrides(rules, config)

        assert len(result) == 1
        assert result[0].severity == SeverityLevel.LOW

    def test_apply_both_overrides(self):
        """Test applying both disabled and severity overrides."""
        rules = [
            ValidationRule(
                rule_id="rule-1",
                name="Rule 1",
                description="Test",
                pattern="test",
                severity=SeverityLevel.HIGH,
                enabled=True,
            ),
            ValidationRule(
                rule_id="rule-2",
                name="Rule 2",
                description="Test",
                pattern="test",
                severity=SeverityLevel.MEDIUM,
                enabled=True,
            ),
        ]

        config = OutputValidationConfig(
            disabled_rules=["rule-1"],
            severity_overrides={"rule-2": "critical"}
        )

        result = apply_config_overrides(rules, config)

        assert len(result) == 1
        assert result[0].rule_id == "rule-2"
        assert result[0].severity == SeverityLevel.CRITICAL

    def test_does_not_modify_original_rules(self):
        """Test that original rules are not modified."""
        rules = [
            ValidationRule(
                rule_id="rule-1",
                name="Rule 1",
                description="Test",
                pattern="test",
                severity=SeverityLevel.HIGH,
                enabled=True,
            ),
        ]

        config = OutputValidationConfig(
            disabled_rules=["rule-1"],
            severity_overrides={"rule-1": "low"}
        )

        result = apply_config_overrides(rules, config)

        # Original rule should be unchanged
        assert rules[0].enabled is True
        assert rules[0].severity == SeverityLevel.HIGH

        # Result should have overrides applied
        # But rule is disabled so it won't be in result
        assert len(result) == 0


# =============================================================================
# TESTS: Rule Inspection
# =============================================================================

class TestRuleInspection:
    """Test rule inspection utility functions."""

    def test_get_custom_rule_ids(self):
        """Test getting custom rule IDs from config."""
        config = OutputValidationConfig(
            custom_rules=[
                {"rule_id": "rule-1", "name": "R1", "description": "T1", "pattern": "p1"},
                {"rule_id": "rule-2", "name": "R2", "description": "T2", "pattern": "p2"},
            ]
        )

        ids = get_custom_rule_ids(config)

        assert ids == ["rule-1", "rule-2"]

    def test_get_custom_rule_ids_empty(self):
        """Test getting custom rule IDs from empty config."""
        config = OutputValidationConfig(custom_rules=[])

        ids = get_custom_rule_ids(config)

        assert ids == []

    def test_get_active_rules_by_tool_type(self):
        """Test filtering rules by tool type."""
        rules = [
            ValidationRule(
                rule_id="rule-1",
                name="Rule 1",
                description="Test",
                pattern="test",
                tool_types=[ToolType.BASH],
            ),
            ValidationRule(
                rule_id="rule-2",
                name="Rule 2",
                description="Test",
                pattern="test",
                tool_types=[ToolType.WRITE],
            ),
            ValidationRule(
                rule_id="rule-3",
                name="Rule 3",
                description="Test",
                pattern="test",
                tool_types=[],  # Applies to all tools
            ),
        ]

        bash_rules = get_active_rules(rules, tool_type=ToolType.BASH)

        # Should include rule-1 and rule-3
        assert len(bash_rules) == 2
        bash_rule_ids = [r.rule_id for r in bash_rules]
        assert "rule-1" in bash_rule_ids
        assert "rule-3" in bash_rule_ids
        assert "rule-2" not in bash_rule_ids

    def test_get_active_rules_by_severity(self):
        """Test filtering rules by minimum severity."""
        rules = [
            ValidationRule(
                rule_id="rule-1",
                name="Rule 1",
                description="Test",
                pattern="test",
                severity=SeverityLevel.CRITICAL,
            ),
            ValidationRule(
                rule_id="rule-2",
                name="Rule 2",
                description="Test",
                pattern="test",
                severity=SeverityLevel.HIGH,
            ),
            ValidationRule(
                rule_id="rule-3",
                name="Rule 3",
                description="Test",
                pattern="test",
                severity=SeverityLevel.LOW,
            ),
        ]

        high_plus_rules = get_active_rules(rules, min_severity=SeverityLevel.HIGH)

        # Should include CRITICAL and HIGH
        assert len(high_plus_rules) == 2
        high_rule_ids = [r.rule_id for r in high_plus_rules]
        assert "rule-1" in high_rule_ids
        assert "rule-2" in high_rule_ids
        assert "rule-3" not in high_rule_ids

    def test_get_active_rules_both_filters(self):
        """Test filtering rules by both tool type and severity."""
        rules = [
            ValidationRule(
                rule_id="rule-1",
                name="Rule 1",
                description="Test",
                pattern="test",
                tool_types=[ToolType.BASH],
                severity=SeverityLevel.HIGH,
            ),
            ValidationRule(
                rule_id="rule-2",
                name="Rule 2",
                description="Test",
                pattern="test",
                tool_types=[ToolType.BASH],
                severity=SeverityLevel.LOW,
            ),
            ValidationRule(
                rule_id="rule-3",
                name="Rule 3",
                description="Test",
                pattern="test",
                tool_types=[ToolType.WRITE],
                severity=SeverityLevel.HIGH,
            ),
        ]

        filtered = get_active_rules(
            rules,
            tool_type=ToolType.BASH,
            min_severity=SeverityLevel.HIGH
        )

        # Should only include rule-1
        assert len(filtered) == 1
        assert filtered[0].rule_id == "rule-1"
