import { useEffect, useState, useCallback, useRef } from 'react';
import {
  loadProjectContext,
  refreshProjectIndex,
  searchMemories
} from '../../stores/context-store';
import type { MemoryGraphData, MemoryGraphNode, MemoryGraphEdge, MemoryStorageStats } from '../../../shared/types';

export function useProjectContext(projectId: string) {
  useEffect(() => {
    if (projectId) {
      loadProjectContext(projectId);
    }
  }, [projectId]);
}

export function useRefreshIndex(projectId: string) {
  return async () => {
    await refreshProjectIndex(projectId);
  };
}

export function useMemorySearch(projectId: string) {
  return async (query: string) => {
    if (query.trim()) {
      await searchMemories(projectId, query);
    }
  };
}

/**
 * Custom hook for managing graph data fetching, caching, and state management.
 *
 * Features:
 * - Fetches graph data (nodes, edges, stats) from the backend
 * - Caches data to avoid unnecessary re-fetches
 * - Provides loading and error states
 * - Returns refresh function for manual re-fetching
 * - Auto-refetches when projectId changes
 *
 * @param projectId - The project ID to fetch graph data for
 * @returns Graph data state and refresh function
 *
 * @example
 * ```tsx
 * const { graphData, loading, error, refresh } = useMemoryGraph(projectId);
 *
 * if (loading) return <Spinner />;
 * if (error) return <Error message={error} />;
 * if (!graphData) return <EmptyState />;
 *
 * return <GraphView data={graphData} />;
 * ```
 */
export function useMemoryGraph(projectId: string) {
  const [graphData, setGraphData] = useState<MemoryGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Cache for storing fetched data to avoid unnecessary re-fetches
  const cacheRef = useRef<Map<string, MemoryGraphData>>(new Map());
  // Track if a fetch is in progress to avoid duplicate requests
  const fetchingRef = useRef<Set<string>>(new Set());

  /**
   * Fetches graph data from the backend with caching support
   */
  const fetchGraphData = useCallback(async (id: string, useCache = true) => {
    if (!id) {
      setGraphData(null);
      setLoading(false);
      setError(null);
      return;
    }

    // Check cache first if caching is enabled
    if (useCache && cacheRef.current.has(id)) {
      setGraphData(cacheRef.current.get(id)!);
      setLoading(false);
      setError(null);
      return;
    }

    // Prevent duplicate fetches
    if (fetchingRef.current.has(id)) {
      return;
    }

    fetchingRef.current.add(id);
    setLoading(true);
    setError(null);

    try {
      const result = await window.electronAPI.getGraphData(id);
      if (result.success && result.data) {
        const data = result.data;
        setGraphData(data);
        // Cache the result
        cacheRef.current.set(id, data);
      } else {
        setError(result.error || 'Failed to load graph data');
        setGraphData(null);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      setGraphData(null);
    } finally {
      setLoading(false);
      fetchingRef.current.delete(id);
    }
  }, []);

  /**
   * Refreshes graph data by bypassing the cache
   */
  const refresh = useCallback(async () => {
    if (projectId) {
      await fetchGraphData(projectId, false);
    }
  }, [projectId, fetchGraphData]);

  /**
   * Clears the cache for a specific project or all projects
   */
  const clearCache = useCallback((id?: string) => {
    if (id) {
      cacheRef.current.delete(id);
    } else {
      cacheRef.current.clear();
    }
  }, []);

  // Fetch data when projectId changes
  useEffect(() => {
    fetchGraphData(projectId);
  }, [projectId, fetchGraphData]);

  return {
    /** Graph data containing nodes, edges, and optional stats */
    graphData,
    /** Nodes from the graph (convenience accessor) */
    nodes: graphData?.nodes || [],
    /** Edges from the graph (convenience accessor) */
    edges: graphData?.edges || [],
    /** Statistics about memory storage (if available) */
    stats: graphData?.stats,
    /** Total node count (convenience accessor) */
    nodeCount: graphData?.nodeCount || graphData?.nodes?.length || 0,
    /** Total edge count (convenience accessor) */
    edgeCount: graphData?.edgeCount || graphData?.edges?.length || 0,
    /** Whether data is currently being fetched */
    loading,
    /** Error message if fetch failed */
    error,
    /** Function to manually refresh the data (bypasses cache) */
    refresh,
    /** Function to clear the cache */
    clearCache
  };
}
