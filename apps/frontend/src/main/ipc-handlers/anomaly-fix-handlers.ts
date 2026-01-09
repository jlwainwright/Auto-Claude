/**
 * Anomaly Fix IPC Handlers
 *
 * Handles AI-powered anomaly resolution for Auto-Claude specs.
 * Runs the Python script fix_anomaly.py to resolve detected issues.
 */

import { ipcMain, BrowserWindow } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { IPC_CHANNELS } from '../../shared/constants';
import type {
  IPCResult,
  AnomalyFixRequest,
  AnomalyFixResponse,
  AnomalyFixState,
  FixLogEntry,
  FixStatus
} from '../../shared/types';
import { projectStore } from '../project-store';

// Path to the anomaly fix script (relative to Auto-Claude root)
const ANOMALY_FIX_SCRIPT = 'scripts/fix_anomaly.py';

// Active fix processes
const activeFixes = new Map<string, ChildProcess>();
// Fix state storage
const fixStates = new Map<string, AnomalyFixState>();

/**
 * Find the Auto-Claude installation root
 * (reuses logic from status-report-handlers)
 */
function findAutoClaudeRoot(projectPath: string): string | null {
  let searchDir = path.resolve(projectPath);
  for (let i = 0; i < 15; i++) {
    const scriptsPath = path.join(searchDir, 'scripts', 'fix_anomaly.py');
    if (existsSync(scriptsPath)) {
      return searchDir;
    }
    const parent = path.dirname(searchDir);
    if (parent === searchDir) break;
    searchDir = parent;
  }
  return null;
}

/**
 * Send a log entry to the renderer
 */
function sendLogEntry(fixId: string, entry: FixLogEntry): void {
  const mainWindow = BrowserWindow.getAllWindows()[0];
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(IPC_CHANNELS.ANOMALY_FIX_LOG, {
      fixId,
      entry
    });
  }
}

/**
 * Send fix completion event
 */
function sendFixComplete(fixId: string, result: AnomalyFixState['result']): void {
  const mainWindow = BrowserWindow.getAllWindows()[0];
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(IPC_CHANNELS.ANOMALY_FIX_COMPLETE, {
      fixId,
      result
    });
  }
}

/**
 * Send fix error event
 */
function sendFixError(fixId: string, error: string): void {
  const mainWindow = BrowserWindow.getAllWindows()[0];
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(IPC_CHANNELS.ANOMALY_FIX_ERROR, {
      fixId,
      error
    });
  }
}

/**
 * Create a log entry with current timestamp
 */
function createLogEntry(
  type: FixLogEntry['type'],
  message: string,
  details?: string
): FixLogEntry {
  return {
    timestamp: new Date().toISOString(),
    type,
    message,
    details
  };
}

/**
 * Parse a log line from the Python script
 * Expects JSON lines or structured text:
 * [TYPE] message
 * or JSON: {"type": "...", "message": "...", "details": "..."}
 */
function parseLogLine(line: string): FixLogEntry | null {
  const trimmed = line.trim();
  if (!trimmed) return null;

  // Try JSON first
  if (trimmed.startsWith('{')) {
    try {
      const parsed = JSON.parse(trimmed);
      return {
        timestamp: parsed.timestamp || new Date().toISOString(),
        type: parsed.type || 'info',
        message: parsed.message || '',
        details: parsed.details
      };
    } catch {
      // Not valid JSON, continue to text parsing
    }
  }

  // Parse structured text: [TYPE] message
  const typeMatch = trimmed.match(/^\[(\w+)\]\s*(.+)$/);
  if (typeMatch) {
    const [, typeStr, message] = typeMatch;
    const validTypes = ['info', 'reasoning', 'action', 'success', 'error', 'warning'];
    const type = validTypes.includes(typeStr.toLowerCase())
      ? (typeStr.toLowerCase() as FixLogEntry['type'])
      : 'info';
    return createLogEntry(type, message);
  }

  // Plain text line
  return createLogEntry('info', trimmed);
}

/**
 * Run the anomaly fix script
 */
