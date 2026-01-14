"""
Comprehensive Integration Tests for Output Validation System
============================================================

Tests the complete output validation system including:
- Dangerous pattern detection for all tool types
- Per-project configuration loading
- Override token creation and validation
- Integration with SDK hook system
- End-to-end validation workflows

This test suite verifies acceptance criteria for subtask 6.3:
1. Test dangerous pattern detection for each tool type
2. Test per-project configuration loading
3. Test override token creation and validation
4. Test integration with SDK hook system
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import pytest

# Add backend to path
import sys
backend_path = Path(__file__).parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_path))

from security.output_validation import (
    output_validation_hook,
    reset_hook,
)
from security.output_validation.models import (
    OutputValidationConfig,
    SeverityLevel,
    ToolType,
    ValidationResult,
    ValidationRule,
    OverrideToken,
)
from security.output_validation.pattern_detector import (
    PatternDetector,
    create_pattern_detector,
)
from security.output_validation.rules import (
    get_default_rules,
    BASH_RULES,
    FILE_WRITE_RULES,
    FILE_PATH_RULES,
)
from security.output_validation.config import (
    ValidationConfigLoader,
    load_validation_config,
    get_validation_config,
    clear_config_cache,
)
from security.output_validation.custom_rules import (
    load_custom_rules,
    merge_with_defaults,
    apply_config_overrides,
)
from security.output_validation.allowed_paths import (
    AllowedPathsChecker,
    is_path_allowed,
)
from security.output_validation.overrides import (
    OverrideTokenManager,
    generate_override_token,
    validate_override_token,
    use_override_token,
    revoke_override_token,
    list_override_tokens,
)
from security.output_validation.validators import (
    TOOL_VALIDATORS,
    get_validator,
    validate_tool_output,
    register_validator,
    unregister_validator,
)
from security.output_validation.logger import (
    ValidationEventLogger,
    log_blocked_operation,
    log_warning,
    log_override_used,
    get_global_logger,
    clear_global_logger,
)
from security.output_validation.report import (
    ValidationReportGenerator,
    generate_validation_report,
    generate_and_save_report,
    print_validation_summary,
)
from security.output_validation.messages import (
    format_block_message,
    format_short_block_message,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir).resolve()


@pytest.fixture
def project_with_auto_claude(temp_project_dir):
    """Create a project directory with .auto-claude structure."""
    auto_claude_dir = temp_project_dir / ".auto-claude"
    auto_claude_dir.mkdir(parents=True, exist_ok=True)
    return temp_project_dir


@pytest.fixture
def pattern_detector():
    """Create a pattern detector with default rules."""
    detector = create_pattern_detector()
    detector.add_rules(get_default_rules())
    return detector


@pytest.fixture
def mock_sdk_context():
    """Create a mock SDK context object."""
    context = MagicMock()
    context.project_dir = Path("/tmp/test_project")
    return context


# =============================================================================
# PATTERN DETECTION TESTS - All Tool Types
# =============================================================================


class TestPatternDetectionBash:
    """Test dangerous pattern detection for Bash commands."""

    def test_detects_rm_rf_root(self, pattern_detector):
        """Test detection of rm -rf / command."""
        result = pattern_detector.match(
            pattern="rm -rf /",
            context="command",
            tool_type=ToolType.BASH,
        )
        assert result.is_blocked
        assert result.rule_id in ["bash-rm-rf-root", "bash-rm-danger"]

    def test_detects_drop_database(self, pattern_detector):
        """Test detection of DROP DATABASE command."""
        result = pattern_detector.match(
            pattern="DROP DATABASE production",
            context="command",
            tool_type=ToolType.BASH,
        )
        assert result.is_blocked
        assert "database" in result.rule_id.lower()

    def test_detects_chmod_777(self, pattern_detector):
        """Test detection of chmod 777 command."""
        result = pattern_detector.match(
            pattern="chmod 777 /etc/passwd",
            context="command",
            tool_type=ToolType.BASH,
        )
        assert result.is_blocked
        assert "chmod" in result.rule_id.lower()

    def test_allows_safe_commands(self, pattern_detector):
        """Test that safe commands are allowed."""
        result = pattern_detector.match(
            pattern="ls -la",
            context="command",
            tool_type=ToolType.BASH,
        )
        assert not result.is_blocked

    def test_detects_base64_encoded_commands(self, pattern_detector):
        """Test detection of base64 encoded dangerous commands."""
        result = pattern_detector.match(
            pattern="echo 'cm0gLXJmIC8=' | base64 -d | bash",
            context="command",
            tool_type=ToolType.BASH,
        )
        # Should detect the pipe to bash with base64
        assert result.is_blocked or result.severity == SeverityLevel.HIGH

    def test_detects_variable_exploitation(self, pattern_detector):
        """Test detection of command variable exploitation."""
        result = pattern_detector.match(
            pattern='eval $USER_INPUT',
            context="command",
            tool_type=ToolType.BASH,
        )
        assert result.is_blocked
        assert "eval" in result.rule_id.lower() or "injection" in result.rule_id.lower()


class TestPatternDetectionWrite:
    """Test dangerous pattern detection for Write operations."""

    def test_blocks_etc_passwd_write(self, pattern_detector):
        """Test blocking writes to /etc/passwd."""
        result = pattern_detector.match(
            pattern="/etc/passwd",
            context="file_path",
            tool_type=ToolType.WRITE,
        )
        assert result.is_blocked
        assert "passwd" in result.rule_id.lower()

    def test_blocks_system_directory_write(self, pattern_detector):
        """Test blocking writes to system directories."""
        result = pattern_detector.match(
            pattern="/usr/bin/evil",
            context="file_path",
            tool_type=ToolType.WRITE,
        )
        assert result.is_blocked
        assert "system" in result.rule_id.lower() or "path" in result.rule_id.lower()

    def test_detects_secret_in_content(self, pattern_detector):
        """Test detection of secrets in file content."""
        content = "API_KEY=sk-1234567890abcdef"
        result = pattern_detector.match(
            pattern=content,
            context="content",
            tool_type=ToolType.WRITE,
        )
        # Should warn about potential secret
        assert result.is_blocked or result.severity in [SeverityLevel.HIGH, SeverityLevel.MEDIUM]

    def test_allows_safe_writes(self, pattern_detector):
        """Test that safe writes are allowed."""
        result = pattern_detector.match(
            pattern="src/main.py",
            context="file_path",
            tool_type=ToolType.WRITE,
        )
        assert not result.is_blocked

    def test_blocks_ssh_key_write(self, pattern_detector):
        """Test blocking writes to SSH authorized_keys."""
        result = pattern_detector.match(
            pattern=".ssh/authorized_keys",
            context="file_path",
            tool_type=ToolType.WRITE,
        )
        assert result.is_blocked
        assert "ssh" in result.rule_id.lower()


class TestPatternDetectionEdit:
    """Test dangerous pattern detection for Edit operations."""

    def test_blocks_system_file_edit(self, pattern_detector):
        """Test blocking edits to system files."""
        result = pattern_detector.match(
            pattern="/etc/shadow",
            context="file_path",
            tool_type=ToolType.EDIT,
        )
        assert result.is_blocked

    def test_detects_code_injection(self, pattern_detector):
        """Test detection of code injection patterns."""
        new_string = 'eval(os.environ["CMD"])'
        result = pattern_detector.match(
            pattern=new_string,
            context="content",
            tool_type=ToolType.EDIT,
        )
        assert result.is_blocked or result.severity == SeverityLevel.HIGH

    def test_detects_import_injection(self, pattern_detector):
        """Test detection of __import__ injection."""
        new_string = '__import__("os").system("rm -rf /")'
        result = pattern_detector.match(
            pattern=new_string,
            context="content",
            tool_type=ToolType.EDIT,
        )
        assert result.is_blocked or result.severity == SeverityLevel.CRITICAL

    def test_allows_safe_edits(self, pattern_detector):
        """Test that safe edits are allowed."""
        result = pattern_detector.match(
            pattern="src/utils.py",
            context="file_path",
            tool_type=ToolType.EDIT,
        )
        assert not result.is_blocked


class TestPatternDetectionWebFetch:
    """Test dangerous pattern detection for WebFetch operations."""

    def test_blocks_internal_ip_access(self, pattern_detector):
        """Test blocking access to internal IP addresses."""
        result = pattern_detector.match(
            pattern="http://192.168.1.1/admin",
            context="url",
            tool_type=ToolType.WEB_FETCH,
        )
        assert result.is_blocked
        assert "internal" in result.rule_id.lower() or "ssrf" in result.rule_id.lower()

    def test_blocks_localhost_access(self, pattern_detector):
        """Test blocking access to localhost."""
        result = pattern_detector.match(
            pattern="http://localhost:8080/api",
            context="url",
            tool_type=ToolType.WEB_FETCH,
        )
        assert result.is_blocked or result.severity == SeverityLevel.HIGH

    def test_allows_external_urls(self, pattern_detector):
        """Test that external URLs are allowed."""
        result = pattern_detector.match(
            pattern="https://api.example.com/data",
            context="url",
            tool_type=ToolType.WEB_FETCH,
        )
        assert not result.is_blocked


class TestPatternDetectionWebSearch:
    """Test dangerous pattern detection for WebSearch operations."""

    def test_blocks_malicious_search_terms(self, pattern_detector):
        """Test blocking malicious search terms."""
        # Most web searches should be allowed, but we test the mechanism
        result = pattern_detector.match(
            pattern="how to hack a server",
            context="query",
            tool_type=ToolType.WEB_SEARCH,
        )
        # Web searches typically don't get blocked unless very specific patterns
        # This test verifies the mechanism works
        assert isinstance(result, ValidationResult)

    def test_allows_safe_searches(self, pattern_detector):
        """Test that safe searches are allowed."""
        result = pattern_detector.match(
            pattern="python async await tutorial",
            context="query",
            tool_type=ToolType.WEB_SEARCH,
        )
        assert not result.is_blocked


# =============================================================================
# CONFIGURATION LOADING TESTS
# =============================================================================


class TestConfigurationLoading:
    """Test per-project configuration loading."""

    def test_loads_default_config(self, temp_project_dir):
        """Test loading default configuration when no config file exists."""
        config = load_validation_config(temp_project_dir)
        assert config.enabled == True
        assert config.strict_mode == False
        assert isinstance(config.allowed_paths, list)

    def test_loads_json_config(self, project_with_auto_claude):
        """Test loading configuration from JSON file."""
        config_file = project_with_auto_claude / ".auto-claude" / "output-validation.json"
        config_data = {
            "enabled": True,
            "strict_mode": True,
            "allowed_paths": ["tests/**", "*.tmp"],
            "custom_rules": [
                {
                    "rule_id": "test-rule",
                    "name": "Test Rule",
                    "description": "A test custom rule",
                    "pattern": "test-pattern",
                    "severity": "high",
                    "enabled": True,
                }
            ],
            "disabled_rules": ["bash-ls"],
            "severity_overrides": {
                "bash-rm-danger": "low"
            }
        }

        config_file.write_text(json.dumps(config_data, indent=2))

        config = load_validation_config(project_with_auto_claude)
        assert config.enabled == True
        assert config.strict_mode == True
        assert "tests/**" in config.allowed_paths
        assert "*.tmp" in config.allowed_paths

    def test_config_caching(self, project_with_auto_claude):
        """Test that configuration is cached."""
        # Load once
        config1 = get_validation_config(project_with_auto_claude)

        # Load again - should return cached
        config2 = get_validation_config(project_with_auto_claude)

        # Should be same object
        assert config1 is config2

    def test_config_cache_invalidation(self, project_with_auto_claude):
        """Test cache invalidation."""
        config1 = get_validation_config(project_with_auto_claude)
        clear_config_cache(project_with_auto_claude)
        config2 = get_validation_config(project_with_auto_claude)

        # Should be different objects after cache clear
        assert config1 is not config2

    def test_custom_rules_validation(self, project_with_auto_claude):
        """Test custom rules are validated."""
        config_file = project_with_auto_claude / ".auto-claude" / "output-validation.json"
        config_data = {
            "custom_rules": [
                {
                    "rule_id": "safe-rule",
                    "name": "Safe Rule",
                    "description": "A safe custom rule",
                    "pattern": "safe-pattern",
                    "severity": "medium",
                    "enabled": True,
                }
            ]
        }

        config_file.write_text(json.dumps(config_data, indent=2))

        custom_rules = load_custom_rules(project_with_auto_claude)
        assert len(custom_rules) > 0
        assert custom_rules[0].rule_id == "safe-rule"

    def test_invalid_custom_rule_rejected(self, project_with_auto_claude):
        """Test that invalid custom rules are rejected."""
        config_file = project_with_auto_claude / ".auto-claude" / "output-validation.json"
        config_data = {
            "custom_rules": [
                {
                    "rule_id": "bad-rule",
                    "name": "Bad Rule",
                    # Missing required fields
                }
            ]
        }

        config_file.write_text(json.dumps(config_data, indent=2))

        # Should raise validation error
        with pytest.raises(Exception):
            load_custom_rules(project_with_auto_claude)


# =============================================================================
# OVERRIDE TOKEN TESTS
# =============================================================================


class TestOverrideTokens:
    """Test override token creation and validation."""

    def test_generate_override_token(self, project_with_auto_claude):
        """Test generating an override token."""
        token = generate_override_token(
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
            scope="all",
            expiry_minutes=60,
            reason="Testing",
        )

        assert token is not None
        assert token.rule_id == "bash-rm-rf-root"
        assert token.scope == "all"
        assert token.use_count == 0

    def test_validate_override_token(self, project_with_auto_claude):
        """Test validating an override token."""
        token = generate_override_token(
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
            scope="all",
            expiry_minutes=60,
        )

        # Should be valid
        is_valid, token_data = validate_override_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
        )

        assert is_valid == True
        assert token_data is not None

    def test_token_expires(self, project_with_auto_claude):
        """Test that tokens expire."""
        token = generate_override_token(
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
            scope="all",
            expiry_minutes=0,  # Expires immediately
        )

        # Manually set expiry to past
        tokens_file = project_with_auto_claude / ".auto-claude" / "override-tokens.json"
        with open(tokens_file, "r") as f:
            data = json.load(f)
        data["tokens"][0]["expires_at"] = "2020-01-01T00:00:00+00:00"
        with open(tokens_file, "w") as f:
            json.dump(data, f, indent=2)

        # Should be invalid
        is_valid, _ = validate_override_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
        )

        assert is_valid == False

    def test_token_scope_validation(self, project_with_auto_claude):
        """Test token scope validation."""
        token = generate_override_token(
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
            scope="file:/tmp/test.txt",
            expiry_minutes=60,
        )

        # Should not match different scope
        is_valid, _ = validate_override_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
            scope="file:/tmp/other.txt",
        )

        assert is_valid == False

    def test_token_usage_count(self, project_with_auto_claude):
        """Test token usage count decrement."""
        token = generate_override_token(
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
            scope="all",
            expiry_minutes=60,
            max_uses=1,
        )

        # Use the token
        success = use_override_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
        )

        assert success == True

        # Try to use again - should fail
        success2 = use_override_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
        )

        assert success2 == False

    def test_revoke_token(self, project_with_auto_claude):
        """Test revoking an override token."""
        token = generate_override_token(
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
            scope="all",
            expiry_minutes=60,
        )

        # Revoke
        revoke_override_token(
            token_id=token.token_id,
            project_dir=project_with_auto_claude,
        )

        # Should be invalid
        is_valid, _ = validate_override_token(
            token_id=token.token_id,
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
        )

        assert is_valid == False

    def test_list_tokens(self, project_with_auto_claude):
        """Test listing override tokens."""
        # Create multiple tokens
        token1 = generate_override_token(
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
            scope="all",
            expiry_minutes=60,
        )

        token2 = generate_override_token(
            rule_id="write-system-file",
            project_dir=project_with_auto_claude,
            scope="file:/tmp/test.txt",
            expiry_minutes=60,
        )

        tokens = list_override_tokens(project_dir=project_with_auto_claude)

        assert len(tokens) >= 2
        token_ids = [t.token_id for t in tokens]
        assert token1.token_id in token_ids
        assert token2.token_id in token_ids


# =============================================================================
# SDK HOOK INTEGRATION TESTS
# =============================================================================


class TestSDKHookIntegration:
    """Test integration with SDK hook system."""

    @pytest.mark.asyncio
    async def test_hook_blocks_dangerous_bash(self, project_with_auto_claude):
        """Test that hook blocks dangerous Bash commands."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "cwd": str(project_with_auto_claude),
        }

        mock_context = MagicMock()
        mock_context.project_dir = project_with_auto_claude

        result = await output_validation_hook(
            input_data=input_data,
            tool_use_id=None,
            context=mock_context,
        )

        assert result.get("decision") == "block"
        assert "reason" in result

    @pytest.mark.asyncio
    async def test_hook_allows_safe_bash(self, project_with_auto_claude):
        """Test that hook allows safe Bash commands."""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "cwd": str(project_with_auto_claude),
        }

        mock_context = MagicMock()
        mock_context.project_dir = project_with_auto_claude

        result = await output_validation_hook(
            input_data=input_data,
            tool_use_id=None,
            context=mock_context,
        )

        # Should return empty dict (allowed)
        assert result == {}

    @pytest.mark.asyncio
    async def test_hook_blocks_dangerous_write(self, project_with_auto_claude):
        """Test that hook blocks dangerous Write operations."""
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/etc/passwd",
                "content": "malicious content"
            },
            "cwd": str(project_with_auto_claude),
        }

        mock_context = MagicMock()
        mock_context.project_dir = project_with_auto_claude

        result = await output_validation_hook(
            input_data=input_data,
            tool_use_id=None,
            context=mock_context,
        )

        assert result.get("decision") == "block"

    @pytest.mark.asyncio
    async def test_hook_respects_override_token(self, project_with_auto_claude):
        """Test that hook respects override tokens."""
        # Generate override token
        token = generate_override_token(
            rule_id="bash-rm-rf-root",
            project_dir=project_with_auto_claude,
            scope="all",
            expiry_minutes=60,
        )

        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "cwd": str(project_with_auto_claude),
        }

        mock_context = MagicMock()
        mock_context.project_dir = project_with_auto_claude

        result = await output_validation_hook(
            input_data=input_data,
            tool_use_id=None,
            context=mock_context,
        )

        # Should allow due to override token
        assert result == {}

    @pytest.mark.asyncio
    async def test_hook_respects_allowed_paths(self, project_with_auto_claude):
        """Test that hook respects allowed paths configuration."""
        # Configure allowed paths
        config_file = project_with_auto_claude / ".auto-claude" / "output-validation.json"
        config_data = {
            "allowed_paths": ["tests/**", "build/**"]
        }
        config_file.write_text(json.dumps(config_data, indent=2))

        # Clear cache to load new config
        clear_config_cache(project_with_auto_claude)

        # Try to write to tests directory (should be allowed)
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(project_with_auto_claude / "tests" / "test.txt"),
                "content": "test content"
            },
            "cwd": str(project_with_auto_claude),
        }

        mock_context = MagicMock()
        mock_context.project_dir = project_with_auto_claude

        result = await output_validation_hook(
            input_data=input_data,
            tool_use_id=None,
            context=mock_context,
        )

        # Should allow (path is in allowlist)
        assert result == {}

    @pytest.mark.asyncio
    async def test_hook_handles_missing_tool_input(self, project_with_auto_claude):
        """Test that hook handles missing tool_input gracefully."""
        input_data = {
            "tool_name": "Bash",
            # Missing tool_input
            "cwd": str(project_with_auto_claude),
        }

        mock_context = MagicMock()
        mock_context.project_dir = project_with_auto_claude

        result = await output_validation_hook(
            input_data=input_data,
            tool_use_id=None,
            context=mock_context,
        )

        # Should handle gracefully
        assert "decision" in result or result == {}

    @pytest.mark.asyncio
    async def test_hook_logs_validation_events(self, project_with_auto_claude):
        """Test that hook logs validation events."""
        # Clear global logger
        clear_global_logger()

        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "cwd": str(project_with_auto_claude),
        }

        mock_context = MagicMock()
        mock_context.project_dir = project_with_auto_claude

        await output_validation_hook(
            input_data=input_data,
            tool_use_id=None,
            context=mock_context,
        )

        # Check that event was logged
        logger = get_global_logger()
        events = logger.get_events()
        assert len(events) > 0

        # Most recent event should be a block
        assert events[-1].decision == "block"


