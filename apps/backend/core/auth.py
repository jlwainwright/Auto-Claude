"""
Authentication helpers for Auto Claude.

Provides centralized authentication token resolution with fallback support
for multiple environment variables, and SDK environment variable passthrough
for custom API endpoints.
"""

import json
import os
import platform
import subprocess

# Priority order for auth token resolution
# NOTE: We intentionally do NOT fall back to ANTHROPIC_API_KEY.
# Auto Claude is designed to use Claude Code OAuth tokens only.
# This prevents silent billing to user's API credits when OAuth fails.
AUTH_TOKEN_ENV_VARS = [
    "CLAUDE_CODE_OAUTH_TOKEN",  # OAuth token from Claude Code CLI
    "ANTHROPIC_AUTH_TOKEN",  # CCR/proxy token (for enterprise setups)
]

# Environment variables to pass through to SDK subprocess
# NOTE: ANTHROPIC_API_KEY is intentionally excluded to prevent silent API billing
SDK_ENV_VARS = [
    # API endpoint configuration
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    # Model overrides (from API Profile custom model mappings)
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    # SDK behavior configuration
    "NO_PROXY",
    "DISABLE_TELEMETRY",
    "DISABLE_COST_WARNINGS",
    "API_TIMEOUT_MS",
    # Windows-specific: Git Bash path for Claude Code CLI
    "CLAUDE_CODE_GIT_BASH_PATH",
]


def get_token_from_keychain() -> str | None:
    """
    Get authentication token from system credential store.

    Reads Claude Code credentials from:
    - macOS: Keychain
    - Windows: Credential Manager
    - Linux: Not yet supported (use env var)

    Returns:
        Token string if found, None otherwise
    """
    system = platform.system()

    if system == "Darwin":
        return _get_token_from_macos_keychain()
    elif system == "Windows":
        return _get_token_from_windows_credential_files()
    else:
        # Linux: secret-service not yet implemented
        return None


def _get_token_from_macos_keychain() -> str | None:
    """Get token from macOS Keychain."""
    # #region agent log
    import json
    import time
    log_path = "/Users/jacques/DevFolder/Auto-Claude/.cursor/debug.log"
    # #endregion

    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                "Claude Code-credentials",
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    log_entry = {
                        "id": f"log_{int(time.time()*1000)}_keychain_error",
                        "timestamp": int(time.time() * 1000),
                        "location": "auth.py:_get_token_from_macos_keychain",
                        "message": "Keychain lookup failed (non-zero return code)",
                        "data": {"returncode": result.returncode},
                        "sessionId": "debug-session",
                        "hypothesisId": "A"
                    }
                    f.write(json.dumps(log_entry) + "\n")
            except:
                pass
            # #endregion

            return None

        credentials_json = result.stdout.strip()
        if not credentials_json:
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    log_entry = {
                        "id": f"log_{int(time.time()*1000)}_keychain_empty",
                        "timestamp": int(time.time() * 1000),
                        "location": "auth.py:_get_token_from_macos_keychain",
                        "message": "Keychain returned empty string",
                        "data": {},
                        "sessionId": "debug-session",
                        "hypothesisId": "A"
                    }
                    f.write(json.dumps(log_entry) + "\n")
            except:
                pass
            # #endregion

            return None

        data = json.loads(credentials_json)
        token = data.get("claudeAiOauth", {}).get("accessToken")

        if not token:
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    log_entry = {
                        "id": f"log_{int(time.time()*1000)}_keychain_no_token",
                        "timestamp": int(time.time() * 1000),
                        "location": "auth.py:_get_token_from_macos_keychain",
                        "message": "Keychain has no accessToken field",
                        "data": {"has_claudeAiOauth": "claudeAiOauth" in data},
                        "sessionId": "debug-session",
                        "hypothesisId": "A"
                    }
                    f.write(json.dumps(log_entry) + "\n")
            except:
                pass
            # #endregion

            return None

        # Validate token format (Claude OAuth tokens start with sk-ant-oat01-)
        if not token.startswith("sk-ant-oat01-"):
            # #region agent log
            try:
                with open(log_path, "a") as f:
                    log_entry = {
                        "id": f"log_{int(time.time()*1000)}_keychain_invalid_format",
                        "timestamp": int(time.time() * 1000),
                        "location": "auth.py:_get_token_from_macos_keychain",
                        "message": "Keychain token has invalid format",
                        "data": {"token_prefix": token[:30] + "..."},
                        "sessionId": "debug-session",
                        "hypothesisId": "A"
                    }
                    f.write(json.dumps(log_entry) + "\n")
            except:
                pass
            # #endregion

            return None

        # #region agent log
        try:
            with open(log_path, "a") as f:
                log_entry = {
                    "id": f"log_{int(time.time()*1000)}_keychain_success",
                    "timestamp": int(time.time() * 1000),
                    "location": "auth.py:_get_token_from_macos_keychain",
                    "message": "Successfully retrieved token from keychain",
                    "data": {"token_prefix": token[:20] + "..."},
                    "sessionId": "debug-session",
                    "hypothesisId": "A"
                }
                f.write(json.dumps(log_entry) + "\n")
        except:
            pass
        # #endregion

        return token

    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, Exception) as e:
        # #region agent log
        try:
            with open(log_path, "a") as f:
                log_entry = {
                    "id": f"log_{int(time.time()*1000)}_keychain_exception",
                    "timestamp": int(time.time() * 1000),
                    "location": "auth.py:_get_token_from_macos_keychain",
                    "message": "Exception in keychain lookup",
                    "data": {"exception_type": type(e).__name__},
                    "sessionId": "debug-session",
                    "hypothesisId": "A"
                }
                f.write(json.dumps(log_entry) + "\n")
        except:
            pass
        # #endregion

        return None


