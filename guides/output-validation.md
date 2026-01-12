# Output Validation System Guide

## Overview

Auto Claude's Output Validation System provides a fourth layer of defense that inspects all agent-generated tool calls before execution. This catches potentially harmful operations that might slip through other security layers.

### Why Output Validation?

AI agents can generate commands or file operations that are technically valid but dangerous:
- An agent might suggest `rm -rf /data` to clean up files
- File writes might accidentally expose API keys
- Web requests might target internal network resources

The output validation system uses pattern matching to detect these dangerous operations **before** they execute.

### Key Features

- **Pre-Execution Inspection**: All tool outputs validated before execution
- **Pattern Detection**: Regex and literal matching for dangerous operations
- **Per-Project Configuration**: Customize rules via `.auto-claude/output-validation.json`
- **Override Mechanism**: Time-limited and scope-limited bypass tokens
- **Clear Messages**: User-friendly explanations with actionable suggestions
- **Comprehensive Logging**: Full audit trail of all blocked operations

## How It Works

### Architecture Flow

```
Agent Tool Call
    ↓
Output Validation Hook (pre-tool-use)
    ↓
Override Token Check
    ↓ (if no valid override)
Allowed Paths Check
    ↓ (if path not in allowlist)
Pattern Detection (regex/literal)
    ↓ (if pattern matches)
Block with User-Friendly Message
```

### Protected Tools

The output validation system protects these Claude Agent SDK tools:

| Tool | What's Validated | Example Dangers |
|------|------------------|-----------------|
| **Bash** | Commands executed in shell | `rm -rf /`, `dd if=/dev/zero of=/dev/sda` |
| **Write** | New file creation | Writing API keys to files, creating reverse shells |
| **Edit** | File modifications | Injecting malicious code into config files |
| **WebFetch** | HTTP/HTTPS requests | SSRF attacks, accessing internal IPs |
| **WebSearch** | Search queries | Information disclosure |

### Four-Layer Security

Auto Claude's security model now includes **four layers**:

1. **OS Sandbox** - Bash command isolation
2. **Filesystem Permissions** - Operations restricted to project directory
3. **Command Allowlist** - Dynamic allowlist from project analysis
4. **Output Validation** - Pattern-based detection (NEW)

## Configuration

### Configuration File Location

Create a configuration file in your project's `.auto-claude` directory:

```
project/
├── .auto-claude/
│   ├── output-validation.json    # JSON format
│   └── output-validation.yaml    # YAML format (alternative)
└── ...
```

### Configuration Schema

```json
{
  // Enable/disable output validation
  "enabled": true,

  // Enable strict mode (warnings become blocks)
  "strict_mode": false,

  // Paths that bypass validation (glob patterns)
  "allowed_paths": [
    "tests/**",
    "test_*.py",
    "build/**",
    "dist/**",
    ".git/**"
  ],

  // Rule IDs to disable (override default rules)
  "disabled_rules": [
    "bash-deprecated-command"
  ],

  // Severity overrides (make rules stricter/lenient)
  "severity_overrides": {
    "bash-curl-data-exfil": "HIGH",
    "write-password-pattern": "CRITICAL"
  },

  // Custom validation rules
  "custom_rules": [
    {
      "rule_id": "my-custom-rule",
      "name": "My Custom Rule",
      "description": "Detects something specific to my project",
      "pattern": "dangerous-pattern",
      "pattern_type": "literal",
      "severity": "HIGH",
      "priority": "P1",
      "tool_types": ["bash"],
      "context": "command",
      "message": "This matches my custom dangerous pattern",
      "suggestions": [
        "Use alternative approach",
        "Consult documentation"
      ],
      "category": "custom",
      "enabled": true
    }
  ]
}
```

### Configuration Options

#### `enabled` (boolean, default: true)
Enable or disable output validation entirely. Only use this if you understand the risks.

#### `strict_mode` (boolean, default: false)
When enabled, MEDIUM and LOW severity rules result in blocks instead of warnings.

#### `allowed_paths` (array of strings)
Glob patterns for paths that bypass validation. Useful for test files, build outputs, etc.

**Supported patterns:**
- `**` - Match any directories
- `*` - Match any files
- `?` - Match single character
- `[abc]` - Match specific characters
- `[!abc]` - Negation