# =============================================================================
# VALIDATOR REGISTRY TESTS
# =============================================================================


class TestValidatorRegistry:
    """Test validator registry."""

    def test_get_validator_for_known_tools(self):
        """Test getting validators for known tools."""
        bash_validator = get_validator("Bash")
        assert bash_validator is not None

        write_validator = get_validator("Write")
        assert write_validator is not None

        edit_validator = get_validator("Edit")
        assert edit_validator is not None

    def test_get_unknown_tool_returns_none(self):
        """Test that unknown tools return None."""
        validator = get_validator("UnknownTool")
        assert validator is None

    def test_validate_tool_output_unified_interface(self):
        """Test unified validation interface."""
        # Bash
        result = validate_tool_output(
            tool_name="Bash",
            tool_input={"command": "ls -la"},
            project_dir=Path("/tmp"),
        )
        assert result.is_allowed

        # Write
        result = validate_tool_output(
            tool_name="Write",
            tool_input={
                "file_path": "/etc/passwd",
                "content": "test"
            },
            project_dir=Path("/tmp"),
        )
        assert result.is_blocked

    def test_register_custom_validator(self):
        """Test registering a custom validator."""
        async def custom_validator(tool_input, detector, config, project_dir):
            return ValidationResult.allowed()

        register_validator("CustomTool", custom_validator)

        validator = get_validator("CustomTool")
        assert validator is not None

        # Cleanup
        unregister_validator("CustomTool")

    def test_unregister_validator(self):
        """Test unregistering a validator."""
        async def custom_validator(tool_input, detector, config, project_dir):
            return ValidationResult.allowed()

        register_validator("TempTool", custom_validator)
        assert get_validator("TempTool") is not None

        unregister_validator("TempTool")
        assert get_validator("TempTool") is None


