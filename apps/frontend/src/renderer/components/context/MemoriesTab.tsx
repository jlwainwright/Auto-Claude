import { useState, useMemo } from 'react';
import {
  RefreshCw,
  Database,
  Brain,
  Search,
  CheckCircle,
  XCircle,
  GitPullRequest,
  Lightbulb,
  FolderTree,
  Code,
  AlertTriangle,
  Calendar,
  X,
  Trash2,
  Download,
  CheckSquare,
  Square
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { ScrollArea } from '../ui/scroll-area';
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';
import { useToast } from '../../hooks/use-toast';
import { cn } from '../../lib/utils';
import { MemoryCard } from './MemoryCard';
import { InfoItem } from './InfoItem';
import { memoryFilterCategories } from './constants';
import { loadProjectContext } from '../../stores/context-store';
import type { GraphitiMemoryStatus, GraphitiMemoryState, MemoryEpisode } from '../../../shared/types';

type FilterCategory = keyof typeof memoryFilterCategories;

type DateFilterOption = 'all' | 'today' | 'thisWeek' | 'thisMonth' | 'custom';

interface MemoriesTabProps {
  projectId: string;
  memoryStatus: GraphitiMemoryStatus | null;
  memoryState: GraphitiMemoryState | null;
  recentMemories: MemoryEpisode[];
  memoriesLoading: boolean;
  searchResults: Array<{ type: string; content: string; score: number }>;
  searchLoading: boolean;
  onSearch: (query: string) => void;
}

// Helper to check if memory is a PR review (by type or content)
function isPRReview(memory: MemoryEpisode): boolean {
  if (['pr_review', 'pr_finding', 'pr_pattern', 'pr_gotcha'].includes(memory.type)) {
    return true;
  }
  try {
    const parsed = JSON.parse(memory.content);
    return parsed.prNumber !== undefined && parsed.verdict !== undefined;
  } catch {
    return false;
  }
}

// Get the effective category for a memory
function getMemoryCategory(memory: MemoryEpisode): FilterCategory {
  if (isPRReview(memory)) return 'pr';
  if (['session_insight', 'task_outcome'].includes(memory.type)) return 'sessions';
  if (['codebase_discovery', 'codebase_map'].includes(memory.type)) return 'codebase';
  if (['pattern', 'pr_pattern'].includes(memory.type)) return 'patterns';
  if (['gotcha', 'pr_gotcha'].includes(memory.type)) return 'gotchas';
  return 'sessions'; // default
}

// Date filter helpers
function isToday(timestamp: string): boolean {
  const date = new Date(timestamp);
  const today = new Date();
  return date.toDateString() === today.toDateString();
}

function isThisWeek(timestamp: string): boolean {
  const date = new Date(timestamp);
  const today = new Date();
  const startOfWeek = new Date(today);
  startOfWeek.setDate(today.getDate() - today.getDay()); // Start of week (Sunday)
  startOfWeek.setHours(0, 0, 0, 0);
  return date >= startOfWeek;
}

function isThisMonth(timestamp: string): boolean {
  const date = new Date(timestamp);
  const today = new Date();
  return date.getMonth() === today.getMonth() && date.getFullYear() === today.getFullYear();
}

function isInCustomRange(timestamp: string, startDate: Date, endDate: Date): boolean {
  const date = new Date(timestamp);
  return date >= startDate && date <= endDate;
}

// Filter icons for each category
const filterIcons: Record<FilterCategory, React.ElementType> = {
  all: Brain,
  pr: GitPullRequest,
  sessions: Lightbulb,
  codebase: FolderTree,
  patterns: Code,
  gotchas: AlertTriangle
};

export function MemoriesTab({
  projectId,
  memoryStatus,
  memoryState,
  recentMemories,
  memoriesLoading,
  searchResults,
  searchLoading,
  onSearch
}: MemoriesTabProps) {
  const { t } = useTranslation(['context', 'common']);
  const { toast } = useToast();
  const [localSearchQuery, setLocalSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<FilterCategory>('all');
  const [dateFilter, setDateFilter] = useState<DateFilterOption>('all');
  const [customStartDate, setCustomStartDate] = useState<string>('');
  const [customEndDate, setCustomEndDate] = useState<string>('');
  const [selectedMemoryIds, setSelectedMemoryIds] = useState<Set<string>>(new Set());
  const [selectionMode, setSelectionMode] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // Calculate memory counts by category
  const memoryCounts = useMemo(() => {
    const counts: Record<FilterCategory, number> = {
      all: recentMemories.length,
      pr: 0,
      sessions: 0,
      codebase: 0,
      patterns: 0,
      gotchas: 0
    };

    for (const memory of recentMemories) {
      const category = getMemoryCategory(memory);
      counts[category]++;
    }

    return counts;
  }, [recentMemories]);

  // Filter memories based on active filter and date range
  const filteredMemories = useMemo(() => {
    let filtered = recentMemories;

    // Apply category filter
    if (activeFilter !== 'all') {
      filtered = filtered.filter(memory => getMemoryCategory(memory) === activeFilter);
    }

    // Apply date filter
    if (dateFilter !== 'all') {
      filtered = filtered.filter(memory => {
        if (dateFilter === 'today') return isToday(memory.timestamp);
        if (dateFilter === 'thisWeek') return isThisWeek(memory.timestamp);
        if (dateFilter === 'thisMonth') return isThisMonth(memory.timestamp);
        if (dateFilter === 'custom' && customStartDate && customEndDate) {
          return isInCustomRange(memory.timestamp, new Date(customStartDate), new Date(customEndDate));
        }
        return true;
      });
    }

    return filtered;
  }, [recentMemories, activeFilter, dateFilter, customStartDate, customEndDate]);

  const handleSearch = () => {
    if (localSearchQuery.trim()) {
      onSearch(localSearchQuery);
    }
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const handleDateFilterChange = (option: DateFilterOption) => {
    setDateFilter(option);
    if (option !== 'custom') {
      setCustomStartDate('');
      setCustomEndDate('');
    }
  };

  const handleClearDateFilter = () => {
    setDateFilter('all');
    setCustomStartDate('');
    setCustomEndDate('');
  };

  const handleDeleteMemory = async (memoryId: string) => {
    try {
      const result = await window.electronAPI.deleteMemory(projectId, memoryId);

      if (result.success) {
        toast({
          title: 'Memory deleted',
          description: 'The memory has been successfully deleted.',
        });

        // Reload memories to update the list
        await loadProjectContext(projectId);
      } else {
        toast({
          title: 'Delete failed',
          description: result.error || 'Failed to delete memory. Please try again.',
          variant: 'destructive',
        });
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
      toast({
        title: 'Delete failed',
        description: errorMessage,
        variant: 'destructive',
      });
    }
  };

  const handleToggleSelection = (memoryId: string) => {
    setSelectedMemoryIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(memoryId)) {
        newSet.delete(memoryId);
      } else {
        newSet.add(memoryId);
      }
      return newSet;
    });
  };

  const handleSelectAll = () => {
    const allIds = new Set(filteredMemories.map(m => m.id));
    setSelectedMemoryIds(allIds);
  };

  const handleClearSelection = () => {
    setSelectedMemoryIds(new Set());
    setSelectionMode(false);
  };

  const handleBulkDelete = async () => {
    if (selectedMemoryIds.size === 0) return;

    let successCount = 0;
    let errorCount = 0;

    for (const memoryId of selectedMemoryIds) {
      try {
        const result = await window.electronAPI.deleteMemory(projectId, memoryId);
        if (result.success) {
          successCount++;
        } else {
          errorCount++;
        }
      } catch {
        errorCount++;
      }
    }

    if (successCount > 0) {
      toast({
        title: t('memories.bulkActions.deleteSuccess', { count: successCount }),
      });
    }

    if (errorCount > 0) {
      toast({
        title: t('memories.bulkActions.deleteError'),
        variant: 'destructive',
      });
    }

    // Clear selection and reload memories
    setSelectedMemoryIds(new Set());
    setSelectionMode(false);
    await loadProjectContext(projectId);
    setDeleteDialogOpen(false);
  };

  const handleExportJSON = () => {
    if (selectedMemoryIds.size === 0) return;

    try {
      const selectedMemories = filteredMemories.filter(m => selectedMemoryIds.has(m.id));
      const exportData = {
        exportDate: new Date().toISOString(),
        count: selectedMemories.length,
        memories: selectedMemories.map(m => ({
          id: m.id,
          type: m.type,
          timestamp: m.timestamp,
          content: m.content,
          session_number: m.session_number,
        }))
      };

      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `memories-export-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      toast({
        title: t('memories.bulkActions.exportSuccess', { count: selectedMemories.length }),
      });
    } catch {
      toast({
        title: t('memories.bulkActions.exportError'),
        variant: 'destructive',
      });
    }
  };

  return (
    <ScrollArea className="h-full">
      <div className="p-6 space-y-6">
        {/* Memory Status */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <Database className="h-4 w-4" />
                {t('memories.status.database')}
              </CardTitle>
              {memoryStatus?.available ? (
                <Badge variant="outline" className="bg-success/10 text-success border-success/30">
                  <CheckCircle className="h-3 w-3 mr-1" />
                  {t('memories.status.connected')}
                </Badge>
              ) : (
                <Badge variant="outline" className="bg-muted text-muted-foreground">
                  <XCircle className="h-3 w-3 mr-1" />
                  {t('memories.status.notAvailable')}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {memoryStatus?.available ? (
              <>
                <div className="grid gap-3 sm:grid-cols-2 text-sm">
                  <InfoItem label={t('memories.status.database')} value={memoryStatus.database || 'auto_claude_memory'} />
                  <InfoItem label={t('memories.status.path')} value={memoryStatus.dbPath || '~/.auto-claude/memories'} />
                </div>

                {/* Memory Stats Summary */}
                {recentMemories.length > 0 && (
                  <div className="pt-3 border-t border-border/50">
                    <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                      <div className="text-center p-2 rounded-lg bg-muted/30">
                        <div className="text-lg font-semibold text-foreground">{memoryCounts.all}</div>
                        <div className="text-xs text-muted-foreground">{t('memories.stats.total')}</div>
                      </div>
                      <div className="text-center p-2 rounded-lg bg-cyan-500/10">
                        <div className="text-lg font-semibold text-cyan-400">{memoryCounts.pr}</div>
                        <div className="text-xs text-muted-foreground">{t('memories.stats.prReviews')}</div>
                      </div>
                      <div className="text-center p-2 rounded-lg bg-amber-500/10">
                        <div className="text-lg font-semibold text-amber-400">{memoryCounts.sessions}</div>
                        <div className="text-xs text-muted-foreground">{t('memories.stats.sessions')}</div>
                      </div>
                      <div className="text-center p-2 rounded-lg bg-blue-500/10">
                        <div className="text-lg font-semibold text-blue-400">{memoryCounts.codebase}</div>
                        <div className="text-xs text-muted-foreground">{t('memories.stats.codebase')}</div>
                      </div>
                      <div className="text-center p-2 rounded-lg bg-purple-500/10">
                        <div className="text-lg font-semibold text-purple-400">{memoryCounts.patterns}</div>
                        <div className="text-xs text-muted-foreground">{t('memories.stats.patterns')}</div>
                      </div>
                      <div className="text-center p-2 rounded-lg bg-red-500/10">
                        <div className="text-lg font-semibold text-red-400">{memoryCounts.gotchas}</div>
                        <div className="text-xs text-muted-foreground">{t('memories.stats.gotchas')}</div>
                      </div>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-sm text-muted-foreground">
                <p>{memoryStatus?.reason || t('memories.status.notConfigured')}</p>
                <p className="mt-2 text-xs">
                  {t('memories.status.enableInfo', { code: '<code className="bg-muted px-1 py-0.5 rounded">GRAPHITI_ENABLED=true</code>' })}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Search */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            {t('memories.searchTitle')}
          </h3>
          <div className="flex gap-2">
            <Input
              placeholder={t('memories.searchPlaceholder')}
              value={localSearchQuery}
              onChange={(e) => setLocalSearchQuery(e.target.value)}
              onKeyDown={handleSearchKeyDown}
            />
            <Button onClick={handleSearch} disabled={searchLoading}>
              <Search className={cn('h-4 w-4', searchLoading && 'animate-pulse')} />
            </Button>
          </div>

          {/* Search Results */}
          {searchResults.length > 0 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {t('memories.resultsCount', { count: searchResults.length })}
              </p>
              {searchResults.map((result, idx) => (
                <Card key={idx} className="bg-muted/50">
                  <CardContent className="pt-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="outline" className="text-xs capitalize">
                        {result.type.replace('_', ' ')}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        Score: {result.score.toFixed(2)}
                      </span>
                    </div>
                    <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono max-h-40 overflow-auto">
                      {result.content}
                    </pre>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Memory Browser */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                {t('memories.title')}
              </h3>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={() => setSelectionMode(!selectionMode)}
              >
                {selectionMode ? <CheckSquare className="h-3.5 w-3.5 mr-1" /> : <Square className="h-3.5 w-3.5 mr-1" />}
                {selectionMode ? 'Done' : 'Select'}
              </Button>
            </div>
            <div className="flex items-center gap-2">
              {selectedMemoryIds.size > 0 && (
                <>
                  <Badge variant="secondary" className="text-xs">
                    {t('memories.bulkActions.selected', { count: selectedMemoryIds.size })}
                  </Badge>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={handleSelectAll}
                  >
                    {t('memories.bulkActions.selectAll')}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={handleClearSelection}
                  >
                    {t('memories.bulkActions.clearSelection')}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs gap-1"
                    onClick={handleExportJSON}
                  >
                    <Download className="h-3.5 w-3.5" />
                    {t('memories.bulkActions.exportSelected')}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs gap-1 text-destructive hover:text-destructive"
                    onClick={() => setDeleteDialogOpen(true)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    {t('memories.bulkActions.deleteSelected')}
                  </Button>
                </>
              )}
              <span className="text-xs text-muted-foreground">
                {t('memories.of', { filtered: filteredMemories.length, total: recentMemories.length })}
              </span>
            </div>
          </div>

          {/* Filter Pills */}
          <div className="flex flex-wrap gap-2">
            {(Object.keys(memoryFilterCategories) as FilterCategory[]).map((category) => {
              const config = memoryFilterCategories[category];
              const count = memoryCounts[category];
              const Icon = filterIcons[category];
              const isActive = activeFilter === category;

              return (
                <Button
                  key={category}
                  variant={isActive ? 'default' : 'outline'}
                  size="sm"
                  className={cn(
                    'gap-1.5 h-8',
                    isActive && 'bg-accent text-accent-foreground',
                    !isActive && count === 0 && 'opacity-50'
                  )}
                  onClick={() => setActiveFilter(category)}
                  disabled={count === 0 && category !== 'all'}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{config.label}</span>
                  {count > 0 && (
                    <Badge
                      variant="secondary"
                      className={cn(
                        'ml-1 px-1.5 py-0 text-xs',
                        isActive && 'bg-background/20'
                      )}
                    >
                      {count}
                    </Badge>
                  )}
                </Button>
              );
            })}
          </div>

          {/* Date Filter */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm text-muted-foreground">{t('memories.dateFilter.title')}:</span>
            <div className="flex flex-wrap gap-1">
              <Button
                variant={dateFilter === 'all' ? 'default' : 'outline'}
                size="sm"
                className="h-8"
                onClick={() => handleDateFilterChange('all')}
              >
                {t('memories.dateFilter.allTime')}
              </Button>
              <Button
                variant={dateFilter === 'today' ? 'default' : 'outline'}
                size="sm"
                className="h-8"
                onClick={() => handleDateFilterChange('today')}
              >
                {t('memories.dateFilter.today')}
              </Button>
              <Button
                variant={dateFilter === 'thisWeek' ? 'default' : 'outline'}
                size="sm"
                className="h-8"
                onClick={() => handleDateFilterChange('thisWeek')}
              >
                {t('memories.dateFilter.thisWeek')}
              </Button>
              <Button
                variant={dateFilter === 'thisMonth' ? 'default' : 'outline'}
                size="sm"
                className="h-8"
                onClick={() => handleDateFilterChange('thisMonth')}
              >
                {t('memories.dateFilter.thisMonth')}
              </Button>
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant={dateFilter === 'custom' ? 'default' : 'outline'}
                    size="sm"
                    className="h-8 gap-1.5"
                  >
                    <Calendar className="h-3.5 w-3.5" />
                    {t('memories.dateFilter.customRange')}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-80 p-4" align="start">
                  <div className="space-y-3">
                    <h4 className="font-medium text-sm flex items-center gap-2">
                      <Calendar className="h-4 w-4" />
                      {t('memories.dateFilter.customRange')}
                    </h4>
                    <div className="space-y-2">
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground">{t('memories.dateFilter.from')}</label>
                        <Input
                          type="date"
                          value={customStartDate}
                          onChange={(e) => setCustomStartDate(e.target.value)}
                          className="h-8"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground">{t('memories.dateFilter.to')}</label>
                        <Input
                          type="date"
                          value={customEndDate}
                          onChange={(e) => setCustomEndDate(e.target.value)}
                          className="h-8"
                        />
                      </div>
                    </div>
                    <div className="flex gap-2 pt-1">
                      <Button
                        size="sm"
                        className="flex-1"
                        onClick={() => {
                          if (customStartDate && customEndDate) {
                            handleDateFilterChange('custom');
                          }
                        }}
                        disabled={!customStartDate || !customEndDate}
                      >
                        {t('memories.dateFilter.apply')}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="flex-1"
                        onClick={handleClearDateFilter}
                      >
                        {t('memories.dateFilter.clear')}
                      </Button>
                    </div>
                  </div>
                </PopoverContent>
              </Popover>
              {dateFilter !== 'all' && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 text-muted-foreground"
                  onClick={handleClearDateFilter}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </div>

          {/* Memory List */}
          {memoriesLoading && (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {!memoriesLoading && filteredMemories.length === 0 && recentMemories.length === 0 && (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Brain className="h-10 w-10 text-muted-foreground mb-3" />
              <p className="text-sm text-muted-foreground">
                {t('memories.empty.noMemories')}
              </p>
            </div>
          )}

          {!memoriesLoading && filteredMemories.length === 0 && recentMemories.length > 0 && (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Brain className="h-10 w-10 text-muted-foreground mb-3" />
              <p className="text-sm text-muted-foreground">
                {t('memories.empty.noMatch')}
              </p>
              <Button
                variant="link"
                size="sm"
                onClick={() => {
                  setActiveFilter('all');
                  handleClearDateFilter();
                }}
                className="mt-2"
              >
                {t('memories.empty.showAll')}
              </Button>
            </div>
          )}

          {filteredMemories.length > 0 && (
            <div className="space-y-3">
              {filteredMemories.map((memory) => (
                <MemoryCard
                  key={memory.id}
                  memory={memory}
                  projectId={projectId}
                  onDelete={handleDeleteMemory}
                  isSelected={selectedMemoryIds.has(memory.id)}
                  onSelectionToggle={handleToggleSelection}
                  selectionMode={selectionMode}
                />
              ))}
            </div>
          )}
        </div>

        {/* Bulk Delete Confirmation Dialog */}
        <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('memories.bulkActions.deleteSelected')}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('memories.bulkActions.deleteConfirm', { count: selectedMemoryIds.size })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleBulkDelete}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </ScrollArea>
  );
}
