/**
 * TaskEditDialog - Dialog for editing task details
 *
 * Allows users to modify all task properties including title, description,
 * classification fields, images, and review settings.
 *
 * Now uses the shared TaskModalLayout for consistent styling with other task modals,
 * and TaskFormFields for the form content.
 *
 * Features:
 * - Pre-populates form with current task values
 * - Form validation (description required)
 * - Editable classification fields (category, priority, complexity, impact)
 * - Editable image attachments (add/remove images)
 * - Editable review settings (requireReviewBeforeCoding)
 * - Saves changes via persistUpdateTask (updates store + spec files)
 * - Prevents save when no changes have been made
 *
 * @example
 * ```tsx
 * <TaskEditDialog
 *   task={selectedTask}
 *   open={isEditDialogOpen}
 *   onOpenChange={setIsEditDialogOpen}
 *   onSaved={() => console.log('Task updated!')}
 * />
 * ```
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';
import { Button } from './ui/button';
import { TaskModalLayout } from './task-form/TaskModalLayout';
import { TaskFormFields } from './task-form/TaskFormFields';
import { persistUpdateTask } from '../stores/task-store';
import type { Task, ImageAttachment, TaskCategory, TaskPriority, TaskComplexity, TaskImpact, ModelType, ThinkingLevel } from '../../shared/types';
import {
  DEFAULT_AGENT_PROFILES,
  DEFAULT_PHASE_MODELS,
  DEFAULT_PHASE_THINKING
} from '../../shared/constants';
import type { PhaseModelConfig, PhaseThinkingConfig } from '../../shared/types/settings';
import { useSettingsStore } from '../stores/settings-store';

/**
 * Props for the TaskEditDialog component
 */
interface TaskEditDialogProps {
  /** The task to edit */
  task: Task;
  /** Whether the dialog is open */
  open: boolean;
  /** Callback when the dialog open state changes */
  onOpenChange: (open: boolean) => void;
  /** Optional callback when task is successfully saved */
  onSaved?: () => void;
}

