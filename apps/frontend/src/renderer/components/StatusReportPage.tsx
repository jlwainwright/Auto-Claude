import { useEffect, useState, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  FileText,
  RefreshCw,
  Loader2,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
  Download,
  Wand2,
  X,
  Terminal,
  Minus,
  Maximize2,
  Filter,
  Clock,
  History
} from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from './ui/dropdown-menu';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger
} from './ui/collapsible';
import { cn } from '../lib/utils';
import type {
  StatusReport,
  SpecStatusRow,
  Anomaly,
  AnomalySeverity,
  AnomalyFixState,
  FixLogEntry,
  FixStatus
} from '../../shared/types';

interface StatusReportPageProps {
  projectId: string;
}

// Color mapping for anomaly severity
const severityColors: Record<AnomalySeverity, string> = {
  error: 'bg-destructive text-destructive-foreground hover:bg-destructive/80',
  warning: 'bg-yellow-500 text-white hover:bg-yellow-600',
  info: 'bg-blue-500 text-white hover:bg-blue-600'
};

const severityIcons: Record<AnomalySeverity, React.ElementType> = {
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info
};

// Log entry color mapping
const logTypeColors: Record<FixLogEntry['type'], string> = {
  info: 'text-foreground',
  reasoning: 'text-blue-500 italic',
  action: 'text-yellow-500',
  success: 'text-green-500',
  error: 'text-destructive',
  warning: 'text-orange-500'
};

// Status badge colors
const getStatusColor = (status: string) => {
  const s = status.toLowerCase();
  if (s === 'done' || s === 'completed' || s === 'approved') {
    return 'bg-green-500 text-white hover:bg-green-600';
  }
  if (s === 'in_progress' || s === 'pending') {
    return 'bg-blue-500 text-white hover:bg-blue-600';
  }
  if (s === 'validation' || s === 'human_review') {
    return 'bg-purple-500 text-white hover:bg-purple-600';
  }
  if (s === 'failed' || s === 'error') {
    return 'bg-destructive text-destructive-foreground hover:bg-destructive/80';
  }
  return 'bg-muted text-muted-foreground';
};

// Fix status colors
const getFixStatusColor = (status: FixStatus) => {
  switch (status) {
    case 'completed': return 'text-green-500';
    case 'failed': return 'text-destructive';
    case 'cancelled': return 'text-muted-foreground';
    case 'running': return 'text-blue-500 animate-pulse';
    default: return 'text-muted-foreground';
  }
};

// Get fix status label
const getFixStatusLabel = (status: FixStatus): string => {
  switch (status) {
    case 'idle': return 'Idle';
    case 'starting': return 'Starting...';
    case 'running': return 'Fixing...';
    case 'completed': return 'Completed';
    case 'failed': return 'Failed';
    case 'cancelled': return 'Cancelled';
  }
};

// NEW: Get worst severity from a list of anomalies
const getWorstSeverity = (anomalies: Anomaly[]): AnomalySeverity | null => {
  if (anomalies.length === 0) return null;
  if (anomalies.some(a => a.severity === 'error')) return 'error';
  if (anomalies.some(a => a.severity === 'warning')) return 'warning';
  if (anomalies.some(a => a.severity === 'info')) return 'info';
  return null;
};

// NEW: Get border class based on worst anomaly severity
const getRowBorderClass = (anomalies: Anomaly[]): string => {
  const worst = getWorstSeverity(anomalies);
  if (worst === 'error') return 'border-l-4 border-l-destructive';
  if (worst === 'warning') return 'border-l-4 border-l-yellow-500';
  if (worst === 'info') return 'border-l-4 border-l-blue-500';
  return '';
};

// NEW: Filter anomalies by severity
const filterAnomalies = (anomalies: Anomaly[], filter: 'all' | 'error' | 'warning' | 'info' | null | undefined): Anomaly[] => {
  if (!filter || filter === 'all') return anomalies;
  return anomalies.filter(a => a.severity === filter);
};

