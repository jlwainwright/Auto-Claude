import { ipcMain } from 'electron';
import { spawn } from 'child_process';
import { IPC_CHANNELS } from '../../shared/constants';
import type { IPCResult, StatusReport, AnomalyFixPlanRequest, AnomalyFixPlanResponse } from '../../shared/types';
import { projectStore } from '../project-store';
import { PythonEnvManager } from '../python-env-manager';
import { getEffectiveSourcePath } from '../updater/path-resolver';
import path from 'path';

/**
 * Register status report IPC handlers
 */
export function registerStatusReportHandlers(pythonEnvManager: PythonEnvManager): void {
  // Generate status report
  ipcMain.handle(IPC_CHANNELS.STATUS_REPORT_GENERATE, async (_event, projectId: string): Promise<IPCResult<StatusReport>> => {
    try {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      const sourcePath = getEffectiveSourcePath();
      const scriptPath = path.join(sourcePath, 'scripts', 'auto_claude_status_report.py');
      const pythonPath = pythonEnvManager.getPythonPath();

      if (!pythonPath) {
        return { success: false, error: 'Python environment not ready' };
      }

      return new Promise((resolve) => {
        const child = spawn(pythonPath, [scriptPath], {
          cwd: project.path,
          env: {
            ...process.env,
            AUTO_CLAUDE_PROJECT_PATH: project.path,
          },
        });

        let stdout = '';
        let stderr = '';

        child.stdout.on('data', (data) => {
          stdout += data.toString();
        });

        child.stderr.on('data', (data) => {
          stderr += data.toString();
        });

        child.on('close', (code) => {
          if (code !== 0) {
            resolve({ success: false, error: stderr || `Script exited with code ${code}` });
            return;
          }

          try {
            const report = JSON.parse(stdout) as StatusReport;
            resolve({ success: true, data: report });
          } catch (error) {
            resolve({ success: false, error: `Failed to parse report: ${error}` });
          }
        });

        child.on('error', (error) => {
          resolve({ success: false, error: `Failed to spawn script: ${error.message}` });
        });
      });
    } catch (error) {
      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  });

  // Plan fix for an anomaly
  ipcMain.handle(
    IPC_CHANNELS.STATUS_REPORT_ANOMALY_FIX_PLAN,
    async (_event, request: AnomalyFixPlanRequest): Promise<IPCResult<AnomalyFixPlanResponse>> => {
      try {
        const sourcePath = getEffectiveSourcePath();
        const scriptPath = path.join(sourcePath, 'scripts', 'fix_anomaly.py');
        const pythonPath = pythonEnvManager.getPythonPath();

        if (!pythonPath) {
          return { success: false, error: 'Python environment not ready' };
        }

        return new Promise((resolve) => {
          const child = spawn(pythonPath, [scriptPath, '--plan'], {
            cwd: request.projectPath,
            env: {
              ...process.env,
              AUTO_CLAUDE_PROJECT_PATH: request.projectPath,
            },
          });

          let stdout = '';
          let stderr = '';

          // Send request as JSON to stdin
          child.stdin.write(JSON.stringify(request));
          child.stdin.end();

          child.stdout.on('data', (data) => {
            stdout += data.toString();
          });

          child.stderr.on('data', (data) => {
            stderr += data.toString();
          });

          child.on('close', (code) => {
            if (code !== 0) {
              resolve({
                success: false,
                data: { success: false, error: stderr || `Script exited with code ${code}` },
              });
              return;
            }

            try {
              const plan = JSON.parse(stdout);
              resolve({
                success: true,
                data: { success: true, plan },
              });
            } catch (error) {
              resolve({
                success: false,
                data: { success: false, error: `Failed to parse plan: ${error}` },
              });
            }
          });

          child.on('error', (error) => {
            resolve({
              success: false,
              data: { success: false, error: `Failed to spawn script: ${error.message}` },
            });
          });
        });
      } catch (error) {
        return {
          success: false,
          data: { success: false, error: error instanceof Error ? error.message : String(error) },
        };
      }
    }
  );

  // Apply fix for an anomaly
  ipcMain.handle(
    IPC_CHANNELS.STATUS_REPORT_ANOMALY_FIX_APPLY,
    async (_event, request: AnomalyFixPlanRequest): Promise<IPCResult<{ success: boolean; error?: string }>> => {
      try {
        const sourcePath = getEffectiveSourcePath();
        const scriptPath = path.join(sourcePath, 'scripts', 'fix_anomaly.py');
        const pythonPath = pythonEnvManager.getPythonPath();

        if (!pythonPath) {
          return { success: false, error: 'Python environment not ready' };
        }

        return new Promise((resolve) => {
          const child = spawn(pythonPath, [scriptPath, '--apply'], {
            cwd: request.projectPath,
            env: {
              ...process.env,
              AUTO_CLAUDE_PROJECT_PATH: request.projectPath,
            },
          });

          let stdout = '';
          let stderr = '';

          // Send request as JSON to stdin
          child.stdin.write(JSON.stringify(request));
          child.stdin.end();

          child.stdout.on('data', (data) => {
            stdout += data.toString();
          });

          child.stderr.on('data', (data) => {
            stderr += data.toString();
          });

          child.on('close', (code) => {
            if (code !== 0) {
              resolve({ success: false, error: stderr || `Script exited with code ${code}` });
              return;
            }

            try {
              const result = JSON.parse(stdout);
              resolve({ success: result.success || false, error: result.error });
            } catch (error) {
              resolve({ success: false, error: `Failed to parse result: ${error}` });
            }
          });

          child.on('error', (error) => {
            resolve({ success: false, error: `Failed to spawn script: ${error.message}` });
          });
        });
      } catch (error) {
        return { success: false, error: error instanceof Error ? error.message : String(error) };
      }
    }
  );
}
