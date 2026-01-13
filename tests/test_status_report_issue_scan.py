"""Unit tests for status report issue scanning."""

import json
import tempfile
from pathlib import Path

import pytest

# Add backend to path
import sys
backend_dir = Path(__file__).parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_dir))

from status_report.scan import scan_spec_issues, scan_roadmap_issues
from status_report.json_utils import read_json_strict, JSONReadError
from status_report.models import Issue


def test_scan_detects_missing_required_files(tmp_path: Path):
    """Test that missing required files are detected."""
    spec_dir = tmp_path / "001-test"
    spec_dir.mkdir()
    project_dir = tmp_path

    issues = scan_spec_issues(spec_dir, project_dir)

    # Should detect 4 missing files
    assert len(issues) == 4
    missing_file_codes = [issue.code for issue in issues]
    assert "missing_file" in missing_file_codes

    # Check that all required files are reported as missing
    reported_paths = []
    for issue in issues:
        if issue.code == "missing_file":
            reported_paths.extend(issue.paths)

    assert any("task_metadata.json" in path for path in reported_paths)
    assert any("requirements.json" in path for path in reported_paths)
    assert any("context.json" in path for path in reported_paths)
    assert any("implementation_plan.json" in path for path in reported_paths)


def test_scan_detects_duplicate_json_keys(tmp_path: Path):
    """Test that duplicate JSON keys are detected."""
    spec_dir = tmp_path / "001-test"
    spec_dir.mkdir()
    project_dir = tmp_path

    # Create a JSON file with duplicate keys
    json_file = spec_dir / "implementation_plan.json"
    json_file.write_text('{"feature": "test", "feature": "duplicate"}')

    issues = scan_spec_issues(spec_dir, project_dir)

    # Should detect duplicate keys
    duplicate_issues = [issue for issue in issues if issue.code == "duplicate_json_keys"]
    assert len(duplicate_issues) > 0


def test_scan_detects_invalid_json_with_location(tmp_path: Path):
    """Test that invalid JSON is detected with location information."""
    spec_dir = tmp_path / "001-test"
    spec_dir.mkdir()
    project_dir = tmp_path

    # Create invalid JSON
    json_file = spec_dir / "implementation_plan.json"
    json_file.write_text('{"feature": "test", invalid}')

    issues = scan_spec_issues(spec_dir, project_dir)

    # Should detect invalid JSON
    invalid_json_issues = [issue for issue in issues if issue.code == "invalid_json"]
    assert len(invalid_json_issues) > 0

    # Check that location details are included
    issue = invalid_json_issues[0]
    assert "details" in issue.to_dict()
    assert issue.details.get("line") is not None or issue.details.get("position") is not None


def test_scan_detects_structural_invalidity(tmp_path: Path):
    """Test that structural invalidities are detected."""
    spec_dir = tmp_path / "001-test"
    spec_dir.mkdir()
    project_dir = tmp_path

    # Create implementation_plan.json missing required fields
    json_file = spec_dir / "implementation_plan.json"
    json_file.write_text('{"feature": "test"}')  # Missing workflow_type and phases

    issues = scan_spec_issues(spec_dir, project_dir)

    # Should detect structural invalidity
    structural_issues = [issue for issue in issues if issue.code == "structural_invalidity"]
    assert len(structural_issues) > 0


def test_scan_detects_resume_blockers(tmp_path: Path):
    """Test that resume blockers are detected."""
    spec_dir = tmp_path / "001-test"
    spec_dir.mkdir()
    project_dir = tmp_path

    # Create implementation_plan.json without workflow_type
    json_file = spec_dir / "implementation_plan.json"
    json_file.write_text('{"feature": "test", "phases": []}')

    issues = scan_spec_issues(spec_dir, project_dir)

    # Should detect resume blocker
    blocker_issues = [issue for issue in issues if issue.code == "resume_blocker"]
    assert len(blocker_issues) > 0


def test_read_json_strict_detects_duplicate_keys(tmp_path: Path):
    """Test that read_json_strict detects duplicate keys."""
    json_file = tmp_path / "test.json"
    json_file.write_text('{"key": "value1", "key": "value2"}')

    with pytest.raises(JSONReadError) as exc_info:
        read_json_strict(json_file)

    assert "Duplicate keys" in str(exc_info.value)


def test_read_json_strict_detects_invalid_json(tmp_path: Path):
    """Test that read_json_strict detects invalid JSON."""
    json_file = tmp_path / "test.json"
    json_file.write_text('{"key": invalid}')

    with pytest.raises(JSONReadError) as exc_info:
        read_json_strict(json_file)

    assert "Invalid JSON" in str(exc_info.value)
    assert exc_info.value.line is not None or exc_info.value.position is not None


def test_scan_roadmap_issues_missing_spec(tmp_path: Path):
    """Test that roadmap issues for missing specs are detected."""
    project_dir = tmp_path
    auto_claude_dir = tmp_path / ".auto-claude"
    auto_claude_dir.mkdir()
    roadmap_path = auto_claude_dir / "roadmap.json"

    # Create roadmap referencing non-existent spec
    roadmap_data = {
        "features": [
            {
                "id": "feature-1",
                "linked_spec_id": "001-missing-spec"
            }
        ]
    }
    roadmap_path.write_text(json.dumps(roadmap_data))

    issues = scan_roadmap_issues(roadmap_path, project_dir)

    # Should detect missing spec
    missing_spec_issues = [
        issue for issue in issues
        if issue.code == "missing_spec_for_roadmap_feature"
    ]
    assert len(missing_spec_issues) > 0
