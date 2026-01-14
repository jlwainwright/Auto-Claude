/**
 * Mock implementation for context and memory operations
 */

export const contextMock = {
  getProjectContext: async () => ({
    success: true,
    data: {
      projectIndex: null,
      memoryStatus: null,
      memoryState: null,
      recentMemories: [],
      isLoading: false
    }
  }),

  refreshProjectIndex: async () => ({
    success: false,
    error: 'Not available in browser mock'
  }),

  getMemoryStatus: async () => ({
    success: true,
    data: {
      enabled: false,
      available: false,
      reason: 'Browser mock environment'
    }
  }),

  searchMemories: async () => ({
    success: true,
    data: []
  }),

  getRecentMemories: async () => ({
    success: true,
    data: []
  }),

  getGraphData: async () => ({
    success: true,
    data: {
      nodes: [],
      edges: [],
      stats: {
        episode_count: 0,
        entity_count: 0,
        edge_count: 0,
        storage_bytes: 0,
        storage_human: '0 B'
      },
      nodeCount: 0,
      edgeCount: 0
    }
  }),

  getMemoryStats: async () => ({
    success: true,
    data: {
      episode_count: 0,
      entity_count: 0,
      edge_count: 0,
      storage_bytes: 0,
      storage_human: '0 B'
    }
  }),

  deleteMemory: async () => ({
    success: false,
    error: 'Not available in browser mock'
  }),

  updateMemory: async () => ({
    success: false,
    error: 'Not available in browser mock'
  })
};
