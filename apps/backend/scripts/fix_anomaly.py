#!/usr/bin/env python3
"""
AI-Powered Anomaly Fix Script (backend-bundled entrypoint)
=========================================================

This file exists so the Electron app can run anomaly fix planning/apply from the
bundled backend source path (apps/backend/).

The repo also contains a root-level script at `scripts/fix_anomaly.py` for CLI usage;
keep both in sync.
"""

import json
import sys
from pathlib import Path

# Ensure backend imports resolve when executed as a script
backend_dir = Path(__file__).resolve().parent.parent
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
    """
    issue_code = anomaly.get("code", "")
    changes: list[PatchChange] = []

    if issue_code == "missing_file":
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
    """
    client = create_client(
        project_dir=project_dir,
        spec_dir=spec_dir,
        model=model,
        agent_type="coder",
    )

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

    # Extract JSON from code fences if present
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
        return FixPlan(
            issue_codes=[anomaly.get("code", "unknown")],
            changes=[],
            description=f"Failed to parse AI response: {e}",
            dry_run=True,
        )

    changes = []
    for change_data in plan_data.get("changes", []):
        change_path = change_data.get("path", "")
        if not change_path.startswith(".auto-claude/"):
            continue

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
    """Apply a fix plan to the filesystem."""
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


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Fix anomalies in Auto Claude specs")
    parser.add_argument("--plan", action="store_true", help="Generate fix plan only (dry-run mode)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the fix plan (requires --plan to be run first or plan from stdin)",
    )

    args = parser.parse_args()

    input_data = json.load(sys.stdin)
    anomaly = input_data.get("anomaly", {})
    spec_id = input_data.get("specId", "")
    project_path = input_data.get("projectPath", "")

    project_dir = Path(project_path) if project_path else find_project_root()
    spec_dir = project_dir / ".auto-claude" / "specs" / spec_id if spec_id else project_dir

    plan = generate_deterministic_fix(anomaly, spec_dir, project_dir)

    if not plan.changes and args.plan:
        plan = await generate_ai_fix(anomaly, spec_dir, project_dir)

    if args.plan:
        print(json.dumps(plan.to_dict(), indent=2))
        return

    if args.apply:
        apply_fix_plan(plan, project_dir)
        print(json.dumps({"success": True, "applied_changes": len(plan.changes)}, indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

