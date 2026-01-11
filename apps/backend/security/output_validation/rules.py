"""
Default Validation Rules
========================

Comprehensive default rules for detecting dangerous operations across all tool types.

This module provides:
- BASH_RULES: Dangerous command patterns (rm -rf, drop database, etc.)
- FILE_WRITE_RULES: Dangerous file content patterns (secrets, malware indicators)
- FILE_PATH_RULES: Dangerous path patterns (system files, config overwrites)
- get_default_rules(): Function to load all default rules

Rules are organized by category with clear documentation for easy customization.
"""

from .models import (
    RulePriority,
    SeverityLevel,
    ToolType,
    ValidationRule,
)

# ============================================================================
# BASH COMMAND RULES
# ============================================================================

BASH_RULES: list[ValidationRule] = [
    # --------------------------------------------------------------------
    # P0: Critical - Destructive operations
    # --------------------------------------------------------------------
    ValidationRule(
        rule_id="bash-rm-rf-root",
        name="Recursive Delete from Root",
        description="Detects attempts to recursively delete from root directory or critical system paths",
        pattern=r"(?i)\brm\s+-rf?\s+[/'\"]?(/|\.?\.[/'\"]?|/etc|/usr|/bin|/sbin|/var|/boot|/home/[^/]+/\.ssh)",
        pattern_type="regex",
        severity=SeverityLevel.CRITICAL,
        priority=RulePriority.P0,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command would recursively delete critical system directories, which would destroy your operating system.",
        suggestions=[
            "Review the command and ensure you're targeting the correct directory",
            "Use absolute paths to avoid ambiguity",
            "Consider using --preserve-root flag with rm",
        ],
        category="filesystem",
    ),
    ValidationRule(
        rule_id="bash-dd-overwrite",
        name="Block Device Overwrite",
        description="Detects dd commands that would overwrite disk blocks or devices",
        pattern=r"(?i)\bdd\s+(.*\s)?(of=/dev/(sd[a-z]|nvme|mmcblk)|if=/dev/zero|if=/dev/random)",
        pattern_type="regex",
        severity=SeverityLevel.CRITICAL,
        priority=RulePriority.P0,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command would overwrite a block device or disk, potentially destroying all data.",
        suggestions=[
            "Verify the target device (of=) is correct",
            "Ensure you're not writing to a system disk",
            "Consider using a safer alternative for your use case",
        ],
        category="filesystem",
    ),
    ValidationRule(
        rule_id="bash-mkfs-filesystem",
        name="Create Filesystem on Device",
        description="Detects mkfs commands that would format a block device, destroying all data",
        pattern=r"(?i)\bmkfs\.(ext[234]|xfs|btrfs|vfat|ntfs)\s+/dev/",
        pattern_type="regex",
        severity=SeverityLevel.CRITICAL,
        priority=RulePriority.P0,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command would create a new filesystem on a block device, destroying all existing data.",
        suggestions=[
            "Verify the target device is correct",
            "Ensure you have backups of any important data",
            "Consider using a live USB/ISO for system-level disk operations",
        ],
        category="filesystem",
    ),
    ValidationRule(
        rule_id="bash-drop-database",
        name="Drop Database",
        description="Detects SQL DROP DATABASE commands",
        pattern=r"(?i)\b(drop\s+database|drop\s+schema)\s+[`'\"]?(\w+)",
        pattern_type="regex",
        severity=SeverityLevel.CRITICAL,
        priority=RulePriority.P0,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command would permanently delete an entire database and all its data.",
        suggestions=[
            "Verify you're targeting the correct database",
            "Ensure you have a recent backup",
            "Consider using DROP TABLE for specific tables instead",
        ],
        category="database",
    ),
    ValidationRule(
        rule_id="bash-truncate-table",
        name="Truncate All Tables",
        description="Detects SQL TRUNCATE commands that would empty tables",
        pattern=r"(?i)\btruncate\s+(table\s+)?([`'\"]?(\w+)[`'\"]?\s*,?\s*)+",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P0,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command would delete all data from the specified table(s).",
        suggestions=[
            "Verify you're targeting the correct table(s)",
            "Ensure you have a backup if needed",
            "Consider DELETE with WHERE clause for selective deletion",
        ],
        category="database",
    ),
    # --------------------------------------------------------------------
    # P1: High - Dangerous operations
    # --------------------------------------------------------------------
    ValidationRule(
        rule_id="bash-chmod-777",
        name="Make Files World-Writable",
        description="Detects chmod 777 commands that make files world-writable",
        pattern=r"(?i)\bchmod\s+(-R\s+)?777\s+",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P1,
        tool_types=[ToolType.BASH],
        context="command",
        message="Setting permissions to 777 makes files world-writable, which is a security risk.",
        suggestions=[
            "Use more restrictive permissions (e.g., 755 for directories, 644 for files)",
            "Consider using 750 for group-accessible files",
            "Only use 777 for temporary debugging and revert immediately",
        ],
        category="filesystem",
    ),
    ValidationRule(
        rule_id="bash-chown-system",
        name="Change System File Ownership",
        description="Detects chown commands on system directories or files",
        pattern=r"(?i)\bchown\s+(-R\s+)?\w+\s+/(etc|usr|bin|sbin|var|lib|boot)",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P1,
        tool_types=[ToolType.BASH],
        context="command",
        message="Changing ownership of system files can break your OS or create security vulnerabilities.",
        suggestions=[
            "Verify you need to change ownership of system files",
            "Consider fixing permissions instead of ownership",
            "Ensure the new owner is appropriate for system files",
        ],
        category="filesystem",
    ),
    ValidationRule(
        rule_id="bash-kill-process",
        name="Kill Critical Process",
        description="Detects attempts to kill critical system processes",
        pattern=r"(?i)\b(kill|killall|pkill)\s+(-9\s+|-SIGKILL\s+)?(1|systemd|init|ssh|cron|nginx|apache)",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P1,
        tool_types=[ToolType.BASH],
        context="command",
        message="Killing critical system processes can make your system unresponsive or unusable.",
        suggestions=[
            "Verify the process ID is correct",
            "Try SIGTERM (kill -15) before SIGKILL (kill -9)",
            "Consider using the service's restart command instead",
        ],
        category="process",
    ),
    ValidationRule(
        rule_id="bash-iptables-flush",
        name="Flush Firewall Rules",
        description="Detects iptables commands that flush all firewall rules",
        pattern=r"(?i)\biptables\s+-F",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P1,
        tool_types=[ToolType.BASH],
        context="command",
        message="Flushing firewall rules removes all network security protections.",
        suggestions=[
            "Ensure you have a backup of your firewall rules",
            "Consider adding new rules instead of flushing",
            "Have a plan to restore rules immediately after",
        ],
        category="network",
    ),
    ValidationRule(
        rule_id="bash-sudo-root",
        name="Privilege Escalation to Root",
        description="Detects suspicious sudo commands that escalate to root",
        pattern=r"(?i)\bsudo\s+(su\s+-|/bin/bash|/bin/sh|.*\s&&\s*)",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P1,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command escalates to root privileges, which should be used with caution.",
        suggestions=[
            "Use sudo only for specific commands that need it",
            "Avoid interactive shells with sudo",
            "Consider using sudo -u to run as a non-root user",
        ],
        category="privilege_escalation",
    ),
    # --------------------------------------------------------------------
    # P2: Medium - Suspicious patterns
    # --------------------------------------------------------------------
    ValidationRule(
        rule_id="bash-curl-data-exfil",
        name="Potential Data Exfiltration",
        description="Detects curl commands sending data to external URLs",
        pattern=r"(?i)\bcurl\s+(-X\s+(POST|PUT)\s+)?(-d\s+|--data-raw\s+|--data-urlencode\s+).+https?://",
        pattern_type="regex",
        severity=SeverityLevel.MEDIUM,
        priority=RulePriority.P2,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command may be sending data to an external server. Ensure this is intentional.",
        suggestions=[
            "Verify the destination URL is trusted",
            "Review the data being sent for sensitive information",
            "Consider using encryption for sensitive data",
        ],
        category="data_exfiltration",
    ),
    ValidationRule(
        rule_id="bash-wget-remote-script",
        name="Download and Execute Remote Script",
        description="Detects wget/curl followed by pipe to shell",
        pattern=r"(?i)(curl|wget)\s+.*\s*\|\s*(bash|sh|python|node)",
        pattern_type="regex",
        severity=SeverityLevel.MEDIUM,
        priority=RulePriority.P2,
        tool_types=[ToolType.BASH],
        context="command",
        message="Downloading and executing remote scripts without review is dangerous.",
        suggestions=[
            "Download the script first and review its contents",
            "Verify the source is trusted",
            "Consider using a package manager instead",
        ],
        category="code_injection",
    ),
    ValidationRule(
        rule_id="bash-history-clear",
        name="Clear Command History",
        description="Detects attempts to clear bash history",
        pattern=r"(?i)\b(history\s+-c|rm\s+.*\.bash_history|cat\s+/dev/null\s+>\s+\.bash_history)",
        pattern_type="regex",
        severity=SeverityLevel.MEDIUM,
        priority=RulePriority.P2,
        tool_types=[ToolType.BASH],
        context="command",
        message="Clearing command history may hide malicious activity.",
        suggestions=[
            "Avoid clearing history in normal operations",
            "Use audit logging for security-sensitive commands",
            "Consider why history needs to be cleared",
        ],
        category="audit_evasion",
    ),
    ValidationRule(
        rule_id="bash-package-install-system",
        name="System Package Installation",
        description="Detects global package manager installations",
        pattern=r"(?i)\b(sudo\s+)?(apt|apt-get|yum|dnf|pacman)\s+(install|update)\s+",
        pattern_type="regex",
        severity=SeverityLevel.MEDIUM,
        priority=RulePriority.P2,
        tool_types=[ToolType.BASH],
        context="command",
        message="Installing packages at the system level may affect system stability.",
        suggestions=[
            "Use virtual environments when possible",
            "Review the package list before installation",
            "Test packages in a non-production environment first",
        ],
        category="system_modification",
    ),
    # --------------------------------------------------------------------
    # P2: Medium - Obfuscation and command chains
    # --------------------------------------------------------------------
    ValidationRule(
        rule_id="bash-base64-decode-exec",
        name="Base64-Encoded Command Execution",
        description="Detects base64 decode followed by command execution",
        pattern=r"(?i)(base64\s+-d|--decode\s+|.*\s*echo\s+.*\s*\|\s*base64\s+-d).*\|\s*(bash|sh|python|php|node|perl)",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P2,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command executes base64-encoded content, which may hide malicious code.",
        suggestions=[
            "Decode the base64 content first to verify it",
            "Use clear, readable commands instead",
            "If legitimate, document why this approach is necessary",
        ],
        category="obfuscation",
    ),
    ValidationRule(
        rule_id="bash-variable-expansion-exec",
        name="Variable Expansion Command Execution",
        description="Detects suspicious variable expansion followed by execution",
        pattern=r"(?i)\$\{?\w+\}?\s*(\||;|&&|\|\|)\s*(bash|sh|eval|exec)|\b(eval|exec)\s+\$\{?\w+\}?",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P2,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command uses variable expansion before execution, which may hide malicious intent.",
        suggestions=[
            "Expand variables explicitly to verify the command",
            "Avoid complex variable expansions in shell commands",
            "Use direct commands instead of dynamic construction",
        ],
        category="obfuscation",
    ),
    ValidationRule(
        rule_id="bash-command-chain-dangerous",
        name="Dangerous Command Chain",
        description="Detects chains of commands that could be malicious",
        pattern=r"(?i)\b(rm\s+-rf?|dd\s+|mkfs|chmod\s+777|> /dev/).*(&&|\||;).*\b(rm|dd|mkfs|chmod|kill|drop|truncate)",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P2,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command chains multiple dangerous operations together.",
        suggestions=[
            "Break the command chain into separate steps",
            "Verify each command in the chain is safe",
            "Consider if all operations are necessary",
        ],
        category="obfuscation",
    ),
    ValidationRule(
        rule_id="bash-xor-decode-exec",
        name="XOR-Encoded Command Execution",
        description="Detects XOR or other encoding operations followed by execution",
        pattern=r"(?i)(perl\s+-e|python\s+-c|awk).*((xor|decode|unpack|chr)\s*\().*\|\s*(bash|sh)",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P2,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command uses encoding/decoding operations, which may hide malicious code.",
        suggestions=[
            "Decode the content first to verify it",
            "Use clear, readable commands instead",
            "If legitimate, document why this approach is necessary",
        ],
        category="obfuscation",
    ),
    ValidationRule(
        rule_id="bash-eval-in-command-chain",
        name="Eval in Command Chain",
        description="Detects eval command in command chains",
        pattern=r"(?i)\beval\s+(\$\{?\w+\}?|\(.+\)|\[.+\]).*(&&|\||;)",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P2,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command uses eval in a chain, which can execute arbitrary code.",
        suggestions=[
            "Avoid eval with dynamic content",
            "Use safer alternatives (arrays, functions)",
            "Verify the content being evaluated",
        ],
        category="code_injection",
    ),
    # --------------------------------------------------------------------
    # P3: Low - Informational
    # --------------------------------------------------------------------
    ValidationRule(
        rule_id="bash-deprecated-command",
        name="Deprecated Command Usage",
        description="Detects use of deprecated commands",
        pattern=r"(?i)\b(ftp|telnet|rcp|rlogin|rsh)\s+",
        pattern_type="regex",
        severity=SeverityLevel.LOW,
        priority=RulePriority.P3,
        tool_types=[ToolType.BASH],
        context="command",
        message="This command is deprecated and may be insecure.",
        suggestions=[
            "Use sftp instead of ftp",
            "Use ssh instead of telnet/rlogin/rsh",
            "Use scp or rsync instead of rcp",
        ],
        category="deprecation",
    ),
]

