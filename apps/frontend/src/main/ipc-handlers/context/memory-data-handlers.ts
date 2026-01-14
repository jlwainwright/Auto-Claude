import { ipcMain } from 'electron';
import type { BrowserWindow } from 'electron';
import path from 'path';
import { existsSync, readFileSync, readdirSync, statSync } from 'fs';
import { IPC_CHANNELS, getSpecsDir } from '../../../shared/constants';
import type {
  IPCResult,
  MemoryEpisode,
  ContextSearchResult,
  MemoryGraphData,
  MemoryStorageStats,
} from '../../../shared/types';
import { projectStore } from '../../project-store';
import { getMemoryService, isKuzuAvailable } from '../../memory-service';
import {
  loadProjectEnvVars,
  isGraphitiEnabled,
  getGraphitiDatabaseDetails
} from './utils';

/**
 * Load file-based memories from spec directories
 */
export function loadFileBasedMemories(
  specsDir: string,
  limit: number
): MemoryEpisode[] {
  const memories: MemoryEpisode[] = [];

  if (!existsSync(specsDir)) {
    return memories;
  }

  const recentSpecDirs = readdirSync(specsDir)
    .filter((f: string) => {
      const specPath = path.join(specsDir, f);
      return statSync(specPath).isDirectory();
    })
    .sort()
    .reverse()
    .slice(0, 10); // Last 10 specs

  for (const specDir of recentSpecDirs) {
    const memoryDir = path.join(specsDir, specDir, 'memory');
    if (!existsSync(memoryDir)) continue;

    // Load session insights
    const sessionInsightsDir = path.join(memoryDir, 'session_insights');
    if (existsSync(sessionInsightsDir)) {
      const sessionFiles = readdirSync(sessionInsightsDir)
        .filter((f: string) => f.startsWith('session_') && f.endsWith('.json'))
        .sort()
        .reverse();

      for (const sessionFile of sessionFiles.slice(0, 3)) {
        try {
          const sessionPath = path.join(sessionInsightsDir, sessionFile);
          const sessionContent = readFileSync(sessionPath, 'utf-8');
          const sessionData = JSON.parse(sessionContent);

          if (sessionData.session_number !== undefined) {
            memories.push({
              id: `${specDir}-${sessionFile}`,
              type: 'session_insight',
              timestamp: sessionData.timestamp || new Date().toISOString(),
              content: JSON.stringify({
                discoveries: sessionData.discoveries,
                what_worked: sessionData.what_worked,
                what_failed: sessionData.what_failed,
                recommendations: sessionData.recommendations_for_next_session,
                subtasks_completed: sessionData.subtasks_completed
              }, null, 2),
              session_number: sessionData.session_number
            });
          }
        } catch {
          // Skip invalid files
        }
      }
    }

    // Load codebase map
    const codebaseMapPath = path.join(memoryDir, 'codebase_map.json');
    if (existsSync(codebaseMapPath)) {
      try {
        const mapContent = readFileSync(codebaseMapPath, 'utf-8');
        const mapData = JSON.parse(mapContent);
        if (mapData.discovered_files && Object.keys(mapData.discovered_files).length > 0) {
          memories.push({
            id: `${specDir}-codebase_map`,
            type: 'codebase_map',
            timestamp: mapData.last_updated || new Date().toISOString(),
            content: JSON.stringify(mapData.discovered_files, null, 2),
            session_number: undefined
          });
        }
      } catch {
        // Skip invalid files
      }
    }
  }

  return memories.slice(0, limit);
}

/**
 * Search file-based memories for a query
 */
