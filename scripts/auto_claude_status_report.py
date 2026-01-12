#!/usr/bin/env python3
"""
auto_claude_status_report.py

Generate a machine-readable status report for Auto-Claude projects.

This script is designed to be copy/pasted into ANY repo. It:
- Locates a `.auto-claude/` directory (via --auto-claude, or by walking up from cwd)
- Summarizes spec status from `.auto-claude/specs/*/implementation_plan.json`
- Cross-checks for common "pipeline broke / out-of-sync" anomalies
- Optionally loads `.auto-claude/roadmap/roadmap.json` to detect roadmap/spec drift
- Emits a single JSON report suitable for feeding to an LLM

No third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

VERSION = "1.0.0"

DONE_STATUSES = {"done", "completed"}

BUILD_PROGRESS_FILENAME = "build-progress.txt"
TASK_LOGS_FILENAME = "task_logs.json"
QA_FIX_REQUEST_FILENAME = "QA_FIX_REQUEST.md"
ATTEMPT_HISTORY_PATH = Path("memory") / "attempt_history.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()


def _is_done(status: Any) -> bool:
    return _norm(status).lower() in DONE_STATUSES


def _safe_read_text(path: Path, *, max_bytes: int = 200_000) -> str:
    """
    Read text content safely with a byte cap to avoid loading huge files.
    """
    try:
        with path.open("rb") as f:
            raw = f.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raw = raw[:max_bytes]
        return raw.decode("utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    s = _norm(value)
    if not s:
        return None
    try:
        # handle "Z"
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def find_auto_claude_dir(start: Path) -> Optional[Path]:
    """
    Walk upward from `start` to find a `.auto-claude` directory.
    """
    cur = start.resolve()
    for _ in range(50):
        candidate = cur / ".auto-claude"
        if candidate.exists() and candidate.is_dir():
            return candidate
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def _read_json_file(path: Path) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data, None
        return None, "JSON root is not an object"
    except FileNotFoundError:
        return None, "file not found"
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"
    except Exception as e:
        return None, str(e)


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return []


def _phase_id(phase: dict[str, Any]) -> str:
    return _norm(
        phase.get("id")
        or phase.get("phase_id")
        or phase.get("phaseId")
        or phase.get("phaseID")
    )


def _phase_name(phase: dict[str, Any]) -> str:
    return _norm(phase.get("name") or phase.get("title"))


def _subtask_id(subtask: dict[str, Any]) -> str:
    return _norm(
        subtask.get("id")
        or subtask.get("subtask_id")
        or subtask.get("subtaskId")
        or subtask.get("subtaskID")
    )


def _detect_plan_schema(plan: dict[str, Any]) -> dict[str, Any]:
    phases = plan.get("phases")
    if phases is None:
        return {"schema_type": "no_phases_key"}
    if not isinstance(phases, list):
        return {"schema_type": "phases_not_list"}
    if not phases:
        return {"schema_type": "empty_phases"}
    ph0 = phases[0]
    if not isinstance(ph0, dict):
        return {"schema_type": "phase_not_dict"}

    # Phase key
    phase_key = "unknown"
    if "id" in ph0:
        phase_key = "id"
    elif "phase_id" in ph0:
        phase_key = "phase_id"

    subtask_key = "unknown"
    sts = ph0.get("subtasks")
    if isinstance(sts, list) and sts and isinstance(sts[0], dict):
        st0 = sts[0]
        if "id" in st0:
            subtask_key = "id"
        elif "subtask_id" in st0:
            subtask_key = "subtask_id"

    schema_type = f"{phase_key}/{subtask_key}"
    return {
        "schema_type": schema_type,
        "phase_key": phase_key,
        "subtask_key": subtask_key,
    }


def _flatten_subtasks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for ph in _coerce_list(plan.get("phases")):
        if not isinstance(ph, dict):
            continue
        for st in _coerce_list(ph.get("subtasks")):
            if not isinstance(st, dict):
                continue
            tasks.append(
                {
                    "phase_id": _phase_id(ph),
                    "phase_name": _phase_name(ph),
                    "subtask_id": _subtask_id(st),
                    "title": _norm(st.get("title")),
                    "description": _norm(st.get("description")),
                    "status": _norm(st.get("status")),
                    "dependencies": st.get("dependencies") if "dependencies" in st else None,
                    "file_paths": st.get("file_paths")
                    or st.get("file_path")
                    or st.get("files_to_modify")
                    or st.get("files_to_create"),
                    "updated_at": _norm(st.get("updated_at") or st.get("timestamp")),
                }
            )
    return tasks


@dataclass(frozen=True)
class Anomaly:
    type: str
    severity: str  # "error" | "warning" | "info"
    detail: str
    context: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "type": self.type,
            "severity": self.severity,
            "detail": self.detail,
        }
        if self.context:
            out["context"] = self.context
        return out


_RE_BUILD_PROGRESS_STATUS = re.compile(r"^(?:##\\s*)?Status:\\s*(.+?)\\s*$", re.IGNORECASE)
_RE_BUILD_PROGRESS_CREATED = re.compile(
    r"^(?:##\\s*)?Created:\\s*(.+?)\\s*$", re.IGNORECASE
)


def _parse_build_progress(build_progress_text: str) -> dict[str, Any]:
    status: Optional[str] = None
    created: Optional[str] = None

    for line in build_progress_text.splitlines()[:250]:
        if status is None:
            m = _RE_BUILD_PROGRESS_STATUS.match(line.strip())
            if m:
                status = m.group(1).strip()
                continue
        if created is None:
            m = _RE_BUILD_PROGRESS_CREATED.match(line.strip())
            if m:
                created = m.group(1).strip()
                continue

        if status is not None and created is not None:
            break

    return {
        "status": status or "",
        "created": created or "",
    }


def _read_auto_claude_status_file(auto_claude_dir: Path) -> Optional[dict[str, Any]]:
    """Read and parse the .auto-claude-status file from the auto-claude directory."""
    status_path = auto_claude_dir / ".auto-claude-status"
    if not status_path.exists():
        return None
    data, _ = _read_json_file(status_path)
    return data


def _get_time_since_update(updated_at_str: str) -> Optional[float]:
    """Get hours since a timestamp string."""
    dt = _parse_iso_datetime(updated_at_str)
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    delta = now - dt
    return delta.total_seconds() / 3600  # Return hours


def _check_stuck_subtasks(tasks: list[dict[str, Any]], stale_hours: float = 2.0) -> list[dict[str, Any]]:
    """Find subtasks that have been in_progress for too long."""
    stuck = []
    for task in tasks:
        if _norm(task.get("status")) == "in_progress":
            updated_at = _norm(task.get("updated_at") or task.get("timestamp"))
            if updated_at:
                hours = _get_time_since_update(updated_at)
                if hours is not None and hours > stale_hours:
                    stuck.append({
                        "subtask": task.get("id") or task.get("subtask_id") or "unknown",
                        "title": task.get("title") or "",
                        "hours_stuck": round(hours, 1)
                    })
    return stuck


def generate_report(auto_claude_dir: Path) -> dict[str, Any]:
    auto_claude_dir = auto_claude_dir.resolve()
    specs_dir = auto_claude_dir / "specs"
    roadmap_path = auto_claude_dir / "roadmap" / "roadmap.json"

    # Read .auto-claude-status file for orphaned status detection
    status_file = _read_auto_claude_status_file(auto_claude_dir)
    active_spec_id = _norm(status_file.get("spec")) if status_file else ""
    is_building = status_file.get("state") == "building" if status_file else False
    is_active = status_file.get("active") is True if status_file else False

    roadmap: dict[str, Any] = {}
    roadmap_features_by_spec: dict[str, dict[str, Any]] = {}
    roadmap_loaded = False
    roadmap_error: Optional[str] = None

    if roadmap_path.exists():
        roadmap_data, err = _read_json_file(roadmap_path)
        if roadmap_data is not None:
            roadmap = roadmap_data
            roadmap_loaded = True
            for f in _coerce_list(roadmap.get("features")):
                if not isinstance(f, dict):
                    continue
                spec_id = _norm(f.get("linked_spec_id"))
                if spec_id:
                    roadmap_features_by_spec[spec_id] = f
        else:
            roadmap_error = err

    spec_rows: list[dict[str, Any]] = []

    if not specs_dir.exists():
        return {
            "version": VERSION,
            "generated_at": _now_iso(),
            "auto_claude_dir": str(auto_claude_dir),
            "error": "specs directory not found",
            "specs_dir": str(specs_dir),
        }

    for spec_dir in sorted([p for p in specs_dir.iterdir() if p.is_dir() and p.name != ".gitkeep"]):
        plan_path = spec_dir / "implementation_plan.json"
        plan, plan_err = _read_json_file(plan_path)

        files = sorted([p.name for p in spec_dir.iterdir() if p.is_file()])
        has_task_logs = (spec_dir / TASK_LOGS_FILENAME).exists()
        has_build_progress = (spec_dir / BUILD_PROGRESS_FILENAME).exists()
        has_qa_fix_request = (spec_dir / QA_FIX_REQUEST_FILENAME).exists()
        has_attempt_history = (spec_dir / ATTEMPT_HISTORY_PATH).exists()

        build_progress_meta: dict[str, Any] = {}
        if has_build_progress:
            txt = _safe_read_text(spec_dir / BUILD_PROGRESS_FILENAME)
            build_progress_meta = _parse_build_progress(txt)

        anomalies: list[Anomaly] = []

        if plan is None:
            anomalies.append(
                Anomaly(
                    type="implementation_plan_unreadable",
                    severity="error",
                    detail=f"Cannot read implementation_plan.json ({plan_err})",
                )
            )
            spec_rows.append(
                {
                    "spec_id": spec_dir.name,
                    "feature": "",
                    "status": "",
                    "planStatus": "",
                    "created_at": "",
                    "updated_at": "",
                    "qa": {"status": "", "timestamp": ""},
                    "subtasks": {"done": 0, "total": 0},
                    "schema": {"schema_type": ""},
                    "next_subtask": None,
                    "artifacts": {
                        "files": files,
                        "has_task_logs": has_task_logs,
                        "has_build_progress": has_build_progress,
                        "build_progress": build_progress_meta,
                        "has_qa_fix_request": has_qa_fix_request,
                        "has_attempt_history": has_attempt_history,
                    },
                    "roadmap_feature": None,
                    "anomalies": [a.to_dict() for a in anomalies],
                }
            )
            continue

        status = _norm(plan.get("status"))
        plan_status = _norm(plan.get("planStatus") or plan.get("plan_status"))
        created_at = _norm(plan.get("created_at"))
        updated_at = _norm(plan.get("updated_at") or plan.get("last_updated"))

        qa_signoff = plan.get("qa_signoff") if isinstance(plan.get("qa_signoff"), dict) else {}
        qa_status = _norm(qa_signoff.get("status"))
        qa_ts = _norm(qa_signoff.get("timestamp"))

        schema = _detect_plan_schema(plan)
        tasks = _flatten_subtasks(plan)
        total = len(tasks)
        done_count = sum(1 for t in tasks if _is_done(t.get("status")))
        next_subtask = next((t for t in tasks if not _is_done(t.get("status"))), None)

        # Roadmap linkage
        rm_feature = roadmap_features_by_spec.get(spec_dir.name)
        if rm_feature:
            rm_status = _norm(rm_feature.get("status"))
            if _norm(status).lower() in DONE_STATUSES and rm_status.lower() not in DONE_STATUSES:
                if rm_status in {"planned", "under_review"}:
                    anomalies.append(
                        Anomaly(
                            type="roadmap_out_of_sync",
                            severity="warning",
                            detail=f"Roadmap feature is '{rm_status}' but spec plan is '{status}'",
                            context={
                                "roadmap_feature_id": _norm(rm_feature.get("id")),
                                "roadmap_feature_title": _norm(rm_feature.get("title")),
                            },
                        )
                    )
            if _norm(status).lower() not in DONE_STATUSES and rm_status.lower() in DONE_STATUSES:
                anomalies.append(
                    Anomaly(
                        type="roadmap_out_of_sync",
                        severity="warning",
                        detail=f"Roadmap feature is '{rm_status}' but spec plan is '{status}'",
                        context={
                            "roadmap_feature_id": _norm(rm_feature.get("id")),
                            "roadmap_feature_title": _norm(rm_feature.get("title")),
                        },
                    )
                )
        elif roadmap_loaded:
            anomalies.append(
                Anomaly(
                    type="roadmap_link_missing",
                    severity="warning",
                    detail="No roadmap feature found with linked_spec_id for this spec",
                )
            )

        # Schema variant (common pipeline break source)
        if schema.get("schema_type") and schema.get("schema_type") not in {"id/id", "empty_phases"}:
            anomalies.append(
                Anomaly(
                    type="plan_schema_variant",
                    severity="warning",
                    detail=f"implementation_plan.json schema is '{schema.get('schema_type')}' (pipeline code may assume 'id/id')",
                )
            )

        # Status/subtask mismatches
        if _norm(status).lower() in DONE_STATUSES and total and done_count != total:
            anomalies.append(
                Anomaly(
                    type="done_but_incomplete_subtasks",
                    severity="error",
                    detail=f"Plan status '{status}' but subtasks completed {done_count}/{total}",
                )
            )

        if status and status.lower() != "pending" and total == 0:
            anomalies.append(
                Anomaly(
                    type="no_subtasks_in_plan",
                    severity="error",
                    detail=f"Plan status '{status}' but implementation_plan.json contains 0 subtasks",
                )
            )

        if status.lower() == "in_progress" and total and done_count == 0:
            anomalies.append(
                Anomaly(
                    type="in_progress_zero_subtasks_done",
                    severity="warning",
                    detail=f"Status is in_progress but 0/{total} subtasks are marked done",
                )
            )

        if status.lower() == "in_progress" and not (has_task_logs or has_build_progress):
            anomalies.append(
                Anomaly(
                    type="in_progress_missing_logs",
                    severity="warning",
                    detail="Status is in_progress but neither task_logs.json nor build-progress.txt exist",
                )
            )

        # QA vs status mismatches
        if _norm(status).lower() in DONE_STATUSES and not qa_status:
            anomalies.append(
                Anomaly(
                    type="done_missing_qa_signoff",
                    severity="warning",
                    detail="Plan is done/completed but qa_signoff.status is missing",
                )
            )

        if qa_status.lower() == "approved" and _norm(status).lower() not in DONE_STATUSES:
            anomalies.append(
                Anomaly(
                    type="qa_approved_status_not_done",
                    severity="warning",
                    detail=f"qa_signoff is approved but plan status is '{status}'",
                )
            )

        # Recovery & QA iteration signals
        recovery_note = _norm(plan.get("recoveryNote"))
        if recovery_note:
            anomalies.append(
                Anomaly(
                    type="recovered_from_stuck",
                    severity="info",
                    detail=recovery_note,
                )
            )

        qa_iter_hist = _coerce_list(plan.get("qa_iteration_history"))
        non_approved_iters = [
            it
            for it in qa_iter_hist
            if isinstance(it, dict) and _norm(it.get("status")) and _norm(it.get("status")) != "approved"
        ]
        if non_approved_iters:
            anomalies.append(
                Anomaly(
                    type="qa_iteration_nonapproved",
                    severity="info",
                    detail=f"qa_iteration_history has {len(non_approved_iters)} non-approved iteration(s)",
                )
            )

        if has_qa_fix_request:
            anomalies.append(
                Anomaly(
                    type="qa_fix_request_present",
                    severity="error",
                    detail="QA_FIX_REQUEST.md exists (human intervention requested)",
                )
            )

        # build-progress.txt drift signals (best-effort; not all specs have same format)
        if has_build_progress:
            bp_status = _norm(build_progress_meta.get("status"))
            bp_created = _norm(build_progress_meta.get("created"))
            if bp_status and status and bp_status.lower() != status.lower():
                anomalies.append(
                    Anomaly(
                        type="build_progress_status_mismatch",
                        severity="warning",
                        detail=f"build-progress.txt status '{bp_status}' != implementation_plan.json status '{status}'",
                    )
                )

            # If build-progress created date looks wildly different from plan created_at, flag it.
            # We accept many formats; if parsing fails, skip.
            plan_created_dt = _parse_iso_datetime(created_at)
            if bp_created and plan_created_dt:
                # Many build-progress files use YYYY-MM-DD
                try:
                    bp_created_dt = datetime.fromisoformat(bp_created).replace(tzinfo=timezone.utc)
                except Exception:
                    bp_created_dt = None
                if bp_created_dt is not None:
                    delta_days = abs((plan_created_dt.date() - bp_created_dt.date()).days)
                    if delta_days >= 90:
                        anomalies.append(
                            Anomaly(
                                type="build_progress_date_anomaly",
                                severity="info",
                                detail=f"build-progress.txt created '{bp_created}' differs from plan created_at '{created_at}' by ~{delta_days} days",
                            )
                        )

        # ===== NEW ANOMALY DETECTION =====
        # Detect stuck states and orphaned status

        # Anomaly: orphaned_active_status - .auto-claude-status shows active=true but spec may be orphaned
        if is_active and is_building and active_spec_id == spec_dir.name:
            # Check if the spec appears stuck (e.g., in_progress but no recent updates)
            if status.lower() == "in_progress" and updated_at:
                hours_since_update = _get_time_since_update(updated_at)
                if hours_since_update is not None and hours_since_update > 4:
                    anomalies.append(
                        Anomaly(
                            type="orphaned_active_status",
                            severity="error",
                            detail=f".auto-claude-status shows active=true for '{spec_dir.name}' but no updates for {hours_since_update:.1f} hours (agent may have crashed)",
                        )
                    )

        # Anomaly: stuck_in_human_review - status is human_review with 0 subtasks for >1 hour
        if status.lower() == "human_review" and total == 0:
            if updated_at:
                hours_since_update = _get_time_since_update(updated_at)
                if hours_since_update is not None and hours_since_update > 1:
                    anomalies.append(
                        Anomaly(
                            type="stuck_in_human_review",
                            severity="error",
                            detail=f"Status is human_review with 0 subtasks for {hours_since_update:.1f} hours (planner may have failed)",
                        )
                    )

        # Anomaly: mismatched_active_spec - .auto-claude-status references a non-existent spec
        if is_active and is_building and active_spec_id:
            # Check if the active spec exists
            active_spec_exists = any(s.name == active_spec_id for s in specs_dir.iterdir() if s.is_dir())
            if not active_spec_exists and spec_dir.name == active_spec_id:
                # This is the last iteration and the active spec doesn't exist
                pass  # Will be caught in the check below
            elif spec_dir.name == active_spec_id and not active_spec_exists:
                anomalies.append(
                    Anomaly(
                        type="mismatched_active_spec",
                        severity="warning",
                        detail=f".auto-claude-status references spec '{active_spec_id}' which doesn't exist in specs directory",
                    )
                )

        # Anomaly: subtask_stuck_in_progress - subtask has been in_progress for >2 hours
        stuck_subtasks = _check_stuck_subtasks(tasks, stale_hours=2.0)
        if stuck_subtasks:
            for stuck in stuck_subtasks:
                anomalies.append(
                    Anomaly(
                        type="subtask_stuck_in_progress",
                        severity="warning",
                        detail=f"Subtask '{stuck['subtask']}' ({stuck.get('title', '')}) stuck in_progress for {stuck['hours_stuck']} hours",
                    )
                )

        # Anomaly: plan_status_abandoned - status is in_progress but no updates for >24 hours
        if status.lower() == "in_progress" and updated_at:
            hours_since_update = _get_time_since_update(updated_at)
            if hours_since_update is not None and hours_since_update > 24:
                anomalies.append(
                    Anomaly(
                        type="plan_status_abandoned",
                        severity="error",
                        detail=f"Status is in_progress but no updates for {hours_since_update:.1f} hours (build may be abandoned)",
                    )
                )

        # Anomaly: worker_count_mismatch - .auto-claude-status shows active workers but no activity
        if status_file and is_active and is_building:
            workers = status_file.get("workers", {})
            active_workers = workers.get("active", 0)
            if active_workers > 0 and status.lower() == "in_progress":
                # Check if there's been recent activity
                if updated_at:
                    hours_since_update = _get_time_since_update(updated_at)
                    if hours_since_update is not None and hours_since_update > 2:
                        anomalies.append(
                            Anomaly(
                                type="worker_count_mismatch",
                                severity="warning",
                                detail=f".auto-claude-status shows {active_workers} active workers but no updates for {hours_since_update:.1f} hours",
                            )
                        )

        spec_rows.append(
            {
                "spec_id": spec_dir.name,
                "feature": _norm(plan.get("feature") or plan.get("title")),
                "status": status,
                "planStatus": plan_status,
                "created_at": created_at,
                "updated_at": updated_at,
                "qa": {"status": qa_status, "timestamp": qa_ts},
                "subtasks": {"done": done_count, "total": total},
                "schema": schema,
                "next_subtask": next_subtask,
                "artifacts": {
                    "files": files,
                    "has_task_logs": has_task_logs,
                    "has_build_progress": has_build_progress,
                    "build_progress": build_progress_meta,
                    "has_qa_fix_request": has_qa_fix_request,
                    "has_attempt_history": has_attempt_history,
                },
                "roadmap_feature": {
                    "id": _norm(rm_feature.get("id")) if rm_feature else "",
                    "title": _norm(rm_feature.get("title")) if rm_feature else "",
                    "status": _norm(rm_feature.get("status")) if rm_feature else "",
                }
                if rm_feature
                else None,
                "anomalies": [a.to_dict() for a in anomalies],
            }
        )

    status_counts = Counter((_norm(r.get("status")).lower() or "unknown") for r in spec_rows)
    all_anoms = [a for r in spec_rows for a in _coerce_list(r.get("anomalies"))]
    anomaly_type_counts = Counter(_norm(a.get("type")) or "unknown" for a in all_anoms if isinstance(a, dict))
    anomaly_severity_counts = Counter(
        _norm(a.get("severity")) or "unknown" for a in all_anoms if isinstance(a, dict)
    )

    report: dict[str, Any] = {
        "version": VERSION,
        "generated_at": _now_iso(),
        "auto_claude_dir": str(auto_claude_dir),
        "roadmap": {
            "path": str(roadmap_path),
            "loaded": roadmap_loaded,
            "error": roadmap_error or "",
            "metadata": roadmap.get("metadata") if isinstance(roadmap.get("metadata"), dict) else {},
        },
        "summary": {
            "spec_count": len(spec_rows),
            "status_counts": dict(sorted(status_counts.items())),
            "anomaly_count": len(all_anoms),
            "anomaly_type_counts": dict(sorted(anomaly_type_counts.items())),
            "anomaly_severity_counts": dict(sorted(anomaly_severity_counts.items())),
        },
        "specs": spec_rows,
    }

    return report


LLM_PROMPT_TEMPLATE = """\
You are an engineering QA assistant. You will be given a JSON report generated by a scanner script.

