"""Scan spec directories and roadmap for issues."""

import json
from pathlib import Path
from typing import Any

from .json_utils import JSONReadError, read_json_strict
from .models import Issue

# NOTE: We intentionally inline the minimal schema requirements here to avoid
# importing the full `spec` package (which pulls in optional provider deps).
IMPLEMENTATION_PLAN_REQUIRED_FIELDS = ["feature", "workflow_type", "phases"]
CONTEXT_REQUIRED_FIELDS = ["task_description"]


def scan_spec_issues(spec_dir: Path, project_dir: Path) -> list[Issue]:
    """
    Scan a spec directory for issues.

    Args:
        spec_dir: Path to spec directory (e.g., .auto-claude/specs/001-name/)
        project_dir: Path to project root

    Returns:
        List of detected issues
    """
    issues: list[Issue] = []

    # Required files to check
    required_files = {
        "task_metadata.json": "task_metadata",
        "requirements.json": "requirements",
        "context.json": "context",
        "implementation_plan.json": "implementation_plan",
    }

    # Check for missing files
    for filename, file_type in required_files.items():
        file_path = spec_dir / filename
        if not file_path.exists():
            issues.append(
                Issue(
                    severity="error",
                    code="missing_file",
                    message=f"Missing required file: {filename}",
                    paths=[str(file_path.relative_to(project_dir))],
                    suggested_fix=f"Create {filename} with appropriate structure",
                )
            )

    # Check JSON validity for existing files
    for filename, file_type in required_files.items():
        file_path = spec_dir / filename
        if not file_path.exists():
            continue

        try:
            data, metadata = read_json_strict(file_path)
            if metadata.get("has_duplicate_keys"):
                issues.append(
                    Issue(
                        severity="error",
                        code="duplicate_json_keys",
                        message=f"Duplicate keys found in {filename}",
                        paths=[str(file_path.relative_to(project_dir))],
                        suggested_fix="Remove duplicate keys and ensure unique JSON object keys",
                    )
                )
                continue  # Skip structural checks if JSON is invalid

            # Structural validation
            if file_type == "implementation_plan":
                _validate_implementation_plan(data, file_path, project_dir, issues)
            elif file_type == "context":
                _validate_context(data, file_path, project_dir, issues)

        except JSONReadError as e:
            # Check if this is a duplicate key error
            if "Duplicate keys found" in str(e):
                issues.append(
                    Issue(
                        severity="error",
                        code="duplicate_json_keys",
                        message=f"Duplicate keys found in {filename}",
                        paths=[str(file_path.relative_to(project_dir))],
                        suggested_fix="Remove duplicate keys and ensure unique JSON object keys",
                    )
                )
            else:
                issues.append(
                    Issue(
                        severity="error",
                        code="invalid_json",
                        message=f"Invalid JSON in {filename}: {str(e)}",
                        paths=[str(file_path.relative_to(project_dir))],
                        suggested_fix="Fix JSON syntax errors",
                        details={
                            "line": e.line,
                            "column": e.column,
                            "position": e.position,
                        },
                    )
                )
        except Exception as e:
            issues.append(
                Issue(
                    severity="error",
                    code="unknown_error",
                    message=f"Unexpected error reading {filename}: {str(e)}",
                    paths=[str(file_path.relative_to(project_dir))],
                    details={"exception_type": type(e).__name__},
                )
            )

    # Check for resume blockers
    impl_plan_path = spec_dir / "implementation_plan.json"
    if impl_plan_path.exists():
        try:
            data, _ = read_json_strict(impl_plan_path)
            if isinstance(data, dict):
                if "workflow_type" not in data:
                    issues.append(
                        Issue(
                            severity="error",
                            code="resume_blocker",
                            message="Missing 'workflow_type' in implementation_plan.json",
                            paths=[str(impl_plan_path.relative_to(project_dir))],
                            suggested_fix="Add 'workflow_type' field to implementation_plan.json",
                        )
                    )
                if "phases" not in data or not data.get("phases"):
                    issues.append(
                        Issue(
                            severity="error",
                            code="resume_blocker",
                            message="Missing or empty 'phases' in implementation_plan.json",
                            paths=[str(impl_plan_path.relative_to(project_dir))],
                            suggested_fix="Add 'phases' array with at least one phase to implementation_plan.json",
                        )
                    )
        except (JSONReadError, Exception):
            pass  # Already reported as invalid_json

    return issues


