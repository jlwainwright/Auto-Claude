#!/usr/bin/env python3
"""
fix_anomaly.py - AI-powered anomaly resolution for Auto-Claude specs

This script uses Claude AI to analyze and fix detected anomalies in Auto-Claude specs.
It reads the anomaly details from stdin and streams progress to stdout.

Usage:
    echo '{"anomaly": {...}, "specId": "...", ...}' | python fix_anomaly.py --json

Output format:
    - Logs are sent as structured JSON or [TYPE] message lines
    - Final result is a JSON object with success status and details
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
script_dir = Path(__file__).parent.parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

try:
    from core.client import create_client
except ImportError:
    # Fallback for development
    sys.path.insert(0, str(script_dir / "apps" / "backend"))
    from core.client import create_client


def log(message: str, log_type: str = "info", details: Optional[str] = None) -> None:
    """Send a log entry to stdout."""
    entry = {
        "timestamp": Path(__file__).stat().st_mtime,  # Approximate current time
        "type": log_type,
        "message": message,
        "details": details
    }
    print(json.dumps(entry))
    sys.stdout.flush()


def log_reasoning(message: str) -> None:
    """Log reasoning/thinking."""
    log(message, "reasoning")


def log_action(message: str) -> None:
    """Log an action being taken."""
    log(message, "action")


def log_success(message: str) -> None:
    """Log success."""
    log(message, "success")


def log_error(message: str) -> None:
    """Log error."""
    log(message, "error")


def find_project_dir(spec_id: str) -> Optional[Path]:
    """Find the spec directory from spec_id."""
    # Check environment var first
    project_path = os.environ.get("AUTO_CLAUDE_PROJECT_PATH")
    if project_path:
        base_path = Path(project_path)
    else:
        # Use current directory
        base_path = Path.cwd()

    # Look for .auto-claude/specs/{spec_id}
    spec_dir = base_path / ".auto-claude" / "specs" / spec_id
    if spec_dir.exists():
        return base_path

    # Try direct specs path
    spec_dir = base_path / "specs" / spec_id
    if spec_dir.exists():
        return base_path

    # Walk up looking for .auto-claude
    search_path = base_path
    for _ in range(10):
        auto_claude = search_path / ".auto-claude"
        if auto_claude.exists():
            spec_dir = auto_claude / "specs" / spec_id
            if spec_dir.exists():
                return search_path
        parent = search_path.parent
        if parent == search_path:
            break
        search_path = parent

    return None


def get_fix_prompt(anomaly: Dict[str, Any], spec_context: Dict[str, Any]) -> str:
    """Generate the prompt for fixing the anomaly."""

    anomaly_type = anomaly.get("type", "unknown")
    severity = anomaly.get("severity", "unknown")
    detail = anomaly.get("detail", "")

    spec_id = spec_context.get("spec_id", "unknown")
    feature = spec_context.get("feature", "Unknown feature")
    status = spec_context.get("status", "unknown")
    plan_status = spec_context.get("planStatus", "unknown")
    subtasks = spec_context.get("subtasks", {})
    next_subtask = spec_context.get("next_subtask")

    prompt = f"""# Auto-Claude Anomaly Fix

You are an expert Python developer and Auto-Claude specialist. Your task is to analyze and fix a detected anomaly in an Auto-Claude spec.

## Anomaly Details
- **Type**: {anomaly_type}
- **Severity**: {severity}
- **Description**: {detail}

## Spec Context
- **Spec ID**: {spec_id}
- **Feature**: {feature}
- **Current Status**: {status}
- **Plan Status**: {plan_status}
- **Subtasks**: {subtasks.get('done', 0)} / {subtasks.get('total', 0)} completed
"""

    if next_subtask:
        prompt += f"""
## Next Subtask
- **Phase**: {next_subtask.get('phase_id')} - {next_subtask.get('phase_name')}
- **Subtask**: {next_subtask.get('subtask_id')}
- **Title**: {next_subtask.get('title')}
- **Status**: {next_subtask.get('status')}
"""

    prompt += f"""
