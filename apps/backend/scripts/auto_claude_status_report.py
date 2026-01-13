#!/usr/bin/env python3
"""
Auto Claude Status Report Generator (backend-bundled entrypoint)
===============================================================

This file exists so the Electron app can run the status report generator from the
bundled backend source path (apps/backend/).

The repo also contains a root-level script at `scripts/auto_claude_status_report.py`
for CLI usage; keep both in sync.
"""

import json
import sys
from pathlib import Path

# Ensure backend imports resolve when executed as a script
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

try:
    from status_report.scan import scan_roadmap_issues, scan_spec_issues
except ImportError:
    # Fallback if status_report module not available (shouldn't happen in normal runs)
    def scan_spec_issues(spec_dir: Path, project_dir: Path) -> list:
        return []

    def scan_roadmap_issues(roadmap_path: Path, project_dir: Path) -> list:
        return []


def find_project_root() -> Path:
    """Find the project root by looking for .auto-claude directory."""
    cwd = Path.cwd()

    if (cwd / ".auto-claude").exists():
        return cwd

    for parent in cwd.parents:
        if (parent / ".auto-claude").exists():
            return parent

    return cwd


def generate_status_report(project_dir: Path) -> dict:
    """Generate comprehensive status report."""
    auto_claude_dir = project_dir / ".auto-claude"
    specs_dir = auto_claude_dir / "specs"
    roadmap_path = auto_claude_dir / "roadmap.json"

    report: dict = {
        "summary": {
            "total_specs": 0,
            "total_issues": 0,
            "issue_severity_counts": {
                "error": 0,
                "warning": 0,
                "info": 0,
            },
        },
        "specs": [],
        "roadmap": {
            "exists": roadmap_path.exists(),
            "issues": [],
        },
    }

    # Scan roadmap issues
    if roadmap_path.exists():
        roadmap_issues = scan_roadmap_issues(roadmap_path, project_dir)
        report["roadmap"]["issues"] = [issue.to_dict() for issue in roadmap_issues]
        for issue in roadmap_issues:
            report["summary"]["total_issues"] += 1
            if issue.severity in report["summary"]["issue_severity_counts"]:
                report["summary"]["issue_severity_counts"][issue.severity] += 1

    # Scan each spec directory
    if specs_dir.exists():
        spec_dirs = [d for d in specs_dir.iterdir() if d.is_dir()]
        report["summary"]["total_specs"] = len(spec_dirs)

        for spec_dir in spec_dirs:
            spec_id = spec_dir.name
            issues = scan_spec_issues(spec_dir, project_dir)

            spec_row = {
                "id": spec_id,
                "path": str(spec_dir.relative_to(project_dir)),
                "issues": [issue.to_dict() for issue in issues],
                "issue_count": len(issues),
            }

            report["summary"]["total_issues"] += len(issues)
            for issue in issues:
                if issue.severity in report["summary"]["issue_severity_counts"]:
                    report["summary"]["issue_severity_counts"][issue.severity] += 1

            report["specs"].append(spec_row)

    return report


def main() -> None:
    project_dir = find_project_root()
    report = generate_status_report(project_dir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

