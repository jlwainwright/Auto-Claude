/**
 * Status Report types
 */

export type IssueSeverity = 'error' | 'warning' | 'info';

export interface Issue {
  severity: IssueSeverity;
  code: string;
  message: string;
  paths: string[];
  suggestedFix?: string;
  details?: Record<string, unknown>;
}

export interface FixPlanChange {
  path: string;
  action: 'create' | 'update' | 'delete';
  content?: string;
  encoding?: string;
}

export interface FixPlan {
  issueCodes: string[];
  changes: FixPlanChange[];
  description: string;
  dryRun: boolean;
}

export interface StatusReportSpec {
  id: string;
  path: string;
  issues: Issue[];
  issueCount: number;
}

export interface StatusReportRoadmap {
  exists: boolean;
  issues: Issue[];
}

export interface StatusReport {
  summary: {
    totalSpecs: number;
    totalIssues: number;
    issueSeverityCounts: {
      error: number;
      warning: number;
      info: number;
    };
  };
  specs: StatusReportSpec[];
  roadmap: StatusReportRoadmap;
}

export interface AnomalyFixPlanRequest {
  anomaly: Issue;
  specId: string;
  projectPath: string;
}

export interface AnomalyFixPlanResponse {
  success: boolean;
  plan?: FixPlan;
  error?: string;
}
