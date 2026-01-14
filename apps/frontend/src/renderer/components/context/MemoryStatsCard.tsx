import { useMemo, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  HardDrive,
  Calendar,
  BarChart3,
  AlertCircle,
  RefreshCw
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import { memoryTypeColors } from './constants';
import { formatDate } from './utils';
import type { MemoryEpisode } from '../../../shared/types';

interface MemoryStatsCardProps {
  memories: MemoryEpisode[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

interface TypeStats {
  type: string;
  count: number;
  percentage: number;
}

interface MemoryDateRange {
  oldest: MemoryEpisode | null;
  newest: MemoryEpisode | null;
}

export function MemoryStatsCard({ memories, loading = false, error = null, onRetry }: MemoryStatsCardProps) {
  const { t } = useTranslation(['context', 'common']);

  // Calculate statistics from memories
  const stats = useMemo(() => {
    if (!memories || memories.length === 0) {
      return {
        total: 0,
        byType: [] as TypeStats[],
        dateRange: { oldest: null, newest: null } as MemoryDateRange,
        storageSize: null
      };
    }

    // Count by type
    const typeCounts: Record<string, number> = {};
    memories.forEach(memory => {
      typeCounts[memory.type] = (typeCounts[memory.type] || 0) + 1;
    });

    // Calculate percentages
    const byType: TypeStats[] = Object.entries(typeCounts)
      .map(([type, count]) => ({
        type,
        count,
        percentage: (count / memories.length) * 100
      }))
      .sort((a, b) => b.count - a.count);

    // Find oldest and newest
    const sortedByDate = [...memories].sort((a, b) =>
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
    const dateRange: MemoryDateRange = {
      oldest: sortedByDate[0] || null,
      newest: sortedByDate[sortedByDate.length - 1] || null
    };

    // Storage size (estimate based on content length)
    // This is a rough estimate since we don't have actual storage stats in MemoryEpisode
    const estimatedSize = new Blob([JSON.stringify(memories)]).size;
    const storageSize = formatBytes(estimatedSize);

    return {
      total: memories.length,
      byType,
      dateRange,
      storageSize
    };
  }, [memories]);

  // Format bytes to human readable format
  function formatBytes(bytes: number, decimals = 2): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  // Get type label translation
  function getTypeLabel(type: string): string {
    const key = type.replace(/_/g, '').replace(/([A-Z])/g, '_$1').toLowerCase();
    const translationKey = `memories.stats.type.${type}`;
    const result = t(translationKey);
    // If translation key is returned as-is, fall back to a simple formatted label
    if (result === translationKey) {
      return type.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    }
    return result;
  }

  // Loading state with skeleton
  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            {t('memories.stats.card.title')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Total count and storage skeletons */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-7 w-16" />
            </div>
            <div className="space-y-1">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-6 w-20" />
            </div>
          </div>

          {/* Date range skeletons */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Skeleton className="h-3 w-3" />
              <Skeleton className="h-3 w-24" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Skeleton className="h-3 w-24 mb-2" />
                <Skeleton className="h-4 w-28" />
              </div>
              <div>
                <Skeleton className="h-3 w-24 mb-2" />
                <Skeleton className="h-4 w-28" />
              </div>
            </div>
          </div>

          {/* Distribution skeletons */}
          <div className="space-y-3">
            <Skeleton className="h-3 w-32" />
            <div className="space-y-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <Skeleton className="h-3 w-24" />
                    <Skeleton className="h-3 w-16" />
                  </div>
                  <Skeleton className="h-2 w-full" />
                </div>
              ))}
            </div>
          </div>

          {/* Badges skeletons */}
          <div className="flex flex-wrap gap-2">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-6 w-20 rounded-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            {t('memories.stats.card.title')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-8 text-center space-y-3">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <div>
              <p className="text-sm font-medium text-destructive">
                {t('memories.stats.card.error')}
              </p>
              <p className="text-xs text-muted-foreground mt-1">{error}</p>
            </div>
            {onRetry && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRetry}
                className="gap-2"
              >
                <RefreshCw className="h-3 w-3" />
                {t('memories.stats.card.retry')}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  // No data state
  if (!memories || memories.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            {t('memories.stats.card.title')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <p className="text-sm">{t('memories.stats.card.noData')}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Main stats display
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <BarChart3 className="h-4 w-4" />
          {t('memories.stats.card.title')}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Total count and storage */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">
              {t('memories.stats.card.totalMemories')}
            </div>
            <div className="text-2xl font-semibold text-foreground">
              {stats.total}
            </div>
          </div>
          {stats.storageSize && (
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground flex items-center gap-1">
                <HardDrive className="h-3 w-3" />
                {t('memories.stats.card.storageSize')}
              </div>
              <div className="text-lg font-medium text-foreground">
                {stats.storageSize}
              </div>
            </div>
          )}
        </div>

        {/* Date range */}
        {(stats.dateRange.oldest || stats.dateRange.newest) && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Calendar className="h-3 w-3" />
              <span className="font-medium">Date Range</span>
            </div>
            <div className="grid grid-cols-2 gap-4 text-xs">
              {stats.dateRange.oldest && (
                <div>
                  <div className="text-muted-foreground">{t('memories.stats.card.oldestMemory')}</div>
                  <div className="text-foreground mt-0.5" title={formatDate(stats.dateRange.oldest.timestamp)}>
                    {formatDate(stats.dateRange.oldest.timestamp)}
                  </div>
                </div>
              )}
              {stats.dateRange.newest && (
                <div>
                  <div className="text-muted-foreground">{t('memories.stats.card.newestMemory')}</div>
                  <div className="text-foreground mt-0.5" title={formatDate(stats.dateRange.newest.timestamp)}>
                    {formatDate(stats.dateRange.newest.timestamp)}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Distribution by type */}
        {stats.byType.length > 0 && (
          <div className="space-y-3">
            <div className="text-xs font-medium text-muted-foreground">
              {t('memories.stats.card.distribution')}
            </div>
            <div className="space-y-2">
              {stats.byType.map((typeStat) => (
                <div key={typeStat.type} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-foreground font-medium">{getTypeLabel(typeStat.type)}</span>
                    <span className="text-muted-foreground">
                      {typeStat.count} ({typeStat.percentage.toFixed(1)}%)
                    </span>
                  </div>
                  <Progress
                    value={typeStat.percentage}
                    className="h-2"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Quick badges for top types */}
        {stats.byType.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {stats.byType.slice(0, 4).map((typeStat) => {
              const colorClass = memoryTypeColors[typeStat.type] || 'bg-muted text-muted-foreground';
              return (
                <Badge
                  key={typeStat.type}
                  variant="outline"
                  className={`text-xs capitalize ${colorClass}`}
                >
                  {getTypeLabel(typeStat.type)} ({typeStat.count})
                </Badge>
              );
            })}
            {stats.byType.length > 4 && (
              <Badge variant="secondary" className="text-xs">
                +{stats.byType.length - 4} more
              </Badge>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
