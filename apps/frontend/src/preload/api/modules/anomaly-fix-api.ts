/**
 * Anomaly Fix API for renderer process
 *
 * Provides access to AI-powered anomaly resolution with streaming logs.
 */

import { IPC_CHANNELS } from '../../../shared/constants';
import { invokeIpc } from './ipc-utils';
import type { AnomalyFixRequest, AnomalyFixResponse, AnomalyFixState } from '../../../shared/types';

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface ElectronEvent {
  sender: unknown;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type EventCallback = (...args: any[]) => void;

/**
 * Anomaly Fix API interface exposed to renderer
 */
export interface AnomalyFixAPI {
  startFix: (request: AnomalyFixRequest) => Promise<{ success: boolean; data?: AnomalyFixResponse; error?: string }>;
  cancelFix: (fixId: string) => Promise<{ success: boolean; error?: string }>;
  getFixState: (fixId: string) => Promise<{ success: boolean; data?: AnomalyFixState; error?: string }>;
  onLog: (callback: (data: { fixId: string; entry: { timestamp: string; type: string; message: string; details?: string } }) => void) => () => void;
  onComplete: (callback: (data: { fixId: string; result?: { success: boolean; actions_taken: string[]; files_modified: string[]; summary: string } }) => void) => () => void;
  onError: (callback: (data: { fixId: string; error: string }) => void) => () => void;
}

/**
 * Creates the Anomaly Fix API implementation
 */
export const createAnomalyFixAPI = (): AnomalyFixAPI => {
  // Get the electronAPI from window (it's injected by preload)
  const electronAPI = (window as any).electronAPI;

  return {
    startFix: (request: AnomalyFixRequest) =>
      invokeIpc(IPC_CHANNELS.ANOMALY_FIX_START, request),

    cancelFix: (fixId: string) =>
      invokeIpc(IPC_CHANNELS.ANOMALY_FIX_CANCEL, fixId),

    getFixState: (fixId: string) =>
      invokeIpc(IPC_CHANNELS.ANOMALY_FIX_GET_STATE, fixId),

    onLog: (callback) => {
      const listener = (_event: ElectronEvent, data: { fixId: string; entry: { timestamp: string; type: string; message: string; details?: string } }) => {
        callback(data);
      };
      electronAPI?.on?.(IPC_CHANNELS.ANOMALY_FIX_LOG, listener);
      return () => electronAPI?.removeListener?.(IPC_CHANNELS.ANOMALY_FIX_LOG, listener);
    },

    onComplete: (callback) => {
      const listener = (_event: ElectronEvent, data: { fixId: string; result?: { success: boolean; actions_taken: string[]; files_modified: string[]; summary: string } }) => {
        callback(data);
      };
      electronAPI?.on?.(IPC_CHANNELS.ANOMALY_FIX_COMPLETE, listener);
      return () => electronAPI?.removeListener?.(IPC_CHANNELS.ANOMALY_FIX_COMPLETE, listener);
    },

    onError: (callback) => {
      const listener = (_event: ElectronEvent, data: { fixId: string; error: string }) => {
        callback(data);
      };
      electronAPI?.on?.(IPC_CHANNELS.ANOMALY_FIX_ERROR, listener);
      return () => electronAPI?.removeListener?.(IPC_CHANNELS.ANOMALY_FIX_ERROR, listener);
    }
  };
};