Your job:
- Produce a concise, user-facing status report in structured Markdown.
- Output a single Markdown table where the RIGHTMOST column is **LLM Notes**.
- The table must include one row per spec/task section in the JSON.
- Use the anomalies to call out out-of-sync / broken-pipeline signals.

Output format (STRICT):

## Summary
- Total specs: <n>
- Status counts: <...>
- Total anomalies: <n>

## Spec status table
| Spec | Feature | Plan status | QA | Subtasks | Updated | Anomalies | LLM Notes |
|------|---------|-------------|----|----------|---------|----------|-----------|
| ...  | ...     | ...         | ...| ...      | ...     | ...      | ...       |

Rules for the table:
- **Anomalies** column: list anomaly `type` values (comma-separated). If none, write `-`.
- **LLM Notes** column: 1-3 sentences, focused on (a) likely cause, (b) what to do next, (c) risk.
- If `no_subtasks_in_plan` or `qa_fix_request_present` is present, explicitly state: \"pipeline likely broke during planning\".
- If `plan_schema_variant` is present, explicitly state: \"plan schema drift may break tooling that expects id/id\".

After the table, add:

## Anomalies (grouped)
- Group by anomaly type; for each group, list affected specs and 1 recommended fix.

The JSON report to analyze is below:

```json
<REPORT_JSON_HERE>
```
"""


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate Auto-Claude status + anomalies JSON report.")
    p.add_argument(
        "--auto-claude",
        type=str,
        default="",
        help="Path to the .auto-claude directory. If omitted, will search upward from --start-dir/cwd.",
    )
    p.add_argument(
        "--start-dir",
        type=str,
        default="",
        help="Directory to start searching upward for .auto-claude (default: cwd).",
    )
    p.add_argument(
        "--output",
        type=str,
        default="",
        help="Write JSON report to this file path. If omitted, prints to stdout.",
    )
    p.add_argument(
        "--include-prompt-template",
        action="store_true",
        help="Include an llm_prompt_template field in the JSON output.",
    )
    p.add_argument(
        "--print-prompt-template",
        action="store_true",
        help="Print the built-in LLM prompt template and exit.",
    )
    p.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Exit with code 2 if any anomaly has severity=error.",
    )
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON with indentation.")
    p.add_argument("--version", action="store_true", help="Print version and exit.")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    if args.version:
        print(VERSION)
        return 0

    if args.print_prompt_template:
        print(LLM_PROMPT_TEMPLATE.rstrip())
        return 0

    start_dir = Path(args.start_dir).resolve() if args.start_dir else Path.cwd()
    auto_claude_dir: Optional[Path]

    if args.auto_claude:
        auto_claude_dir = Path(args.auto_claude).expanduser().resolve()
    else:
        auto_claude_dir = find_auto_claude_dir(start_dir)

    if not auto_claude_dir:
        err_report = {
            "version": VERSION,
            "generated_at": _now_iso(),
            "error": "Could not find .auto-claude directory",
            "start_dir": str(start_dir),
        }
        out = json.dumps(err_report, indent=2 if args.pretty else None, sort_keys=True)
        if args.output:
            Path(args.output).write_text(out, encoding="utf-8")
        else:
            print(out)
        return 1

    report = generate_report(auto_claude_dir)
    if args.include_prompt_template:
        report["llm_prompt_template"] = LLM_PROMPT_TEMPLATE

    out = json.dumps(report, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)

    if args.fail_on_errors:
        severities = [
            _norm(a.get("severity")).lower()
            for spec in _coerce_list(report.get("specs"))
            for a in _coerce_list(spec.get("anomalies")) if isinstance(spec, dict)
        ]
        if "error" in severities:
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

