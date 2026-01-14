/**
 * MemoryGraphView Component
 *
 * Performance Optimizations for Large Memory Sets:
 *
 * 1. Performance Tier Detection:
 *    - SMALL (< 100 nodes): Full rendering, all features enabled
 *    - MEDIUM (100-500 nodes): Balanced rendering
 *    - LARGE (500-1000 nodes): Optimizations enabled
 *    - VERY LARGE (1000+ nodes): Aggressive optimizations
 *
 * 2. Level-of-Detail (LOD) Rendering:
 *    - Node labels only shown when zoomed in (1.5x+) or on hover/selection
 *    - Node borders only shown when zoomed in (1.2x+)
 *    - Reduces canvas drawing operations significantly when zoomed out
 *
 * 3. Efficient Neighbor Lookups:
 *    - Adjacency map built once on load (O(1) lookups vs O(n) array search)
 *    - Dramatically improves hover highlighting performance on large graphs
 *
 * 4. Debounced Hover Events:
 *    - 50ms debounce on hover for large graphs
 *    - Prevents excessive re-renders during mouse movement
 *
 * 5. Memoized Callbacks:
 *    - All render callbacks use useCallback to prevent unnecessary re-creations
 *    - Expensive computations memoized with useMemo
 *
 * 6. Adaptive Physics:
 *    - Force simulation parameters adjusted based on graph size
 *    - Larger graphs use faster decay and fewer warmup ticks
 *
 * 7. Reduced Visual Complexity:
 *    - Thinner links and smaller arrows on very large graphs
 *    - Performance indicator shows when optimizations are active
 */
import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import ForceGraph2D from 'react-force-graph-2d';
import {
  RefreshCw,
  Brain,
  ZoomIn,
  ZoomOut,
  Maximize2,
  AlertCircle
} from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { useToast } from '../../hooks/use-toast';
import { cn } from '../../lib/utils';
import { memoryTypeColors, memoryTypeLabels } from './constants';
import { formatDate } from './utils';
import { MemoryDetailPanel } from './MemoryDetailPanel';
import { MemoryEditDialog } from './MemoryEditDialog';
import type { MemoryGraphNode, MemoryGraphEdge, MemoryGraphData, MemoryType } from '../../../shared/types';

// Performance configuration thresholds
const PERFORMANCE_THRESHOLDS = {
  SMALL_GRAPH: 100,      // Nodes below this count get full rendering
  MEDIUM_GRAPH: 500,     // Medium-sized graph
  LARGE_GRAPH: 1000,     // Large graph - enable optimizations
  VERY_LARGE_GRAPH: 2000 // Very large graph - aggressive optimizations
} as const;

// Level-of-detail settings
const LOD_SETTINGS = {
  // Minimum zoom level to show node labels
  LABEL_MIN_ZOOM: 1.5,
  // Minimum zoom level to show node borders
  BORDER_MIN_ZOOM: 1.2,
  // Maximum nodes to render when zoomed out (virtualization)
  MAX_VISIBLE_NODES_LOW_ZOOM: 200,
  // Zoom threshold for enabling virtualization
  VIRTUALIZATION_ZOOM_THRESHOLD: 0.8
} as const;

interface MemoryGraphViewProps {
  projectId: string;
}

interface TooltipState {
  node: MemoryGraphNode;
  x: number;
  y: number;
}

// Color mapping for graph nodes (hex colors for react-force-graph-2d)
const NODE_COLORS: Record<string, string> = {
  session_insight: '#f59e0b',     // amber-500
  codebase_discovery: '#3b82f6',  // blue-500
  codebase_map: '#3b82f6',        // blue-500
  pattern: '#a855f7',             // purple-500
  gotcha: '#ef4444',              // red-500
  task_outcome: '#22c55e',        // green-500
  qa_result: '#14b8a6',           // teal-500
  historical_context: '#64748b',  // slate-500
  pr_review: '#06b6d4',           // cyan-500
  pr_finding: '#f97316',          // orange-500
  pr_pattern: '#a855f7',          // purple-500
  pr_gotcha: '#ef4444'            // red-500
};

// Get node color with fallback
function getNodeColor(type: MemoryType): string {
  return NODE_COLORS[type] || NODE_COLORS.session_insight;
}

