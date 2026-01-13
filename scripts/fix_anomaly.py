#!/usr/bin/env python3
"""
AI-Powered Anomaly Fix Script
==============================

Generates fix plans for detected issues in specs and roadmap.
Supports both dry-run (planning) and apply modes.
"""

import json
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_dir))

from core.client import create_client
from status_report.models import FixPlan, PatchChange


def find_project_root() -> Path:
    """Find the project root by looking for .auto-claude directory."""
    cwd = Path.cwd()

    if (cwd / ".auto-claude").exists():
        return cwd

    for parent in cwd.parents:
        if (parent / ".auto-claude").exists():
            return parent

    return cwd


def generate_deterministic_fix(anomaly: dict, spec_dir: Path, project_dir: Path) -> FixPlan:
    """
    Generate a deterministic fix for common issues without AI.

    Args:
        anomaly: Issue dictionary with code, message, paths, etc.
        spec_dir: Path to spec directory
        project_dir: Path to project root

    Returns:
        FixPlan with changes
    """
    issue_code = anomaly.get("code", "")
    changes: list[PatchChange] = []

    if issue_code == "missing_file":
        # Create minimal file structure based on filename
        file_path = anomaly.get("paths", [""])[0]
        if file_path:
            rel_path = Path(file_path)
            if rel_path.name == "task_metadata.json":
                content = json.dumps(
                    {
                        "created_at": "",
                        "updated_at": "",
                        "status": "planned",
                    },
                    indent=2,
                )
                changes.append(PatchChange(path=file_path, action="create", content=content))
            elif rel_path.name == "requirements.json":
                content = json.dumps(
                    {
                        "user_requirements": [],
                        "acceptance_criteria": [],
                    },
                    indent=2,
                )
                changes.append(PatchChange(path=file_path, action="create", content=content))
            elif rel_path.name == "context.json":
                content = json.dumps(
                    {
                        "task_description": "",
                    },
                    indent=2,
                )
                changes.append(PatchChange(path=file_path, action="create", content=content))
            elif rel_path.name == "implementation_plan.json":
                content = json.dumps(
                    {
                        "feature": "",
                        "workflow_type": "feature",
                        "phases": [],
                    },
                    indent=2,
                )
                changes.append(PatchChange(path=file_path, action="create", content=content))

    elif issue_code in ("invalid_json", "duplicate_json_keys"):
        # For JSON errors, we'll need AI to fix them properly
        # This is a placeholder - AI will handle it
        pass

    return FixPlan(
        issue_codes=[issue_code],
        changes=changes,
        description=f"Deterministic fix for {issue_code}",
        dry_run=True,
    )