**Examples:**
```json
{
  "allowed_paths": [
    "tests/**",              // All files under tests/
    "test_*.py",             // Python test files in root
    "build/**",              // Build outputs
    "*.tmp",                 // Temp files anywhere
    "generated/code/**"      // Specific nested directory
  ]
}
```

#### `disabled_rules` (array of strings)
Rule IDs to disable. Use sparingly and document why.

```json
{
  "disabled_rules": [
    "bash-deprecated-command",  // Allow deprecated commands
    "write-crypto-miner"        // Mining code is OK for this project
  ]
}
```

#### `severity_overrides` (object)
Change severity levels for specific rules. Valid levels: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.

```json
{
  "severity_overrides": {
    "bash-curl-data-exfil": "CRITICAL",      // Upgrade to critical
    "bash-deprecated-command": "LOW"         // Downgrade to low
  }
}
```

#### `custom_rules` (array of objects)
Define project-specific validation rules.

**Rule properties:**

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `rule_id` | string | Yes | Unique identifier (alphanumeric, hyphens, underscores only) |
| `name` | string | Yes | Short, human-readable name |
| `description` | string | Yes | Detailed description of what the rule detects |
| `pattern` | string | Yes | Regex pattern or literal string to match |
| `pattern_type` | string | No | `regex` (default) or `literal` |
| `severity` | string | No | `LOW`, `MEDIUM` (default), `HIGH`, `CRITICAL` |
| `priority` | string | No | `P0`, `P1`, `P2`, `P3` (default: `P2`) |
| `tool_types` | array | Yes | Tools this applies to: `bash`, `write`, `edit`, `web_fetch`, `web_search` |
| `context` | string | No | Where to match: `command`, `file_content`, `file_path`, `all` (default) |
| `message` | string | Yes | Explanation shown when rule matches |
| `suggestions` | array | No | Actionable suggestions (1-3 items) |
| `category` | string | Yes | Category for grouping: `filesystem`, `database`, etc. |
| `enabled` | boolean | No | Whether rule is active (default: true) |

### Example Configuration Files

#### Minimal Configuration (JSON)

```json
{
  "enabled": true,
  "allowed_paths": [
    "tests/**",
    "build/**"
  ]
}
```

#### Minimal Configuration (YAML)

```yaml
enabled: true
allowed_paths:
  - tests/**
  - build/**
```

#### Full Configuration (JSON)

```json
{
  "enabled": true,
  "strict_mode": false,
  "allowed_paths": [
    "tests/**",
    "test_*.py",
    "build/**",
    "dist/**",
    ".git/**",
    "node_modules/**"
  ],
  "disabled_rules": [
    "bash-deprecated-command"
  ],
  "severity_overrides": {
    "bash-curl-data-exfil": "CRITICAL"
  },
  "custom_rules": [
    {
      "rule_id": "protect-production-db",
      "name": "Protect Production Database",
      "description": "Block any commands targeting production database",
      "pattern": "prod-db\\.example\\.com",
      "pattern_type": "regex",
      "severity": "CRITICAL",
      "priority": "P0",
      "tool_types": ["bash"],
      "context": "command",
      "message": "Commands targeting production database are blocked",
      "suggestions": [
        "Use staging database for testing",
        "Contact DBA for production access"
      ],
      "category": "database",
      "enabled": true
    }
  ]
}
```

## Default Validation Rules

The output validation system includes comprehensive default rules organized by category and severity.

### Rule Categories

- **filesystem** - File system operations (rm, dd, mkfs, chmod, etc.)
- **database** - SQL operations (DROP, TRUNCATE, etc.)
- **process** - Process management (kill, killall, etc.)
- **network** - Network operations (iptables, curl, etc.)
- **privilege_escalation** - sudo and related commands
- **data_exfiltration** - Data sent to external servers
- **code_injection** - Dynamic code execution patterns
- **obfuscation** - Encoded or hidden commands
- **audit_evasion** - History clearing, etc.
- **system_modification** - Package installations, etc.
- **secret_exposure** - API keys, passwords, private keys
- **backdoor** - Reverse shells, etc.
- **resource_abuse** - Crypto mining, etc.
- **system_files** - System file modifications
- **access_control** - SSH, sudoers, etc.
- **deprecation** - Deprecated commands
- **file_access** - Local file access
- **network_security** - SSRF, internal IPs, etc.