def _get_token_from_windows_credential_files() -> str | None:
    """Get token from Windows credential files.

    Claude Code on Windows stores credentials in ~/.claude/.credentials.json
    """
    try:
        # Claude Code stores credentials in ~/.claude/.credentials.json
        cred_paths = [
            os.path.expandvars(r"%USERPROFILE%\.claude\.credentials.json"),
            os.path.expandvars(r"%USERPROFILE%\.claude\credentials.json"),
            os.path.expandvars(r"%LOCALAPPDATA%\Claude\credentials.json"),
            os.path.expandvars(r"%APPDATA%\Claude\credentials.json"),
        ]

        for cred_path in cred_paths:
            if os.path.exists(cred_path):
                with open(cred_path, encoding="utf-8") as f:
                    data = json.load(f)
                    token = data.get("claudeAiOauth", {}).get("accessToken")
                    if token and token.startswith("sk-ant-oat01-"):
                        return token

        return None

    except (json.JSONDecodeError, KeyError, FileNotFoundError, Exception):
        return None


def get_auth_token() -> str | None:
    """
    Get authentication token from environment variables or system credential store.

    Checks multiple sources in priority order:
    1. CLAUDE_CODE_OAUTH_TOKEN (env var)
    2. ANTHROPIC_AUTH_TOKEN (CCR/proxy env var for enterprise setups)
    3. System credential store (macOS Keychain, Windows Credential Manager)

    NOTE: ANTHROPIC_API_KEY is intentionally NOT supported to prevent
    silent billing to user's API credits when OAuth is misconfigured.

    Returns:
        Token string if found, None otherwise
    """
    # #region agent log
    import json
    import time
    log_path = "/Users/jacques/DevFolder/Auto-Claude/.cursor/debug.log"
    try:
        with open(log_path, "a") as f:
            log_entry = {
                "id": f"log_{int(time.time()*1000)}_auth_get",
                "timestamp": int(time.time() * 1000),
                "location": "auth.py:get_auth_token",
                "message": "Checking auth token sources",
                "data": {
                    "env_CLAUDE_CODE_OAUTH_TOKEN": os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")[:50] + "..." if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") else None,
                    "env_ANTHROPIC_AUTH_TOKEN": os.environ.get("ANTHROPIC_AUTH_TOKEN", "")[:50] + "..." if os.environ.get("ANTHROPIC_AUTH_TOKEN") else None,
                    "system": platform.system()
                },
                "sessionId": "debug-session",
                "hypothesisId": "A"
            }
            f.write(json.dumps(log_entry) + "\n")
    except:
        pass
    # #endregion

    # First check environment variables
    for var in AUTH_TOKEN_ENV_VARS:
        token = os.environ.get(var)
        if not token:
            continue

        # Ignore Electron-safeStorage encrypted tokens ("enc:...") which cannot be
        # decrypted in the backend process. This prevents confusing auth/connection
        # failures when a UI-written .env contains an encrypted value.
        token = token.strip()
        if not token or token.startswith("enc:"):
            continue

        # #region agent log
        try:
            with open(log_path, "a") as f:
                log_entry = {
                    "id": f"log_{int(time.time()*1000)}_auth_found",
                    "timestamp": int(time.time() * 1000),
                    "location": "auth.py:get_auth_token",
                    "message": f"Token found in env var: {var}",
                    "data": {
                        "source": var,
                        "token_prefix": token[:20] + "..." if token else None
                    },
                    "sessionId": "debug-session",
                    "hypothesisId": "A"
                }
                f.write(json.dumps(log_entry) + "\n")
        except:
            pass
        # #endregion

        return token

    # Fallback to system credential store
    # #region agent log
    try:
        keychain_token = get_token_from_keychain()
        with open(log_path, "a") as f:
            log_entry = {
                "id": f"log_{int(time.time()*1000)}_auth_keychain",
                "timestamp": int(time.time() * 1000),
                "location": "auth.py:get_auth_token",
                "message": "Falling back to keychain",
                "data": {
                    "has_token": keychain_token is not None,
                    "token_prefix": keychain_token[:20] + "..." if keychain_token else None
                },
                "sessionId": "debug-session",
                "hypothesisId": "A"
            }
            f.write(json.dumps(log_entry) + "\n")
    except:
        pass
    # #endregion

    return get_token_from_keychain()


