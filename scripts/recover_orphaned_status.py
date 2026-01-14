#!/usr/bin/env python3
"""
recover_orphaned_status.py

Recovers from orphaned .auto-claude-status files when agents crash.
This handles the case where .auto-claude-status shows active=true but
no agent process is actually running.

Usage:
    python recover_orphaned_status.py <auto_claude_dir> <spec_id>

Output:
    JSON result with success status and actions taken
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _norm(s: Any) -> str:
    """Normalize a value to string."""
    if s is None:
        return ""
    return str(s).strip()


def _read_json_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read a JSON file and return parsed data or error."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data, None
        return None, "JSON root is not an object"
    except FileNotFoundError:
        return None, "file not found"
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"
    except Exception as e:
        return None, str(e)


def _write_json_file(path: Path, data: dict[str, Any]) -> tuple[bool, str | None]:
    """Write data to a JSON file."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True, None
    except Exception as e:
        return False, str(e)


def recover_orphaned_status(auto_claude_dir: Path, spec_id: str) -> dict[str, Any]:
    """
    Recover orphaned .auto-claude-status by:
    1. Setting active=false
    2. Setting state=failed
    3. Adding recovery note with timestamp
    4. Updating spec's implementation_plan.json with recovery note
    """
    actions_taken = []

    # Validate inputs
    auto_claude_dir = auto_claude_dir.resolve()
    if not auto_claude_dir.exists():
        return {
            "success": False,
            "error": f"Auto-claude directory does not exist: {auto_claude_dir}",
            "actions_taken": []
        }

    status_path = auto_claude_dir / ".auto-claude-status"
    if not status_path.exists():
        return {
            "success": False,
            "error": "No .auto-claude-status file found",
            "actions_taken": []
        }

    # Read current status
    status_data, err = _read_json_file(status_path)
    if status_data is None:
        return {
            "success": False,
            "error": f"Failed to read .auto-claude-status: {err}",
            "actions_taken": []
        }

    # Verify this is for the correct spec
    active_spec = _norm(status_data.get("spec", ""))
    if active_spec != spec_id:
        return {
            "success": False,
            "error": f"Status file is for spec '{active_spec}', not '{spec_id}'",
            "actions_taken": []
        }

    # Check if actually orphaned (active=true but state=building)
    is_active = status_data.get("active") is True
    current_state = status_data.get("state", "")
    if not is_active or current_state != "building":
        return {
            "success": False,
            "error": f"Status not orphaned: active={is_active}, state={current_state}",
            "actions_taken": []
        }

    # Update .auto-claude-status
    recovery_timestamp = datetime.now(timezone.utc).isoformat()
    status_data["active"] = False
    status_data["state"] = "failed"
    status_data["recovery_note"] = f"Recovered from orphaned status (agent crash) at {recovery_timestamp}"
    status_data["recovered_at"] = recovery_timestamp

    # Write updated status
    success, err = _write_json_file(status_path, status_data)
    if not success:
        return {
            "success": False,
            "error": f"Failed to write .auto-claude-status: {err}",
            "actions_taken": []
        }
    actions_taken.append("Set .auto-claude-status.active to false")
    actions_taken.append("Set .auto-claude-status.state to 'failed'")
    actions_taken.append("Added recovery note with timestamp")

    # Also update spec's implementation_plan.json if it exists
    spec_dir = auto_claude_dir / "specs" / spec_id
    plan_path = spec_dir / "implementation_plan.json"

    if plan_path.exists():
        plan_data, err = _read_json_file(plan_path)
        if plan_data is not None:
            # Add recovery note
            plan_data["recoveryNote"] = (
                f"Recovered from agent crash - .auto-claude-status was orphaned. "
                f"Recovered at {recovery_timestamp}"
            )
            plan_data["recoveredAt"] = recovery_timestamp

            # Write updated plan
            success, err = _write_json_file(plan_path, plan_data)
            if success:
                actions_taken.append("Added recovery note to implementation_plan.json")
            else:
                actions_taken.append(f"Warning: Failed to update implementation_plan.json: {err}")

    return {
        "success": True,
        "actions_taken": actions_taken,
        "summary": f"Recovered orphaned status for spec '{spec_id}'"
    }


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Recover from orphaned .auto-claude-status files"
    )
    parser.add_argument(
        "auto_claude_dir",
        type=str,
        help="Path to the .auto-claude directory"
    )
    parser.add_argument(
        "spec_id",
        type=str,
        help="Spec ID to recover"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON"
    )

    args = parser.parse_args()

    # Run recovery
    auto_claude_dir = Path(args.auto_claude_dir).expanduser().resolve()
    result = recover_orphaned_status(auto_claude_dir, args.spec_id)

    # Output result
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            print("Recovery successful!")
            for action in result.get("actions_taken", []):
                print(f"  - {action}")
            print(f"\n{result.get('summary', '')}")
        else:
            print(f"Recovery failed: {result.get('error', 'Unknown error')}")
            return 1

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
