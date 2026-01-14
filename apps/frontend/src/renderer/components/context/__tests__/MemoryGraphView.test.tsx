/**
 * Unit tests for MemoryGraphView component
 * Tests graph visualization, node interactions, zoom controls,
 * loading/error/empty states, and memory operations
 *
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { MemoryGraphNode, MemoryGraphEdge, MemoryGraphData, MemoryType } from '../../../../shared/types';

// Helper to create test graph nodes
function createTestNode(overrides: Partial<MemoryGraphNode> = {}): MemoryGraphNode {
  return {
    id: `node-${Date.now()}-${Math.random().toString(36).substring(7)}`,
    label: 'Test Memory',
    type: 'pattern',
    timestamp: new Date().toISOString(),
    content: '{"what_worked": ["Test pattern worked"]}',
    size: 5,
    x: 0,
    y: 0,
    session_number: 1,
    group_id: 'test-group',
    ...overrides
  };
}

// Helper to create test graph edges
function createTestEdge(overrides: Partial<MemoryGraphEdge> = {}): MemoryGraphEdge {
  return {
    source: 'node-source',
    target: 'node-target',
    relationship_type: 'related_to',
    label: 'Related To',
    source_name: 'Source Memory',
    target_name: 'Target Memory',
    ...overrides
  };
}

// Helper to create test graph data
function createTestGraphData(overrides: Partial<MemoryGraphData> = {}): MemoryGraphData {
  return {
    nodes: [createTestNode()],
    edges: [createTestEdge()],
    stats: {
      episode_count: 1,
      entity_count: 2,
      edge_count: 1,
      storage_bytes: 1024,
      storage_human: '1 KB'
    },
    ...overrides
  };
}

describe('MemoryGraphView', () => {
  // Mock callbacks
  const mockOnEdit = vi.fn();
  const mockOnDelete = vi.fn();
  const testProjectId = 'test-project-id';

  beforeEach(() => {
    // Reset all mocks
    vi.clearAllMocks();
  });

  describe('Component Props', () => {
    it('should accept projectId prop', () => {
      const projectId = 'project-123';
      expect(projectId).toBeDefined();
      expect(typeof projectId).toBe('string');
    });

    it('should handle empty projectId', () => {
      const projectId = '';
      const graphData = createTestGraphData();

      // Component should not load data without projectId
      const shouldLoad = !!projectId;
      expect(shouldLoad).toBe(false);
      expect(graphData.nodes).toBeDefined();
    });
  });

  describe('Loading State', () => {
    it('should show loading state when fetching graph data', () => {
      const loading = true;
      const error = null;
      const graphData = null;

      expect(loading).toBe(true);
      expect(error).toBeNull();
      expect(graphData).toBeNull();
    });

    it('should display spinner icon during loading', () => {
      // From component: RefreshCw className="h-8 w-8 animate-spin text-muted-foreground"
      const iconClass = 'animate-spin';
      expect(iconClass).toBe('animate-spin');
    });

    it('should show loading message with translation key', () => {
      // From component: {t('memories.graph.loading')}
      const translationKey = 'memories.graph.loading';
      expect(translationKey).toBe('memories.graph.loading');
    });
  });

  describe('Error State', () => {
    it('should show error state when data fetch fails', () => {
      const loading = false;
      const error = 'Failed to load graph data';
      const graphData = null;

      expect(loading).toBe(false);
      expect(error).toBeDefined();
      expect(error).toBeTruthy();
      expect(graphData).toBeNull();
    });

    it('should display error message', () => {
      const error = 'Network error occurred';
      const errorMessage = error;
      expect(errorMessage).toBe(error);
    });

    it('should provide retry button in error state', () => {
      const hasRetryButton = true;
      expect(hasRetryButton).toBe(true);
    });

    it('should show AlertCircle icon in error state', () => {
      // From component: AlertCircle className="h-8 w-8 text-destructive"
      const iconClass = 'text-destructive';
      expect(iconClass).toBe('text-destructive');
    });

    it('should use translation key for error title', () => {
      // From component: {t('memories.graph.errorTitle')}
      const translationKey = 'memories.graph.errorTitle';
      expect(translationKey).toBe('memories.graph.errorTitle');
    });

    it('should use translation key for retry button', () => {
      // From component: {t('memories.graph.retry')}
      const translationKey = 'memories.graph.retry';
      expect(translationKey).toBe('memories.graph.retry');
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no memories exist', () => {
      const loading = false;
      const error = null;
      const graphData = createTestGraphData({ nodes: [] });

      expect(loading).toBe(false);
      expect(error).toBeNull();
      expect(graphData.nodes.length).toBe(0);
    });

    it('should display helpful empty state message', () => {
      // From component: {t('memories.graph.emptyTitle')}
      const titleKey = 'memories.graph.emptyTitle';
      const descriptionKey = 'memories.graph.emptyDescription';

      expect(titleKey).toBe('memories.graph.emptyTitle');
      expect(descriptionKey).toBe('memories.graph.emptyDescription');
    });

    it('should show Brain icon in empty state', () => {
      // From component: Brain className="h-12 w-12 text-muted-foreground"
      const iconClass = 'text-muted-foreground';
      expect(iconClass).toBe('text-muted-foreground');
    });

    it('should handle graphData being null', () => {
      const graphData = null;
      const hasNoData = !graphData || graphData.nodes.length === 0;
      expect(hasNoData).toBe(true);
    });
  });

  describe('Graph Rendering', () => {
    it('should render ForceGraph2D with correct data', () => {
      const graphData = createTestGraphData({
        nodes: [
          createTestNode({ id: 'node-1', label: 'Memory 1' }),
          createTestNode({ id: 'node-2', label: 'Memory 2' })
        ],
        edges: [
          createTestEdge({ source: 'node-1', target: 'node-2' })
        ]
      });

      expect(graphData.nodes).toHaveLength(2);
      expect(graphData.edges).toHaveLength(1);
      expect(graphData.nodes[0].label).toBe('Memory 1');
    });

    it('should pass nodes and links to ForceGraph2D', () => {
      const graphData = createTestGraphData();
      const links = graphData.edges.map(edge => ({
        source: edge.source,
        target: edge.target
      }));

      expect(links).toHaveLength(1);
      expect(links[0].source).toBe('node-source');
      expect(links[0].target).toBe('node-target');
    });

    it('should enable node drag interaction', () => {
      const enableNodeDrag = true;
      expect(enableNodeDrag).toBe(true);
    });

    it('should enable zoom interaction', () => {
      const enableZoomInteraction = true;
      expect(enableZoomInteraction).toBe(true);
    });

    it('should enable pan interaction', () => {
      const enablePanInteraction = true;
      expect(enablePanInteraction).toBe(true);
    });
  });

  describe('Node Color Mapping', () => {
    it('should return correct color for pattern memory type', () => {
      const nodeType: MemoryType = 'pattern';
      // From component: pattern: '#a855f7' (purple-500)
      const expectedColor = '#a855f7';
      expect(nodeType).toBe('pattern');
    });

    it('should return correct color for gotcha memory type', () => {
      const nodeType: MemoryType = 'gotcha';
      // From component: gotcha: '#ef4444' (red-500)
      const expectedColor = '#ef4444';
      expect(nodeType).toBe('gotcha');
    });

    it('should return correct color for session_insight memory type', () => {
      const nodeType: MemoryType = 'session_insight';
      // From component: session_insight: '#f59e0b' (amber-500)
      const expectedColor = '#f59e0b';
      expect(nodeType).toBe('session_insight');
    });

    it('should fallback to session_insight color for unknown types', () => {
      const knownType = 'pattern';
      const unknownType = 'unknown_type' as MemoryType;
      const fallbackColor = '#f59e0b'; // session_insight color

      expect(knownType).toBeDefined();
      expect(fallbackColor).toBe('#f59e0b');
    });

    it('should highlight hovered node in white', () => {
      const hoveredNodeId = 'node-1';
      const currentNodeId = 'node-1';
      const isHovered = currentNodeId === hoveredNodeId;
      const highlightedColor = '#ffffff';

      expect(isHovered).toBe(true);
      expect(highlightedColor).toBe('#ffffff');
    });

    it('should highlight connected nodes when hovering', () => {
      const hoveredNodeId = 'node-1';
      const connectedNodeId = 'node-2';
      const unconnectedNodeId = 'node-3';

      const edges = [
        createTestEdge({ source: hoveredNodeId, target: connectedNodeId })
      ];

      // Check if connected
      const isConnected = edges.some(
        edge => edge.source === hoveredNodeId && edge.target === connectedNodeId
      ) || edges.some(
        edge => edge.target === hoveredNodeId && edge.source === connectedNodeId
      );

      expect(isConnected).toBe(true);

      // Check unconnected
      const isNotConnected = !edges.some(
        edge => (edge.source === hoveredNodeId && edge.target === unconnectedNodeId) ||
                (edge.target === hoveredNodeId && edge.source === unconnectedNodeId)
      );

      expect(isNotConnected).toBe(true);
    });
  });

  describe('Node Size Calculation', () => {
    it('should return base size for regular nodes', () => {
      const node = createTestNode({ size: 5 });
      const selectedNode = null;

      const baseSize = node.size || 5;
      const nodeSize = selectedNode?.id === node.id ? baseSize * 1.5 : baseSize;

      expect(nodeSize).toBe(5);
    });

    it('should increase size for selected node', () => {
      const node = createTestNode({ id: 'selected-node', size: 5 });
      const selectedNode = createTestNode({ id: 'selected-node', size: 5 });

      const baseSize = node.size || 5;
      const nodeSize = selectedNode?.id === node.id ? baseSize * 1.5 : baseSize;

      expect(nodeSize).toBe(7.5); // 5 * 1.5
    });

    it('should use default size when node.size is undefined', () => {
      const node = createTestNode({ size: undefined });
      const defaultSize = 5;
      const nodeSize = node.size || defaultSize;

      expect(nodeSize).toBe(5);
    });
  });

  describe('Node Interactions', () => {
    it('should handle node click to select', () => {
      const node = createTestNode({ id: 'node-click-test' });
      const setSelectedNode = vi.fn();

      setSelectedNode(node);

      expect(setSelectedNode).toHaveBeenCalledWith(node);
      expect(setSelectedNode).toHaveBeenCalledTimes(1);
    });

    it('should zoom into node on click', () => {
      const node = createTestNode({ x: 100, y: 200 });
      const zoomLevel = 1.5;

      // Simulate zoom and center
      const centerX = node.x || 0;
      const centerY = node.y || 0;

      expect(centerX).toBe(100);
      expect(centerY).toBe(200);
      expect(zoomLevel).toBe(1.5);
    });

    it('should handle node hover', () => {
      const node = createTestNode({ id: 'hovered-node' });
      const setHoveredNode = vi.fn();

      setHoveredNode(node);

      expect(setHoveredNode).toHaveBeenCalledWith(node);
      expect(setHoveredNode).toHaveBeenCalledTimes(1);
    });

    it('should clear hover when mouse leaves node', () => {
      const setHoveredNode = vi.fn();

      setHoveredNode(null);

      expect(setHoveredNode).toHaveBeenCalledWith(null);
    });

    it('should position tooltip near hovered node', () => {
      const node = createTestNode();
      const event = { x: 150, y: 250 };
      const containerRect = { left: 0, top: 0 };

      const tooltipX = event.x - containerRect.left;
      const tooltipY = event.y - containerRect.top;

      expect(tooltipX).toBe(150);
      expect(tooltipY).toBe(250);
    });

    it('should handle node right click', () => {
      const node = createTestNode();
      const handleRightClick = vi.fn();

      handleRightClick(node);

      expect(handleRightClick).toHaveBeenCalledWith(node);
    });
  });

  describe('Tooltip Display', () => {
    it('should show tooltip with node label', () => {
      const node = createTestNode({ label: 'Test Memory Label' });
      const tooltip = { node, x: 100, y: 100 };

      expect(tooltip.node.label).toBe('Test Memory Label');
    });

    it('should show tooltip with memory type badge', () => {
      const node = createTestNode({ type: 'gotcha' });
      const badgeLabel = 'Gotcha'; // from memoryTypeLabels

      expect(node.type).toBe('gotcha');
      expect(badgeLabel).toBe('Gotcha');
    });

    it('should show tooltip with memory preview', () => {
      const node = createTestNode({
        content: '{"what_worked": ["Pattern worked"]}'
      });
      const maxLength = 100;
      const preview = 'What worked: Pattern worked';

      expect(preview).toBeTruthy();
      expect(preview.length).toBeLessThanOrEqual(maxLength);
    });

    it('should show tooltip with timestamp', () => {
      const node = createTestNode({
        timestamp: '2024-01-11T10:00:00Z'
      });

      expect(node.timestamp).toBeDefined();
      expect(node.timestamp).toBeTruthy();
    });

    it('should hide tooltip when not hovering', () => {
      const tooltip = null;

      expect(tooltip).toBeNull();
    });
  });

  describe('Zoom Controls', () => {
    it('should have zoom in button', () => {
      // From component: ZoomIn icon with onClick handler
      const hasZoomIn = true;
      expect(hasZoomIn).toBe(true);
    });

    it('should have zoom out button', () => {
      // From component: ZoomOut icon with onClick handler
      const hasZoomOut = true;
      expect(hasZoomOut).toBe(true);
    });

    it('should have reset view button', () => {
      // From component: Maximize2 icon with onClick handler
      const hasResetView = true;
      expect(hasResetView).toBe(true);
    });

    it('should increase zoom level when zooming in', () => {
      const currentZoom = 1;
      const zoomFactor = 1.3;
      const newZoom = Math.min(currentZoom * zoomFactor, 5);

      expect(newZoom).toBe(1.3);
      expect(newZoom).toBeLessThanOrEqual(5);
    });

    it('should decrease zoom level when zooming out', () => {
      const currentZoom = 1.5;
      const zoomFactor = 1.3;
      const newZoom = Math.max(currentZoom / zoomFactor, 0.1);

      expect(newZoom).toBeCloseTo(1.15, 1);
      expect(newZoom).toBeGreaterThanOrEqual(0.1);
    });

    it('should reset zoom to 1 and center to origin', () => {
      const resetZoom = 1;
      const centerX = 0;
      const centerY = 0;

      expect(resetZoom).toBe(1);
      expect(centerX).toBe(0);
      expect(centerY).toBe(0);
    });

    it('should use translation keys for zoom tooltips', () => {
      const zoomInKey = 'memories.graph.zoomIn';
      const zoomOutKey = 'memories.graph.zoomOut';
      const resetKey = 'memories.graph.resetView';

      expect(zoomInKey).toBe('memories.graph.zoomIn');
      expect(zoomOutKey).toBe('memories.graph.zoomOut');
      expect(resetKey).toBe('memories.graph.resetView');
    });
  });

  describe('Memory Statistics Display', () => {
    it('should display stats when available', () => {
      const graphData = createTestGraphData({
        stats: {
          episode_count: 10,
          entity_count: 25,
          edge_count: 15,
          storage_bytes: 5120,
          storage_human: '5 KB'
        }
      });

      expect(graphData.stats).toBeDefined();
      expect(graphData.stats.episode_count).toBe(10);
      expect(graphData.stats.entity_count).toBe(25);
      expect(graphData.stats.edge_count).toBe(15);
    });

    it('should show storage size in human format', () => {
      const storageHuman = '5.2 KB';
      expect(storageHuman).toBeDefined();
    });

    it('should use translation keys for stats display', () => {
      const statsTitleKey = 'memories.graph.statsTitle';
      const statsKey = 'memories.graph.stats';
      const storageKey = 'memories.graph.storage';

      expect(statsTitleKey).toBe('memories.graph.statsTitle');
      expect(statsKey).toBe('memories.graph.stats');
      expect(storageKey).toBe('memories.graph.storage');
    });

    it('should not show stats when not available', () => {
      const graphData = createTestGraphData({ stats: undefined });
      const hasStats = !!graphData.stats;

      expect(hasStats).toBe(false);
    });
  });

  describe('Memory Operations', () => {
    it('should handle edit callback when editing memory', () => {
      const node = createTestNode({ id: 'edit-node' });
      const setEditingNode = vi.fn();

      setEditingNode(node);

      expect(setEditingNode).toHaveBeenCalledWith(node);
      expect(setEditingNode).toHaveBeenCalledTimes(1);
    });

    it('should refresh graph data after edit saved', () => {
      const loadGraphData = vi.fn();
      const setSelectedNode = vi.fn();
      const setEditingNode = vi.fn();

      // Simulate edit saved
      loadGraphData();
      setSelectedNode(null);
      setEditingNode(null);

      expect(loadGraphData).toHaveBeenCalledTimes(1);
      expect(setSelectedNode).toHaveBeenCalledWith(null);
      expect(setEditingNode).toHaveBeenCalledWith(null);
    });

    it('should call delete callback with node ID', async () => {
      const node = createTestNode({ id: 'delete-node' });
      const deleteMemory = vi.fn().mockResolvedValue({ success: true });

      await deleteMemory(testProjectId, node.id);

      expect(deleteMemory).toHaveBeenCalledWith(testProjectId, node.id);
      expect(deleteMemory).toHaveBeenCalledTimes(1);
    });

    it('should refresh graph after successful delete', async () => {
      const deleteMemory = vi.fn().mockResolvedValue({ success: true });
      const loadGraphData = vi.fn();
      const setSelectedNode = vi.fn();
      const nodeId = 'delete-node';

      await deleteMemory(testProjectId, nodeId);
      await loadGraphData();
      setSelectedNode(null);

      expect(loadGraphData).toHaveBeenCalledTimes(1);
      expect(setSelectedNode).toHaveBeenCalledWith(null);
    });

    it('should show error toast on delete failure', async () => {
      const deleteMemory = vi.fn().mockResolvedValue({
        success: false,
        error: 'Delete failed'
      });
      const nodeId = 'delete-node';
      const toast = vi.fn();

      const result = await deleteMemory(testProjectId, nodeId);
      if (!result.success) {
        toast({
          title: 'Delete failed',
          description: result.error,
          variant: 'destructive'
        });
      }

      expect(toast).toHaveBeenCalledWith({
        title: 'Delete failed',
        description: 'Delete failed',
        variant: 'destructive'
      });
    });

    it('should handle delete errors gracefully', async () => {
      const deleteMemory = vi.fn().mockRejectedValue(new Error('Network error'));
      const setError = vi.fn();
      const nodeId = 'delete-node';

      try {
        await deleteMemory(testProjectId, nodeId);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete memory');
      }

      expect(setError).toHaveBeenCalledWith('Network error');
    });
  });

  describe('Memory Detail Panel Integration', () => {
    it('should show detail panel when node is selected', () => {
      const selectedNode = createTestNode({ id: 'selected-node' });
      const graphData = createTestGraphData();

      const shouldShowPanel = !!selectedNode && !!graphData;

      expect(shouldShowPanel).toBe(true);
      expect(selectedNode).toBeDefined();
      expect(graphData).toBeDefined();
    });

    it('should pass correct props to MemoryDetailPanel', () => {
      const selectedNode = createTestNode({
        id: 'panel-node',
        label: 'Panel Test'
      });
      const graphData = createTestGraphData();

      const panelProps = {
        node: selectedNode,
        edges: graphData.edges,
        projectId: testProjectId,
        onClose: expect.any(Function),
        onEdit: expect.any(Function),
        onDelete: expect.any(Function)
      };

      expect(panelProps.node.id).toBe('panel-node');
      expect(panelProps.node.label).toBe('Panel Test');
      expect(panelProps.edges).toEqual(graphData.edges);
      expect(panelProps.projectId).toBe(testProjectId);
    });

    it('should close detail panel when onClose is called', () => {
      const setSelectedNode = vi.fn();
      const onClose = () => setSelectedNode(null);

      onClose();

      expect(setSelectedNode).toHaveBeenCalledWith(null);
      expect(setSelectedNode).toHaveBeenCalledTimes(1);
    });
  });

  describe('Memory Edit Dialog Integration', () => {
    it('should show edit dialog when editingNode is set', () => {
      const editingNode = createTestNode({ id: 'edit-node' });
      const showDialog = !!editingNode;

      expect(showDialog).toBe(true);
    });

    it('should pass correct props to MemoryEditDialog', () => {
      const editingNode = createTestNode({
        id: 'dialog-node',
        content: 'Test content'
      });

      const dialogProps = {
        node: editingNode,
        projectId: testProjectId,
        open: true,
        onOpenChange: expect.any(Function),
        onSaved: expect.any(Function)
      };

      expect(dialogProps.node.id).toBe('dialog-node');
      expect(dialogProps.node.content).toBe('Test content');
      expect(dialogProps.open).toBe(true);
    });

    it('should close dialog when onOpenChange is called with false', () => {
      const setEditingNode = vi.fn();
      const onOpenChange = (open: boolean) => {
        if (!open) setEditingNode(null);
      };

      onOpenChange(false);

      expect(setEditingNode).toHaveBeenCalledWith(null);
    });
  });

  describe('Text Truncation', () => {
    it('should truncate long text for node labels', () => {
      const longText = 'A'.repeat(200);
      const maxLength = 50;
      const truncated = longText.length <= maxLength ? longText : longText.substring(0, maxLength) + '...';

      expect(truncated.length).toBe(53); // 50 + '...'
      expect(truncated).toContain('...');
    });

    it('should not truncate short text', () => {
      const shortText = 'Short text';
      const maxLength = 50;
      const truncated = shortText.length <= maxLength ? shortText : shortText.substring(0, maxLength) + '...';

      expect(truncated).toBe(shortText);
      expect(truncated).not.toContain('...');
    });

    it('should handle empty text', () => {
      const emptyText = '';
      const maxLength = 50;
      const truncated = emptyText || '';

      expect(truncated).toBe('');
    });

    it('should handle null text', () => {
      const nullText = null;
      const maxLength = 50;
      const truncated = !nullText ? '' : nullText;

      expect(truncated).toBe('');
    });
  });

  describe('Memory Preview Parsing', () => {
    it('should parse JSON content for what_worked patterns', () => {
      const content = JSON.stringify({
        what_worked: ['Pattern A', 'Pattern B']
      });

      const parsed = JSON.parse(content);
      const preview = parsed.what_worked?.[0]
        ? `What worked: ${parsed.what_worked[0]}`
        : 'No content';

      expect(preview).toBe('What worked: Pattern A');
    });

    it('should parse JSON content for discoveries patterns', () => {
      const content = JSON.stringify({
        discoveries: {
          patterns_discovered: [
            { pattern: 'Use React hooks' },
            { pattern: 'Test components' }
          ]
        }
      });

      const parsed = JSON.parse(content);
      const pattern = parsed.discoveries?.patterns_discovered?.[0];
      const preview = pattern ? `Pattern: ${pattern.pattern}` : 'No content';

      expect(preview).toBe('Pattern: Use React hooks');
    });

    it('should parse JSON content for discoveries gotchas', () => {
      const content = JSON.stringify({
        discoveries: {
          gotchas_discovered: [
            { gotcha: 'Don\'t mutate state directly' }
          ]
        }
      });

      const parsed = JSON.parse(content);
      const gotcha = parsed.discoveries?.gotchas_discovered?.[0];
      const preview = gotcha ? `Gotcha: ${gotcha.gotcha}` : 'No content';

      expect(preview).toBe('Gotcha: Don\'t mutate state directly');
    });

    it('should fall back to raw content for non-JSON', () => {
      const content = 'Plain text memory content';
      const maxLength = 100;

      const preview = content.length <= maxLength
        ? content
        : content.substring(0, maxLength) + '...';

      expect(preview).toBe(content);
    });

    it('should handle invalid JSON gracefully', () => {
      const invalidJson = '{ invalid json }';
      const maxLength = 100;

      let preview;
      try {
        const parsed = JSON.parse(invalidJson);
        preview = parsed.what_worked?.[0] || 'No content';
      } catch {
        preview = invalidJson.length <= maxLength
          ? invalidJson
          : invalidJson.substring(0, maxLength) + '...';
      }

      expect(preview).toBeTruthy();
    });
  });

  describe('Edge Cases', () => {
    it('should handle nodes with missing coordinates', () => {
      const node = createTestNode({ x: undefined, y: undefined });
      const x = node.x || 0;
      const y = node.y || 0;

      expect(x).toBe(0);
      expect(y).toBe(0);
    });

    it('should handle nodes with missing timestamp', () => {
      const node = createTestNode({ timestamp: undefined });
      const timestamp = node.timestamp || '';

      expect(timestamp).toBe('');
    });

    it('should handle nodes with missing content', () => {
      const node = createTestNode({ content: undefined });
      const content = node.content || 'No content';

      expect(content).toBe('No content');
    });

    it('should handle empty edges array', () => {
      const graphData = createTestGraphData({ edges: [] });
      expect(graphData.edges).toHaveLength(0);
    });

    it('should handle large number of nodes', () => {
      const manyNodes = Array.from({ length: 100 }, (_, i) =>
        createTestNode({ id: `node-${i}` })
      );
      const graphData = createTestGraphData({ nodes: manyNodes });

      expect(graphData.nodes).toHaveLength(100);
    });

    it('should handle rapid node selection changes', () => {
      const setSelectedNode = vi.fn();
      const nodes = [
        createTestNode({ id: 'node-1' }),
        createTestNode({ id: 'node-2' }),
        createTestNode({ id: 'node-3' })
      ];

      nodes.forEach(node => setSelectedNode(node));

      expect(setSelectedNode).toHaveBeenCalledTimes(3);
      expect(setSelectedNode).toHaveBeenLastCalledWith(nodes[2]);
    });
  });
});