export function searchFileBasedMemories(
  specsDir: string,
  query: string,
  limit: number
): ContextSearchResult[] {
  const results: ContextSearchResult[] = [];
  const queryLower = query.toLowerCase();

  if (!existsSync(specsDir)) {
    return results;
  }

  const allSpecDirs = readdirSync(specsDir)
    .filter((f: string) => {
      const specPath = path.join(specsDir, f);
      return statSync(specPath).isDirectory();
    });

  for (const specDir of allSpecDirs) {
    const memoryDir = path.join(specsDir, specDir, 'memory');
    if (!existsSync(memoryDir)) continue;

    const memoryFiles = readdirSync(memoryDir)
      .filter((f: string) => f.endsWith('.json'));

    for (const memFile of memoryFiles) {
      try {
        const memPath = path.join(memoryDir, memFile);
        const memContent = readFileSync(memPath, 'utf-8');

        if (memContent.toLowerCase().includes(queryLower)) {
          const memData = JSON.parse(memContent);
          results.push({
            content: JSON.stringify(memData.insights || memData, null, 2),
            score: 1.0,
            type: 'session_insight'
          });
        }
      } catch {
        // Skip invalid files
      }
    }
  }

  return results.slice(0, limit);
}

/**
 * Register memory data handlers
 */