async function runFixScript(
  fixId: string,
  request: AnomalyFixRequest,
  autoClaudeRoot: string
): Promise<void> {
  const scriptPath = path.join(autoClaudeRoot, ANOMALY_FIX_SCRIPT);
  const pythonExe = process.platform === 'win32' ? 'python' : 'python3';

  // Prepare input for the script
  const inputJson = JSON.stringify({
    anomaly: request.anomaly,
    specId: request.specId,
    specContext: {
      spec_id: request.specContext.spec_id,
      feature: request.specContext.feature,
      status: request.specContext.status,
      planStatus: request.specContext.planStatus,
      subtasks: request.specContext.subtasks,
      next_subtask: request.specContext.next_subtask
    }
  });

  const child = spawn(pythonExe, [scriptPath, '--json'], {
    cwd: autoClaudeRoot,
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      AUTO_CLAUDE_PROJECT_PATH: request.projectId
    }
  });

  activeFixes.set(fixId, child);

  let stdout = '';
  let stderr = '';

  // Handle stdout - parse log entries
  child.stdout?.on('data', (data) => {
    const text = data.toString();
    stdout += text;

    // Process line by line
    const lines = text.split('\n');
    for (const line of lines) {
      const entry = parseLogLine(line);
      if (entry) {
        // Add to state
        const state = fixStates.get(fixId);
        if (state) {
          state.logs.push(entry);
          // Send to renderer
          sendLogEntry(fixId, entry);
        }
      }
    }
  });

  // Handle stderr - treat as error logs
  child.stderr?.on('data', (data) => {
    const text = data.toString();
    stderr += text;

    const state = fixStates.get(fixId);
    if (state) {
      const entry = createLogEntry('error', text.trim());
      state.logs.push(entry);
      sendLogEntry(fixId, entry);
    }
  });

  // Handle process exit
  child.on('close', (code) => {
    activeFixes.delete(fixId);

    const state = fixStates.get(fixId);
    if (!state) return;

    state.endTime = new Date().toISOString();

    if (code === 0) {
      state.status = 'completed';
      // Try to parse result from stdout
      try {
        // Look for JSON result at the end
        const lastBrace = stdout.lastIndexOf('}');
        if (lastBrace > 0) {
          const firstBrace = stdout.lastIndexOf('{', lastBrace);
          if (firstBrace >= 0) {
            const resultJson = stdout.substring(firstBrace, lastBrace + 1);
            const result = JSON.parse(resultJson);
            state.result = {
              success: result.success ?? true,
              actions_taken: result.actions_taken || [],
              files_modified: result.files_modified || [],
              summary: result.summary || 'Fix completed successfully'
            };
          }
        }
      } catch {
        // Failed to parse result, use default
        state.result = {
          success: true,
          actions_taken: [],
          files_modified: [],
          summary: 'Fix completed'
        };
      }
      sendFixComplete(fixId, state.result);
    } else {
      state.status = 'failed';
      state.error = stderr || `Process exited with code ${code}`;
      sendFixError(fixId, state.error);
    }
  });

  // Handle process error
  child.on('error', (err) => {
    activeFixes.delete(fixId);

    const state = fixStates.get(fixId);
    if (!state) return;

    state.status = 'failed';
    state.error = err.message;
    state.endTime = new Date().toISOString();
    sendFixError(fixId, err.message);
  });

  // Send input to the script
  if (child.stdin) {
    child.stdin.write(inputJson + '\n');
    child.stdin.end();
  }
}

/**
 * Register all anomaly fix IPC handlers
 */
export function registerAnomalyFixHandlers(): void {
  // Start an anomaly fix
  ipcMain.handle(
    IPC_CHANNELS.ANOMALY_FIX_START,
    async (_, request: AnomalyFixRequest): Promise<IPCResult<AnomalyFixResponse>> => {
      try {
        const project = projectStore.getProject(request.projectId);
        if (!project) {
          return { success: false, error: 'Project not found' };
        }

        const autoClaudeRoot = findAutoClaudeRoot(project.path);
        if (!autoClaudeRoot) {
          return {
            success: false,
            error: 'Could not find Auto-Claude installation. Ensure fix_anomaly.py exists.'
          };
        }

        // Create unique fix ID
        const fixId = uuidv4();

        // Initialize fix state
        const state: AnomalyFixState = {
          fixId,
          specId: request.specId,
          anomaly: request.anomaly,
          status: 'starting',
          logs: [createLogEntry('info', 'Starting anomaly fix...')],
          startTime: new Date().toISOString()
        };
        fixStates.set(fixId, state);

        // Send initial log
        sendLogEntry(fixId, state.logs[0]);

        // Start the fix script asynchronously
        setImmediate(() => {
          state.status = 'running';
          runFixScript(fixId, request, autoClaudeRoot);
        });

        return {
          success: true,
          data: { fixId, success: true }
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to start anomaly fix'
        };
      }
    }
  );

  // Cancel a running fix
  ipcMain.handle(
    IPC_CHANNELS.ANOMALY_FIX_CANCEL,
    async (_, fixId: string): Promise<IPCResult<void>> => {
      try {
        const child = activeFixes.get(fixId);
        if (child) {
          child.kill('SIGTERM');
          activeFixes.delete(fixId);

          const state = fixStates.get(fixId);
          if (state) {
            state.status = 'cancelled';
            state.endTime = new Date().toISOString();
            state.logs.push(createLogEntry('info', 'Fix cancelled by user'));
            sendLogEntry(fixId, state.logs[state.logs.length - 1]);
          }

          return { success: true };
        }

        return { success: false, error: 'Fix not found or already completed' };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to cancel fix'
        };
      }
    }
  );

  // Get current fix state
  ipcMain.handle(
    IPC_CHANNELS.ANOMALY_FIX_GET_STATE,
    async (_, fixId: string): Promise<IPCResult<AnomalyFixState>> => {
      const state = fixStates.get(fixId);
      if (!state) {
        return { success: false, error: 'Fix not found' };
      }
      return { success: true, data: state };
    }
  );
}

/**
 * Clean up old fix states (call periodically)
 */
export function cleanupOldFixStates(maxAgeMs: number = 3600000): void {
  const now = Date.now();
  for (const [fixId, state] of fixStates.entries()) {
    const endTime = state.endTime ? new Date(state.endTime).getTime() : now;
    if (now - endTime > maxAgeMs) {
      fixStates.delete(fixId);
    }
  }
}
