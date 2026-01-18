#!/usr/bin/env python3
"""Debug script to trace OAuth token flow."""
import os
import json
import platform
import subprocess
from pathlib import Path

def debug_token_sources():
    """Check all OAuth token sources and log what's found."""
    timestamp = int(__import__('time').time() * 1000)
    
    log_entries = []
    
    # Check environment variables
    env_oauth = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    env_auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    
    log_entries.append({
        "id": f"log_{timestamp}_env_vars",
        "timestamp": timestamp,
        "location": "debug_token_flow.py:env_vars",
        "message": "Checking environment variables",
        "data": {
            "CLAUDE_CODE_OAUTH_TOKEN": env_oauth[:20] + "..." if env_oauth else None,
            "ANTHROPIC_AUTH_TOKEN": env_auth_token[:20] + "..." if env_auth_token else None
        },
        "sessionId": "debug-session",
        "hypothesisId": "B"
    })
    
    # Check macOS Keychain
    keychain_token = None
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["/usr/bin/security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                credentials_json = result.stdout.strip()
                if credentials_json:
                    data = json.loads(credentials_json)
                    keychain_token = data.get("claudeAiOauth", {}).get("accessToken")
                    
            log_entries.append({
                "id": f"log_{timestamp}_keychain",
                "timestamp": timestamp,
                "location": "debug_token_flow.py:keychain",
                "message": "Checked macOS Keychain",
                "data": {
                    "has_token": keychain_token is not None,
                    "token_prefix": keychain_token[:20] + "..." if keychain_token else None,
                    "returncode": result.returncode
                },
                "sessionId": "debug-session",
                "hypothesisId": "A"
            })
        except Exception as e:
            log_entries.append({
                "id": f"log_{timestamp}_keychain_error",
                "timestamp": timestamp,
                "location": "debug_token_flow.py:keychain_error",
                "message": "Keychain access failed",
                "data": {"error": str(e)},
                "sessionId": "debug-session",
                "hypothesisId": "A"
            })
    
    # Check .auto-claude/.env file
    auto_claude_env_path = Path("/Users/jacques/DevFolder/Auto-Claude/apps/backend/.auto-claude/.env")
    env_file_token = None
    if auto_claude_env_path.exists():
        env_content = auto_claude_env_path.read_text()
        for line in env_content.strip().split('\n'):
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                if 'CLAUDE_CODE_OAUTH_TOKEN' in key or 'ANTHROPIC_AUTH_TOKEN' in key:
                    env_file_token = value.strip()
                    break
    
    log_entries.append({
        "id": f"log_{timestamp}_env_file",
        "timestamp": timestamp,
        "location": "debug_token_flow.py:auto_claude_env_file",
        "message": "Checked .auto-claude/.env",
        "data": {
            "exists": auto_claude_env_path.exists(),
            "has_oauth_token": env_file_token is not None,
            "token_prefix": env_file_token[:20] + "..." if env_file_token else None
        },
        "sessionId": "debug-session",
        "hypothesisId": "B"
    })
    
    # Write all logs
    log_path = Path("/Users/jacques/DevFolder/Auto-Claude/.cursor/debug.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(log_path, "a") as f:
        for entry in log_entries:
            f.write(json.dumps(entry) + "\n")
    
    print(f"\n{'='*60}")
    print("OAuth Token Debug Report")
    print(f"{'='*60}")
    print(f"  Environment CLAUDE_CODE_OAUTH_TOKEN: {env_oauth[:30] + '...' if env_oauth else 'NOT SET'}")
    print(f"  Environment ANTHROPIC_AUTH_TOKEN: {env_auth_token[:30] + '...' if env_auth_token else 'NOT SET'}")
    print(f"  macOS Keychain Token: {keychain_token[:30] + '...' if keychain_token else 'NOT FOUND'}")
    print(f"  .auto-claude/.env Token: {env_file_token[:30] + '...' if env_file_token else 'NOT FOUND'}")
    print(f"  Full report written to: {log_path}")
    print(f"{'='*60}")

if __name__ == "__main__":
    debug_token_sources()