// Truncate text for display
function truncateText(text: string, maxLength: number): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

// Parse memory content for preview
function getMemoryPreview(content: string, maxLength: number = 150): string {
  if (!content) return 'No content';
  try {
    const parsed = JSON.parse(content);
    // If it's structured data, try to extract meaningful info
    if (parsed.what_worked && parsed.what_worked.length > 0) {
      return `What worked: ${parsed.what_worked[0]}`;
    }
    if (parsed.discoveries?.patterns_discovered && parsed.discoveries.patterns_discovered.length > 0) {
      const pattern = parsed.discoveries.patterns_discovered[0];
      const text = typeof pattern === 'string' ? pattern : pattern.pattern;
      return `Pattern: ${text}`;
    }
    if (parsed.discoveries?.gotchas_discovered && parsed.discoveries.gotchas_discovered.length > 0) {
      const gotcha = parsed.discoveries.gotchas_discovered[0];
      const text = typeof gotcha === 'string' ? gotcha : gotcha.gotcha;
      return `Gotcha: ${text}`;
    }
    // Fallback to raw content
    return truncateText(content, maxLength);
  } catch {
    return truncateText(content, maxLength);
  }
}

// Performance tier detection based on node count
function getPerformanceTier(nodeCount: number): 'small' | 'medium' | 'large' | 'very-large' {
  if (nodeCount < PERFORMANCE_THRESHOLDS.SMALL_GRAPH) return 'small';
  if (nodeCount < PERFORMANCE_THRESHOLDS.MEDIUM_GRAPH) return 'medium';
  if (nodeCount < PERFORMANCE_THRESHOLDS.LARGE_GRAPH) return 'large';
  return 'very-large';
}

// Build adjacency map for efficient neighbor lookups
function buildAdjacencyMap(edges: MemoryGraphEdge[]): Map<string, Set<string>> {
  const adjMap = new Map<string, Set<string>>();
  for (const edge of edges) {
    const sourceId = edge.source;
    const targetId = edge.target;

    if (!adjMap.has(sourceId)) adjMap.set(sourceId, new Set());
    if (!adjMap.has(targetId)) adjMap.set(targetId, new Set());

    adjMap.get(sourceId)!.add(targetId);
    adjMap.get(targetId)!.add(sourceId);
  }
  return adjMap;
}

// Check if two nodes are connected (using adjacency map)
function areNodesConnected(nodeId1: string, nodeId2: string, adjMap: Map<string, Set<string>>): boolean {
  const neighbors = adjMap.get(nodeId1);
  return neighbors ? neighbors.has(nodeId2) : false;
}