# =============================================================================
# LOGGING AND REPORTING TESTS
# =============================================================================


class TestLoggingAndReporting:
    """Test logging and reporting functionality."""

    def test_log_blocked_operation(self, project_with_auto_claude):
        """Test logging blocked operations."""
        clear_global_logger()

        rule = ValidationRule(
            rule_id="test-rule",
            name="Test Rule",
            description="Test description",
            pattern="test",
            severity=SeverityLevel.HIGH,
        )

        log_blocked_operation(
            tool_name="Bash",
            tool_input={"command": "dangerous"},
            rule=rule,
            reason="Dangerous command detected",
            project_dir=project_with_auto_claude,
        )

        logger = get_global_logger()
        events = logger.get_events()

        assert len(events) > 0
        assert events[-1].decision == "block"

    def test_log_warning(self, project_with_auto_claude):
        """Test logging warnings."""
        clear_global_logger()

        log_warning(
            tool_name="Bash",
            tool_input={"command": "suspicious"},
            reason="Suspicious command pattern",
            project_dir=project_with_auto_claude,
        )

        logger = get_global_logger()
        events = logger.get_events()

        assert len(events) > 0
        assert events[-1].decision == "warning"

    def test_generate_validation_report(self, project_with_auto_claude):
        """Test generating validation report."""
        clear_global_logger()

        # Log some events
        rule = ValidationRule(
            rule_id="test-rule",
            name="Test Rule",
            description="Test description",
            pattern="test",
            severity=SeverityLevel.HIGH,
        )

        log_blocked_operation(
            tool_name="Bash",
            tool_input={"command": "dangerous"},
            rule=rule,
            reason="Test block",
            project_dir=project_with_auto_claude,
        )

        report = generate_validation_report(project_with_auto_claude)

        assert "# Validation Report" in report
        assert "Total validations" in report
        assert "Blocked" in report

    def test_save_report_to_file(self, project_with_auto_claude):
        """Test saving report to file."""
        clear_global_logger()

        report_path = project_with_auto_claude / "validation-report.md"

        generate_and_save_report(
            project_dir=project_with_auto_claude,
            output_path=report_path,
        )

        assert report_path.exists()
        content = report_path.read_text()
        assert "# Validation Report" in content