# ============================================================================
# FILE WRITE RULES (Content-based)
# ============================================================================

FILE_WRITE_RULES: list[ValidationRule] = [
    # --------------------------------------------------------------------
    # P0: Critical - Secret exposure
    # --------------------------------------------------------------------
    ValidationRule(
        rule_id="write-api-key-pattern",
        name="API Key in File",
        description="Detects potential API keys being written to files",
        pattern=r"(?i)(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|secret[_-]?key)\s*[=:]\s*['\"]?[a-zA-Z0-9_\-\.]{20,}",
        pattern_type="regex",
        severity=SeverityLevel.CRITICAL,
        priority=RulePriority.P0,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_content",
        message="This file appears to contain an API key or access token. Secrets should not be committed to version control.",
        suggestions=[
            "Use environment variables for secrets",
            "Add this file to .gitignore if it contains secrets",
            "Use a secret management system (e.g., HashiCorp Vault)",
            "Rotate the key if it was accidentally exposed",
        ],
        category="secret_exposure",
    ),
    ValidationRule(
        rule_id="write-aws-key-pattern",
        name="AWS Access Key in File",
        description="Detects AWS access keys being written to files",
        pattern=r"(?i)aws_access_key_id\s*[=:]\s*['\"]?(AKIA[0-9A-Z]{16})",
        pattern_type="regex",
        severity=SeverityLevel.CRITICAL,
        priority=RulePriority.P0,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_content",
        message="This file contains an AWS access key ID. AWS credentials should never be in files.",
        suggestions=[
            "Use AWS IAM roles or environment variables",
            "Add this file to .gitignore",
            "Rotate the AWS access key immediately",
            "Use AWS Secrets Manager or Parameter Store",
        ],
        category="secret_exposure",
    ),
    ValidationRule(
        rule_id="write-private-key-pattern",
        name="Private Key in File",
        description="Detects SSH private keys or certificates being written to files",
        pattern=r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
        pattern_type="regex",
        severity=SeverityLevel.CRITICAL,
        priority=RulePriority.P0,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_content",
        message="This file contains a private key. Private keys should never be committed to version control.",
        suggestions=[
            "Add this file to .gitignore immediately",
            "Rotate the key if it was exposed",
            "Ensure file permissions are 600 (owner read/write only)",
            "Use a key management system for production credentials",
        ],
        category="secret_exposure",
    ),
    ValidationRule(
        rule_id="write-password-pattern",
        name="Password in File",
        description="Detects hardcoded passwords in files",
        pattern=r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"]?[^\s'\"]{8,}",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P0,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_content",
        message="This file appears to contain a hardcoded password. Passwords should not be stored in files.",
        suggestions=[
            "Use environment variables for passwords",
            "Use a secure credential store",
            "Hash passwords instead of storing them in plain text",
            "Add this file to .gitignore",
        ],
        category="secret_exposure",
    ),
    # --------------------------------------------------------------------
    # P1: High - Malware indicators
    # --------------------------------------------------------------------
    ValidationRule(
        rule_id="write-eval-exec-pattern",
        name="Dynamic Code Execution",
        description="Detects eval/exec patterns that may indicate malicious code",
        pattern=r"(?i)(?:^|\s|\W)(?:(?:eval|exec|__import__|compile)\s*\()",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P1,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_content",
        message="This file contains dynamic code execution patterns, which can be dangerous if used with untrusted input.",
        suggestions=[
            "Avoid eval/exec with user input",
            "Use safer alternatives (e.g., ast.literal_eval for Python)",
            "Sanitize and validate all input before dynamic execution",
            "Consider if there's a safer way to achieve the same goal",
        ],
        category="code_injection",
    ),
    ValidationRule(
        rule_id="write-base64-decode-exec",
        name="Base64-Encoded Code Execution",
        description="Detects base64 decode followed by execution",
        pattern=r"(?i)(?:base64\s+-d|decode).*\|\s*(bash|python|node|php)",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P1,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_content",
        message="This file contains base64-encoded code execution, which is often used to hide malicious code.",
        suggestions=[
            "Avoid encoded execution in scripts",
            "Use clear, readable code instead",
            "If this is legitimate, document why this approach is necessary",
        ],
        category="obfuscation",
    ),
    ValidationRule(
        rule_id="write-reverse-shell",
        name="Reverse Shell Pattern",
        description="Detects reverse shell patterns",
        pattern=r"(?i)(?:bash\s+-i\s+>&\s*/dev/tcp/|nc\s+.*\s+-e\s+|/bin/sh\s+-i)",
        pattern_type="regex",
        severity=SeverityLevel.CRITICAL,
        priority=RulePriority.P1,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_content",
        message="This file contains a reverse shell pattern, which is typically used for unauthorized remote access.",
        suggestions=[
            "If this is intentional for remote administration, document the purpose",
            "Use proper remote access tools (SSH, VPN) instead",
            "Ensure adequate authentication and logging",
        ],
        category="backdoor",
    ),
    # --------------------------------------------------------------------
    # P2: Medium - Suspicious content
    # --------------------------------------------------------------------
    ValidationRule(
        rule_id="write-crypto-miner",
        name="Cryptocurrency Miner Pattern",
        description="Detects common cryptocurrency mining patterns",
        pattern=r"(?i)(crypto?mining?|miner|xmrig|cpuminer|monero|bitcoin.*mine|stratum\+tcp://)",
        pattern_type="regex",
        severity=SeverityLevel.MEDIUM,
        priority=RulePriority.P2,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_content",
        message="This file may contain cryptocurrency mining code.",
        suggestions=[
            "Ensure mining is authorized on this system",
            "Mining can consume significant CPU resources",
            "Check system resource usage policies",
        ],
        category="resource_abuse",
    ),
    ValidationRule(
        rule_id="write-coinhive",
        name="CoinHive or Similar In-Browser Miner",
        description="Detects in-browser cryptocurrency mining scripts",
        pattern=r"(?i)(coinhive|jsecoin|cryptoloot|crypto-loot|minergate)",
        pattern_type="regex",
        severity=SeverityLevel.MEDIUM,
        priority=RulePriority.P2,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_content",
        message="This file contains an in-browser mining script, which can degrade user experience.",
        suggestions=[
            "Obtain user consent before running mining scripts",
            "Consider alternative monetization strategies",
            "Mining without consent is considered malware",
        ],
        category="resource_abuse",
    ),
]

