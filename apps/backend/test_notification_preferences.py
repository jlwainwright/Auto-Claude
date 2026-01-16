#!/usr/bin/env python3
"""
Test Notification Preferences for Slack Integration

This script tests that notification preferences are correctly checked
before sending Slack notifications.
"""

import json
import sys
from pathlib import Path


def test_preference_checking_exists():
    """Test that all notification functions check preferences."""
    print("Testing preference checks in notification functions...")

    updater_path = Path(__file__).parent / "integrations" / "slack" / "updater.py"
    content = updater_path.read_text()

    # Define required preference checks
    required_checks = {
        "slack_build_started": "notify_build_start",
        "slack_build_completed": "notify_build_complete",
        "slack_build_failed": "notify_build_fail",
        "slack_subtask_update": "notify_subtask_updates",
        "send_spec_approval_request": "notify_spec_approval",
    }

    all_passed = True

    for func_name, pref_key in required_checks.items():
        # Find the function definition
        func_start = content.find(f"async def {func_name}(")
        if func_start == -1:
            print(f"  ❌ Function {func_name} not found")
            all_passed = False
            continue

        # Find the next function definition (to limit search scope)
        next_func = content.find("\nasync def ", func_start + 1)
        if next_func == -1:
            next_func = len(content)

        func_body = content[func_start:next_func]

        # Check if preference is checked
        if f'"{pref_key}"' in func_body or f"'{pref_key}'" in func_body:
            print(f"  ✅ {func_name} checks {pref_key}")
        else:
            print(f"  ❌ {func_name} does NOT check {pref_key}")
            all_passed = False

    return all_passed


def test_preference_structure():
    """Test that SlackProjectState has preferences structure."""
    print("\nTesting preference structure in config...")

    config_path = Path(__file__).parent / "integrations" / "slack" / "config.py"
    content = config_path.read_text()

    required_fields = [
        "notify_build_start",
        "notify_build_complete",
        "notify_build_fail",
        "notify_spec_approval",
        "notify_subtask_updates",
    ]

    all_passed = True

    # Check NotificationPreferences class
    if "class NotificationPreferences" in content:
        print("  ✅ NotificationPreferences class exists")

        for field in required_fields:
            if field in content:
                print(f"    ✅ Field {field} defined")
            else:
                print(f"    ❌ Field {field} missing")
                all_passed = False
    else:
        print("  ❌ NotificationPreferences class not found")
        all_passed = False

    # Check SlackProjectState has preferences field
    if "preferences:" in content or "preferences =" in content:
        print("  ✅ SlackProjectState has preferences field")
    else:
        print("  ❌ SlackProjectState missing preferences field")
        all_passed = False

    return all_passed


def test_preference_defaults():
    """Test that preference defaults are correctly set."""
    print("\nTesting preference defaults...")

    config_path = Path(__file__).parent / "integrations" / "slack" / "config.py"
    content = config_path.read_text()

    defaults = {
        "DEFAULT_NOTIFY_BUILD_START": "True",
        "DEFAULT_NOTIFY_BUILD_COMPLETE": "True",
        "DEFAULT_NOTIFY_BUILD_FAIL": "True",
        "DEFAULT_NOTIFY_SPEC_APPROVAL": "True",
        "DEFAULT_NOTIFY_SUBTASK_UPDATES": "False",
    }

    all_passed = True

    for const_name, expected_value in defaults.items():
        if f"{const_name} = {expected_value}" in content:
            print(f"  ✅ {const_name} = {expected_value}")
        else:
            print(f"  ❌ {const_name} not set to {expected_value}")
            all_passed = False

    return all_passed


def test_preference_methods():
    """Test that SlackManager has preference methods."""
    print("\nTesting SlackManager preference methods...")

    integration_path = Path(__file__).parent / "integrations" / "slack" / "integration.py"
    content = integration_path.read_text()

    required_methods = [
        "def get_notification_preferences",
        "def update_notification_preferences",
    ]

    all_passed = True

    for method in required_methods:
        if method in content:
            print(f"  ✅ Method {method} exists")
        else:
            print(f"  ❌ Method {method} missing")
            all_passed = False

    return all_passed