def _validate_implementation_plan(
    data: Any, file_path: Path, project_dir: Path, issues: list[Issue]
) -> None:
    """Validate implementation_plan.json structure."""
    if not isinstance(data, dict):
        issues.append(
            Issue(
                severity="error",
                code="structural_invalidity",
                message="implementation_plan.json must be a JSON object",
                paths=[str(file_path.relative_to(project_dir))],
            )
        )
        return

    # Check required fields
    for field in IMPLEMENTATION_PLAN_REQUIRED_FIELDS:
        if field not in data:
            issues.append(
                Issue(
                    severity="error",
                    code="structural_invalidity",
                    message=f"Missing required field: {field}",
                    paths=[str(file_path.relative_to(project_dir))],
                    suggested_fix=f"Add '{field}' field to implementation_plan.json",
                )
            )

    # Validate phases structure
    if "phases" in data:
        phases = data["phases"]
        if not isinstance(phases, list):
            issues.append(
                Issue(
                    severity="error",
                    code="structural_invalidity",
                    message="'phases' must be an array",
                    paths=[str(file_path.relative_to(project_dir))],
                )
            )
        elif len(phases) == 0:
            issues.append(
                Issue(
                    severity="error",
                    code="structural_invalidity",
                    message="'phases' array is empty",
                    paths=[str(file_path.relative_to(project_dir))],
                )
            )
        else:
            # Check each phase has subtasks
            for i, phase in enumerate(phases):
                if not isinstance(phase, dict):
                    continue
                if "subtasks" not in phase or not phase.get("subtasks"):
                    issues.append(
                        Issue(
                            severity="warning",
                            code="structural_invalidity",
                            message=f"Phase {i+1} has no subtasks",
                            paths=[str(file_path.relative_to(project_dir))],
                        )
                    )


def _validate_context(data: Any, file_path: Path, project_dir: Path, issues: list[Issue]) -> None:
    """Validate context.json structure."""
    if not isinstance(data, dict):
        issues.append(
            Issue(
                severity="error",
                code="structural_invalidity",
                message="context.json must be a JSON object",
                paths=[str(file_path.relative_to(project_dir))],
            )
        )
        return

    # Check required fields
    for field in CONTEXT_REQUIRED_FIELDS:
        if field not in data:
            issues.append(
                Issue(
                    severity="error",
                    code="structural_invalidity",
                    message=f"Missing required field: {field}",
                    paths=[str(file_path.relative_to(project_dir))],
                    suggested_fix=f"Add '{field}' field to context.json",
                )
            )


def scan_roadmap_issues(roadmap_path: Path, project_dir: Path) -> list[Issue]:
    """
    Scan roadmap.json for issues.

    Args:
        roadmap_path: Path to roadmap.json
        project_dir: Path to project root

    Returns:
        List of detected issues
    """
    issues: list[Issue] = []

    if not roadmap_path.exists():
        return issues

    try:
        data, metadata = read_json_strict(roadmap_path)
        if metadata.get("has_duplicate_keys"):
            issues.append(
                Issue(
                    severity="error",
                    code="duplicate_json_keys",
                    message="Duplicate keys found in roadmap.json",
                    paths=[str(roadmap_path.relative_to(project_dir))],
                    suggested_fix="Remove duplicate keys and ensure unique JSON object keys",
                )
            )
            return issues

        # Check for missing specs referenced in roadmap
        if isinstance(data, dict) and "features" in data:
            features = data["features"]
            if isinstance(features, list):
                specs_dir = project_dir / ".auto-claude" / "specs"
                for feature in features:
                    if isinstance(feature, dict) and "linked_spec_id" in feature:
                        spec_id = feature["linked_spec_id"]
                        if spec_id:
                            spec_dir = specs_dir / spec_id
                            if not spec_dir.exists():
                                issues.append(
                                    Issue(
                                        severity="warning",
                                        code="missing_spec_for_roadmap_feature",
                                        message=f"Roadmap feature references missing spec: {spec_id}",
                                        paths=[
                                            str(roadmap_path.relative_to(project_dir)),
                                            str(spec_dir.relative_to(project_dir)),
                                        ],
                                        suggested_fix=f"Create spec directory {spec_id} or remove linked_spec_id from roadmap feature",
                                    )
                                )

    except JSONReadError as e:
        issues.append(
            Issue(
                severity="error",
                code="invalid_json",
                message=f"Invalid JSON in roadmap.json: {str(e)}",
                paths=[str(roadmap_path.relative_to(project_dir))],
                suggested_fix="Fix JSON syntax errors",
                details={
                    "line": e.line,
                    "column": e.column,
                    "position": e.position,
                },
            )
        )
    except Exception as e:
        issues.append(
            Issue(
                severity="error",
                code="unknown_error",
                message=f"Unexpected error reading roadmap.json: {str(e)}",
                paths=[str(roadmap_path.relative_to(project_dir))],
                details={"exception_type": type(e).__name__},
            )
        )

    return issues