# ============================================================================
# FILE PATH RULES (Path-based)
# ============================================================================

FILE_PATH_RULES: list[ValidationRule] = [
    # --------------------------------------------------------------------
    # P0: Critical - System files
    # --------------------------------------------------------------------
    ValidationRule(
        rule_id="path-system-directory-write",
        name="Write to System Directory",
        description="Detects writes to critical system directories",
        pattern=r"^/(etc|usr|bin|sbin|lib|boot|sys|proc)/",
        pattern_type="regex",
        severity=SeverityLevel.CRITICAL,
        priority=RulePriority.P0,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_path",
        message="Writing to system directories can break your operating system.",
        suggestions=[
            "Use /usr/local for custom installations",
            "Use package managers (apt, yum, etc.) for system software",
            "Write to user directories instead",
        ],
        category="system_files",
    ),
    ValidationRule(
        rule_id="path-etc-passwd",
        name="Write to /etc/passwd",
        description="Detects writes to the system password file",
        pattern=r"^/etc/passwd$",
        pattern_type="regex",
        severity=SeverityLevel.CRITICAL,
        priority=RulePriority.P0,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_path",
        message="Writing to /etc/passwd can compromise system security and break authentication.",
        suggestions=[
            "Use 'useradd' and 'usermod' commands instead",
            "Never manually edit /etc/passwd unless absolutely necessary",
            "Backup the file before making changes",
        ],
        category="system_files",
    ),
    ValidationRule(
        rule_id="path-etc-shadow",
        name="Write to /etc/shadow",
        description="Detects writes to the system shadow password file",
        pattern=r"^/etc/shadow$",
        pattern_type="regex",
        severity=SeverityLevel.CRITICAL,
        priority=RulePriority.P0,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_path",
        message="Writing to /etc/shadow exposes password hashes and breaks authentication.",
        suggestions=[
            "Use 'passwd' command to change passwords",
            "Never manually edit /etc/shadow",
            "Ensure proper file permissions (600 root:root)",
        ],
        category="system_files",
    ),
    ValidationRule(
        rule_id="path-ssh-authorized-keys",
        name="Write to SSH Authorized Keys",
        description="Detects writes to SSH authorized_keys files",
        pattern=r"^/home/[^/]+/\.ssh/authorized_keys$|^/root/\.ssh/authorized_keys$",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P0,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_path",
        message="Writing to SSH authorized_keys can grant unauthorized access.",
        suggestions=[
            "Use 'ssh-copy-id' to add keys safely",
            "Review the key before adding it",
            "Ensure proper file permissions (600)",
        ],
        category="access_control",
    ),
    ValidationRule(
        rule_id="path-sudoers",
        name="Write to Sudoers File",
        description="Detects writes to sudoers configuration",
        pattern=r"^/etc/sudoers(|\.d/[^\s]+)$",
        pattern_type="regex",
        severity=SeverityLevel.CRITICAL,
        priority=RulePriority.P0,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_path",
        message="Writing to sudoers can grant unrestricted root access and break system security.",
        suggestions=[
            "Use 'visudo' command to edit sudoers safely",
            "Never manually edit /etc/sudoers",
            "Test sudoers configuration with 'visudo -c'",
        ],
        category="access_control",
    ),
    ValidationRule(
        rule_id="path-crontab",
        name="Write to System Crontab",
        description="Detects writes to system cron configuration",
        pattern=r"^/etc/crontab$|^/etc/cron\.(d|daily|hourly|monthly|weekly)/",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P0,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_path",
        message="Writing to system cron files can schedule malicious tasks.",
        suggestions=[
            "Use user crontabs (crontab -e) instead of system crontab",
            "Review scheduled tasks carefully",
            "Test cron jobs in a non-production environment first",
        ],
        category="system_files",
    ),
    # --------------------------------------------------------------------
    # P1: High - Security-sensitive files
    # --------------------------------------------------------------------
    ValidationRule(
        rule_id="path-ssh-config",
        name="Write to SSH Config",
        description="Detects writes to SSH configuration files",
        pattern=r"/\.ssh/config$|/\.ssh/known_hosts$",
        pattern_type="regex",
        severity=SeverityLevel.MEDIUM,
        priority=RulePriority.P1,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_path",
        message="Writing to SSH configuration files can affect security and connectivity.",
        suggestions=[
            "Review SSH configuration changes carefully",
            "Test SSH connections after changes",
            "Backup original config before modifying",
        ],
        category="access_control",
    ),
    ValidationRule(
        rule_id="path-environment-file",
        name="Write to .env File",
        description="Detects writes to environment files (may contain secrets)",
        pattern=r"/\.env$|/\.env\.",
        pattern_type="regex",
        severity=SeverityLevel.MEDIUM,
        priority=RulePriority.P1,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_path",
        message="Writing to .env files may expose secrets if committed to version control.",
        suggestions=[
            "Add .env files to .gitignore",
            "Use .env.example for template (without real values)",
            "Review file for secrets before writing",
        ],
        category="secret_exposure",
    ),
    ValidationRule(
        rule_id="path-hosts-file",
        name="Write to /etc/hosts",
        description="Detects writes to the system hosts file",
        pattern=r"^/etc/hosts$",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P1,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_path",
        message="Writing to /etc/hosts can redirect traffic and break network functionality.",
        suggestions=[
            "Backup the file before editing",
            "Test DNS resolution after changes",
            "Document the reason for each entry",
        ],
        category="network",
    ),
    # --------------------------------------------------------------------
    # P2: Medium - Other users' directories
    # --------------------------------------------------------------------
    ValidationRule(
        rule_id="path-other-user-home",
        name="Write to Another User's Home Directory",
        description="Detects writes to directories owned by other users",
        pattern=r"^/home/[^/]+/",
        pattern_type="regex",
        severity=SeverityLevel.MEDIUM,
        priority=RulePriority.P2,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_path",
        message="Writing to another user's home directory may violate privacy or permissions.",
        suggestions=[
            "Verify you have permission to write to this directory",
            "Write to your own home directory instead",
            "Use shared directories (e.g., /tmp, /var/tmp) for temporary files",
        ],
        category="access_control",
    ),
    ValidationRule(
        rule_id="path-systemd-unit",
        name="Write to Systemd Unit File",
        description="Detects writes to systemd service unit files",
        pattern=r"^/etc/systemd/system/.*\.service$|^/lib/systemd/system/.*\.service$",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P2,
        tool_types=[ToolType.WRITE, ToolType.EDIT],
        context="file_path",
        message="Writing to systemd unit files affects system services and startup behavior.",
        suggestions=[
            "Test unit files in ~/.config/systemd/user/ first",
            "Use 'systemctl daemon-reload' after changes",
            "Review unit file syntax with 'systemd-analyze verify'",
        ],
        category="system_files",
    ),
]

