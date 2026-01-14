/**
 * MemoryEditDialog - Modal dialog for editing memory content
 *
 * Allows users to edit the content of a memory episode stored in Graphiti.
 * Provides a textarea with the current content, validation, and loading states.
 *
 * Features:
 * - Pre-populates textarea with current memory content
 * - Content validation (cannot be empty)
 * - Loading state during save
 * - Success/error toast notifications
 * - Save and Cancel buttons
 * - Prevents closing while saving
 *
 * @example
 * ```tsx
 * <MemoryEditDialog
 *   node={selectedNode}
 *   projectId={currentProjectId}
 *   open={isEditDialogOpen}
 *   onOpenChange={setIsEditDialogOpen}
 *   onSaved={() => console.log('Memory updated!')}
 * />
 * ```
 */
import { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';
import { Label } from '../ui/label';
import { useToast } from '../../hooks/use-toast';
import { cn } from '../../lib/utils';
import type { MemoryGraphNode } from '../../../shared/types';

/**
 * Props for the MemoryEditDialog component
 */
interface MemoryEditDialogProps {
  /** The memory node to edit */
  node: MemoryGraphNode;
  /** Project ID for the memory */
  projectId: string;
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when the dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** Optional callback when memory is successfully saved */
  onSaved?: () => void;
}

export function MemoryEditDialog({
  node,
  projectId,
  open,
  onOpenChange,
  onSaved
}: MemoryEditDialogProps) {
  const { t } = useTranslation(['context', 'common']);
  const { toast } = useToast();
  const [content, setContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset form when dialog opens or node changes
  useEffect(() => {
    if (open) {
      setContent(node.content || '');
      setError(null);
    }
  }, [open, node]);

  /**
   * Handle save action
   */
  const handleSave = async () => {
    const trimmedContent = content.trim();

    // Validate content is not empty
    if (!trimmedContent) {
      setError(t('memories.edit.validation.empty'));
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      // Call the IPC API to update the memory
      const result = await window.electronAPI.updateMemory(projectId, node.id, trimmedContent);

      if (result.success) {
        // Show success toast
        toast({
          title: t('memories.edit.toast.success.title'),
          description: t('memories.edit.toast.success.description'),
        });

        // Close dialog and notify parent
        onOpenChange(false);
        onSaved?.();
      } else {
        // Show error from API
        setError(result.error || t('memories.edit.toast.error.description'));
        toast({
          title: t('memories.edit.toast.error.title'),
          description: result.error || t('memories.edit.toast.error.description'),
          variant: 'destructive',
        });
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('memories.edit.toast.error.description');
      setError(errorMessage);
      toast({
        title: t('memories.edit.toast.error.title'),
        description: errorMessage,
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  /**
   * Handle close action
   * Prevents closing while saving
   */
  const handleClose = () => {
    if (!isSaving) {
      onOpenChange(false);
    }
  };

  // Form is valid if content is not empty
  const isValid = content.trim().length > 0;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="text-foreground">{t('memories.edit.title')}</DialogTitle>
          <DialogDescription>
            {t('memories.edit.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Memory Type Badge (Read-only) */}
          <div className="flex items-center gap-2">
            <Label className="text-sm font-medium text-muted-foreground">{t('memories.edit.type')}</Label>
            <span className="text-sm capitalize text-foreground">
              {node.type.replace(/_/g, ' ')}
            </span>
          </div>

          {/* Memory Label (Read-only) */}
          <div className="space-y-2">
            <Label className="text-sm font-medium text-muted-foreground">{t('memories.edit.label')}</Label>
            <div className="text-sm text-foreground">{node.label}</div>
          </div>

          {/* Content Editable Textarea */}
          <div className="space-y-2">
            <Label htmlFor="memory-content" className="text-sm font-medium text-foreground">
              {t('memories.edit.contentLabel')} <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="memory-content"
              placeholder={t('memories.edit.contentPlaceholder')}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={10}
              disabled={isSaving}
              aria-required="true"
              className={cn(
                'font-mono text-sm',
                error && 'border-destructive focus-visible:ring-destructive'
              )}
            />
            <p className="text-xs text-muted-foreground">
              {t('memories.edit.contentHint')}
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="rounded-lg bg-destructive/10 border border-destructive/30 p-3 text-sm text-destructive" role="alert">
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isSaving}>
            {t('memories.edit.cancel')}
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving || !isValid}
          >
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('memories.edit.saving')}
              </>
            ) : (
              t('memories.edit.saveChanges')
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