async def generate_ai_fix(
    anomaly: dict, spec_dir: Path, project_dir: Path, model: str = "claude-sonnet-4-20250514"
) -> FixPlan:
    """
    Generate a fix plan using Claude Agent SDK.

    Args:
        anomaly: Issue dictionary
        spec_dir: Path to spec directory
        project_dir: Path to project root
        model: Claude model to use

    Returns:
        FixPlan with AI-generated changes
    """
    # Create client for repair agent
    client = create_client(
        project_dir=project_dir,
        spec_dir=spec_dir,
        model=model,
        agent_type="coder",  # Use coder agent for repair tasks
    )

    # Build repair prompt
    prompt = f"""You are a repair agent fixing issues in Auto Claude spec files.

Issue to fix:
- Code: {anomaly.get('code')}
- Message: {anomaly.get('message')}
- Paths: {', '.join(anomaly.get('paths', []))}
- Suggested fix: {anomaly.get('suggestedFix', 'None')}

Spec directory: {spec_dir.relative_to(project_dir)}
Project directory: {project_dir}

Your task:
1. Analyze the issue
2. Generate a JSON patch plan with the following structure:
{{
  "issueCodes": ["<issue_code>"],
  "changes": [
    {{
      "path": "<relative_path_from_project_root>",
      "action": "create|update|delete",
      "content": "<file_content_for_create_or_update>"
    }}
  ],
  "description": "<human_readable_description>"
}}

Rules:
- Only modify files in `.auto-claude/specs/<spec_id>/` or `roadmap.json`
- For JSON fixes, preserve as much data as possible
- For missing files, create minimal valid structure
- For duplicate keys, remove duplicates keeping the last occurrence
- Output ONLY valid JSON, no markdown, no explanations
- Paths must be relative to project root
- Content must be valid JSON if the file is JSON

Generate the fix plan now:"""

    # Run agent session
    response_text = ""
    try:
        async with client:
            await client.query(prompt)
            async for msg in client.receive_response():
                msg_type = type(msg).__name__
                if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                    for block in msg.content:
                        block_type = type(block).__name__
                        if block_type == "TextBlock" and hasattr(block, "text"):
                            response_text += block.text
    except Exception as e:
        return FixPlan(
            issue_codes=[anomaly.get("code", "unknown")],
            changes=[],
            description=f"Failed to generate AI fix: {e}",
            dry_run=True,
        )

    # Parse JSON from response
    # Try to extract JSON from markdown code blocks if present
    if "```json" in response_text:
        json_start = response_text.find("```json") + 7
        json_end = response_text.find("```", json_start)
        response_text = response_text[json_start:json_end].strip()
    elif "```" in response_text:
        json_start = response_text.find("```") + 3
        json_end = response_text.find("```", json_start)
        response_text = response_text[json_start:json_end].strip()

    try:
        plan_data = json.loads(response_text)
    except json.JSONDecodeError as e:
        # Fallback: return error plan
        return FixPlan(
            issue_codes=[anomaly.get("code", "unknown")],
            changes=[],
            description=f"Failed to parse AI response: {e}",
            dry_run=True,
        )

    # Validate and convert to FixPlan
    changes = []
    for change_data in plan_data.get("changes", []):
        # Validate path is within allowed scope
        change_path = change_data.get("path", "")
        if not change_path.startswith(".auto-claude/"):
            continue  # Skip paths outside allowed scope

        changes.append(
            PatchChange(
                path=change_path,
                action=change_data.get("action", "update"),
                content=change_data.get("content"),
            )
        )

    return FixPlan(
        issue_codes=plan_data.get("issueCodes", [anomaly.get("code", "unknown")]),
        changes=changes,
        description=plan_data.get("description", "AI-generated fix"),
        dry_run=True,
    )


def apply_fix_plan(plan: FixPlan, project_dir: Path) -> None:
    """
    Apply a fix plan to the filesystem.

    Args:
        plan: FixPlan to apply
        project_dir: Path to project root
    """
    for change in plan.changes:
        file_path = project_dir / change.path

        if change.action == "create":
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if change.content:
                file_path.write_text(change.content, encoding=change.encoding)
        elif change.action == "update":
            if change.content:
                file_path.write_text(change.content, encoding=change.encoding)
        elif change.action == "delete":
            if file_path.exists():
                file_path.unlink()


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Fix anomalies in Auto Claude specs")
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Generate fix plan only (dry-run mode)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the fix plan (requires --plan to be run first or plan from stdin)",
    )

    args = parser.parse_args()

    # Read anomaly from stdin
    input_data = json.load(sys.stdin)
    anomaly = input_data.get("anomaly", {})
    spec_id = input_data.get("specId", "")
    project_path = input_data.get("projectPath", "")

    project_dir = Path(project_path) if project_path else find_project_root()
    spec_dir = project_dir / ".auto-claude" / "specs" / spec_id if spec_id else project_dir

    # Try deterministic fix first
    plan = generate_deterministic_fix(anomaly, spec_dir, project_dir)

    # If deterministic fix didn't work, use AI
    if not plan.changes and args.plan:
        plan = await generate_ai_fix(anomaly, spec_dir, project_dir)

    # Output plan
    if args.plan:
        print(json.dumps(plan.to_dict(), indent=2))
        return

    # Apply plan
    if args.apply:
        apply_fix_plan(plan, project_dir)
        print(json.dumps({"success": True, "applied_changes": len(plan.changes)}, indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