### Severity Levels

| Severity | Description | Default Action |
|----------|-------------|----------------|
| **CRITICAL** | Severe damage or security breach | Always blocked |
| **HIGH** | Significant risk or damage | Always blocked |
| **MEDIUM** | Suspicious or potentially dangerous | Warning (block in strict mode) |
| **LOW** | Informational or deprecated practices | Warning (block in strict mode) |

### Priority Levels

| Priority | Description | Example |
|----------|-------------|---------|
| **P0** | Most critical checks | `rm -rf /`, DROP DATABASE |
| **P1** | High-risk operations | chmod 777, kill systemd |
| **P2** | Suspicious patterns | curl data exfil, base64 decode |
| **P3** | Informational | deprecated commands |

### Complete Rule Reference

#### Bash Command Rules

| Rule ID | Name | Severity | Pattern |
|---------|------|----------|---------|
| `bash-rm-rf-root` | Recursive Delete from Root | CRITICAL | `rm -rf /`, `rm -rf /etc`, etc. |
| `bash-dd-overwrite` | Block Device Overwrite | CRITICAL | `dd of=/dev/sda`, `dd if=/dev/zero` |
| `bash-mkfs-filesystem` | Create Filesystem on Device | CRITICAL | `mkfs.ext4 /dev/sda` |
| `bash-drop-database` | Drop Database | CRITICAL | `DROP DATABASE`, `DROP SCHEMA` |
| `bash-truncate-table` | Truncate All Tables | HIGH | `TRUNCATE TABLE` |
| `bash-chmod-777` | Make Files World-Writable | HIGH | `chmod 777`, `chmod -R 777` |
| `bash-chown-system` | Change System File Ownership | HIGH | `chown /etc`, `chown /usr` |
| `bash-kill-process` | Kill Critical Process | HIGH | `kill -9 systemd`, `killall cron` |
| `bash-iptables-flush` | Flush Firewall Rules | HIGH | `iptables -F` |
| `bash-sudo-root` | Privilege Escalation to Root | HIGH | `sudo su -`, `sudo /bin/bash` |
| `bash-curl-data-exfil` | Potential Data Exfiltration | MEDIUM | `curl -X POST` with data |
| `bash-wget-remote-script` | Download and Execute Remote Script | MEDIUM | `curl ... \| bash`, `wget ... \| sh` |
| `bash-history-clear` | Clear Command History | MEDIUM | `history -c`, `rm .bash_history` |
| `bash-package-install-system` | System Package Installation | MEDIUM | `apt install`, `yum install` |
| `bash-base64-decode-exec` | Base64-Encoded Command Execution | HIGH | `base64 -d \| bash` |
| `bash-variable-expansion-exec` | Variable Expansion Command Execution | HIGH | `${var} \| bash`, `eval $var` |
| `bash-command-chain-dangerous` | Dangerous Command Chain | HIGH | `rm -rf && chmod 777` |
| `bash-xor-decode-exec` | XOR-Encoded Command Execution | HIGH | `perl -e 'xor...' \| bash` |
| `bash-eval-in-command-chain` | Eval in Command Chain | HIGH | `eval ${...} &&` |
| `bash-deprecated-command` | Deprecated Command Usage | LOW | `ftp`, `telnet`, `rsh` |

#### File Write Rules (Content-Based)

| Rule ID | Name | Severity | Pattern |
|---------|------|----------|---------|
| `write-api-key-pattern` | API Key in File | CRITICAL | `api_key=`, `access_token=` with long value |
| `write-aws-key-pattern` | AWS Access Key in File | CRITICAL | `aws_access_key_id=AKIA...` |
| `write-private-key-pattern` | Private Key in File | CRITICAL | `-----BEGIN PRIVATE KEY-----` |
| `write-password-pattern` | Password in File | HIGH | `password=`, `pwd=` with value |
| `write-eval-exec-pattern` | Dynamic Code Execution | HIGH | `eval(`, `exec(`, `__import__` |
| `write-base64-decode-exec` | Base64-Encoded Code Execution | HIGH | `base64 -d \| python` |
| `write-reverse-shell` | Reverse Shell Pattern | CRITICAL | `bash -i >& /dev/tcp/` |
| `write-crypto-miner` | Cryptocurrency Miner Pattern | MEDIUM | `cryptominer`, `xmrig`, `stratum+tcp://` |
| `write-coinhive` | CoinHive or Similar In-Browser Miner | MEDIUM | `coinhive`, `jsecoin`, `cryptoloot` |

