/**
 * Recovery IPC Handlers
 *
 * Handles recovery from orphaned .auto-claude-status files and agent crashes.
 * Runs the Python script recover_orphaned_status.py to reset orphaned states.
 */

import { ipcMain } from 'electron';
import { spawn } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';
import { IPC_CHANNELS } from '../../shared/constants';
import type { IPCResult } from '../../shared/types';
import { projectStore } from '../project-store';

// Path to the recovery script (relative to Auto-Claude root)
const RECOVERY_SCRIPT = 'scripts/recover_orphaned_status.py';

/**
 * Find the Auto-Claude installation root
 * Uses multiple search strategies to locate the installation
 */
function findAutoClaudeRoot(projectPath: string): string | null {
  // Strategy 1: Walk up from project path (up to 15 levels)
  let searchDir = path.resolve(projectPath);
  for (let i = 0; i < 15; i++) {
    const scriptsPath = path.join(searchDir, 'scripts', 'recover_orphaned_status.py');
    if (existsSync(scriptsPath)) {
      return searchDir;
    }
    const parent = path.dirname(searchDir);
    if (parent === searchDir) break;
    searchDir = parent;
  }

  // Strategy 2: Check relative to app installation (go up from app to find repo root)
  const appRoot = path.join(__dirname, '..', '..', '..', '..', '..');
  for (let i = 0; i < 5; i++) {
    const checkPath = path.resolve(appRoot, ...Array(i).fill('..'), 'scripts', 'recover_orphaned_status.py');
    const rootDir = path.resolve(path.dirname(checkPath), '..');
    if (existsSync(checkPath)) {
      return rootDir;
    }
  }

  // Strategy 3: Check DevFolder (specific to user's setup)
  const devFolderPath = '/Users/jacques/DevFolder/Auto-Claude';
  const devFolderScript = path.join(devFolderPath, 'scripts', 'recover_orphaned_status.py');
  if (existsSync(devFolderScript)) {
    return devFolderPath;
  }

  // Strategy 4: Check common Auto-Claude fork paths
  const commonPaths = [
    '/Users/jacques/DevFolder/Auto-Claude',
    path.join(process.env.HOME || '', 'DevFolder', 'Auto-Claude'),
    path.join(process.env.HOME || '', 'Projects', 'Auto-Claude'),
  ];

  for (const checkPath of commonPaths) {
    const scriptPath = path.join(checkPath, 'scripts', 'recover_orphaned_status.py');
    if (existsSync(scriptPath)) {
      return checkPath;
    }
  }

  return null;
}

/**
 * Recovery result type
 */
interface RecoveryResult {
  success: boolean;
  actions_taken: string[];
  summary: string;
  error?: string;
}

/**
 * Run the recovery script
 */
async function runRecoveryScript(
  autoClaudeRoot: string,
  autoClaudeDir: string,
  specId: string
): Promise<RecoveryResult> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(autoClaudeRoot, RECOVERY_SCRIPT);
    const pythonExe = process.platform === 'win32' ? 'python' : 'python3';

    const child = spawn(pythonExe, [scriptPath, autoClaudeDir, specId, '--json'], {
      cwd: autoClaudeRoot,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });

    let stdout = '';
    let stderr = '';

    child.stdout?.on('data', (data) => {
      stdout += data.toString();
    });

    child.stderr?.on('data', (data) => {
      stderr += data.toString();
    });

    child.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout) as RecoveryResult;
          resolve(result);
        } catch (e) {
          reject(new Error(`Failed to parse recovery script output: ${e}`));
        }
      } else {
        reject(new Error(`Recovery script failed (code ${code}): ${stderr}`));
      }
    });

    child.on('error', (err) => {
      reject(new Error(`Failed to run recovery script: ${err.message}`));
    });
  });
}

/**
 * Register all recovery IPC handlers
 */
export function registerRecoveryHandlers(): void {
  // Recover orphaned status
  ipcMain.handle(
    IPC_CHANNELS.RECOVER_ORPHANED_STATUS,
    async (_, projectId: string, specId: string): Promise<IPCResult<RecoveryResult>> => {
      try {
        const project = projectStore.getProject(projectId);
        if (!project) {
          return { success: false, error: 'Project not found' };
        }

        const autoClaudeRoot = findAutoClaudeRoot(project.path);
        if (!autoClaudeRoot) {
          return {
            success: false,
            error: 'Could not find Auto-Claude installation. Ensure recover_orphaned_status.py exists.'
          };
        }

        // Use .auto-claude directory in project path
        const autoClaudeDir = path.join(project.path, '.auto-claude');

        const result = await runRecoveryScript(autoClaudeRoot, autoClaudeDir, specId);

        return {
          success: true,
          data: result
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to recover orphaned status'
        };
      }
    }
  );
}