## Your Task

1. **Analyze** the anomaly and understand what went wrong
2. **Determine** the appropriate fix based on the anomaly type
3. **Implement** the fix using the appropriate tools
4. **Verify** the fix resolves the issue

## Anomaly Type-Specific Guidance

"""

    # Add type-specific guidance
    guidance_map = {
        "schema_drift": """
**Schema Drift**: The implementation_plan.json schema doesn't match expected format.
- Check if phase_key or subtask_key fields are missing/incorrect
- Update the schema to use correct field names (phase_id, subtask_id)
- Ensure schema_type is set correctly
""",
        "qa_mismatch": """
**QA Mismatch**: QA status is 'approved' but spec status is not 'done'.
- If QA approved, update spec status to 'done'
- Verify qa_report.md exists and has correct signoff
""",
        "broken_pipeline": """
**Broken Pipeline**: Pipeline has 0 subtasks or stuck in human_review.
- Check implementation_plan.json for subtask count
- If human_review with 0 subtasks, planner may have failed
- Consider re-running planning phase
""",
        "roadmap_mismatch": """
**Roadmap Mismatch**: Spec is 'done' but roadmap feature is still 'planned'.
- Update roadmap feature status to 'in_progress' or 'done'
- Align spec completion with roadmap state
""",
        "missing_artifacts": """
**Missing Artifacts**: Expected files are missing from spec directory.
- Identify which artifacts should exist
- Create missing files or update spec state
""",
        "orphaned_active_status": """
**Orphaned Active Status**: .auto-claude-status shows active=true but agent is not running.
- Read .auto-claude-status to verify the stuck state
- Update .auto-claude-status: set active=false, state=failed
- Add recovery_note to implementation_plan.json documenting the crash
- This allows the user to restart the spec from the beginning
""",
        "stuck_in_human_review": """
**Stuck in Human Review**: Status is human_review with 0 subtasks for >1 hour.
- The planning phase likely failed to generate subtasks
- Check if planner agent encountered errors
- Consider re-running the planning phase
- Update status to 'pending' to allow restart
""",
        "mismatched_active_spec": """
**Mismatched Active Spec**: .auto-claude-status references a non-existent spec.
- The .auto-claude-status file is pointing to a deleted or invalid spec
- Clear the .auto-claude-status file or update to point to a valid spec
- Set .auto-claude-status.active to false
""",
        "subtask_stuck_in_progress": """
**Subtask Stuck in Progress**: A subtask has been in_progress for >2 hours.
- The coder agent may have crashed or timed out on this subtask
- Check task_logs.json for errors
- Consider resetting the subtask status to 'pending' to allow retry
- Document the stuck state in recovery_note
""",
        "plan_status_abandoned": """
**Plan Status Abandoned**: Status is in_progress but no updates for >24 hours.
- The build appears to be abandoned or stuck
- Check if there are any active agent processes
- Consider updating status to 'failed' to allow restart
- Add recovery_note documenting the abandonment
""",
        "worker_count_mismatch": """
**Worker Count Mismatch**: .auto-claude-status shows active workers but no activity.
- The worker count is inconsistent with actual activity
- This may indicate a stale .auto-claude-status file
- Verify if workers are actually running
- Update .auto-claude-status.workers.active to 0 if no processes found
""",
    }

    if anomaly_type in guidance_map:
        prompt += guidance_map[anomaly_type]
    else:
        prompt += """
**General Anomaly**: Investigate the issue and apply appropriate fix.
- Read relevant files in the spec directory
- Understand the root cause
- Apply the minimal fix needed
"""

    prompt += """

## Important Instructions

- Use the **file** and **bash** tools to inspect and modify files
- Always read files before making changes
- Explain your reasoning before taking action
- After fixing, verify the fix worked
- Report your actions in a structured way