# ============================================================================
# WEB FETCH/SEARCH RULES
# ============================================================================

WEB_RULES: list[ValidationRule] = [
    ValidationRule(
        rule_id="web-fetch-internal-ip",
        name="Access Internal Network Resource",
        description="Detects web fetch requests to internal IP addresses",
        pattern=r"(?i)https?://(127\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)",
        pattern_type="regex",
        severity=SeverityLevel.MEDIUM,
        priority=RulePriority.P2,
        tool_types=[ToolType.WEB_FETCH, ToolType.WEB_SEARCH],
        context="all",
        message="This request targets an internal IP address, which may indicate SSRF or internal network access.",
        suggestions=[
            "Verify the URL is correct and intentional",
            "Ensure access to internal resources is authorized",
            "Consider if there's a safer way to access the resource",
        ],
        category="network_security",
    ),
    ValidationRule(
        rule_id="web-fetch-local-file",
        name="Local File Inclusion Attempt",
        description="Detects web fetch requests to local files (file://)",
        pattern=r"(?i)file://",
        pattern_type="regex",
        severity=SeverityLevel.HIGH,
        priority=RulePriority.P1,
        tool_types=[ToolType.WEB_FETCH, ToolType.WEB_SEARCH],
        context="all",
        message="This request uses the file:// protocol, which may indicate local file inclusion.",
        suggestions=[
            "Use the Read tool instead for local files",
            "Verify the file path is correct",
            "Be cautious with sensitive file access",
        ],
        category="file_access",
    ),
]

