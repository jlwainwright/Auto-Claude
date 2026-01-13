"""
Subtask Management Tools
========================

Tools for managing subtask status in implementation_plan.json.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from claude_agent_sdk import tool

    SDK_TOOLS_AVAILABLE = True
except ImportError:
    SDK_TOOLS_AVAILABLE = False
    tool = None


def _load_require_review_before_coding(spec_dir: Path) -> bool:
    """
    Load requireReviewBeforeCoding from task_metadata.json (if present).

    This flag controls whether the plan is expected to pause in a "human_review"
    plan-approval stage before coding begins.
    """
    metadata_path = spec_dir / "task_metadata.json"
    if not metadata_path.exists():
        return False

    try:
        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)
        return bool(metadata.get("requireReviewBeforeCoding", False))
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def _iter_subtasks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Return a flat list of subtask dicts from the plan, supporting both:
      - phases[].subtasks (current)
      - phases[].chunks (legacy)
    """
    subtasks: list[dict[str, Any]] = []
    for phase in plan.get("phases", []) or []:
        if not isinstance(phase, dict):
            continue
        items = phase.get("subtasks") or phase.get("chunks") or []
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                subtasks.append(item)
    return subtasks


def _recompute_plan_status(
    plan: dict[str, Any],
    *,
    require_review_before_coding: bool,
) -> None:
    """
    Recompute plan.status / plan.planStatus from subtask state.

    This prevents stale status values (e.g., "human_review" from an earlier
    plan-review stage) from pinning tasks in Human Review while work is in progress.
    """
    # Preserve terminal statuses that are explicitly user-managed.
    existing_status = str(plan.get("status") or "")
    if existing_status in ("done", "pr_created", "error"):
        return

    subtasks = _iter_subtasks(plan)
    if not subtasks:
        # No subtasks: keep current status unless we can safely default.
        # If review-before-coding is enabled, the spec/plan may be awaiting approval.
        if require_review_before_coding and existing_status == "human_review":
            plan["status"] = "human_review"
            plan["planStatus"] = "review"
            return

        plan.setdefault("status", "backlog")
        plan.setdefault("planStatus", "pending")
        return

    statuses = [str(s.get("status") or "pending") for s in subtasks]

    total = len(statuses)
    completed = sum(1 for s in statuses if s == "completed")
    failed = sum(1 for s in statuses if s == "failed")
    in_progress = sum(1 for s in statuses if s == "in_progress")
    any_started = (completed + failed + in_progress) > 0
    all_completed = total > 0 and completed == total

    if failed > 0:
        plan["status"] = "human_review"
        plan["planStatus"] = "review"
        return

    if all_completed:
        # Default to ai_review when all subtasks are done; QA tools can promote to human_review.
        plan["status"] = "ai_review"
        plan["planStatus"] = "review"
        return

    if any_started:
        plan["status"] = "in_progress"
        plan["planStatus"] = "in_progress"
        return

    # All subtasks pending (plan created, no work started yet).
    if require_review_before_coding:
        plan["status"] = "human_review"
        plan["planStatus"] = "review"
        return

    plan["status"] = "backlog"
    plan["planStatus"] = "pending"


def create_subtask_tools(spec_dir: Path, project_dir: Path) -> list:
    """
    Create subtask management tools.

    Args:
        spec_dir: Path to the spec directory
        project_dir: Path to the project root

    Returns:
        List of subtask tool functions
    """
    if not SDK_TOOLS_AVAILABLE:
        return []

    tools = []

    # -------------------------------------------------------------------------
    # Tool: update_subtask_status
    # -------------------------------------------------------------------------
    @tool(
        "update_subtask_status",
        "Update the status of a subtask in implementation_plan.json. Use this when completing or starting a subtask.",
        {"subtask_id": str, "status": str, "notes": str},
    )
    async def update_subtask_status(args: dict[str, Any]) -> dict[str, Any]:
        """Update subtask status in the implementation plan."""
        subtask_id = args["subtask_id"]
        status = args["status"]
        notes = args.get("notes", "")

        valid_statuses = ["pending", "in_progress", "completed", "failed"]
        if status not in valid_statuses:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: Invalid status '{status}'. Must be one of: {valid_statuses}",
                    }
                ]
            }

        plan_file = spec_dir / "implementation_plan.json"
        if not plan_file.exists():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: implementation_plan.json not found",
                    }
                ]
            }

        try:
            with open(plan_file) as f:
                plan = json.load(f)

            # Find and update the subtask
            subtask_found = False
            for phase in plan.get("phases", []):
                for subtask in phase.get("subtasks", []):
                    if subtask.get("id") == subtask_id:
                        subtask["status"] = status
                        if notes:
                            subtask["notes"] = notes
                        subtask["updated_at"] = datetime.now(timezone.utc).isoformat()
                        subtask_found = True
                        break
                if subtask_found:
                    break

            if not subtask_found:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: Subtask '{subtask_id}' not found in implementation plan",
                        }
                    ]
                }

            # Update plan metadata
            now = datetime.now(timezone.utc).isoformat()
            plan["last_updated"] = now
            plan["updated_at"] = now

            # Keep overall plan status in sync with subtask progress.
            require_review_before_coding = _load_require_review_before_coding(spec_dir)
            _recompute_plan_status(
                plan,
                require_review_before_coding=require_review_before_coding,
            )

            with open(plan_file, "w") as f:
                json.dump(plan, f, indent=2)

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Successfully updated subtask '{subtask_id}' to status '{status}'",
                    }
                ]
            }

        except json.JSONDecodeError as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: Invalid JSON in implementation_plan.json: {e}",
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {"type": "text", "text": f"Error updating subtask status: {e}"}
                ]
            }

    tools.append(update_subtask_status)

    return tools
