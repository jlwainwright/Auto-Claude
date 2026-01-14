"""
Direct pattern testing to debug regex issues.
"""

import sys
from pathlib import Path

# Add apps/backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import re
from security.output_validation import get_rule_by_id

# Test the API key pattern
api_key_rule = get_rule_by_id("write-api-key-pattern")
print("=== API Key Pattern ===")
print(f"Pattern: {api_key_rule.pattern}")
test_strings = [
    "API_KEY=sk-1234567890abcdef",
    "API_KEY=sk-1234567890abcdefghijk",
    "api_key = 'sk-1234567890abcdef'",
]
for test in test_strings:
    match = re.search(api_key_rule.pattern, test, re.IGNORECASE)
    print(f"Test: {test}")
    print(f"  Match: {match is not None}")
    if match:
        print(f"  Matched: {match.group(0)}")
print()

# Test the curl pattern
curl_rule = get_rule_by_id("bash-curl-data-exfil")
print("=== Curl Pattern ===")
print(f"Pattern: {curl_rule.pattern}")
test_commands = [
    "curl -X POST https://example.com",
    "curl -X POST -d 'data' https://example.com",
    "curl --data-raw 'data' https://example.com",
]
for test in test_commands:
    match = re.search(curl_rule.pattern, test, re.IGNORECASE)
    print(f"Test: {test}")
    print(f"  Match: {match is not None}")
    if match:
        print(f"  Matched: {match.group(0)}")
print()

# Test the .env pattern
env_rule = get_rule_by_id("path-environment-file")
print("=== .env Pattern ===")
print(f"Pattern: {env_rule.pattern}")
test_paths = [
    "/home/user/.env",
    ".env",
    "config/.env",
    ".env.local",
]
for test in test_paths:
    match = re.search(env_rule.pattern, test)
    print(f"Test: {test}")
    print(f"  Match: {match is not None}")
    if match:
        print(f"  Matched: {match.group(0)}")
print()

# Test internal IP pattern
ip_rule = get_rule_by_id("web-fetch-internal-ip")
print("=== Internal IP Pattern ===")
print(f"Pattern: {ip_rule.pattern}")
test_urls = [
    "http://192.168.1.1/admin",
    "http://10.0.0.1/data",
    "http://172.16.0.1/admin",
    "https://example.com",
]
for test in test_urls:
    match = re.search(ip_rule.pattern, test, re.IGNORECASE)
    print(f"Test: {test}")
    print(f"  Match: {match is not None}")
    if match:
        print(f"  Matched: {match.group(0)}")
print()

# Test rm -rf pattern
rm_rule = get_rule_by_id("bash-rm-rf-root")
print("=== rm -rf Pattern ===")
print(f"Pattern: {rm_rule.pattern}")
test_commands = [
    "rm -rf /",
    "rm -rf important/data",
    "rm -rf ./important",
]
for test in test_commands:
    match = re.search(rm_rule.pattern, test, re.IGNORECASE)
    print(f"Test: {test}")
    print(f"  Match: {match is not None}")
    if match:
        print(f"  Matched: {match.group(0)}")