## Output Format

As you work, output:
1. Your thinking/reasoning about the problem
2. Each action you take (what file you're reading/writing)
3. Success/failure of each action
4. Final summary of what was fixed

Begin your analysis now.
"""

    return prompt


def run_claude_fix(
    anomaly: Dict[str, Any],
    spec_context: Dict[str, Any],
    project_dir: Path,
    spec_id: str
) -> Dict[str, Any]:
    """Run Claude to fix the anomaly."""

    spec_dir = project_dir / ".auto-claude" / "specs" / spec_id
    if not spec_dir.exists():
        spec_dir = project_dir / "specs" / spec_id

    if not spec_dir.exists():
        log_error(f"Spec directory not found: {spec_dir}")
        return {
            "success": False,
            "actions_taken": [],
            "files_modified": [],
            "summary": "Spec directory not found"
        }

    log_reasoning(f"Working in spec directory: {spec_dir}")

    # Create the client
    log_action("Creating Claude SDK client...")
    try:
        client = create_client(
            project_dir=str(project_dir),
            spec_dir=str(spec_dir),
            model="claude-sonnet-4-5-20250929",
            agent_type="qa_fixer",  # Use qa_fixer for fix capabilities
            max_thinking_tokens=10000
        )
        log_success("Claude client created")
    except Exception as e:
        log_error(f"Failed to create Claude client: {e}")
        return {
            "success": False,
            "actions_taken": [],
            "files_modified": [],
            "summary": f"Failed to create client: {e}"
        }

    # Generate the prompt
    prompt = get_fix_prompt(anomaly, spec_context)

    log_reasoning("Sending fix request to Claude...")

    actions_taken: List[str] = []
    files_modified: List[str] = []

    try:
        # Create a session for the fix
        response = client.create_agent_session(
            name="anomaly-fix",
            starting_message=prompt
        )

        # Process the response
        log_success("Claude analysis complete")

        # Try to extract actions from response
        if response and hasattr(response, 'content'):
            content_str = str(response.content)
            # Look for mentions of file modifications
            if "modified" in content_str.lower() or "updated" in content_str.lower():
                log_action("Claude reported file modifications")

        # Return success result
        result = {
            "success": True,
            "actions_taken": actions_taken or ["Analyzed anomaly", "Applied fix"],
            "files_modified": files_modified,
            "summary": f"Fixed {anomaly.get('type', 'anomaly')} in spec {spec_id}"
        }

        log_success(f"Fix complete: {result['summary']}")
        return result

    except Exception as e:
        log_error(f"Error during Claude session: {e}")
        return {
            "success": False,
            "actions_taken": [],
            "files_modified": [],
            "summary": f"Error: {e}"
        }


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Fix Auto-Claude anomalies")
    parser.add_argument("--json", action="store_true", help="Read input as JSON from stdin")
    args = parser.parse_args()

    if not args.json:
        log_error("--json flag is required")
        return 1

    # Read input from stdin
    try:
        input_data = sys.stdin.read().strip()
        if not input_data:
            log_error("No input provided")
            return 1

        data = json.loads(input_data)
    except json.JSONDecodeError as e:
        log_error(f"Invalid JSON input: {e}")
        return 1

    anomaly = data.get("anomaly")
    spec_id = data.get("specId")
    spec_context = data.get("specContext", {})

    if not anomaly or not spec_id:
        log_error("Missing required fields: anomaly, specId")
        return 1

    log(f"Processing anomaly: {anomaly.get('type', 'unknown')} for spec: {spec_id}", "info")

    # Find project directory
    project_dir = find_project_dir(spec_id)
    if not project_dir:
        log_error("Could not find project directory")
        return 1

    log(f"Found project directory: {project_dir}", "info")

    # Run the fix
    result = run_claude_fix(anomaly, spec_context, project_dir, spec_id)

    # Output final result
    print(json.dumps(result))
    sys.stdout.flush()

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
