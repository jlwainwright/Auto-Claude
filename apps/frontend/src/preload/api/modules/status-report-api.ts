/**
 * Status Report API for renderer process
 *
 * Provides access to status report generation and anomaly fixing:
 * - Generate status report for a project
 * - Plan fixes for detected issues (dry-run)
 * - Apply fixes for detected issues
 */

import { IPC_CHANNELS } from '../../../shared/constants';
import type { StatusReport, AnomalyFixPlanRequest, AnomalyFixPlanResponse, IPCResult } from '../../../shared/types';
import { invokeIpc } from './ipc-utils';

/**
 * Status Report API interface exposed to renderer
 */
export interface StatusReportAPI {
  generateReport: (projectId: string) => Promise<IPCResult<StatusReport>>;
  planFix: (request: AnomalyFixPlanRequest) => Promise<IPCResult<AnomalyFixPlanResponse>>;
  startFix: (request: AnomalyFixPlanRequest) => Promise<IPCResult<{ success: boolean; error?: string }>>;
  cancelFix: () => Promise<IPCResult>;
  getFixState: () => Promise<IPCResult<{ isRunning: boolean }>>;
  onLog: (callback: (log: string) => void) => () => void;
  onComplete: (callback: (result: { success: boolean; error?: string }) => void) => () => void;
  onError: (callback: (error: string) => void) => () => void;
}

/**
 * Creates the Status Report API implementation
 */
export const createStatusReportAPI = (): StatusReportAPI => ({
  generateReport: (projectId: string): Promise<IPCResult<StatusReport>> =>
    invokeIpc(IPC_CHANNELS.STATUS_REPORT_GENERATE, projectId),

  planFix: (request: AnomalyFixPlanRequest): Promise<IPCResult<AnomalyFixPlanResponse>> =>
    invokeIpc(IPC_CHANNELS.STATUS_REPORT_ANOMALY_FIX_PLAN, request),

  startFix: (request: AnomalyFixPlanRequest): Promise<IPCResult<{ success: boolean; error?: string }>> =>
    invokeIpc(IPC_CHANNELS.STATUS_REPORT_ANOMALY_FIX_APPLY, request),

  cancelFix: (): Promise<IPCResult> =>
    Promise.resolve({ success: true }),

  getFixState: (): Promise<IPCResult<{ isRunning: boolean }>> =>
    Promise.resolve({ success: true, data: { isRunning: false } }),

  onLog: (callback: (log: string) => void) => () => {},

  onComplete: (callback: (result: { success: boolean; error?: string }) => void) => () => {},

  onError: (callback: (error: string) => void) => () => {},
});
