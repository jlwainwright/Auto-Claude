import { useState } from 'react';
import {
  X,
  Edit,
  Trash2,
  Loader2,
  Calendar,
  Hash,
  FolderSymlink
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '../ui/alert-dialog';
import { cn } from '../../lib/utils';
import { memoryTypeColors, memoryTypeLabels } from './constants';
import { formatDate } from './utils';
import type { MemoryGraphNode, MemoryGraphEdge } from '../../../shared/types';

interface MemoryDetailPanelProps {
  node: MemoryGraphNode;
  edges: MemoryGraphEdge[];
  projectId: string;
  onClose: () => void;
  onEdit?: (node: MemoryGraphNode) => void;
  onDelete?: (nodeId: string) => void;
}

// Truncate text for display
function truncateText(text: string, maxLength: number): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

export function MemoryDetailPanel({
  node,
  edges,
  projectId,
  onClose,
  onEdit,
  onDelete
}: MemoryDetailPanelProps) {
  const { t } = useTranslation(['context', 'common']);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  // Handle delete action
  const handleDelete = async () => {
    if (!onDelete) return;

    setIsDeleting(true);
    try {
      await onDelete(node.id);
      setShowDeleteDialog(false);
      onClose();
    } catch (error) {
      console.error('Failed to delete memory:', error);
      setIsDeleting(false);
    }
  };

  // Handle edit action
  const handleEdit = () => {
    if (onEdit) {
      onEdit(node);
    }
  };

  // Get incoming and outgoing connections
  const incomingEdges = edges.filter(edge => edge.target === node.id);
  const outgoingEdges = edges.filter(edge => edge.source === node.id);
  const hasConnections = incomingEdges.length > 0 || outgoingEdges.length > 0;

  return (
    <>
      <div className="w-96 border-l border-border bg-background flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border shrink-0">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Badge variant="outline" className={cn('text-xs capitalize whitespace-nowrap', memoryTypeColors[node.type])}>
              {memoryTypeLabels[node.type] || node.type}
            </Badge>
            <span className="text-sm font-medium text-foreground truncate">
              {node.label}
            </span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0 h-8 w-8"
            onClick={onClose}
            title={t('memories.detail.closePanel')}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Content */}
        <ScrollArea className="flex-1 p-4">
          <div className="space-y-4">
            {/* Metadata */}
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Calendar className="h-3.5 w-3.5" />
                <span>{t('memories.detail.created', { date: formatDate(node.timestamp) })}</span>
              </div>
              {node.session_number && (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Hash className="h-3.5 w-3.5" />
                  <span>{t('memories.detail.session', { number: node.session_number })}</span>
                </div>
              )}
              {node.group_id && (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <FolderSymlink className="h-3.5 w-3.5" />
                  <span className="font-mono text-xs">{truncateText(node.group_id, 30)}</span>
                </div>
              )}
            </div>

            {/* Content */}
            {node.content && (
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-foreground">{t('memories.detail.content')}</h4>
                <div className="bg-muted/30 rounded-lg p-3 border border-border/50">
                  <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono max-h-96 overflow-auto">
                    {node.content}
                  </pre>
                </div>
              </div>
            )}

            {/* Connections */}
            {hasConnections && (
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-foreground">
                  {t('memories.detail.connections', { count: incomingEdges.length + outgoingEdges.length })}
                </h4>
                <div className="space-y-2">
                  {/* Incoming connections */}
                  {incomingEdges.length > 0 && (
                    <>
                      {incomingEdges.map((edge, idx) => (
                        <div key={`in-${idx}`} className="text-xs bg-muted/30 rounded p-2 border border-border/50">
                          <div className="text-muted-foreground flex items-center gap-1">
                            <span className="text-accent">←</span>
                            <span className="font-mono">{truncateText(edge.source_name || edge.source, 25)}</span>
                          </div>
                          <div className="text-accent text-[10px] mt-1 capitalize ml-4">
                            {edge.label || edge.relationship_type}
                          </div>
                        </div>
                      ))}
                    </>
                  )}

                  {/* Outgoing connections */}
                  {outgoingEdges.length > 0 && (
                    <>
                      {outgoingEdges.map((edge, idx) => (
                        <div key={`out-${idx}`} className="text-xs bg-muted/30 rounded p-2 border border-border/50">
                          <div className="text-muted-foreground flex items-center gap-1">
                            <span className="text-accent">→</span>
                            <span className="font-mono">{truncateText(edge.target_name || edge.target, 25)}</span>
                          </div>
                          <div className="text-accent text-[10px] mt-1 capitalize ml-4">
                            {edge.label || edge.relationship_type}
                          </div>
                        </div>
                      ))}
                    </>
                  )}
                </div>
              </div>
            )}

            {/* No connections message */}
            {!hasConnections && (
              <div className="text-sm text-muted-foreground text-center py-4 italic">
                {t('memories.detail.noConnections')}
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Footer with action buttons */}
        <div className="p-4 border-t border-border shrink-0">
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="flex-1"
              onClick={handleEdit}
              disabled={!onEdit}
            >
              <Edit className="h-4 w-4 mr-2" />
              {t('memories.detail.edit')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 text-destructive hover:text-destructive hover:bg-destructive/10"
              onClick={() => setShowDeleteDialog(true)}
              disabled={!onDelete || isDeleting}
            >
              {isDeleting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t('memories.detail.deleting')}
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4 mr-2" />
                  {t('memories.detail.delete')}
                </>
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Delete confirmation dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('memories.detail.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('memories.detail.deleteConfirm', { label: node.label })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>{t('memories.detail.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t('memories.detail.deleting')}
                </>
              ) : (
                t('memories.detail.delete')
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