# ============================================================================
# DEFAULT RULE SETS
# ============================================================================

ALL_DEFAULT_RULES: list[ValidationRule] = [
    *BASH_RULES,
    *FILE_WRITE_RULES,
    *FILE_PATH_RULES,
    *WEB_RULES,
]


def get_default_rules(
    tool_type: ToolType | None = None,
    category: str | None = None,
    min_severity: SeverityLevel | None = None,
) -> list[ValidationRule]:
    """
    Get default validation rules with optional filtering.

    Args:
        tool_type: Optional tool type filter (e.g., ToolType.BASH)
        category: Optional category filter (e.g., "filesystem", "database")
        min_severity: Optional minimum severity filter (e.g., SeverityLevel.HIGH)

    Returns:
        List of ValidationRule objects matching the filters

    Examples:
        # Get all default rules
        rules = get_default_rules()

        # Get only Bash rules
        bash_rules = get_default_rules(tool_type=ToolType.BASH)

        # Get only high-severity filesystem rules
        fs_rules = get_default_rules(
            tool_type=ToolType.BASH,
            category="filesystem",
            min_severity=SeverityLevel.HIGH
        )
    """
    rules = ALL_DEFAULT_RULES.copy()

    # Filter by tool type
    if tool_type:
        rules = [r for r in rules if tool_type in r.tool_types or not r.tool_types]

    # Filter by category
    if category:
        rules = [r for r in rules if r.category == category]

    # Filter by severity
    if min_severity:
        severity_order = {
            SeverityLevel.LOW: 0,
            SeverityLevel.MEDIUM: 1,
            SeverityLevel.HIGH: 2,
            SeverityLevel.CRITICAL: 3,
        }
        min_level = severity_order[min_severity]
        rules = [r for r in rules if severity_order.get(r.severity, 0) >= min_level]

    return rules


def get_rule_by_id(rule_id: str) -> ValidationRule | None:
    """
    Get a specific rule by its ID.

    Args:
        rule_id: The rule ID to look up

    Returns:
        ValidationRule if found, None otherwise
    """
    for rule in ALL_DEFAULT_RULES:
        if rule.rule_id == rule_id:
            return rule
    return None


def list_rule_categories() -> list[str]:
    """
    Get all unique rule categories.

    Returns:
        List of category names
    """
    categories = set(r.category for r in ALL_DEFAULT_RULES)
    return sorted(categories)


def list_rule_ids() -> list[str]:
    """
    Get all rule IDs.

    Returns:
        List of rule IDs sorted by priority and category
    """
    priority_order = {
        RulePriority.P0: 0,
        RulePriority.P1: 1,
        RulePriority.P2: 2,
        RulePriority.P3: 3,
    }

    sorted_rules = sorted(
        ALL_DEFAULT_RULES,
        key=lambda r: (priority_order.get(r.priority, 99), r.category, r.rule_id),
    )

    return [r.rule_id for r in sorted_rules]