#### File Path Rules

| Rule ID | Name | Severity | Pattern |
|---------|------|----------|---------|
| `path-system-directory-write` | Write to System Directory | CRITICAL | `/etc/`, `/usr/`, `/bin/`, `/lib/` |
| `path-etc-passwd` | Write to /etc/passwd | CRITICAL | `/etc/passwd` |
| `path-etc-shadow` | Write to /etc/shadow | CRITICAL | `/etc/shadow` |
| `path-ssh-authorized-keys` | Write to SSH Authorized Keys | HIGH | `/.ssh/authorized_keys` |
| `path-sudoers` | Write to Sudoers File | CRITICAL | `/etc/sudoers`, `/etc/sudoers.d/` |
| `path-crontab` | Write to System Crontab | HIGH | `/etc/crontab`, `/etc/cron.d/` |
| `path-ssh-config` | Write to SSH Config | MEDIUM | `/.ssh/config`, `/.ssh/known_hosts` |
| `path-environment-file` | Write to .env File | MEDIUM | `/.env`, `/.env.` |
| `path-hosts-file` | Write to /etc/hosts | HIGH | `/etc/hosts` |
| `path-other-user-home` | Write to Another User's Home | MEDIUM | `/home/otheruser/` |
| `path-systemd-unit` | Write to Systemd Unit File | HIGH | `/etc/systemd/system/*.service` |

#### Web Fetch/Search Rules

| Rule ID | Name | Severity | Pattern |
|---------|------|----------|---------|
| `web-fetch-internal-ip` | Access Internal Network Resource | MEDIUM | `http://127.`, `http://10.`, `http://192.168.` |
| `web-fetch-local-file` | Local File Inclusion Attempt | HIGH | `file://` |

## Override Mechanism

The override mechanism allows you to bypass specific validation rules for legitimate operations. Override tokens are time-limited, scope-limited, and tracked for audit.

### When to Use Overrides

Use overrides for:
- Testing cleanup scripts that use `rm -rf`
- Development database operations
- Legitimate system modifications
- Emergency repairs

**Never use overrides for:**
- Unknown operations
- Operations you don't fully understand
- Production changes without proper authorization

### Override Token Properties

Each override token has:
- **Token ID**: UUID for tracking
- **Rule ID**: Which rule it overrides
- **Scope**: What operations it applies to
- **Expiry**: When it expires (default: 60 minutes)
- **Max Uses**: How many times it can be used (default: 1)
- **Reason**: Documentation for audit trail

### Override Scopes

| Scope | Description | Example Use |
|-------|-------------|--------------|
| `all` | All operations for this rule | Emergency repairs |
| `file:/path/to/file` | Only for specific file | Testing cleanup script |
| `command:pattern` | Only for matching commands | Specific database operation |

### CLI Commands

#### Create Override Token

```bash
# Basic usage
python auto-claude/run.py --override create bash-rm-rf-root

# With scope and reason
python auto-claude/run.py --override create bash-rm-rf-root \
  --override-scope "file:/tmp/test-data" \
  --override-reason "Testing cleanup script"

# Custom expiry (24 hours) and unlimited uses
python auto-claude/run.py --override create bash-drop-database \
  --override-expiry 1440 \
  --override-max-uses 0 \
  --override-reason "Database migration testing"
```

**Options:**
- `--override-rule <rule-id>`: Rule ID to override (required)
- `--override-scope <scope>`: Scope (all, file:path, command:pattern)
- `--override-expiry <minutes>`: Expiry time (default: 60, 0 = no expiry)
- `--override-max-uses <count>`: Max uses (default: 1, 0 = unlimited)
- `--override-reason <text>`: Reason for audit trail

#### List Override Tokens