def test_preference_persistence():
    """Test that preferences are persisted to state file."""
    print("\nTesting preference persistence...")

    integration_path = Path(__file__).parent / "integrations" / "slack" / "integration.py"
    content = integration_path.read_text()

    all_passed = True

    # Check that update_notification_preferences saves state
    if "update_notification_preferences" in content:
        func_start = content.find("def update_notification_preferences")
        func_end = content.find("\n    def ", func_start + 1)
        func_body = content[func_start:func_end]

        if "state.save(" in func_body or ".save(" in func_body:
            print("  ✅ Preferences are saved to state file")
        else:
            print("  ❌ Preferences may not be saved (no state.save call)")
            all_passed = False

    # Check that SlackProjectState has to_dict with preferences
    config_path = Path(__file__).parent / "integrations" / "slack" / "config.py"
    config_content = config_path.read_text()

    if '"preferences"' in config_content or "'preferences'" in config_content:
        print("  ✅ Preferences included in state serialization")
    else:
        print("  ❌ Preferences not included in state serialization")
        all_passed = False

    return all_passed


def test_preference_loading():
    """Test that preferences can be loaded from state."""
    print("\nTesting preference loading...")

    config_path = Path(__file__).parent / "integrations" / "slack" / "config.py"
    content = config_path.read_text()

    all_passed = True

    # Check from_dict method loads preferences
    if "from_dict" in content and "preferences" in content:
        print("  ✅ Preferences can be loaded from dict")
    else:
        print("  ❌ Preferences may not load correctly")
        all_passed = False

    # Check get_preferences method
    integration_path = Path(__file__).parent / "integrations" / "slack" / "integration.py"
    integration_content = integration_path.read_text()

    if "get_notification_preferences" in integration_content:
        print("  ✅ get_notification_preferences method exists")
    else:
        print("  ❌ get_notification_preferences method missing")
        all_passed = False

    return all_passed


def test_frontend_ui():
    """Test that frontend UI has preference toggles."""
    print("\nTesting frontend UI preference toggles...")

    slack_integration_path = (
        Path(__file__).parent.parent / "frontend" / "src" / "renderer" / "components" /
        "settings" / "integrations" / "SlackIntegration.tsx"
    )

    if not slack_integration_path.exists():
        print("  ⚠️  SlackIntegration.tsx not found (frontend may not be built)")
        return True

    content = slack_integration_path.read_text()

    ui_elements = {
        "Build Started": "slackNotifyBuildStart",
        "Build Completed": "slackNotifyBuildComplete",
        "Build Failed": "slackNotifyBuildFailed",
        "Spec Approval Requests": "slackNotifySpecApproval",
    }

    all_passed = True

    for label, prop_name in ui_elements.items():
        if label in content and prop_name in content:
            print(f"  ✅ UI toggle for {label} ({prop_name})")
        else:
            print(f"  ❌ UI toggle for {label} missing")
            all_passed = False

    return all_passed


def run_all_tests():
    """Run all notification preference tests."""
    print("=" * 60)
    print("Slack Notification Preferences Test Suite")
    print("=" * 60)

    tests = [
        ("Preference Checking", test_preference_checking_exists),
        ("Preference Structure", test_preference_structure),
        ("Preference Defaults", test_preference_defaults),
        ("Preference Methods", test_preference_methods),
        ("Preference Persistence", test_preference_persistence),
        ("Preference Loading", test_preference_loading),
        ("Frontend UI", test_frontend_ui),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            passed = test_func()
            results[test_name] = passed
        except Exception as e:
            print(f"\n❌ {test_name} failed with exception: {e}")
            results[test_name] = False

    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    print("\n" + "-" * 60)
    print(f"Total: {passed_count}/{total_count} tests passed")
    print("=" * 60)

    return all(results.values())


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
