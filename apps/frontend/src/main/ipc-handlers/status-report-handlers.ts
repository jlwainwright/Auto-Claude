/**
 * Status Report IPC Handlers
 *
 * Handles generating status reports for Auto-Claude projects.
 * Runs the Python script auto_claude_status_report.py to generate JSON reports.
 */

import { ipcMain, app } from 'electron';
import { spawn } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';
import { IPC_CHANNELS } from '../../shared/constants';
import type { IPCResult, StatusReport, StatusSummaryQuick } from '../../shared/types';
import { projectStore } from '../project-store';

// Path to the status report script (relative to Auto-Claude root)
const STATUS_REPORT_SCRIPT = 'scripts/auto_claude_status_report.py';

/**
 * Find the Auto-Claude installation root by looking for the scripts directory.
 * Tries multiple strategies to locate the script.
 */
function findAutoClaudeRoot(projectPath: string): string | null {
  // Strategy 1: Walk up from project path (for projects inside Auto-Claude tree)
  let searchDir = path.resolve(projectPath);
  for (let i = 0; i < 15; i++) {
    const scriptsPath = path.join(searchDir, 'scripts', 'auto_claude_status_report.py');
    if (existsSync(scriptsPath)) {
      return searchDir;
    }
    const parent = path.dirname(searchDir);
    if (parent === searchDir) break; // reached filesystem root
    searchDir = parent;
  }

  // Strategy 2: Check relative to app installation (development mode)
  // In dev: apps/frontend/dist -> ../../scripts
  // In prod: app.asar -> ../scripts (outside asar)
  let appRoot = app.getAppPath();
  // If we're in an .asar package, we need to look outside
  if (appRoot.endsWith('.asar')) {
    appRoot = path.dirname(appRoot);
  }

  // Check common relative paths from app directory
  const relativePaths = [
    '../../..',  // From apps/frontend/dist to Auto-Claude root
    '../..',     // From frontend to root
    '..',        // Already at root
  ];

  for (const relPath of relativePaths) {
    const tryPath = path.resolve(appRoot, relPath);
    const scriptsPath = path.join(tryPath, 'scripts', 'auto_claude_status_report.py');
    if (existsSync(scriptsPath)) {
      return tryPath;
    }
  }

  // Strategy 3: Check user's DevFolder (common development setup)
  const homeDir = path.dirname(appRoot); // e.g., /Users/jacques/DevFolder
  const autoClaudePath = path.join(homeDir, 'Auto-Claude');
  const scriptsPath = path.join(autoClaudePath, 'scripts', 'auto_claude_status_report.py');
  if (existsSync(scriptsPath)) {
    return autoClaudePath;
  }

  return null;
}

/**
 * Run the status report Python script and return the JSON output
 */
async function runStatusReportScript(
  projectPath: string,
  autoClaudeDir?: string
): Promise<StatusReport> {
  return new Promise((resolve, reject) => {
    // Use provided autoClaudeDir or find Auto-Claude installation root
    const autoClaudeRoot = autoClaudeDir || findAutoClaudeRoot(projectPath);

    if (!autoClaudeRoot) {
      return reject(new Error(
        'Could not find auto_claude_status_report.py. ' +
        'Ensure Auto-Claude is properly installed.'
      ));
    }

    const scriptPath = path.join(autoClaudeRoot, STATUS_REPORT_SCRIPT);
    const autoClaudePath = autoClaudeDir || path.join(projectPath, '.auto-claude');

    const pythonExe = process.platform === 'win32' ? 'python' : 'python3';

    const args: string[] = [
      scriptPath,
      '--auto-claude',
      autoClaudePath,
      '--pretty'
    ];

    const child = spawn(pythonExe, args, {
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
          const report = JSON.parse(stdout) as StatusReport;
          resolve(report);
        } catch (e) {
          reject(new Error(`Failed to parse status report JSON: ${e}`));
        }
      } else {
        reject(new Error(`Status report script failed (code ${code}): ${stderr}`));
      }
    });

    child.on('error', (err) => {
      reject(new Error(`Failed to run status report script: ${err.message}`));
    });
  });
}

/**
 * Register all status report IPC handlers
 */
export function registerStatusReportHandlers(): void {
  // Generate full status report
  ipcMain.handle(
    IPC_CHANNELS.STATUS_REPORT_GENERATE,
    async (_, projectId: string): Promise<IPCResult<StatusReport>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        const report = await runStatusReportScript(project.path);
        return { success: true, data: report };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to generate status report'
        };
      }
    }
  );

  // Get quick summary (lighter version)
  ipcMain.handle(
    IPC_CHANNELS.STATUS_REPORT_GET_SUMMARY,
    async (_, projectId: string): Promise<IPCResult<StatusSummaryQuick>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      try {
        const report = await runStatusReportScript(project.path);

        // Extract summary information
        const anomaliesBySeverity = { error: 0, warning: 0, info: 0 };
        for (const spec of report.specs) {
          for (const anomaly of spec.anomalies) {
            if (anomaly.severity in anomaliesBySeverity) {
              anomaliesBySeverity[anomaly.severity as keyof typeof anomaliesBySeverity]++;
            }
          }
        }

        const summary: StatusSummaryQuick = {
          total_specs: report.summary.spec_count,
          by_status: report.summary.status_counts,
          total_anomalies: report.summary.anomaly_count,
          error_count: anomaliesBySeverity.error,
          warning_count: anomaliesBySeverity.warning,
          info_count: anomaliesBySeverity.info,
          last_updated: report.generated_at
        };

        return { success: true, data: summary };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Failed to get status summary'
        };
      }
    }
  );
}