```bash
# List all active tokens
python auto-claude/run.py --override list

# Filter by rule ID
python auto-claude/run.py --override list --override-rule bash-rm-rf-root

# Include expired tokens
python auto-claude/run.py --override list --include-expired
```

#### Revoke Override Token

```bash
# Revoke by token ID
python auto-claude/run.py --override revoke --override-token 123e4567-e89b-12d3-a456-426614174000
```

#### Show Help

```bash
python auto-claude/run.py --override help
```

### Override Token Storage

Override tokens are stored in `.auto-claude/override-tokens.json`:

```json
{
  "tokens": [
    {
      "token_id": "123e4567-e89b-12d3-a456-426614174000",
      "rule_id": "bash-rm-rf-root",
      "scope": "file:/tmp/test-data",
      "created_at": "2026-01-11T12:00:00Z",
      "expires_at": "2026-01-11T13:00:00Z",
      "max_uses": 1,
      "use_count": 0,
      "creator": "cli",
      "reason": "Testing cleanup script"
    }
  ]
}
```

### Programmatic Usage

```python
from security.output_validation.overrides import generate_override_token
from pathlib import Path

# Generate token
token = generate_override_token(
    rule_id="bash-rm-rf-root",
    project_dir=Path("/my/project"),
    scope="file:/tmp/test-data",
    expiry_minutes=30,
    reason="Testing cleanup script",
)

print(f"Token ID: {token.token_id}")
print(f"Expires at: {token.expires_at}")
```

## Validation Reports

After each build session, a validation report is generated showing all blocked operations, warnings, and override usage.

### Report Location

```
.auto-claude/specs/XXX/validation-report.md
```

### Report Contents

The report includes:

- **Summary Statistics**: Total validations, blocked, warnings, overrides used
- **Blocked Operations**: Grouped by rule with explanations
- **Warnings**: Suspicious but allowed operations
- **Override Token Usage**: When and how overrides were used
- **Statistics by Tool**: Breakdown by tool type
- **Severity Breakdown**: Blocks by severity level

### Example Report

```markdown
# Validation Report

**Generated:** 2026-01-11 12:34:56
**Project:** /my/project
**Spec:** 005-output-validation

## Summary

| Metric | Count |
|--------|-------|
| Total Validations | 47 |
| Blocked | 3 |
| Warnings | 5 |
| Allowed | 39 |
| Overrides Used | 1 |

## Blocked Operations

### bash-rm-rf-root (CRITICAL)
*Count: 2*

This command would recursively delete critical system directories.

**Examples:**
1. `rm -rf /tmp/test-data`
2. `rm -rf ./build`

### write-api-key-pattern (CRITICAL)
*Count: 1*

This file appears to contain an API key or access token.

**Examples:**
1. File: config.py

## Warnings

### bash-curl-data-exfil (MEDIUM)
*Count: 3*

This command may be sending data to an external server.

**Examples:**
1. `curl -X POST https://api.example.com/webhook`
2. `curl -d @data.json https://api.example.com/ingest`
3. `curl --data-urlencode "name=value" https://api.example.com`

### bash-deprecated-command (LOW)
*Count: 2*

This command is deprecated and may be insecure.

**Examples:**
1. `ftp ftp.example.com`
2. `telnet localhost 8080`

## Override Tokens Used

| Token ID | Rule ID | Tool | Context | Reason |
|----------|---------|------|---------|--------|
| 123e4567... | bash-rm-rf-root | bash | file:/tmp/test-data | Testing cleanup script |

## Statistics by Tool

| Tool | Validations | Blocked | Warnings |
|------|-------------|---------|----------|
| bash | 25 | 2 | 4 |
| write | 15 | 1 | 1 |
| edit | 5 | 0 | 0 |
| web_fetch | 2 | 0 | 0 |

## Severity Breakdown

