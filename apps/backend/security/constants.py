"""
Security Constants
==================

Shared constants for the security module.
"""

# Environment variable name for the project directory
# Set by agents (coder.py, loop.py) at startup to ensure security hooks
# can find the correct project directory even in worktree mode.
PROJECT_DIR_ENV_VAR = "AUTO_CLAUDE_PROJECT_DIR"

# Security configuration filenames
# These are the files that control which commands are allowed to run.
ALLOWLIST_FILENAME = ".auto-claude-allowlist"
PROFILE_FILENAME = ".auto-claude-security.json"

# =============================================================================
# INPUT SCREENING CONSTANTS
# =============================================================================

# Environment variable for configuring input screening level
SCREENING_LEVEL_ENV_VAR = "AUTO_CLAUDE_SCREENING_LEVEL"

# Input screening allowlist filename
SCREENING_ALLOWLIST_FILENAME = ".auto-claude-screening-allowlist.txt"

# Default screening level (can be overridden via environment)
DEFAULT_SCREENING_LEVEL = "normal"

# Maximum input length to screen (in characters)
MAX_SCREENING_INPUT_LENGTH = 100_000

# Screening level descriptions
SCREENING_LEVELS = {
    "permissive": "Only block critical threats. Higher false positive rate but maximum flexibility.",
    "normal": "Balance security and usability. Default recommended level.",
    "strict": "Block anything suspicious. Lowest false positive rate but may reject valid input.",
}

# Default allowlist for safe technical phrases
# These are phrases that are commonly used in legitimate development tasks
# but may contain keywords that could be misinterpreted as malicious
DEFAULT_SCREENING_ALLOWLIST = [
    # CSS/styling related
    "override default css",
    "override styles",
    "override styling",
    "override css styles",
    # Configuration/settings related
    "override configuration",
    "override settings",
    "override defaults",
    "override insecure defaults",
    "override default configuration",
    # Command execution (legitimate admin/dev tasks)
    "shell command",
    "shell command execution",
    "execute shell commands",
    "execute queries",
    "run commands",
    "command execution",
    # Security testing (legitimate security work)
    "test for vulnerabilities",
    "test for authentication",
    "injection prevention",
    "injection attacks",
    "sql injection",
    "authentication bypass",
    "test authentication bypass",
    # Web development
    "override http",
    "override headers",
    "override response",
    # Other technical contexts
    "method override",
    "override method",
]

# Confidence thresholds for each screening level
# These thresholds are tuned to achieve <1% false positive rate
SCREENING_THRESHOLDS = {
    "permissive": {
        "suspicious_threshold": 0.8,  # Only flag very high confidence threats
        "reject_threshold": 0.95,  # Only reject critical threats
    },
    "normal": {
        "suspicious_threshold": 0.5,  # Flag moderate confidence threats
        "reject_threshold": 0.7,  # Reject high confidence threats
    },
    "strict": {
        "suspicious_threshold": 0.3,  # Flag low confidence threats
        "reject_threshold": 0.5,  # Reject anything suspicious
    },
}