export function TaskEditDialog({ task, open, onOpenChange, onSaved }: TaskEditDialogProps) {
  const { t } = useTranslation(['tasks', 'common']);
  // Get selected agent profile from settings for defaults
  const { settings } = useSettingsStore();
  const allProfiles = useMemo(
    () => [...DEFAULT_AGENT_PROFILES, ...(settings.customAgentProfiles ?? [])],
    [settings.customAgentProfiles]
  );
  const selectedProfile = useMemo(
    () => allProfiles.find((p) => p.id === settings.selectedAgentProfile) || allProfiles.find((p) => p.id === 'auto')!,
    [allProfiles, settings.selectedAgentProfile]
  );

  // Form state
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showClassification, setShowClassification] = useState(false);

  // Classification fields
  const [category, setCategory] = useState<TaskCategory | ''>(task.metadata?.category || '');
  const [priority, setPriority] = useState<TaskPriority | ''>(task.metadata?.priority || '');
  const [complexity, setComplexity] = useState<TaskComplexity | ''>(task.metadata?.complexity || '');
  const [impact, setImpact] = useState<TaskImpact | ''>(task.metadata?.impact || '');

  // Agent profile / model configuration
  const [profileId, setProfileId] = useState<string>(() => {
    const storedProfileId = task.metadata?.profileId;
    if (storedProfileId) {
      if (storedProfileId === 'custom') return 'custom';
      if (allProfiles.some((p) => p.id === storedProfileId)) return storedProfileId;
      return 'custom';
    }
    if (task.metadata?.isAutoProfile) return 'auto';
    const taskModel = task.metadata?.model;
    const taskThinking = task.metadata?.thinkingLevel;
    if (taskModel && taskThinking) {
      const matchingProfile = allProfiles.find(
        p => p.id !== 'auto' && p.model === taskModel && p.thinkingLevel === taskThinking
      );
      return matchingProfile?.id || 'custom';
    }
    return settings.selectedAgentProfile || 'auto';
  });
  const [model, setModel] = useState<ModelType | ''>(task.metadata?.model || selectedProfile.model);
  const [thinkingLevel, setThinkingLevel] = useState<ThinkingLevel | ''>(
    task.metadata?.thinkingLevel || selectedProfile.thinkingLevel
  );
  const [phaseModels, setPhaseModels] = useState<PhaseModelConfig | undefined>(
    task.metadata?.phaseModels || selectedProfile.phaseModels || DEFAULT_PHASE_MODELS
  );
  const [phaseThinking, setPhaseThinking] = useState<PhaseThinkingConfig | undefined>(
    task.metadata?.phaseThinking || selectedProfile.phaseThinking || DEFAULT_PHASE_THINKING
  );

  // Image attachments
  const [images, setImages] = useState<ImageAttachment[]>(task.metadata?.attachedImages || []);

  // Review setting
  const [requireReviewBeforeCoding, setRequireReviewBeforeCoding] = useState(
    task.metadata?.requireReviewBeforeCoding ?? false
  );

  // Initialize form when dialog opens (or when switching tasks while open).
  // Important: tasks update frequently during execution (logs/progress), so we must not
  // clobber in-progress user edits while the modal is open.
  const initializedTaskIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (!open) {
      initializedTaskIdRef.current = null;
      return;
    }

    if (initializedTaskIdRef.current === task.id) {
      return;
    }
    initializedTaskIdRef.current = task.id;

    setTitle(task.title);
    setDescription(task.description);
    setCategory(task.metadata?.category || '');
    setPriority(task.metadata?.priority || '');
    setComplexity(task.metadata?.complexity || '');
    setImpact(task.metadata?.impact || '');

    // Reset model configuration
    const taskModel = task.metadata?.model;
    const taskThinking = task.metadata?.thinkingLevel;
    const storedProfileId = task.metadata?.profileId;

    let nextProfileId: string;
    if (storedProfileId) {
      if (storedProfileId === 'custom') {
        nextProfileId = 'custom';
      } else if (allProfiles.some((p) => p.id === storedProfileId)) {
        nextProfileId = storedProfileId;
      } else {
        nextProfileId = 'custom';
      }
    } else if (task.metadata?.isAutoProfile) {
      nextProfileId = 'auto';
    } else if (taskModel && taskThinking) {
      const matchingProfile = allProfiles.find(
        (p) => p.id !== 'auto' && p.model === taskModel && p.thinkingLevel === taskThinking
      );
      nextProfileId = matchingProfile?.id || 'custom';
    } else {
      nextProfileId = settings.selectedAgentProfile || 'auto';
    }

    const profileDefaults = allProfiles.find((p) => p.id === nextProfileId) || selectedProfile;

    setProfileId(nextProfileId);
    setModel(taskModel || profileDefaults.model);
    setThinkingLevel(taskThinking || profileDefaults.thinkingLevel);
    setPhaseModels(task.metadata?.phaseModels || profileDefaults.phaseModels || DEFAULT_PHASE_MODELS);
    setPhaseThinking(task.metadata?.phaseThinking || profileDefaults.phaseThinking || DEFAULT_PHASE_THINKING);

    setImages(task.metadata?.attachedImages || []);
    setRequireReviewBeforeCoding(task.metadata?.requireReviewBeforeCoding ?? false);
    setError(null);

    // Auto-expand classification if it has content
    if (task.metadata?.category || task.metadata?.priority || task.metadata?.complexity || task.metadata?.impact) {
      setShowClassification(true);
    } else {
      setShowClassification(false);
    }
  }, [open, task, allProfiles, settings.selectedAgentProfile, selectedProfile]);

  const handleSave = async () => {
    // Validate input
    if (!description.trim()) {
      setError(t('tasks:form.errors.descriptionRequired'));
      return;
    }

    // Check if anything changed
    const trimmedTitle = title.trim();
    const trimmedDescription = description.trim();

    // Detect changes in agent configuration (single-model vs per-phase)
    const isCustomProfile = profileId === 'custom';
    const nextPhaseModels = isCustomProfile ? undefined : (phaseModels || DEFAULT_PHASE_MODELS);
    const nextPhaseThinking = isCustomProfile ? undefined : (phaseThinking || DEFAULT_PHASE_THINKING);
    const prevPhaseModels = task.metadata?.phaseModels;
    const prevPhaseThinking = task.metadata?.phaseThinking;

    const normalize = (value: unknown) => (value ? JSON.stringify(value) : null);
    const phaseModelsChanged = normalize(nextPhaseModels) !== normalize(prevPhaseModels);
    const phaseThinkingChanged = normalize(nextPhaseThinking) !== normalize(prevPhaseThinking);

    const hasChanges =
      trimmedTitle !== task.title ||
      trimmedDescription !== task.description ||
      category !== (task.metadata?.category || '') ||
      priority !== (task.metadata?.priority || '') ||
      complexity !== (task.metadata?.complexity || '') ||
      impact !== (task.metadata?.impact || '') ||
      model !== (task.metadata?.model || '') ||
      thinkingLevel !== (task.metadata?.thinkingLevel || '') ||
      phaseModelsChanged ||
      phaseThinkingChanged ||
      requireReviewBeforeCoding !== (task.metadata?.requireReviewBeforeCoding ?? false) ||
      JSON.stringify(images) !== JSON.stringify(task.metadata?.attachedImages || []);

    if (!hasChanges) {
      onOpenChange(false);
      return;
    }

    setIsSaving(true);
    setError(null);

    // Build metadata updates
    const metadataUpdates: Partial<typeof task.metadata> = {};
    if (category) metadataUpdates.category = category;
    if (priority) metadataUpdates.priority = priority;
    if (complexity) metadataUpdates.complexity = complexity;
    if (impact) metadataUpdates.impact = impact;
    metadataUpdates.profileId = profileId;
    if (model) metadataUpdates.model = model as ModelType;
    if (thinkingLevel) metadataUpdates.thinkingLevel = thinkingLevel as ThinkingLevel;

    // Per-phase config is used for all saved profiles; single-model config uses 'custom'
    if (profileId === 'custom') {
      metadataUpdates.isAutoProfile = false;
      metadataUpdates.phaseModels = undefined;
      metadataUpdates.phaseThinking = undefined;
    } else {
      metadataUpdates.isAutoProfile = profileId === 'auto';
      metadataUpdates.phaseModels = phaseModels || DEFAULT_PHASE_MODELS;
      metadataUpdates.phaseThinking = phaseThinking || DEFAULT_PHASE_THINKING;
    }
    // Always set attachedImages to persist removal when all images are deleted
    metadataUpdates.attachedImages = images.length > 0 ? images : [];
    metadataUpdates.requireReviewBeforeCoding = requireReviewBeforeCoding;

    const success = await persistUpdateTask(task.id, {
      title: trimmedTitle,
      description: trimmedDescription,
      metadata: metadataUpdates
    });

    if (success) {
      onOpenChange(false);
      onSaved?.();
    } else {
      setError(t('tasks:edit.errors.updateFailed'));
    }

    setIsSaving(false);
  };

  const isValid = description.trim().length > 0;

  return (
    <TaskModalLayout
      open={open}
      onOpenChange={onOpenChange}
      title={t('tasks:edit.title')}
      description={t('tasks:edit.description')}
      disabled={isSaving}
      footer={
        <div className="flex items-center justify-end gap-3">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            {t('common:buttons.cancel')}
          </Button>
          <Button onClick={handleSave} disabled={isSaving || !isValid}>
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('common:buttons.saving')}
              </>
            ) : (
              t('tasks:edit.saveChanges')
            )}
          </Button>
        </div>
      }
    >
      <TaskFormFields
        description={description}
        onDescriptionChange={setDescription}
        title={title}
        onTitleChange={setTitle}
        profileId={profileId}
        model={model}
        thinkingLevel={thinkingLevel}
        phaseModels={phaseModels}
        phaseThinking={phaseThinking}
        onProfileChange={(newProfileId, newModel, newThinkingLevel) => {
          setProfileId(newProfileId);
          setModel(newModel);
          setThinkingLevel(newThinkingLevel);
        }}
        onModelChange={setModel}
        onThinkingLevelChange={setThinkingLevel}
        onPhaseModelsChange={setPhaseModels}
        onPhaseThinkingChange={setPhaseThinking}
        category={category}
        priority={priority}
        complexity={complexity}
        impact={impact}
        onCategoryChange={setCategory}
        onPriorityChange={setPriority}
        onComplexityChange={setComplexity}
        onImpactChange={setImpact}
        showClassification={showClassification}
        onShowClassificationChange={setShowClassification}
        images={images}
        onImagesChange={setImages}
        requireReviewBeforeCoding={requireReviewBeforeCoding}
        onRequireReviewChange={setRequireReviewBeforeCoding}
        disabled={isSaving}
        error={error}
        onError={setError}
        idPrefix="edit"
      />
    </TaskModalLayout>
  );
}
