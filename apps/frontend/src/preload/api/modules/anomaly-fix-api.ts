/**
 * Anomaly Fix API for renderer process
 *
 * Provides access to AI-powered anomaly resolution with streaming logs.
 */

import { IPC_CHANNELS } from '../../../shared/constants';
import { invokeIpc, createIpcListener, IpcListenerCleanup } from './ipc-utils';
import type { AnomalyFixRequest, AnomalyFixResponse, AnomalyFixState } from '../../../shared/types';

/**
 * Anomaly Fix API interface exposed to renderer
 */
export interface AnomalyFixAPI {
  startFix: (request: AnomalyFixRequest) => Promise<{ success: boolean; data?: AnomalyFixResponse; error?: string }>;
  cancelFix: (fixId: string) => Promise<{ success: boolean; error?: string }>;
  getFixState: (fixId: string) => Promise<{ success: boolean; data?: AnomalyFixState; error?: string }>;
  onLog: (callback: (data: { fixId: string; entry: { timestamp: string; type: string; message: string; details?: string } }) => void) => IpcListenerCleanup;
  onComplete: (callback: (data: { fixId: string; result?: { success: boolean; actions_taken: string[]; files_modified: string[]; summary: string } }) => void) => IpcListenerCleanup;
  onError: (callback: (data: { fixId: string; error: string }) => void) => IpcListenerCleanup;
}

/**
 * Creates the Anomaly Fix API implementation
 */
export const createAnomalyFixAPI = (): AnomalyFixAPI => ({
  startFix: (request: AnomalyFixRequest) =>
    invokeIpc(IPC_CHANNELS.ANOMALY_FIX_START, request),

  cancelFix: (fixId: string) =>
    invokeIpc(IPC_CHANNELS.ANOMALY_FIX_CANCEL, fixId),

  getFixState: (fixId: string) =>
    invokeIpc(IPC_CHANNELS.ANOMALY_FIX_GET_STATE, fixId),

  onLog: (callback) =>
    createIpcListener(IPC_CHANNELS.ANOMALY_FIX_LOG, callback),

  onComplete: (callback) =>
    createIpcListener(IPC_CHANNELS.ANOMALY_FIX_COMPLETE, callback),

  onError: (callback) =>
    createIpcListener(IPC_CHANNELS.ANOMALY_FIX_ERROR, callback)
});
