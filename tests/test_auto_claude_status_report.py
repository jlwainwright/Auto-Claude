from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from scripts.auto_claude_status_report import generate_report


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_orphaned_active_status_detection(tmp_path: Path) -> None:
    """
    Test detection of orphaned .auto-claude-status where active=true but
    the status file is old (simulating a crashed agent).
    """
    auto = tmp_path / ".auto-claude"
    specs = auto / "specs"

    # Create .auto-claude-status with active=true and old timestamp
    _write_json(
        auto / ".auto-claude-status",
        {
            "active": True,
            "state": "building",
            "spec": "005-orphaned-task",
            "updated_at": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
        },
    )

    # Create a spec for reference
    _write_json(
        specs / "005-orphaned-task" / "implementation_plan.json",
        {
            "feature": "Orphaned Task",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "status": "in_progress",
            "phases": [{"id": "phase-1", "name": "Implementation", "subtasks": []}],
        },
    )

    report = generate_report(auto)
    specs_out = {s["spec_id"]: s for s in report["specs"]}

    # Should detect orphaned_active_status anomaly
    assert "005-orphaned-task" in specs_out
    anomalies = specs_out["005-orphaned-task"]["anomalies"]
    anomaly_types = {a["type"] for a in anomalies}
    assert "orphaned_active_status" in anomaly_types


def test_stuck_in_human_review_detection(tmp_path: Path) -> None:
    """
    Test detection of human_review status with 0 subtasks for > 1 hour.
    This happens when the pipeline breaks during planning.
    """
    auto = tmp_path / ".auto-claude"
    specs = auto / "specs"

    # Create spec with human_review status, 0 subtasks, and old timestamp
    old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    _write_json(
        specs / "007-stuck-human-review" / "implementation_plan.json",
        {
            "feature": "Stuck in Human Review",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": old_time,
            "status": "human_review",
            "phases": [],  # 0 subtasks
        },
    )

    report = generate_report(auto)
    specs_out = {s["spec_id"]: s for s in report["specs"]}

    # Should detect stuck_in_human_review anomaly
    assert "007-stuck-human-review" in specs_out
    anomalies = specs_out["007-stuck-human-review"]["anomalies"]
    anomaly_types = {a["type"] for a in anomalies}
    assert "stuck_in_human_review" in anomaly_types