def get_auth_token_source() -> str | None:
    """Get the name of the source that provided the auth token."""
    # Check environment variables first
    for var in AUTH_TOKEN_ENV_VARS:
        token = os.environ.get(var)
        if not token:
            continue
        token = token.strip()
        if token and not token.startswith("enc:"):
            return var

    # Check if token came from system credential store
    if get_token_from_keychain():
        system = platform.system()
        if system == "Darwin":
            return "macOS Keychain"
        elif system == "Windows":
            return "Windows Credential Files"
        else:
            return "System Credential Store"

    return None


def require_auth_token() -> str:
    """
    Get authentication token or raise ValueError.

    Raises:
        ValueError: If no auth token is found in any supported source
    """
    token = get_auth_token()
    if not token:
        error_msg = (
            "No OAuth token found.\n\n"
            "Auto Claude requires Claude Code OAuth authentication.\n"
            "Direct API keys (ANTHROPIC_API_KEY) are not supported.\n\n"
        )
        # Provide platform-specific guidance
        system = platform.system()
        if system == "Darwin":
            error_msg += (
                "To authenticate:\n"
                "  1. Run: claude setup-token\n"
                "  2. The token will be saved to macOS Keychain automatically\n\n"
                "Or set CLAUDE_CODE_OAUTH_TOKEN in your .env file."
            )
        elif system == "Windows":
            error_msg += (
                "To authenticate:\n"
                "  1. Run: claude setup-token\n"
                "  2. The token should be saved to Windows Credential Manager\n\n"
                "If auto-detection fails, set CLAUDE_CODE_OAUTH_TOKEN in your .env file.\n"
                "Check: %LOCALAPPDATA%\\Claude\\credentials.json"
            )
        else:
            error_msg += (
                "To authenticate:\n"
                "  1. Run: claude setup-token\n"
                "  2. Set CLAUDE_CODE_OAUTH_TOKEN in your .env file"
            )
        raise ValueError(error_msg)
    return token