export function MemoryGraphView({ projectId }: MemoryGraphViewProps) {
  const { t } = useTranslation(['context', 'common']);
  const { toast } = useToast();
  const [graphData, setGraphData] = useState<MemoryGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<MemoryGraphNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<MemoryGraphNode | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [editingNode, setEditingNode] = useState<MemoryGraphNode | null>(null);

  // graphRef uses 'any' because react-force-graph-2d doesn't export a ref type
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const adjacencyMapRef = useRef<Map<string, Set<string>>>(new Map());
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Memoize performance tier
  const performanceTier = useMemo(() => {
    return graphData ? getPerformanceTier(graphData.nodes.length) : 'small';
  }, [graphData]);

  // Memoize whether optimizations are enabled
  const optimizationsEnabled = useMemo(() => {
    return performanceTier === 'large' || performanceTier === 'very-large';
  }, [performanceTier]);

  // Load graph data
  const loadGraphData = useCallback(async () => {
    if (!projectId) return;

    setLoading(true);
    setError(null);

    try {
      const result = await window.electronAPI.getGraphData(projectId);
      if (result.success && result.data) {
        setGraphData(result.data);
        // Build adjacency map for efficient neighbor lookups
        adjacencyMapRef.current = buildAdjacencyMap(result.data.edges);
      } else {
        setError(result.error || 'Failed to load graph data');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadGraphData();
  }, [loadGraphData]);

  // Cleanup hover timeout on unmount
  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }
    };
  }, []);

  // Handle node click
  const handleNodeClick = (node: MemoryGraphNode) => {
    setSelectedNode(node);
    // Zoom into the node
    if (graphRef.current) {
      graphRef.current.centerAt(node.x || 0, node.y || 0, 300);
      graphRef.current.zoom(1.5, 300);
    }
  };

  // Handle memory edit
  const handleEditMemory = (node: MemoryGraphNode) => {
    setEditingNode(node);
  };

  // Handle memory edit saved
  const handleEditSaved = async () => {
    // Refresh graph data to show updated content
    await loadGraphData();
    // Update selected node with new content
    if (selectedNode && editingNode && selectedNode.id === editingNode.id) {
      // The selectedNode will be updated when graph data refreshes
      setSelectedNode(null);
    }
    setEditingNode(null);
  };

  // Handle memory delete
  const handleDeleteMemory = async (nodeId: string) => {
    try {
      const result = await window.electronAPI.deleteMemory(projectId, nodeId);
      if (result.success) {
        // Show success toast
        toast({
          title: t('memories.graph.toast.deleteSuccess.title'),
          description: t('memories.graph.toast.deleteSuccess.description'),
        });

        // Refresh graph data
        await loadGraphData();

        // Close detail panel
        setSelectedNode(null);
      } else {
        // Show error toast
        toast({
          title: t('memories.graph.toast.deleteError.title'),
          description: result.error || t('memories.graph.toast.deleteError.description'),
          variant: 'destructive',
        });
        setError(result.error || 'Failed to delete memory');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete memory';
      // Show error toast
      toast({
        title: t('memories.graph.toast.deleteError.title'),
        description: errorMessage,
        variant: 'destructive',
      });
      setError(errorMessage);
    }
  };

  // Handle node hover with debouncing for large graphs
  const handleNodeHover = useCallback((node: MemoryGraphNode | null) => {
    // For large graphs, debounce hover events to improve performance
    if (optimizationsEnabled) {
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }

      hoverTimeoutRef.current = setTimeout(() => {
        setHoveredNode(node);
      }, 50); // 50ms debounce
    } else {
      // For small graphs, immediate response
      setHoveredNode(node);
    }
  }, [optimizationsEnabled]);

  // Handle node right click (for future context menu)
  const handleNodeRightClick = (_node: MemoryGraphNode) => {
    // Keep for future implementation
  };

  // Handle node hover for tooltip positioning
  const handleNodeHoverTooltip = (node: MemoryGraphNode | null, event: any) => {
    if (node && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setTooltip({
        node,
        x: event.x - rect.left,
        y: event.y - rect.top
      });
    } else {
      setTooltip(null);
    }
  };

  // Zoom controls
  const handleZoomIn = () => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.zoom();
      graphRef.current.zoom(Math.min(currentZoom * 1.3, 5), 300);
    }
  };

  const handleZoomOut = () => {
    if (graphRef.current) {
      const currentZoom = graphRef.current.zoom();
      graphRef.current.zoom(Math.max(currentZoom / 1.3, 0.1), 300);
    }
  };

  const handleResetZoom = () => {
    if (graphRef.current) {
      graphRef.current.zoom(1, 300);
      graphRef.current.centerAt(0, 0, 300);
    }
  };

  // Highlight connected nodes on hover (optimized with adjacency map)
  const handleNodeColor = useCallback((node: MemoryGraphNode) => {
    const baseColor = getNodeColor(node.type);

    // If hovering over a node, highlight it and its neighbors
    if (hoveredNode && graphData) {
      if (node.id === hoveredNode.id) {
        return '#ffffff'; // White for hovered node
      }
      // Use adjacency map for O(1) neighbor lookup instead of O(n) array search
      const isConnected = areNodesConnected(node.id, hoveredNode.id, adjacencyMapRef.current);
      if (isConnected) {
        return baseColor; // Full color for connected nodes
      }
      return '#374151'; // Gray for unconnected nodes
    }

    return baseColor;
  }, [hoveredNode, graphData]);

  // Node size based on type and connections (memoized)
  const handleNodeRelSize = useCallback((node: MemoryGraphNode) => {
    const baseSize = node.size || 5;

    // Larger for selected node
    if (selectedNode && node.id === selectedNode.id) {
      return baseSize * 1.5;
    }

    return baseSize;
  }, [selectedNode]);

  // Optimized node canvas rendering with level-of-detail
  const nodeCanvasObject = useCallback((
    node: MemoryGraphNode,
    ctx: CanvasRenderingContext2D,
    globalScale: number
  ) => {
    const size = handleNodeRelSize(node) / globalScale;
    const color = handleNodeColor(node);

    // Draw node circle
    ctx.beginPath();
    ctx.arc(node.x || 0, node.y || 0, size, 0, 2 * Math.PI, false);
    ctx.fillStyle = color;
    ctx.fill();

    // Level-of-detail: Only draw borders when zoomed in enough
    if (globalScale >= LOD_SETTINGS.BORDER_MIN_ZOOM && selectedNode && node.id === selectedNode.id) {
      ctx.lineWidth = 2 / globalScale;
      ctx.strokeStyle = '#ffffff';
      ctx.stroke();
    }

    // Level-of-detail: Only draw labels when zoomed in enough or node is interacted with
    const shouldShowLabel =
      globalScale >= LOD_SETTINGS.LABEL_MIN_ZOOM ||
      (hoveredNode && node.id === hoveredNode.id) ||
      (selectedNode && node.id === selectedNode.id);

    if (shouldShowLabel) {
      const label = node.label || node.id;
      const fontSize = 12 / globalScale;
      ctx.font = `${fontSize}px Sans-Serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#ffffff';
      ctx.fillText(label, node.x || 0, (node.y || 0) + size + (10 / globalScale));
    }
  }, [handleNodeRelSize, handleNodeColor, selectedNode, hoveredNode]);

  // Memoize physics configuration based on performance tier
  const physicsConfig = useMemo(() => {
    switch (performanceTier) {
      case 'small':
        return {
          d3AlphaDecay: 0.02,
          d3VelocityDecay: 0.3,
          warmupTicks: 100,
          cooldownTicks: 0
        };
      case 'medium':
        return {
          d3AlphaDecay: 0.03,
          d3VelocityDecay: 0.4,
          warmupTicks: 80,
          cooldownTicks: 0
        };
      case 'large':
        return {
          d3AlphaDecay: 0.05,
          d3VelocityDecay: 0.5,
          warmupTicks: 50,
          cooldownTicks: 0
        };
      case 'very-large':
        return {
          d3AlphaDecay: 0.08,
          d3VelocityDecay: 0.6,
          warmupTicks: 30,
          cooldownTicks: 0
        };
      default:
        return {
          d3AlphaDecay: 0.02,
          d3VelocityDecay: 0.3,
          warmupTicks: 100,
          cooldownTicks: 0
        };
    }
  }, [performanceTier]);

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <div className="text-center space-y-4">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground mx-auto" />
          <p className="text-sm text-muted-foreground">{t('memories.graph.loading')}</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <Card className="max-w-md">
          <CardContent className="pt-6 text-center space-y-4">
            <AlertCircle className="h-8 w-8 text-destructive mx-auto" />
            <div>
              <h3 className="font-semibold text-foreground">{t('memories.graph.errorTitle')}</h3>
              <p className="text-sm text-muted-foreground mt-1">{error}</p>
            </div>
            <Button onClick={loadGraphData} variant="outline">
              <RefreshCw className="h-4 w-4 mr-2" />
              {t('memories.graph.retry')}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Empty state
  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <Card className="max-w-md">
          <CardContent className="pt-6 text-center space-y-4">
            <Brain className="h-12 w-12 text-muted-foreground mx-auto" />
            <div>
              <h3 className="font-semibold text-foreground">{t('memories.graph.emptyTitle')}</h3>
              <p className="text-sm text-muted-foreground mt-1">
                {t('memories.graph.emptyDescription')}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full flex">
      {/* Main graph container */}
      <div ref={containerRef} className="flex-1 relative bg-background">
        <ForceGraph2D
          ref={graphRef}
          graphData={{
            nodes: graphData.nodes,
            links: graphData.edges.map(edge => ({
              source: edge.source,
              target: edge.target
            }))
          }}
          nodeLabel={(node: MemoryGraphNode) => node.label || node.id}
          nodeColor={handleNodeColor}
          nodeVal={handleNodeRelSize}
          nodeCanvasObject={nodeCanvasObject}
          linkColor={() => '#4b5563'}
          linkWidth={performanceTier === 'very-large' ? 0.5 : 1}
          linkDirectionalArrowLength={performanceTier === 'very-large' ? 2 : 3}
          linkDirectionalArrowRelPos={1}
          onNodeClick={handleNodeClick}
          onNodeHover={(node, event) => {
            handleNodeHover(node);
            handleNodeHoverTooltip(node, event);
          }}
          onNodeRightClick={handleNodeRightClick}
          enableNodeDrag={true}
          enableZoomInteraction={true}
          enablePanInteraction={true}
          d3AlphaDecay={physicsConfig.d3AlphaDecay}
          d3VelocityDecay={physicsConfig.d3VelocityDecay}
          warmupTicks={physicsConfig.warmupTicks}
          cooldownTicks={physicsConfig.cooldownTicks}
        />

        {/* Custom tooltip */}
        {tooltip && (
          <div
            className="absolute pointer-events-none z-50 bg-popover border border-border rounded-lg shadow-lg p-3 max-w-xs"
            style={{
              left: tooltip.x + 10,
              top: tooltip.y + 10
            }}
          >
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={cn('text-xs capitalize', memoryTypeColors[tooltip.node.type])}>
                  {memoryTypeLabels[tooltip.node.type] || tooltip.node.type}
                </Badge>
              </div>
              <div className="text-sm font-medium text-foreground">
                {tooltip.node.label}
              </div>
              {tooltip.node.content && (
                <div className="text-xs text-muted-foreground">
                  {getMemoryPreview(tooltip.node.content, 100)}
                </div>
              )}
              <div className="text-xs text-muted-foreground">
                {formatDate(tooltip.node.timestamp)}
              </div>
            </div>
          </div>
        )}

        {/* Zoom controls */}
        <div className="absolute top-4 right-4 flex flex-col gap-2">
          <Button
            variant="secondary"
            size="icon"
            className="h-8 w-8 bg-background/80 backdrop-blur-sm"
            onClick={handleZoomIn}
            title={t('memories.graph.zoomIn')}
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button
            variant="secondary"
            size="icon"
            className="h-8 w-8 bg-background/80 backdrop-blur-sm"
            onClick={handleZoomOut}
            title={t('memories.graph.zoomOut')}
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <Button
            variant="secondary"
            size="icon"
            className="h-8 w-8 bg-background/80 backdrop-blur-sm"
            onClick={handleResetZoom}
            title={t('memories.graph.resetView')}
          >
            <Maximize2 className="h-4 w-4" />
          </Button>
        </div>

        {/* Stats summary */}
        {graphData.stats && (
          <div className="absolute bottom-4 left-4 bg-background/80 backdrop-blur-sm border border-border rounded-lg p-3">
            <div className="text-xs space-y-1">
              <div className="font-semibold text-foreground">{t('memories.graph.statsTitle')}</div>
              <div className="text-muted-foreground">
                {t('memories.graph.stats', {
                  episodes: graphData.stats.episode_count,
                  entities: graphData.stats.entity_count,
                  connections: graphData.stats.edge_count
                })}
              </div>
              <div className="text-muted-foreground">
                {t('memories.graph.storage', { size: graphData.stats.storage_human })}
              </div>
              {/* Performance indicator for large graphs */}
              {optimizationsEnabled && (
                <div className="flex items-center gap-1 text-xs text-muted-foreground pt-1">
                  <RefreshCw className="h-3 w-3" />
                  <span>
                    {performanceTier === 'very-large'
                      ? t('memories.graph.performanceModeAggressive')
                      : t('memories.graph.performanceMode')}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Detail panel */}
      {selectedNode && graphData && (
        <MemoryDetailPanel
          node={selectedNode}
          edges={graphData.edges}
          projectId={projectId}
          onClose={() => setSelectedNode(null)}
          onEdit={handleEditMemory}
          onDelete={handleDeleteMemory}
        />
      )}

      {/* Edit dialog */}
      {editingNode && (
        <MemoryEditDialog
          node={editingNode}
          projectId={projectId}
          open={!!editingNode}
          onOpenChange={(open) => !open && setEditingNode(null)}
          onSaved={handleEditSaved}
        />
      )}
    </div>
  );
}
