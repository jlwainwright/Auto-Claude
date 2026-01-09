from __future__ import annotations

import json
from pathlib import Path

from scripts.auto_claude_status_report import generate_report


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


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