def _find_git_bash_path() -> str | None:
    """
    Find git-bash (bash.exe) path on Windows.

    Uses 'where git' to find git.exe, then derives bash.exe location from it.
    Git for Windows installs bash.exe in the 'bin' directory alongside git.exe
    or in the parent 'bin' directory when git.exe is in 'cmd'.

    Returns:
        Full path to bash.exe if found, None otherwise
    """
    if platform.system() != "Windows":
        return None

    # If already set in environment, use that
    existing = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if existing and os.path.exists(existing):
        return existing

    git_path = None

    # Method 1: Use 'where' command to find git.exe
    try:
        # Use where.exe explicitly for reliability
        result = subprocess.run(
            ["where.exe", "git"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )

        if result.returncode == 0 and result.stdout.strip():
            git_paths = result.stdout.strip().splitlines()
            if git_paths:
                git_path = git_paths[0].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        # Intentionally suppress errors - best-effort detection with fallback to common paths
        pass

    # Method 2: Check common installation paths if 'where' didn't work
    if not git_path:
        common_git_paths = [
            os.path.expandvars(r"%PROGRAMFILES%\Git\cmd\git.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Git\bin\git.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Git\cmd\git.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
        ]
        for path in common_git_paths:
            if os.path.exists(path):
                git_path = path
                break

    if not git_path:
        return None

    # Derive bash.exe location from git.exe location
    # Git for Windows structure:
    #   C:\...\Git\cmd\git.exe     -> bash.exe is at C:\...\Git\bin\bash.exe
    #   C:\...\Git\bin\git.exe     -> bash.exe is at C:\...\Git\bin\bash.exe
    #   C:\...\Git\mingw64\bin\git.exe -> bash.exe is at C:\...\Git\bin\bash.exe
    git_dir = os.path.dirname(git_path)
    git_parent = os.path.dirname(git_dir)
    git_grandparent = os.path.dirname(git_parent)

    # Check common bash.exe locations relative to git installation
    possible_bash_paths = [
        os.path.join(git_parent, "bin", "bash.exe"),  # cmd -> bin
        os.path.join(git_dir, "bash.exe"),  # If git.exe is in bin
        os.path.join(git_grandparent, "bin", "bash.exe"),  # mingw64/bin -> bin
    ]

    for bash_path in possible_bash_paths:
        if os.path.exists(bash_path):
            return bash_path

    return None


def get_sdk_env_vars() -> dict[str, str]:
    """
    Get environment variables to pass to SDK.

    Collects relevant env vars (ANTHROPIC_BASE_URL, etc.) that should
    be passed through to the claude-agent-sdk subprocess.

    On Windows, auto-detects CLAUDE_CODE_GIT_BASH_PATH if not already set.

    Returns:
        Dict of env var name -> value for non-empty vars
    """
    env = {}
    for var in SDK_ENV_VARS:
        value = os.environ.get(var)
        if value:
            value = value.strip()
            if not value or value.startswith("enc:"):
                continue
            env[var] = value

    # On Windows, auto-detect git-bash path if not already set
    # Claude Code CLI requires bash.exe to run on Windows
    if platform.system() == "Windows" and "CLAUDE_CODE_GIT_BASH_PATH" not in env:
        bash_path = _find_git_bash_path()
        if bash_path:
            env["CLAUDE_CODE_GIT_BASH_PATH"] = bash_path

    return env


def ensure_claude_code_oauth_token() -> None:
    """
    Ensure CLAUDE_CODE_OAUTH_TOKEN is set (for SDK compatibility).

    If not set but other auth tokens are available, copies the value
    to CLAUDE_CODE_OAUTH_TOKEN so the underlying SDK can use it.
    """
    # #region agent log
    import json
    import time
    log_path = "/Users/jacques/DevFolder/Auto-Claude/.cursor/debug.log"
    try:
        existing_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
        with open(log_path, "a") as f:
            log_entry = {
                "id": f"log_{int(time.time()*1000)}_ensure_start",
                "timestamp": int(time.time() * 1000),
                "location": "auth.py:ensure_claude_code_oauth_token",
                "message": "Checking existing CLAUDE_CODE_OAUTH_TOKEN",
                "data": {
                    "existing_token_prefix": existing_token[:20] + "..." if existing_token else None,
                    "existing_token_length": len(existing_token) if existing_token else 0
                },
                "sessionId": "debug-session",
                "hypothesisId": "B"
            }
            f.write(json.dumps(log_entry) + "\n")
    except:
        pass
    # #endregion

    existing = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if existing and existing.strip() and not existing.strip().startswith("enc:"):
        # #region agent log
        try:
            with open(log_path, "a") as f:
                log_entry = {
                    "id": f"log_{int(time.time()*1000)}_ensure_skip",
                    "timestamp": int(time.time() * 1000),
                    "location": "auth.py:ensure_claude_code_oauth_token",
                    "message": "Skipping - valid existing token already set",
                    "data": {
                        "existing_token_prefix": existing[:20] + "...",
                        "existing_token_length": len(existing)
                    },
                    "sessionId": "debug-session",
                    "hypothesisId": "B"
                }
                f.write(json.dumps(log_entry) + "\n")
        except:
            pass
        # #endregion
        return

    token = get_auth_token()
    if token:
        # #region agent log
        try:
            with open(log_path, "a") as f:
                log_entry = {
                    "id": f"log_{int(time.time()*1000)}_ensure_set",
                    "timestamp": int(time.time() * 1000),
                    "location": "auth.py:ensure_claude_code_oauth_token",
                    "message": "Setting CLAUDE_CODE_OAUTH_TOKEN from get_auth_token()",
                    "data": {
                        "token_prefix": token[:20] + "...",
                        "token_length": len(token)
                    },
                    "sessionId": "debug-session",
                    "hypothesisId": "B"
                }
                f.write(json.dumps(log_entry) + "\n")
        except:
            pass
        # #endregion
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token
