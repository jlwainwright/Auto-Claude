/**
 * Types for Status Report feature
 *
 * The status report provides a comprehensive overview of all Auto-Claude specs
 * including anomaly detection, progress tracking, and roadmap alignment.
 */

/**
 * Severity levels for anomalies
 */
export type AnomalySeverity = 'error' | 'warning' | 'info';

/**
 * Supported anomaly types
 *
 * Status inconsistencies:
 * - "qa_approved_status_not_done" - QA approved but status not done
 * - "done_missing_qa_signoff" - Done but missing QA signoff
 * - "done_but_incomplete_subtasks" - Done status but incomplete subtasks
 *
 * Pipeline issues:
 * - "no_subtasks_in_plan" - Plan has 0 subtasks
 * - "implementation_plan_unreadable" - Cannot read implementation_plan.json
 * - "broken_pipeline" - 0 subtasks or stuck in human_review
 * - "plan_schema_variant" - Schema drift from expected id/id format
 *
 * Stuck states (NEW):
 * - "orphaned_active_status" - .auto-claude-status shows active but agent not running
 * - "stuck_in_human_review" - Status human_review with 0 subtasks for >1 hour
 * - "mismatched_active_spec" - .auto-claude-status references non-existent spec
 * - "subtask_stuck_in_progress" - Subtask stuck in_progress for >2 hours
 * - "plan_status_abandoned" - In_progress with no updates for >24 hours
 * - "worker_count_mismatch" - .auto-claude-status shows active workers but no activity
 *
 * Roadmap issues:
 * - "roadmap_out_of_sync" - Roadmap and spec status mismatch
 * - "roadmap_link_missing" - No roadmap feature linked to spec
 *
 * Recovery signals:
 * - "recovered_from_stuck" - Recovery note present
 * - "qa_iteration_nonapproved" - Non-approved QA iterations exist
 * - "qa_fix_request_present" - QA_FIX_REQUEST.md exists
 *
 * Drift detection:
 * - "build_progress_status_mismatch" - build-progress.txt status != plan status
 * - "build_progress_date_anomaly" - Date mismatch in build-progress.txt
 * - "in_progress_zero_subtasks_done" - In_progress but 0 subtasks done
 * - "in_progress_missing_logs" - In_progress but no logs exist
 */
export type AnomalyType = string;

/**
 * Anomaly detected in a spec
 */
export interface Anomaly {
  type: string;
  severity: AnomalySeverity;
  detail: string;
  context?: Record<string, unknown>;
}

/**
 * Schema detection result for implementation_plan.json
 */
export interface PlanSchema {
  schema_type: string;
  phase_key?: string;
  subtask_key?: string;
}

/**
 * Build progress metadata from build-progress.txt
 */
export interface BuildProgressMeta {
  status: string;
  created: string;
}

/**
 * Artifacts present in a spec directory
 */
export interface SpecArtifacts {
  files: string[];
  has_task_logs: boolean;
  has_build_progress: boolean;
  build_progress: BuildProgressMeta;
  has_qa_fix_request: boolean;
  has_attempt_history: boolean;
}

/**
 * QA signoff information
 */
export interface QASignoff {
  status: string;
  timestamp: string;
}

/**
 * Subtask summary
 */
export interface SubtaskSummary {
  done: number;
  total: number;
}

/**
 * Roadmap feature linked to a spec
 */
export interface RoadmapFeature {
  id: string;
  title: string;
  status: string;
}

/**
 * Spec status row
 */
export interface SpecStatusRow {
  spec_id: string;
  feature: string;
  status: string;
  planStatus: string;
  created_at: string;
  updated_at: string;
  qa: QASignoff;
  subtasks: SubtaskSummary;
  schema: PlanSchema;
  next_subtask: {
    phase_id: string;
    phase_name: string;
    subtask_id: string;
    title: string;
    description: string;
    status: string;
  } | null;
  artifacts: SpecArtifacts;
  roadmap_feature: RoadmapFeature | null;
  anomalies: Anomaly[];
}

/**
 * Summary statistics for the status report
 */
export interface StatusSummary {
  spec_count: number;
  status_counts: Record<string, number>;
  anomaly_count: number;
  anomaly_type_counts: Record<string, number>;
  anomaly_severity_counts: Record<string, number>;
}

/**
 * Roadmap metadata
 */
export interface RoadmapMeta {
  path: string;
  loaded: boolean;
  error: string;
  metadata: Record<string, unknown>;
}

/**
 * Complete status report
 */
export interface StatusReport {
  version: string;
  generated_at: string;
  auto_claude_dir: string;
  error?: string;
  specs_dir?: string;
  roadmap?: RoadmapMeta;
  summary: StatusSummary;
  specs: SpecStatusRow[];
  llm_prompt_template?: string;
}

/**
 * Quick summary (lighter version for dashboard)
 */
export interface StatusSummaryQuick {
  total_specs: number;
  by_status: Record<string, number>;
  total_anomalies: number;
  error_count: number;
  warning_count: number;
  info_count: number;
  last_updated: string;
}

/**
 * Anomaly fix operation types
 */

/**
 * Status of an anomaly fix operation
 */
export type FixStatus = 'idle' | 'starting' | 'running' | 'completed' | 'failed' | 'cancelled';

/**
 * Log entry from the fix operation
 */
export interface FixLogEntry {
  timestamp: string;
  type: 'info' | 'reasoning' | 'action' | 'success' | 'error' | 'warning';
  message: string;
  details?: string;
}

/**
 * Anomaly fix request
 */
export interface AnomalyFixRequest {
  projectId: string;
  specId: string;
  anomaly: Anomaly;
  specContext: SpecStatusRow;
}

/**
 * Anomaly fix response (for IPC)
 */
export interface AnomalyFixResponse {
  success: boolean;
  fixId: string;
  error?: string;
}

/**
 * State of an ongoing fix operation
 */
export interface AnomalyFixState {
  fixId: string;
  specId: string;
  anomaly: Anomaly;
  status: FixStatus;
  logs: FixLogEntry[];
  result?: {
    success: boolean;
    actions_taken: string[];
    files_modified: string[];
    summary: string;
  };
  error?: string;
  startTime: string;
  endTime?: string;
}
