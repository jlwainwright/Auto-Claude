/**
 * Status Report API for renderer process
 *
 * Provides access to Auto-Claude status reporting:
 * - Generate full status report JSON
 * - Get quick summary stats
 */

import { IPC_CHANNELS } from '../../../shared/constants';
import { invokeIpc } from './ipc-utils';
import type { StatusReport, StatusSummaryQuick } from '../../../shared/types';

/**
 * Status Report API interface exposed to renderer
 */
export interface StatusReportAPI {
  generateReport: (projectId: string) => Promise<{ success: boolean; data?: StatusReport; error?: string }>;
  getSummary: (projectId: string) => Promise<{ success: boolean; data?: StatusSummaryQuick; error?: string }>;
}

/**
 * Creates the Status Report API implementation
 */
export const createStatusReportAPI = (): StatusReportAPI => ({
  generateReport: (projectId: string) =>
    invokeIpc(IPC_CHANNELS.STATUS_REPORT_GENERATE, projectId),

  getSummary: (projectId: string) =>
    invokeIpc(IPC_CHANNELS.STATUS_REPORT_GET_SUMMARY, projectId)
});