export function registerMemoryDataHandlers(
  _getMainWindow: () => BrowserWindow | null
): void {
  // Get all memories
  ipcMain.handle(
    IPC_CHANNELS.CONTEXT_GET_MEMORIES,
    async (_, projectId: string, limit: number = 20): Promise<IPCResult<MemoryEpisode[]>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      const projectEnvVars = loadProjectEnvVars(project.path, project.autoBuildPath);
      const graphitiEnabled = isGraphitiEnabled(projectEnvVars);

      // Try LadybugDB first if available
      if (graphitiEnabled && isKuzuAvailable()) {
        try {
          const dbDetails = getGraphitiDatabaseDetails(projectEnvVars);
          const memoryService = getMemoryService({
            dbPath: dbDetails.dbPath,
            database: dbDetails.database,
          });
          const graphMemories = await memoryService.getEpisodicMemories(limit);
          if (graphMemories.length > 0) {
            return { success: true, data: graphMemories };
          }
        } catch (error) {
          console.warn('Failed to get memories from LadybugDB, falling back to file-based:', error);
        }
      }

      // Fall back to file-based memories
      const specsBaseDir = getSpecsDir(project.autoBuildPath);
      const specsDir = path.join(project.path, specsBaseDir);
      const memories = loadFileBasedMemories(specsDir, limit);

      return { success: true, data: memories };
    }
  );

  // Search memories
  ipcMain.handle(
    IPC_CHANNELS.CONTEXT_SEARCH_MEMORIES,
    async (_, projectId: string, query: string): Promise<IPCResult<ContextSearchResult[]>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      const projectEnvVars = loadProjectEnvVars(project.path, project.autoBuildPath);
      const graphitiEnabled = isGraphitiEnabled(projectEnvVars);

      // Try LadybugDB search if available
      if (graphitiEnabled && isKuzuAvailable()) {
        try {
          const dbDetails = getGraphitiDatabaseDetails(projectEnvVars);
          const memoryService = getMemoryService({
            dbPath: dbDetails.dbPath,
            database: dbDetails.database,
          });
          const graphResults = await memoryService.searchMemories(query, 20);
          if (graphResults.length > 0) {
            return {
              success: true,
              data: graphResults.map(r => ({
                content: r.content,
                score: r.score || 1.0,
                type: r.type
              }))
            };
          }
        } catch (error) {
          console.warn('Failed to search LadybugDB, falling back to file-based:', error);
        }
      }

      // Fall back to file-based search
      const specsBaseDir = getSpecsDir(project.autoBuildPath);
      const specsDir = path.join(project.path, specsBaseDir);
      const results = searchFileBasedMemories(specsDir, query, 20);

      return { success: true, data: results };
    }
  );

  // Get graph data for visualization
  ipcMain.handle(
    IPC_CHANNELS.CONTEXT_GET_GRAPH_DATA,
    async (_, projectId: string): Promise<IPCResult<MemoryGraphData>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      const projectEnvVars = loadProjectEnvVars(project.path, project.autoBuildPath);
      const graphitiEnabled = isGraphitiEnabled(projectEnvVars);

      // Graph data is only available from LadybugDB
      if (!graphitiEnabled || !isKuzuAvailable()) {
        return {
          success: false,
          error: 'Graph data requires LadybugDB to be enabled and available'
        };
      }

      try {
        const dbDetails = getGraphitiDatabaseDetails(projectEnvVars);
        const memoryService = getMemoryService({
          dbPath: dbDetails.dbPath,
          database: dbDetails.database,
        });
        const graphData = await memoryService.getGraphData();
        return { success: true, data: graphData };
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : 'Failed to get graph data';
        console.error('Failed to get graph data:', errorMsg);
        return { success: false, error: errorMsg };
      }
    }
  );

  // Get memory storage statistics
  ipcMain.handle(
    IPC_CHANNELS.CONTEXT_GET_MEMORY_STATS,
    async (_, projectId: string): Promise<IPCResult<MemoryStorageStats>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      const projectEnvVars = loadProjectEnvVars(project.path, project.autoBuildPath);
      const graphitiEnabled = isGraphitiEnabled(projectEnvVars);

      // Stats are only available from LadybugDB
      if (!graphitiEnabled || !isKuzuAvailable()) {
        return {
          success: false,
          error: 'Memory stats require LadybugDB to be enabled and available'
        };
      }

      try {
        const dbDetails = getGraphitiDatabaseDetails(projectEnvVars);
        const memoryService = getMemoryService({
          dbPath: dbDetails.dbPath,
          database: dbDetails.database,
        });
        const stats = await memoryService.getStorageStats();
        if (!stats) {
          return { success: false, error: 'Failed to retrieve storage stats' };
        }
        return { success: true, data: stats };
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : 'Failed to get memory stats';
        console.error('Failed to get memory stats:', errorMsg);
        return { success: false, error: errorMsg };
      }
    }
  );

  // Delete a memory episode
  ipcMain.handle(
    IPC_CHANNELS.CONTEXT_DELETE_MEMORY,
    async (_, projectId: string, memoryId: string): Promise<IPCResult<void>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      if (!memoryId) {
        return { success: false, error: 'Memory ID is required' };
      }

      const projectEnvVars = loadProjectEnvVars(project.path, project.autoBuildPath);
      const graphitiEnabled = isGraphitiEnabled(projectEnvVars);

      // Delete is only available from LadybugDB
      if (!graphitiEnabled || !isKuzuAvailable()) {
        return {
          success: false,
          error: 'Memory deletion requires LadybugDB to be enabled and available'
        };
      }

      try {
        const dbDetails = getGraphitiDatabaseDetails(projectEnvVars);
        const memoryService = getMemoryService({
          dbPath: dbDetails.dbPath,
          database: dbDetails.database,
        });
        const result = await memoryService.deleteMemory(memoryId);
        if (!result.success) {
          return { success: false, error: result.error || 'Failed to delete memory' };
        }
        return { success: true, data: undefined };
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : 'Failed to delete memory';
        console.error('Failed to delete memory:', errorMsg);
        return { success: false, error: errorMsg };
      }
    }
  );

  // Update a memory episode
  ipcMain.handle(
    IPC_CHANNELS.CONTEXT_UPDATE_MEMORY,
    async (_, projectId: string, memoryId: string, content: string): Promise<IPCResult<void>> => {
      const project = projectStore.getProject(projectId);
      if (!project) {
        return { success: false, error: 'Project not found' };
      }

      if (!memoryId) {
        return { success: false, error: 'Memory ID is required' };
      }

      if (!content) {
        return { success: false, error: 'Content is required' };
      }

      const projectEnvVars = loadProjectEnvVars(project.path, project.autoBuildPath);
      const graphitiEnabled = isGraphitiEnabled(projectEnvVars);

      // Update is only available from LadybugDB
      if (!graphitiEnabled || !isKuzuAvailable()) {
        return {
          success: false,
          error: 'Memory update requires LadybugDB to be enabled and available'
        };
      }

      try {
        const dbDetails = getGraphitiDatabaseDetails(projectEnvVars);
        const memoryService = getMemoryService({
          dbPath: dbDetails.dbPath,
          database: dbDetails.database,
        });
        const result = await memoryService.updateMemory(memoryId, content);
        if (!result.success) {
          return { success: false, error: result.error || 'Failed to update memory' };
        }
        return { success: true, data: undefined };
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : 'Failed to update memory';
        console.error('Failed to update memory:', errorMsg);
        return { success: false, error: errorMsg };
      }
    }
  );
}