| Severity | Count |
|----------|-------|
| CRITICAL | 3 |
| HIGH | 0 |
| MEDIUM | 3 |
| LOW | 2 |
```

## Best Practices

### 1. Use Allowed Paths for Test Files

```json
{
  "allowed_paths": [
    "tests/**",
    "test_*.py",
    "build/**",
    "dist/**"
  ]
}
```

This prevents validation warnings for legitimate test operations.

### 2. Create Custom Rules for Project-Specific Risks

```json
{
  "custom_rules": [
    {
      "rule_id": "protect-prod-api",
      "name": "Protect Production API",
      "description": "Block operations targeting production API",
      "pattern": "api\\.production\\.example\\.com",
      "severity": "CRITICAL",
      "priority": "P0",
      "tool_types": ["bash", "web_fetch"],
      "context": "all",
      "message": "Operations targeting production API are blocked",
      "suggestions": [
        "Use staging API for testing",
        "Contact operations for production access"
      ],
      "category": "network"
    }
  ]
}
```

### 3. Use Specific Override Scopes

Instead of broad `all` overrides, use specific scopes:

```bash
# Too broad - allows any rm -rf
python auto-claude/run.py --override create bash-rm-rf-root --override-scope all

# Better - only allows for specific file
python auto-claude/run.py --override create bash-rm-rf-root \
  --override-scope "file:/tmp/test-cleanup" \
  --override-reason "Running test cleanup script"
```

### 4. Set Expiry Times Appropriately

```bash
# Short expiry for quick tests (30 minutes)
python auto-claude/run.py --override create bash-rm-rf-root \
  --override-expiry 30

# Longer expiry for multi-hour work (4 hours)
python auto-claude/run.py --override create bash-drop-database \
  --override-expiry 240
```

### 5. Always Provide Reasons

Document why overrides are needed:

```bash
python auto-claude/run.py --override create bash-rm-rf-root \
  --override-reason "Running documented cleanup script from README.md"
```

### 6. Review Validation Reports

After each build session, review the validation report for unexpected blocks or warnings.

### 7. Use Strict Mode in CI/CD

```json
{
  "strict_mode": true
}
```

In strict mode, MEDIUM and LOW severity rules result in blocks instead of warnings. This is useful for CI/CD pipelines.

### 8. Regularly Audit Override Tokens

```bash
# List all tokens
python auto-claude/run.py --override list

# Revoke unused tokens
python auto-claude/run.py --override revoke --override-token <token-id>
```

### 9. Customize Severity for Your Project

```json
{
  "severity_overrides": {
    "bash-curl-data-exfil": "CRITICAL",
    "bash-package-install-system": "HIGH"
  }
}
```

### 10. Document Custom Rules

Include clear descriptions and suggestions:

```json
{
  "custom_rules": [
    {
      "rule_id": "no-prod-writes",
      "name": "No Production Writes",
      "description": "Block any writes to production database or API",
      "pattern": "prod-db\\.example\\.com",
      "message": "Direct writes to production are blocked",
      "suggestions": [
        "Use staging environment for testing",
        "Go through migration process for production changes",
        "Contact DBA team for production access"
      ]
    }
  ]
}
```

## Troubleshooting

### Issue: Legitimate Command is Blocked

**Solution 1: Use allowed_paths**
If the operation is on test files, add them to allowed paths:

```json
{
  "allowed_paths": ["tests/**", "test_*.py"]
}
```

**Solution 2: Create override token**
For one-time operations:

```bash
python auto-claude/run.py --override create <rule-id> \
  --override-scope "file:/path/to/file" \
  --override-reason "Reason for override"
```

**Solution 3: Disable the rule**
If the rule doesn't apply to your project:

```json
{
  "disabled_rules": ["bash-deprecated-command"]
}
```

### Issue: Too Many Warnings

**Solution 1: Use strict_mode=false**
Keep warnings as warnings (not blocks):

```json
{
  "strict_mode": false
}
```

**Solution 2: Lower severity**
Reduce rule severity:

```json
{
  "severity_overrides": {
    "bash-curl-data-exfil": "LOW"
  }
}
```

**Solution 3: Add to allowed_paths**
If warnings are for test files:

```json
{
  "allowed_paths": ["tests/**"]
}
```

### Issue: Custom Rule Not Working

**Check pattern syntax:**
- Regex patterns must be valid
- Use `(?i)` for case-insensitive matching
- Test patterns with regex tester

**Check tool_types:**
```json
{
  "tool_types": ["bash"]  // Must match tool being used
}
```

**Check context:**
```json
{
  "context": "command"  // or "file_content", "file_path", "all"
}
```

**Check rule_id format:**
```json
{
  "rule_id": "my-custom-rule"  // Alphanumeric, hyphens, underscores only
}
```

### Issue: Override Token Not Working

**Check scope format:**
- `all` - All operations for this rule
- `file:/path/to/file` - Specific file
- `command:pattern` - Matching commands

**Check expiry:**
```bash
# List tokens to see expiry
python auto-claude/run.py --override list
```

**Check rule_id:**
```bash
# List tokens for specific rule
python auto-claude/run.py --override list --override-rule bash-rm-rf-root
```

**Check token usage:**
Tokens with `max_uses: 1` are consumed after first use. Create a new token or use `max_uses: 0` for unlimited uses.

### Issue: Configuration Not Loading

**Check file location:**
Configuration must be at `.auto-claude/output-validation.json` or `.yaml`

**Check JSON syntax:**
```bash
# Validate JSON
python -m json.tool .auto-claude/output-validation.json
```

**Check YAML syntax (if using YAML):**
```bash
# Install PyYAML
pip install pyyaml