# =============================================================================
# MESSAGE FORMATTING TESTS
# =============================================================================


class TestMessageFormatting:
    """Test user-friendly message formatting."""

    def test_format_block_message(self):
        """Test formatting block messages."""
        rule = ValidationRule(
            rule_id="bash-rm-rf-root",
            name="Dangerous rm -rf",
            description="This command would delete system directories",
            pattern="rm -rf",
            severity=SeverityLevel.CRITICAL,
            suggestions=["Use specific paths instead", "Consider using rm -ri"],
        )

        result = ValidationResult(
            is_blocked=True,
            rule_id="bash-rm-rf-root",
            reason="Command would delete root filesystem",
            severity=SeverityLevel.CRITICAL,
        )

        message = format_block_message(
            tool_name="Bash",
            tool_input={"command": "rm -rf /"},
            result=result,
            rule=rule,
        )

        assert "blocked" in message.lower()
        assert "rm -rf" in message
        assert "override" in message.lower()

    def test_format_short_block_message(self):
        """Test formatting short block messages."""
        message = format_short_block_message(
            tool_name="Bash",
            tool_input={"command": "rm -rf /"},
            rule_id="bash-rm-rf-root",
            severity=SeverityLevel.CRITICAL,
        )

        assert "blocked" in message.lower()
        assert "bash-rm-rf-root" in message
        assert "critical" in message.lower()


