import { useEffect, useState, useCallback } from 'react';
import { RefreshCw, AlertCircle, AlertTriangle, Info, Wrench, Loader2, Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from './ui/dialog';
import { useProjectStore } from '../stores/project-store';
import type { StatusReport, Issue, FixPlan } from '../../shared/types/status-report';

interface StatusReportPageProps {
  projectId: string;
}

export function StatusReportPage({ projectId }: StatusReportPageProps) {
  const { t } = useTranslation(['dialogs', 'common']);
  const projects = useProjectStore((state) => state.projects);
  const selectedProject = projects.find((p) => p.id === projectId);

  const [report, setReport] = useState<StatusReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fix dialog state
  const [showFixDialog, setShowFixDialog] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);
  const [selectedSpecId, setSelectedSpecId] = useState<string | null>(null);
  const [fixPlan, setFixPlan] = useState<FixPlan | null>(null);
  const [isPlanning, setIsPlanning] = useState(false);
  const [isApplying, setIsApplying] = useState(false);

  // Load status report
  const loadReport = useCallback(async () => {
    if (!projectId) return;

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
      setError(err instanceof Error ? err.message : 'Failed to load status report');
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  // Load on mount and when project changes
  useEffect(() => {
    loadReport();
  }, [loadReport]);

  // Get severity icon
  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'info':
        return <Info className="h-4 w-4 text-blue-500" />;
      default:
        return <Info className="h-4 w-4" />;
    }
  };

  // Get severity badge variant
  const getSeverityVariant = (severity: string): 'destructive' | 'default' | 'secondary' => {
    switch (severity) {
      case 'error':
        return 'destructive';
      case 'warning':
        return 'default';
      default:
        return 'secondary';
    }
  };

  // Handle fix button click
  const handleFixClick = async (issue: Issue, specId: string) => {
    if (!selectedProject) return;

    setSelectedIssue(issue);
    setSelectedSpecId(specId);
    setShowFixDialog(true);
    setFixPlan(null);
    setIsPlanning(true);

    try {
      const result = await window.electronAPI.planFix({
        anomaly: issue,
        specId,
        projectPath: selectedProject.path,
      });

      if (result.success && result.data?.plan) {
        setFixPlan(result.data.plan);
      } else {
        setError(result.data?.error || result.error || 'Failed to generate fix plan');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate fix plan');
    } finally {
      setIsPlanning(false);
    }
  };

  // Handle apply fix
  const handleApplyFix = async () => {
    if (!selectedIssue || !selectedSpecId || !selectedProject) return;

    setIsApplying(true);
    try {
      const result = await window.electronAPI.startFix({
        anomaly: selectedIssue,
        specId: selectedSpecId,
        projectPath: selectedProject.path,
      });

      if (result.success) {
        // Refresh report after successful fix
        await loadReport();
        setShowFixDialog(false);
        setSelectedIssue(null);
        setSelectedSpecId(null);
        setFixPlan(null);
      } else {
        setError(result.error || 'Failed to apply fix');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply fix');
    } finally {
      setIsApplying(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center space-y-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <p className="text-lg font-semibold">Error</p>
        <p className="text-sm text-muted-foreground">{error}</p>
        <Button onClick={loadReport}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-muted-foreground">No status report available</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col space-y-4 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Status Report</h1>
          <p className="text-sm text-muted-foreground">
            {report.summary.totalSpecs} specs, {report.summary.totalIssues} issues detected
          </p>
        </div>
        <Button onClick={loadReport} variant="outline" size="sm">
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Summary */}
      {report.summary.totalIssues > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex space-x-4">
              {report.summary.issueSeverityCounts.error > 0 && (
                <Badge variant="destructive">
                  {report.summary.issueSeverityCounts.error} Errors
                </Badge>
              )}
              {report.summary.issueSeverityCounts.warning > 0 && (
                <Badge variant="default">
                  {report.summary.issueSeverityCounts.warning} Warnings
                </Badge>
              )}
              {report.summary.issueSeverityCounts.info > 0 && (
                <Badge variant="secondary">
                  {report.summary.issueSeverityCounts.info} Info
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Specs with Issues */}
      <ScrollArea className="flex-1">
        <div className="space-y-4">
          {report.specs.map((spec) => (
            <Card key={spec.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>{spec.id}</CardTitle>
                    <CardDescription>{spec.path}</CardDescription>
                  </div>
                  {spec.issueCount > 0 && (
                    <Badge variant={spec.issueCount > 0 ? 'destructive' : 'default'}>
                      {spec.issueCount} {spec.issueCount === 1 ? 'issue' : 'issues'}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              {spec.issues.length > 0 && (
                <CardContent>
                  <div className="space-y-3">
                    {spec.issues.map((issue, idx) => (
                      <div key={idx} className="flex items-start justify-between rounded-lg border p-3">
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center space-x-2">
                            {getSeverityIcon(issue.severity)}
                            <Badge variant={getSeverityVariant(issue.severity)}>
                              {issue.severity}
                            </Badge>
                            <span className="text-sm font-medium">{issue.code}</span>
                          </div>
                          <p className="text-sm text-muted-foreground">{issue.message}</p>
                          {issue.paths.length > 0 && (
                            <div className="text-xs text-muted-foreground">
                              <span className="font-medium">Paths:</span>{' '}
                              {issue.paths.join(', ')}
                            </div>
                          )}
                          {issue.suggestedFix && (
                            <div className="text-xs text-muted-foreground">
                              <span className="font-medium">Suggested:</span> {issue.suggestedFix}
                            </div>
                          )}
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleFixClick(issue, spec.id)}
                        >
                          <Wrench className="mr-2 h-4 w-4" />
                          Fix with AI
                        </Button>
                      </div>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
          ))}

          {/* Roadmap Issues */}
          {report.roadmap.exists && report.roadmap.issues.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Roadmap Issues</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {report.roadmap.issues.map((issue, idx) => (
                    <div key={idx} className="flex items-start justify-between rounded-lg border p-3">
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center space-x-2">
                          {getSeverityIcon(issue.severity)}
                          <Badge variant={getSeverityVariant(issue.severity)}>
                            {issue.severity}
                          </Badge>
                          <span className="text-sm font-medium">{issue.code}</span>
                        </div>
                        <p className="text-sm text-muted-foreground">{issue.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {report.specs.length === 0 && report.roadmap.issues.length === 0 && (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Check className="h-12 w-12 text-green-500 mb-4" />
                <p className="text-lg font-semibold">No Issues Found</p>
                <p className="text-sm text-muted-foreground">
                  All specs and roadmap are in good health!
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </ScrollArea>

      {/* Fix Preview Dialog */}
      <Dialog open={showFixDialog} onOpenChange={setShowFixDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('dialogs:statusReportFixPlan.title')}</DialogTitle>
            <DialogDescription>
              {t('dialogs:statusReportFixPlan.description')}
            </DialogDescription>
          </DialogHeader>

          {isPlanning ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin" />
              <span className="ml-2">{t('dialogs:statusReportFixPlan.planning')}</span>
            </div>
          ) : fixPlan ? (
            <div className="space-y-4">
              <div>
                <h4 className="font-semibold mb-2">Description</h4>
                <p className="text-sm text-muted-foreground">{fixPlan.description}</p>
              </div>
              <div>
                <h4 className="font-semibold mb-2">Changes</h4>
                <ScrollArea className="h-64 rounded border p-4">
                  <div className="space-y-2">
                    {fixPlan.changes.map((change, idx) => (
                      <div key={idx} className="text-sm">
                        <span className="font-medium">{change.action}:</span>{' '}
                        <span className="text-muted-foreground">{change.path}</span>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            </div>
          ) : (
            <div className="py-8 text-center text-muted-foreground">
              {t('dialogs:statusReportFixPlan.noPlan')}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowFixDialog(false)}>
              {t('common:cancel')}
            </Button>
            {fixPlan && (
              <Button onClick={handleApplyFix} disabled={isApplying}>
                {isApplying ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t('dialogs:statusReportFixPlan.applying')}
                  </>
                ) : (
                  t('dialogs:statusReportFixPlan.apply')
                )}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