// Spec row component with collapsible anomalies and fix buttons
interface SpecRowProps {
  spec: SpecStatusRow;
  projectId: string;
  activeFixes: Map<string, AnomalyFixState>;
  onStartFix: (spec: SpecStatusRow, anomaly: Anomaly) => void;
  onViewLogs: (fixId: string) => void;
}

function SpecRow({ spec, projectId, activeFixes, onStartFix, onViewLogs }: SpecRowProps) {
  const [expanded, setExpanded] = useState(false);
  const hasAnomalies = spec.anomalies.length > 0;
  const borderClass = getRowBorderClass(spec.anomalies);

  return (
    <div className={cn("border rounded-lg overflow-hidden", borderClass)}>
      <Collapsible open={expanded} onOpenChange={setExpanded}>
        <CollapsibleTrigger className="w-full">
          <div
            className={cn(
              "flex items-center justify-between p-3 hover:bg-muted/50 transition-colors",
              hasAnomalies && expanded && "bg-muted/30"
            )}
          >
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium truncate">{spec.feature || spec.spec_id}</span>
                  <Badge variant="outline" className="shrink-0 text-xs">
                    {spec.spec_id}
                  </Badge>
                </div>
                <div className="text-sm text-muted-foreground truncate">
                  {spec.status}
                </div>
              </div>

              <div className="flex items-center gap-4 text-sm">
                <div className="text-center">
                  <div className="text-muted-foreground text-xs">Subtasks</div>
                  <div className="font-medium">{spec.subtasks.done}/{spec.subtasks.total}</div>
                </div>

                <div className="text-center">
                  <div className="text-muted-foreground text-xs">QA</div>
                  <Badge variant="outline" className={cn("text-xs", getStatusColor(spec.qa.status))}>
                    {spec.qa.status || '-'}
                  </Badge>
                </div>

                {hasAnomalies && (
                  <Badge
                    variant="outline"
                    className={cn(
                      "shrink-0",
                      spec.anomalies.some((a) => a.severity === 'error') &&
                        "border-destructive text-destructive"
                    )}
                  >
                    {spec.anomalies.length} {spec.anomalies.length === 1 ? 'anomaly' : 'anomalies'}
                  </Badge>
                )}

                {expanded ? (
                  <ChevronUp className="h-4 w-4 shrink-0" />
                ) : (
                  <ChevronDown className="h-4 w-4 shrink-0" />
                )}
              </div>
            </div>
          </div>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="border-t p-3 space-y-2 bg-muted/20">
            {spec.artifacts.has_build_progress && (
              <div className="text-xs text-muted-foreground">
                Build Progress: {spec.artifacts.build_progress.status || 'N/A'}
                {spec.artifacts.build_progress.created && (
                  <span> • Created: {spec.artifacts.build_progress.created}</span>
                )}
              </div>
            )}

            {hasAnomalies ? (
              <div className="space-y-2">
                <div className="text-sm font-medium">Anomalies:</div>
                {spec.anomalies.map((anomaly, idx) => {
                  const Icon = severityIcons[anomaly.severity];

                  // Check if there's an active fix for this anomaly
                  const anomalyKey = `${spec.spec_id}-${idx}`;
                  const activeFix = Array.from(activeFixes.values()).find(
                    f => f.specId === spec.spec_id &&
                    f.anomaly.type === anomaly.type &&
                    f.anomaly.detail === anomaly.detail
                  );

                  return (
                    <div
                      key={idx}
                      className="flex items-start gap-2 text-sm p-2 rounded bg-background group"
                    >
                      <Icon className="h-4 w-4 shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge className={cn("text-xs", severityColors[anomaly.severity])}>
                            {anomaly.severity}
                          </Badge>
                          <span className="font-medium">{anomaly.type}</span>
                          {activeFix && (
                            <Badge variant="outline" className={cn("text-xs", getFixStatusColor(activeFix.status))}>
                              {getFixStatusLabel(activeFix.status)}
                            </Badge>
                          )}
                        </div>
                        <p className="text-muted-foreground text-xs mt-1">{anomaly.detail}</p>

                        {/* Fix button */}
                        <div className="mt-2 flex items-center gap-2">
                          {activeFix ? (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 px-2 text-xs"
                                onClick={() => onViewLogs(activeFix.fixId)}
                              >
                                <Terminal className="h-3 w-3 mr-1" />
                                View Logs
                              </Button>
                              {activeFix.status === 'running' && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 px-2 text-xs text-destructive hover:text-destructive"
                                  onClick={() => {/* Cancel handled from panel */}}
                                >
                                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                                  Running...
                                </Button>
                              )}
                            </>
                          ) : (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                              onClick={() => onStartFix(spec, anomaly)}
                            >
                              <Wand2 className="h-3 w-3 mr-1" />
                              Fix with AI
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">No anomalies detected ✓</div>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

// Summary cards component
function SummaryCards({
  report,
  onBulkFix
}: {
  report: StatusReport;
  onBulkFix?: (severity: 'error' | 'warning' | 'info') => void;
}) {
  const { summary } = report;
  const errorCount = summary.anomaly_severity_counts.error || 0;
  const warningCount = summary.anomaly_severity_counts.warning || 0;
  const infoCount = summary.anomaly_severity_counts.info || 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>Total Specs</CardDescription>
          <CardTitle className="text-2xl">{summary.spec_count}</CardTitle>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader className="pb-2 space-y-2">
          <div className="flex items-center justify-between">
            <CardDescription>Errors</CardDescription>
            {onBulkFix && errorCount > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={() => onBulkFix('error')}
              >
                <Wand2 className="h-3 w-3 mr-1" />
                Fix All
              </Button>
            )}
          </div>
          <CardTitle className={cn("text-2xl", errorCount > 0 && "text-destructive")}>
            {errorCount}
          </CardTitle>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader className="pb-2 space-y-2">
          <div className="flex items-center justify-between">
            <CardDescription>Warnings</CardDescription>
            {onBulkFix && warningCount > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={() => onBulkFix('warning')}
              >
                <Wand2 className="h-3 w-3 mr-1" />
                Fix All
              </Button>
            )}
          </div>
          <CardTitle className={cn("text-2xl", warningCount > 0 && "text-yellow-600")}>
            {warningCount}
          </CardTitle>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader className="pb-2 space-y-2">
          <div className="flex items-center justify-between">
            <CardDescription>Info</CardDescription>
            {onBulkFix && infoCount > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={() => onBulkFix('info')}
              >
                <Wand2 className="h-3 w-3 mr-1" />
                Fix All
              </Button>
            )}
          </div>
          <CardTitle className="text-2xl text-blue-600">{infoCount}</CardTitle>
        </CardHeader>
      </Card>
    </div>
  );
}

// Status by count component
function StatusBreakdown({ report }: { report: StatusReport }) {
  const statusEntries = Object.entries(report.summary.status_counts).sort(
    ([, a], [, b]) => b - a
  );

  const total = statusEntries.reduce((sum, [, count]) => sum + count, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Status Breakdown</CardTitle>
        <CardDescription>Specs by current status</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {statusEntries.map(([status, count]) => {
            const percent = total > 0 ? (count / total) * 100 : 0;
            return (
              <div key={status}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="capitalize">{status.replace(/_/g, ' ')}</span>
                  <span className="text-muted-foreground">{count} ({percent.toFixed(0)}%)</span>
                </div>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className={cn("h-full rounded-full", getStatusColor(status))}
                    style={{ width: `${percent}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

// Anomaly type breakdown with fix buttons
function AnomalyBreakdown({
  report,
  severityFilter,
  onSetFilter,
  activeFixes,
  onStartFix,
  onViewLogs
}: {
  report: StatusReport;
  severityFilter?: 'all' | 'error' | 'warning' | 'info';
  onSetFilter?: (filter: 'all' | 'error' | 'warning' | 'info') => void;
  activeFixes: Map<string, AnomalyFixState>;
  onStartFix: (spec: SpecStatusRow, anomaly: Anomaly) => void;
  onViewLogs: (fixId: string) => void;
}) {
  // Build a map of anomalies to their specs
  const anomalyToSpec: Map<string, SpecStatusRow> = new Map();
  for (const spec of report.specs) {
    for (const anomaly of spec.anomalies) {
      const key = `${anomaly.type}-${anomaly.detail}`;
      anomalyToSpec.set(key, spec);
    }
  };

  const allAnomalies: Anomaly[] = [];
  for (const spec of report.specs) {
    allAnomalies.push(...spec.anomalies);
  }

  // Apply filter if specified
  const filteredAnomalies = severityFilter && severityFilter !== 'all'
    ? allAnomalies.filter(a => a.severity === severityFilter)
    : allAnomalies;

  // Group by type
  const byType: Record<string, Anomaly[]> = {};
  for (const anomaly of filteredAnomalies) {
    if (!byType[anomaly.type]) {
      byType[anomaly.type] = [];
    }
    byType[anomaly.type].push(anomaly);
  }

  const sortedTypes = Object.entries(byType).sort(([, a], [, b]) => b.length - a.length);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Anomalies by Type</CardTitle>
            <CardDescription>Grouped detection results</CardDescription>
          </div>
          {onSetFilter && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm">
                  <Filter className="h-4 w-4 mr-2" />
                  {severityFilter === 'all' ? 'All' : severityFilter === 'error' ? 'Errors' : severityFilter === 'warning' ? 'Warnings' : 'Info'}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => onSetFilter('all')}>All Anomalies</DropdownMenuItem>
                <DropdownMenuItem onClick={() => onSetFilter('error')}>Errors Only</DropdownMenuItem>
                <DropdownMenuItem onClick={() => onSetFilter('warning')}>Warnings Only</DropdownMenuItem>
                <DropdownMenuItem onClick={() => onSetFilter('info')}>Info Only</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {sortedTypes.map(([type, anomalies]) => {
          const errorCount = anomalies.filter((a) => a.severity === 'error').length;
          const severityClass = errorCount > 0 ? 'border-destructive' : '';

          return (
            <div key={type} className="border rounded-lg overflow-hidden">
              <div
                className={cn(
                  "flex items-center justify-between p-2 bg-muted/30",
                  severityClass
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{type}</span>
                  <Badge variant="outline" className="text-xs">
                    {anomalies.length}
                  </Badge>
                </div>
                <div className="flex items-center gap-1">
                  {anomalies.some((a) => a.severity === 'error') && (
                    <Badge className={severityColors.error}>E</Badge>
                  )}
                  {anomalies.some((a) => a.severity === 'warning') && (
                    <Badge className={severityColors.warning}>W</Badge>
                  )}
                  {anomalies.some((a) => a.severity === 'info') && (
                    <Badge className={severityColors.info}>I</Badge>
                  )}
                </div>
              </div>

              {/* Individual anomalies with fix buttons */}
              <div className="border-t p-2 space-y-1">
                {anomalies.map((anomaly, idx) => {
                  const Icon = severityIcons[anomaly.severity];
                  const anomalyKey = `${anomaly.type}-${anomaly.detail}`;
                  const spec = anomalyToSpec.get(anomalyKey);

                  // Check for active fix
                  const activeFix = spec && Array.from(activeFixes.values()).find(
                    f => f.specId === spec.spec_id &&
                    f.anomaly.type === anomaly.type &&
                    f.anomaly.detail === anomaly.detail
                  );

                  return (
                    <div
                      key={idx}
                      className="flex items-start gap-2 text-sm p-2 rounded bg-background group"
                    >
                      <Icon className="h-3 w-3 shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <p className="text-muted-foreground text-xs truncate">{anomaly.detail}</p>
                        <div className="mt-1 flex items-center gap-1">
                          {spec && (
                            <Badge variant="outline" className="text-xs px-1 py-0 h-4">
                              {spec.spec_id}
                            </Badge>
                          )}
                          {activeFix && (
                            <Badge variant="outline" className={cn("text-xs", getFixStatusColor(activeFix.status))}>
                              {getFixStatusLabel(activeFix.status)}
                            </Badge>
                          )}
                          <div className="ml-auto">
                            {activeFix ? (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 px-1.5 text-xs"
                                onClick={() => onViewLogs(activeFix.fixId)}
                              >
                                <Terminal className="h-2.5 w-2.5 mr-1" />
                                View
                              </Button>
                            ) : spec && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 px-1.5 text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                                onClick={() => onStartFix(spec, anomaly)}
                              >
                                <Wand2 className="h-2.5 w-2.5 mr-1" />
                                Fix
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
        {sortedTypes.length === 0 && (
          <div className="text-sm text-muted-foreground text-center py-4">
            No anomalies detected
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function StatusReportPage({ projectId }: StatusReportPageProps) {
  const { t } = useTranslation(['common', 'navigation']);

  const [report, setReport] = useState<StatusReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'specs'>('overview');

  // Fix state
  const [activeFixes, setActiveFixes] = useState<Map<string, AnomalyFixState>>(new Map());
  const [selectedFixId, setSelectedFixId] = useState<string | null>(null);
  const [logPanelExpanded, setLogPanelExpanded] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  // NEW: Anomaly filter state
  const [severityFilter, setSeverityFilter] = useState<'all' | 'error' | 'warning' | 'info'>('all');

  // NEW: Fix history state with localStorage persistence
  const [fixHistory, setFixHistory] = useState<AnomalyFixState[]>([]);

  // Load fix history from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem('auto-claude-fix-history');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          setFixHistory(parsed);
        }
      }
    } catch (err) {
      console.warn('Failed to load fix history:', err);
    }
  }, []);

  // Save fix history to localStorage whenever it changes
  useEffect(() => {
    try {
      const completedFixes = Array.from(activeFixes.values()).filter(
        fix => fix.status === 'completed' || fix.status === 'failed'
      );
      const historyToSave = [...fixHistory, ...completedFixes]
        .sort((a, b) => {
          const aTime = new Date(a.endTime || a.startTime).getTime();
          const bTime = new Date(b.endTime || b.startTime).getTime();
          return bTime - aTime;
        })
        .slice(0, 50); // Keep only the last 50 fixes
      localStorage.setItem('auto-claude-fix-history', JSON.stringify(historyToSave));
      setFixHistory(historyToSave);
    } catch (err) {
      console.warn('Failed to save fix history:', err);
    }
  }, [activeFixes]);

  // Load report
  const loadReport = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await window.electronAPI.generateReport(projectId);
      if (result.success && result.data) {
        setReport(result.data);
      } else {
        setError(result.error || 'Failed to load status report');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  // Start fix for an anomaly
  const handleStartFix = useCallback(async (spec: SpecStatusRow, anomaly: Anomaly) => {
    try {
      const result = await window.electronAPI.startFix({
        projectId,
        specId: spec.spec_id,
        anomaly,
        specContext: spec
      });

      if (result.success && result.data) {
        setSelectedFixId(result.data.fixId);
        setLogPanelExpanded(true);
      } else {
        setError(result.error || 'Failed to start fix');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }, [projectId]);

  // NEW: Bulk fix handler - fixes all errors (or filtered anomalies) in parallel
  const handleBulkFix = useCallback(async (severity: 'error' | 'warning' | 'info' = 'error') => {
    if (!report) return;

    // Collect all anomalies of the specified severity
    const anomaliesToFix: Array<{ spec: SpecStatusRow; anomaly: Anomaly }> = [];
    for (const spec of report.specs) {
      const filteredAnomalies = spec.anomalies.filter(a => a.severity === severity);
      for (const anomaly of filteredAnomalies) {
        anomaliesToFix.push({ spec, anomaly });
      }
    }

    if (anomaliesToFix.length === 0) {
      setError(`No ${severity} anomalies found to fix`);
      return;
    }

    // Start fixes in parallel (with a small delay between each to avoid overwhelming the system)
    for (const { spec, anomaly } of anomaliesToFix) {
      try {
        const result = await window.electronAPI.startFix({
          projectId,
          specId: spec.spec_id,
          anomaly,
          specContext: spec
        });

        if (result.success && result.data) {
          // Auto-expand log panel for the first fix
          if (anomaliesToFix.length === 1) {
            setSelectedFixId(result.data.fixId);
            setLogPanelExpanded(true);
          }
        }
      } catch (err) {
        console.error('Failed to start fix for', spec.spec_id, anomaly.type, err);
      }

      // Small delay between fixes
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  }, [projectId, report]);

  // Cancel fix
  const handleCancelFix = useCallback(async (fixId: string) => {
    try {
      await window.electronAPI.cancelFix(fixId);
      setActiveFixes(prev => {
        const updated = new Map(prev);
        const fix = updated.get(fixId);
        if (fix) {
          updated.set(fixId, { ...fix, status: 'cancelled' });
        }
        return updated;
      });
    } catch (err) {
      console.error('Failed to cancel fix:', err);
    }
  }, []);

  // View logs for a fix
  const handleViewLogs = useCallback((fixId: string) => {
    setSelectedFixId(fixId);
    setLogPanelExpanded(true);
  }, []);

  // Export report
  const exportReport = useCallback(() => {
    if (!report) return;

    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: 'application/json'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `auto-claude-status-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [report]);

  // Set up IPC event listeners for streaming logs
  useEffect(() => {
    const unsubscribes: (() => void)[] = [];

    // Listen for log entries
    const unsubscribeLog = window.electronAPI.onLog(({ fixId, entry }) => {
      setActiveFixes(prev => {
        const updated = new Map(prev);
        const fix = updated.get(fixId);
        if (fix) {
          updated.set(fixId, {
            ...fix,
            logs: [...fix.logs, entry]
          });
        }
        return updated;
      });

      // Auto-scroll to end if this is the selected fix
      if (fixId === selectedFixId) {
        setTimeout(() => {
          logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 50);
      }
    });
    unsubscribes.push(unsubscribeLog);

    // Listen for completion
    const unsubscribeComplete = window.electronAPI.onComplete(({ fixId, result }) => {
      setActiveFixes(prev => {
        const updated = new Map(prev);
        const fix = updated.get(fixId);
        if (fix) {
          updated.set(fixId, {
            ...fix,
            status: 'completed',
            result,
            endTime: new Date().toISOString()
          });
        }
        return updated;
      });

      // Refresh report after fix completes
      setTimeout(() => {
        loadReport();
      }, 1000);
    });
    unsubscribes.push(unsubscribeComplete);

    // Listen for errors
    const unsubscribeError = window.electronAPI.onError(({ fixId, error: err }) => {
      setActiveFixes(prev => {
        const updated = new Map(prev);
        const fix = updated.get(fixId);
        if (fix) {
          updated.set(fixId, {
            ...fix,
            status: 'failed',
            error: err,
            endTime: new Date().toISOString()
          });
        }
        return updated;
      });
    });
    unsubscribes.push(unsubscribeError);

    return () => {
      unsubscribes.forEach(unsub => unsub());
    };
  }, [selectedFixId, loadReport]);

  // Initial load
  useEffect(() => {
    loadReport();
  }, [loadReport]);

  // Get the selected fix state
  const selectedFix = selectedFixId ? activeFixes.get(selectedFixId) : null;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div>
          <h2 className="text-lg font-semibold">Status Report</h2>
          <p className="text-sm text-muted-foreground">
            Overview of all Auto-Claude specs and detected anomalies
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadReport}
            disabled={isLoading}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Refresh
          </Button>
          {report && (
            <Button variant="outline" size="sm" onClick={exportReport}>
              <Download className="h-4 w-4 mr-2" />
              Export
            </Button>
          )}
        </div>
      </div>

      {/* Main content area with optional log panel */}
      <div className={cn(
        "flex flex-1 overflow-hidden",
        selectedFixId && "gap-4"
      )}>
        {/* Report content */}
        <ScrollArea className={cn(
          "flex-1",
          selectedFixId && !logPanelExpanded ? "w-full" : logPanelExpanded ? "w-1/2" : "w-full"
        )}>
          <div className="p-4 max-w-6xl mx-auto space-y-4">
            {error && (
              <Card className="border-destructive">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-2 text-destructive">
                    <AlertCircle className="h-5 w-5" />
                    <span className="font-medium">Error</span>
                  </div>
                  <p className="text-sm mt-2">{error}</p>
                </CardContent>
              </Card>
            )}

            {isLoading && !report && (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            )}

            {report && !error && (
              <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
                <TabsList className="grid w-full max-w-md grid-cols-2">
                  <TabsTrigger value="overview">Overview</TabsTrigger>
                  <TabsTrigger value="specs">
                    Specs ({report.specs.length})
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="space-y-4 mt-4">
                  <SummaryCards report={report} onBulkFix={handleBulkFix} />

                  <div className="grid md:grid-cols-2 gap-4">
                    <StatusBreakdown report={report} />
                    <AnomalyBreakdown
                      report={report}
                      severityFilter={severityFilter}
                      onSetFilter={setSeverityFilter}
                      activeFixes={activeFixes}
                      onStartFix={handleStartFix}
                      onViewLogs={handleViewLogs}
                    />
                  </div>

                  {/* Roadmap info */}
                  {report.roadmap && report.roadmap.loaded && (
                    <Card>
                      <CardHeader>
                        <CardTitle>Roadmap</CardTitle>
                        <CardDescription>
                          {report.roadmap.metadata?.updated_at
                            ? `Updated: ${new Date(report.roadmap.metadata.updated_at as string).toLocaleDateString()}`
                            : 'Linked to roadmap'}
                        </CardDescription>
                      </CardHeader>
                    </Card>
                  )}

                  {/* NEW: Fix History panel */}
                  {fixHistory.length > 0 && (
                    <Card>
                      <CardHeader>
                        <div className="flex items-center gap-2">
                          <History className="h-4 w-4" />
                          <CardTitle>Fix History</CardTitle>
                        </div>
                        <CardDescription>
                          Recent fix attempts (stored locally)
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {fixHistory.slice(0, 10).map((fix) => (
                            <div
                              key={fix.fixId}
                              className={cn(
                                "flex items-center justify-between p-2 rounded border",
                                "hover:bg-muted/50 transition-colors"
                              )}
                            >
                              <div className="flex items-center gap-2 flex-1 min-w-0">
                                <Badge variant="outline" className={cn("text-xs", getFixStatusColor(fix.status))}>
                                  {getFixStatusLabel(fix.status)}
                                </Badge>
                                <div className="flex-1 min-w-0">
                                  <div className="text-sm font-medium truncate">
                                    {fix.anomaly?.type || 'Unknown'}
                                  </div>
                                  <div className="text-xs text-muted-foreground truncate">
                                    {fix.specId}
                                  </div>
                                </div>
                              </div>
                              <div className="text-xs text-muted-foreground flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {fix.endTime
                                  ? new Date(fix.endTime).toLocaleDateString()
                                  : new Date(fix.startTime).toLocaleDateString()}
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </TabsContent>

                <TabsContent value="specs" className="space-y-4 mt-4">
                  {report.specs.map((spec) => (
                    <SpecRow
                      key={spec.spec_id}
                      spec={spec}
                      projectId={projectId}
                      activeFixes={activeFixes}
                      onStartFix={handleStartFix}
                      onViewLogs={handleViewLogs}
                    />
                  ))}
                </TabsContent>
              </Tabs>
            )}
          </div>
        </ScrollArea>

        {/* Log panel - shown when a fix is selected */}
        {selectedFixId && selectedFix && (
          <Card className={cn(
            "flex flex-col border-l transition-all duration-300",
            logPanelExpanded ? "w-96" : "w-72"
          )}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <Terminal className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <CardTitle className="text-sm truncate">Fix Logs</CardTitle>
                  <Badge variant="outline" className={cn("text-xs shrink-0", getFixStatusColor(selectedFix.status))}>
                    {getFixStatusLabel(selectedFix.status)}
                  </Badge>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => setLogPanelExpanded(!logPanelExpanded)}
                  >
                    {logPanelExpanded ? (
                      <Minus className="h-3 w-3" />
                    ) : (
                      <Maximize2 className="h-3 w-3" />
                    )}
                  </Button>
                  {selectedFix.status === 'running' && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 text-destructive"
                      onClick={() => handleCancelFix(selectedFixId)}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => setSelectedFixId(null)}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
              </div>
              {selectedFix.anomaly && (
                <CardDescription className="text-xs truncate">
                  {selectedFix.anomaly.type}: {selectedFix.anomaly.detail}
                </CardDescription>
              )}
            </CardHeader>

            <ScrollArea className="flex-1">
              <CardContent className="p-2">
                <div className="space-y-1 text-xs font-mono">
                  {selectedFix.logs.length === 0 ? (
                    <div className="text-muted-foreground text-center py-4">
                      Waiting for logs...
                    </div>
                  ) : (
                    selectedFix.logs.map((log, idx) => (
                      <div
                        key={idx}
                        className={cn(
                          "flex gap-2 py-0.5",
                          log.type === 'reasoning' && "bg-blue-500/5 -mx-1 px-1 rounded"
                        )}
                      >
                        <span className="text-muted-foreground shrink-0">
                          [{new Date(log.timestamp).toLocaleTimeString()}]
                        </span>
                        <span className={logTypeColors[log.type]}>
                          {log.message}
                        </span>
                      </div>
                    ))
                  )}
                  {selectedFix.status === 'running' && (
                    <div className="flex gap-2 py-0.5 text-blue-500 animate-pulse">
                      <span className="text-muted-foreground">[...]</span>
                      <span>Processing...</span>
                    </div>
                  )}
                  <div ref={logEndRef} />
                </div>

                {/* Result summary */}
                {selectedFix.result && (
                  <div className="mt-4 pt-4 border-t space-y-2">
                    <div className={cn(
                      "flex items-center gap-2 text-sm font-medium",
                      selectedFix.result.success ? "text-green-500" : "text-destructive"
                    )}>
                      {selectedFix.result.success ? (
                        <>
                          <CheckCircle2 className="h-4 w-4" />
                          Fix Completed
                        </>
                      ) : (
                        <>
                          <AlertCircle className="h-4 w-4" />
                          Fix Failed
                        </>
                      )}
                    </div>
                    {selectedFix.result.summary && (
                      <p className="text-sm text-muted-foreground">{selectedFix.result.summary}</p>
                    )}
                    {selectedFix.result.actions_taken.length > 0 && (
                      <div className="space-y-1">
                        <div className="text-xs font-medium text-muted-foreground">Actions taken:</div>
                        <ul className="text-xs text-muted-foreground list-disc list-inside">
                          {selectedFix.result.actions_taken.map((action, i) => (
                            <li key={i}>{action}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Error display */}
                {selectedFix.error && (
                  <div className="mt-4 pt-4 border-t">
                    <div className="flex items-center gap-2 text-sm font-medium text-destructive">
                      <AlertCircle className="h-4 w-4" />
                      Error
                    </div>
                    <p className="text-sm text-destructive mt-1">{selectedFix.error}</p>
                  </div>
                )}
              </CardContent>
            </ScrollArea>
          </Card>
        )}
      </div>
    </div>
  );
}