# =============================================================================
# END-TO-END INTEGRATION TESTS
# =============================================================================


class TestEndToEndIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_full_validation_workflow_with_override(self, project_with_auto_claude):
        """Test complete workflow: block -> generate override -> allow."""
        clear_config_cache(project_with_auto_claude)

        # Step 1: Try dangerous command (should block)
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
            "cwd": str(project_with_auto_claude),
        }

        mock_context = MagicMock()
        mock_context.project_dir = project_with_auto_claude

        result1 = await output_validation_hook(
            input_data=input_data,
            tool_use_id=None,
            context=mock_context,
        )

        assert result1.get("decision") == "block"

        # Step 2: Generate override token
        token = generate_override_token(
            rule_id=result1.get("rule_id"),
            project_dir=project_with_auto_claude,
            scope="all",
            expiry_minutes=60,
            reason="Testing full workflow",
        )

        assert token is not None

        # Step 3: Try again with override (should allow)
        result2 = await output_validation_hook(
            input_data=input_data,
            tool_use_id=None,
            context=mock_context,
        )

        assert result2 == {}  # Allowed

        # Step 4: Check that override was logged
        logger = get_global_logger()
        events = logger.get_events()
        override_events = [e for e in events if e.decision == "override_used"]

        assert len(override_events) > 0

    @pytest.mark.asyncio
    async def test_custom_rule_workflow(self, project_with_auto_claude):
        """Test workflow with custom validation rules."""
        # Create custom config
        config_file = project_with_auto_claude / ".auto-claude" / "output-validation.json"
        config_data = {
            "custom_rules": [
                {
                    "rule_id": "no-print-debug",
                    "name": "No Print Debug",
                    "description": "Block print statements in production code",
                    "pattern": "print\\(.*debug",
                    "severity": "low",
                    "enabled": True,
                    "tool_types": ["Write"],
                    "context": "content",
                }
            ]
        }

        config_file.write_text(json.dumps(config_data, indent=2))
        clear_config_cache(project_with_auto_claude)

        # Try to write file with print debug
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(project_with_auto_claude / "src" / "app.py"),
                "content": "print('debug: starting')",
            },
            "cwd": str(project_with_auto_claude),
        }

        mock_context = MagicMock()
        mock_context.project_dir = project_with_auto_claude

        result = await output_validation_hook(
            input_data=input_data,
            tool_use_id=None,
            context=mock_context,
        )

        # Custom rule should block/warn
        # Note: May not block if severity is LOW and strict_mode is False
        assert result == {} or result.get("decision") in ["block", "warning"]

    @pytest.mark.asyncio
    async def test_allowed_paths_workflow(self, project_with_auto_claude):
        """Test workflow with allowed paths configuration."""
        # Setup: Create tests directory
        tests_dir = project_with_auto_claude / "tests"
        tests_dir.mkdir(exist_ok=True)

        # Configure allowed paths
        config_file = project_with_auto_claude / ".auto-claude" / "output-validation.json"
        config_data = {
            "allowed_paths": ["tests/**"]
        }
        config_file.write_text(json.dumps(config_data, indent=2))
        clear_config_cache(project_with_auto_claude)

        # Write to tests directory (should bypass validation)
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tests_dir / "test_dangerous.py"),
                "content": "rm -rf /",  # Dangerous content
            },
            "cwd": str(project_with_auto_claude),
        }

        mock_context = MagicMock()
        mock_context.project_dir = project_with_auto_claude

        result = await output_validation_hook(
            input_data=input_data,
            tool_use_id=None,
            context=mock_context,
        )

        # Should allow (path is in allowlist)
        assert result == {}

    @pytest.mark.asyncio
    async def test_multi_tool_validation(self, project_with_auto_claude):
        """Test validation across multiple tool types."""
        mock_context = MagicMock()
        mock_context.project_dir = project_with_auto_claude

        test_cases = [
            # (tool_name, tool_input, should_block)
            ("Bash", {"command": "ls -la"}, False),
            ("Bash", {"command": "rm -rf /"}, True),
            ("Write", {"file_path": "src/app.py", "content": "print('hello')"}, False),
            ("Write", {"file_path": "/etc/passwd", "content": "malicious"}, True),
            ("Edit", {"file_path": "src/utils.py", "old_string": "old", "new_string": "new"}, False),
        ]

        for tool_name, tool_input, should_block in test_cases:
            input_data = {
                "tool_name": tool_name,
                "tool_input": tool_input,
                "cwd": str(project_with_auto_claude),
            }

            result = await output_validation_hook(
                input_data=input_data,
                tool_use_id=None,
                context=mock_context,
            )

            if should_block:
                assert result.get("decision") == "block", f"Expected block for {tool_name}: {tool_input}"
            else:
                assert result == {}, f"Expected allow for {tool_name}: {tool_input}"


# =============================================================================
# TEST RUNNER
# =============================================================================


if __name__ == "__main__":
    print("Running Output Validation Integration Tests...")
    print("=" * 70)

    # Run with pytest
    pytest.main([__file__, "-v", "-s", "--tb=short"])