# Validate YAML
python -c "import yaml; yaml.safe_load(open('.auto-claude/output-validation.yaml'))"
```

**Clear cache:**
```python
from security.output_validation.config import clear_config_cache
clear_config_cache()
```

## Advanced Topics

### Programmatic Configuration

```python
from security.output_validation.config import load_validation_config
from security.output_validation.custom_rules import merge_with_defaults
from pathlib import Path

# Load configuration
config = load_validation_config(Path("/my/project"))

# Merge custom rules with defaults
all_rules = merge_with_defaults(config, get_default_rules())

# Filter rules by tool type
from security.output_validation.custom_rules import get_active_rules
bash_rules = get_active_rules(all_rules, tool_type="bash")
```

### Custom Validators

Create custom validators for special cases:

```python
from security.output_validation.validators import register_validator

async def my_custom_validator(tool_input, detector, config):
    """Custom validation logic."""
    # Your validation logic here
    if dangerous_condition:
        return ValidationResult.blocked(
            rule_id="my-custom-rule",
            reason="Custom dangerous condition detected",
        )
    return ValidationResult.allowed()

# Register validator
register_validator("my_tool", my_custom_validator)
```

### Validation Events API

```python
from security.output_validation.logger import ValidationEventLogger

# Get logger instance
logger = ValidationEventLogger()

# Get blocked events
blocked = logger.get_blocked_events()

# Get warnings
warnings = logger.get_warnings()

# Get events by tool
bash_events = logger.get_events_by_tool("bash")

# Get statistics
stats = logger.get_statistics()
```

## Security Considerations

### Override Token Security

- **Never share override tokens** - They are credentials
- **Use minimal scope** - Prefer `file:/path` over `all`
- **Set short expiry** - Default 60 minutes is reasonable
- **Document reasons** - Audit trail is important
- **Revoke when done** - Clean up unused tokens

### Configuration File Security

- **Add .auto-claude/ to .gitignore** - May contain sensitive configs
- **Never commit override tokens** - They are in `override-tokens.json`
- **Review custom rules** - Ensure they don't create security gaps
- **Use environment-specific configs** - Different rules for dev/staging/prod

### Rule Design Best Practices

- **Specific patterns** - Avoid overly broad matches
- **Clear messages** - Explain why the operation is dangerous
- **Actionable suggestions** - Tell users what to do instead
- **Appropriate severity** - Don't overuse CRITICAL level
- **Test patterns** - Verify patterns match what you expect

## References

- **Main Documentation**: [CLAUDE.md](../CLAUDE.md)
- **Security Module**: `apps/backend/security/output_validation/`
- **Default Rules**: `apps/backend/security/output_validation/rules.py`
- **Configuration Schema**: `apps/backend/security/output_validation/models.py`
- **Override Management**: `apps/backend/cli/override_commands.py`

## Support

For issues or questions:
1. Check validation report for blocked operations
2. Review this guide for configuration options
3. Use `--override help` for CLI command reference
4. Check existing issues on GitHub

## Changelog

### Version 1.0 (2026-01-11)
- Initial release of output validation system
- 40+ default rules across 4 tool types
- Per-project configuration (JSON/YAML)
- Override token mechanism
- Comprehensive validation reports
- CLI commands for override management