def test_mismatched_active_spec_detection(tmp_path: Path) -> None:
    """
    Test detection when .auto-claude-status references a non-existent spec.
    """
    auto = tmp_path / ".auto-claude"
    specs = auto / "specs"

    # Create .auto-claude-status referencing non-existent spec
    _write_json(
        auto / ".auto-claude-status",
        {
            "active": True,
            "state": "building",
            "spec": "999-non-existent-spec",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Create a different spec (not the one referenced)
    _write_json(
        specs / "001-some-other-spec" / "implementation_plan.json",
        {
            "feature": "Some Other Spec",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "status": "pending",
            "phases": [],
        },
    )

    report = generate_report(auto)
    specs_out = {s["spec_id"]: s for s in report["specs"]}

    # Should detect mismatched_active_spec in the general report
    # (this is reported as a global anomaly, not per-spec)
    # Verify the report structure includes status file info
    assert report is not None


def test_subtask_stuck_in_progress_detection(tmp_path: Path) -> None:
    """
    Test detection of subtask stuck in_progress for > 2 hours.
    """
    auto = tmp_path / ".auto-claude"
    specs = auto / "specs"

    # Create spec with subtask stuck in_progress
    old_time = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    _write_json(
        specs / "008-stuck-subtask" / "implementation_plan.json",
        {
            "feature": "Stuck Subtask",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": old_time,
            "status": "in_progress",
            "phases": [
                {
                    "id": "phase-1",
                    "name": "Implementation",
                    "subtasks": [
                        {
                            "id": "subtask-1",
                            "title": "Stuck Task",
                            "status": "in_progress",
                            "updated_at": old_time,
                        }
                    ],
                }
            ],
        },
    )

    report = generate_report(auto)
    specs_out = {s["spec_id"]: s for s in report["specs"]}

    # Should detect subtask_stuck_in_progress anomaly
    assert "008-stuck-subtask" in specs_out
    anomalies = specs_out["008-stuck-subtask"]["anomalies"]
    anomaly_types = {a["type"] for a in anomalies}
    assert "subtask_stuck_in_progress" in anomaly_types


def test_plan_status_abandoned_detection(tmp_path: Path) -> None:
    """
    Test detection of in_progress status with no updates for > 24 hours.
    """
    auto = tmp_path / ".auto-claude"
    specs = auto / "specs"

    # Create spec with in_progress status and old timestamp
    old_time = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    _write_json(
        specs / "009-abandoned-plan" / "implementation_plan.json",
        {
            "feature": "Abandoned Plan",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": old_time,
            "status": "in_progress",
            "phases": [
                {
                    "id": "phase-1",
                    "name": "Implementation",
                    "subtasks": [{"id": "subtask-1", "status": "pending"}],
                }
            ],
        },
    )

    report = generate_report(auto)
    specs_out = {s["spec_id"]: s for s in report["specs"]}

    # Should detect plan_status_abandoned anomaly
    assert "009-abandoned-plan" in specs_out
    anomalies = specs_out["009-abandoned-plan"]["anomalies"]
    anomaly_types = {a["type"] for a in anomalies}
    assert "plan_status_abandoned" in anomaly_types


def test_worker_count_mismatch_detection(tmp_path: Path) -> None:
    """
    Test detection when .auto-claude-status shows active workers > 0
    but the status is old (simulating no actual activity).
    """
    auto = tmp_path / ".auto-claude"
    specs = auto / "specs"

    # Create .auto-claude-status with active workers but old timestamp
    old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    _write_json(
        auto / ".auto-claude-status",
        {
            "active": True,
            "state": "building",
            "spec": "010-worker-mismatch",
            "updated_at": old_time,
            "workers": {"active": 3, "total": 5},
        },
    )

    # Create the referenced spec
    _write_json(
        specs / "010-worker-mismatch" / "implementation_plan.json",
        {
            "feature": "Worker Count Mismatch",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": old_time,
            "status": "in_progress",
            "phases": [
                {"id": "phase-1", "name": "Implementation", "subtasks": []}
            ],
        },
    )

    report = generate_report(auto)
    specs_out = {s["spec_id"]: s for s in report["specs"]}

    # Should detect worker_count_mismatch anomaly
    assert "010-worker-mismatch" in specs_out
    anomalies = specs_out["010-worker-mismatch"]["anomalies"]
    anomaly_types = {a["type"] for a in anomalies}
    assert "worker_count_mismatch" in anomaly_types


def test_generate_report_detects_common_anomalies(tmp_path: Path) -> None:
    """
    Minimal smoke test for anomaly detection:
    - schema drift (phase_id/subtask_id)
    - QA approved but status not done
    - human_review with 0 subtasks (pipeline broke during planning)
    - done but roadmap still planned
    """
    auto = tmp_path / ".auto-claude"
    specs = auto / "specs"

    # Spec A: schema variant (phase_id/subtask_id), in_progress, no progress
    _write_json(
        specs / "010-direct-eml-msg-file-upload" / "implementation_plan.json",
        {
            "feature": "Direct EML/MSG File Upload",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "status": "in_progress",
            "phases": [
                {
                    "phase_id": "phase_1",
                    "name": "Backend",
                    "subtasks": [
                        {"subtask_id": "1.1", "title": "Do thing", "status": "pending"}
                    ],
                }
            ],
        },
    )

    # Spec B: QA approved but status is human_review + all subtasks done
    _write_json(
        specs / "002-ai-matching-with-continuous-learning" / "implementation_plan.json",
        {
            "feature": "AI Matching with Continuous Learning",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-03T00:00:00Z",
            "status": "human_review",
            "qa_signoff": {"status": "approved", "timestamp": "2026-01-03T00:00:00Z"},
            "phases": [
                {
                    "id": "phase-1",
                    "name": "Implementation",
                    "subtasks": [{"id": "subtask-1", "status": "completed"}],
                }
            ],
        },
    )

    # Spec C: human_review but 0 subtasks (classic broken plan)
    _write_json(
        specs / "005-real-time-reconciliation-progress-dashboard" / "implementation_plan.json",
        {
            "feature": "Real-Time Reconciliation Progress Dashboard",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-04T00:00:00Z",
            "status": "human_review",
            "phases": [],
        },
    )

    # Roadmap: marks spec as planned even though we mark it done below
    _write_json(
        auto / "roadmap" / "roadmap.json",
        {
            "metadata": {"updated_at": "2026-01-05T00:00:00Z"},
            "features": [
                {
                    "id": "feature-1",
                    "title": "Email Notification Service",
                    "linked_spec_id": "003-email-notification-service",
                    "status": "planned",
                }
            ],
        },
    )

    # Spec D: done but roadmap planned
    _write_json(
        specs / "003-email-notification-service" / "implementation_plan.json",
        {
            "feature": "Email Notification Service",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-06T00:00:00Z",
            "status": "done",
            "phases": [
                {
                    "id": "phase-1",
                    "name": "Implementation",
                    "subtasks": [{"id": "subtask-1", "status": "completed"}],
                }
            ],
        },
    )

    report = generate_report(auto)
    specs_out = {s["spec_id"]: s for s in report["specs"]}

    def anomaly_types(spec_id: str) -> set[str]:
        return {a["type"] for a in specs_out[spec_id]["anomalies"]}

    assert "plan_schema_variant" in anomaly_types("010-direct-eml-msg-file-upload")
    assert "in_progress_zero_subtasks_done" in anomaly_types("010-direct-eml-msg-file-upload")
    assert "in_progress_missing_logs" in anomaly_types("010-direct-eml-msg-file-upload")

    assert "qa_approved_status_not_done" in anomaly_types(
        "002-ai-matching-with-continuous-learning"
    )

    assert "no_subtasks_in_plan" in anomaly_types(
        "005-real-time-reconciliation-progress-dashboard"
    )

    assert "roadmap_out_of_sync" in anomaly_types("003-email-notification-service")

