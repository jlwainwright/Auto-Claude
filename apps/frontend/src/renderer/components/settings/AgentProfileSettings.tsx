import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Brain, Scale, Zap, Check, Sparkles, ChevronDown, ChevronUp, RotateCcw, Settings2, Plus, Pencil, Trash2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import {
  DEFAULT_AGENT_PROFILES,
  AVAILABLE_MODELS,
  THINKING_LEVELS,
  DEFAULT_PHASE_MODELS,
  DEFAULT_PHASE_THINKING
} from '../../../shared/constants';
import { useSettingsStore, saveSettings } from '../../stores/settings-store';
import { SettingsSection } from './SettingsSection';
import { Label } from '../ui/label';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '../ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '../ui/dialog';
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
import type { AgentProfile, PhaseModelConfig, PhaseThinkingConfig, ModelTypeShort, ThinkingLevel } from '../../../shared/types/settings';

/**
 * Icon mapping for agent profile icons
 */
const iconMap: Record<string, React.ElementType> = {
  Brain,
  Scale,
  Zap,
  Sparkles,
  Settings2
};

const PHASE_KEYS: Array<keyof PhaseModelConfig> = ['spec', 'planning', 'coding', 'qa'];

/**
 * Agent Profile Settings component
 * Displays preset agent profiles for quick model/thinking level configuration
 * All presets show phase configuration for full customization
 */
export function AgentProfileSettings() {
  const { t } = useTranslation('settings');
  const settings = useSettingsStore((state) => state.settings);
  const selectedProfileId = settings.selectedAgentProfile || 'auto';
  const [showPhaseConfig, setShowPhaseConfig] = useState(true);
  const [profileDialogOpen, setProfileDialogOpen] = useState(false);
  const [editingProfileId, setEditingProfileId] = useState<string | null>(null);
  const [profileDraftName, setProfileDraftName] = useState('');
  const [profileDraftDescription, setProfileDraftDescription] = useState('');
  const [profileDraftPhaseModels, setProfileDraftPhaseModels] = useState<PhaseModelConfig>(DEFAULT_PHASE_MODELS);
  const [profileDraftPhaseThinking, setProfileDraftPhaseThinking] = useState<PhaseThinkingConfig>(DEFAULT_PHASE_THINKING);
  const [profileDraftError, setProfileDraftError] = useState<string | null>(null);
  const [deleteConfirmProfileId, setDeleteConfirmProfileId] = useState<string | null>(null);

  const customProfiles = settings.customAgentProfiles ?? [];

  const allProfiles = useMemo(
    () => [...DEFAULT_AGENT_PROFILES, ...customProfiles],
    [customProfiles]
  );

  const isSelectedCustomProfile = useMemo(
    () => customProfiles.some((p) => p.id === selectedProfileId),
    [customProfiles, selectedProfileId]
  );

  // Find the selected profile (includes user-defined profiles)
  const selectedProfile = useMemo(
    () =>
      allProfiles.find((p) => p.id === selectedProfileId) ||
      allProfiles.find((p) => p.id === 'auto') ||
      allProfiles[0],
    [allProfiles, selectedProfileId]
  );

  // Get profile's default phase config
  const profilePhaseModels = selectedProfile.phaseModels || DEFAULT_PHASE_MODELS;
  const profilePhaseThinking = selectedProfile.phaseThinking || DEFAULT_PHASE_THINKING;

  const isAutoProfile = selectedProfileId === 'auto';
  const phaseEditingEnabled = isAutoProfile || isSelectedCustomProfile;

  // Get current phase config:
  // - Auto profile can be overridden via settings.customPhaseModels/customPhaseThinking
  // - Custom profiles are edited in-place (saved to settings.customAgentProfiles)
  // - Built-in non-auto profiles are read-only (create a custom profile to customize)
  const currentPhaseModels: PhaseModelConfig =
    (isAutoProfile ? settings.customPhaseModels : undefined) || profilePhaseModels;
  const currentPhaseThinking: PhaseThinkingConfig =
    (isAutoProfile ? settings.customPhaseThinking : undefined) || profilePhaseThinking;

  /**
   * Check if current config differs from the selected profile's defaults
   */
  const hasCustomConfig = useMemo((): boolean => {
    if (!isAutoProfile) {
      return false;
    }
    if (!settings.customPhaseModels && !settings.customPhaseThinking) {
      return false; // No custom settings, using profile defaults
    }
    return PHASE_KEYS.some(
      phase =>
        currentPhaseModels[phase] !== profilePhaseModels[phase] ||
        currentPhaseThinking[phase] !== profilePhaseThinking[phase]
    );
  }, [isAutoProfile, settings.customPhaseModels, settings.customPhaseThinking, currentPhaseModels, currentPhaseThinking, profilePhaseModels, profilePhaseThinking]);

  const handleSelectProfile = async (profileId: string) => {
    const profile = allProfiles.find(p => p.id === profileId);
    if (!profile) return;

    const success = await saveSettings({
      selectedAgentProfile: profileId
    });
    if (!success) {
      console.error('Failed to save agent profile selection');
      return;
    }
  };

  const handlePhaseModelChange = async (phase: keyof PhaseModelConfig, value: ModelTypeShort) => {
    if (!phaseEditingEnabled) return;

    const newPhaseModels = { ...currentPhaseModels, [phase]: value };

    if (isAutoProfile) {
      await saveSettings({ customPhaseModels: newPhaseModels });
      return;
    }

    if (isSelectedCustomProfile) {
      const updatedCustomProfiles = customProfiles.map((p) => {
        if (p.id !== selectedProfileId) return p;
        const nextPhaseModels = { ...(p.phaseModels || DEFAULT_PHASE_MODELS), ...newPhaseModels };
        return {
          ...p,
          phaseModels: nextPhaseModels,
          model: nextPhaseModels.coding
        };
      });
      await saveSettings({ customAgentProfiles: updatedCustomProfiles });
    }
  };

  const handlePhaseThinkingChange = async (phase: keyof PhaseThinkingConfig, value: ThinkingLevel) => {
    if (!phaseEditingEnabled) return;

    const newPhaseThinking = { ...currentPhaseThinking, [phase]: value };

    if (isAutoProfile) {
      await saveSettings({ customPhaseThinking: newPhaseThinking });
      return;
    }

    if (isSelectedCustomProfile) {
      const updatedCustomProfiles = customProfiles.map((p) => {
        if (p.id !== selectedProfileId) return p;
        const nextPhaseThinking = { ...(p.phaseThinking || DEFAULT_PHASE_THINKING), ...newPhaseThinking };
        return {
          ...p,
          phaseThinking: nextPhaseThinking,
          thinkingLevel: nextPhaseThinking.coding
        };
      });
      await saveSettings({ customAgentProfiles: updatedCustomProfiles });
    }
  };

  const handleResetToProfileDefaults = async () => {
    await saveSettings({
      customPhaseModels: undefined,
      customPhaseThinking: undefined
    });
  };

  const openCreateProfileDialog = () => {
    setEditingProfileId(null);
    setProfileDraftName('');
    setProfileDraftDescription('');
    setProfileDraftPhaseModels(currentPhaseModels);
    setProfileDraftPhaseThinking(currentPhaseThinking);
    setProfileDraftError(null);
    setProfileDialogOpen(true);
  };

  const openEditProfileDialog = (profileId: string) => {
    const profile = customProfiles.find((p) => p.id === profileId);
    if (!profile) return;

    setEditingProfileId(profileId);
    setProfileDraftName(profile.name);
    setProfileDraftDescription(profile.description);
    setProfileDraftPhaseModels(profile.phaseModels || DEFAULT_PHASE_MODELS);
    setProfileDraftPhaseThinking(profile.phaseThinking || DEFAULT_PHASE_THINKING);
    setProfileDraftError(null);
    setProfileDialogOpen(true);
  };

  const handleSaveProfile = async () => {
    const name = profileDraftName.trim();
    if (!name) {
      setProfileDraftError(t('agentProfile.customProfiles.validation.nameRequired'));
      return;
    }

    const description = profileDraftDescription.trim();
    const id = editingProfileId || `custom-${crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;

    const phaseModels = profileDraftPhaseModels;
    const phaseThinking = profileDraftPhaseThinking;

    const profile: AgentProfile = {
      id,
      name,
      description,
      icon: 'Settings2',
      phaseModels,
      phaseThinking,
      model: phaseModels.coding,
      thinkingLevel: phaseThinking.coding
    };

    const updatedCustomProfiles = editingProfileId
      ? customProfiles.map((p) => (p.id === id ? profile : p))
      : [...customProfiles, profile];

    const updates: Parameters<typeof saveSettings>[0] = {
      customAgentProfiles: updatedCustomProfiles
    };
    if (!editingProfileId) {
      updates.selectedAgentProfile = id;
    }

    const success = await saveSettings(updates);
    if (!success) {
      setProfileDraftError(t('agentProfile.customProfiles.validation.saveFailed'));
      return;
    }

    setProfileDialogOpen(false);
  };

  const handleDeleteProfile = async (profileId: string) => {
    const updatedCustomProfiles = customProfiles.filter((p) => p.id !== profileId);
    const updates: Parameters<typeof saveSettings>[0] = {
      customAgentProfiles: updatedCustomProfiles
    };

    if (selectedProfileId === profileId) {
      updates.selectedAgentProfile = 'auto';
    }

    await saveSettings(updates);
  };

  // Clear stale dialog state when closing
  useEffect(() => {
    if (!profileDialogOpen) {
      setEditingProfileId(null);
      setProfileDraftError(null);
    }
  }, [profileDialogOpen]);

  /**
   * Get human-readable model label
   */
  const getModelLabel = (modelValue: string): string => {
    const model = AVAILABLE_MODELS.find((m) => m.value === modelValue);
    return model?.label || modelValue;
  };

  /**
   * Get human-readable thinking level label
   */
  const getThinkingLabel = (thinkingValue: string): string => {
    const level = THINKING_LEVELS.find((l) => l.value === thinkingValue);
    return level?.label || thinkingValue;
  };

  /**
   * Render a single profile card
   */
  const renderProfileCard = (profile: AgentProfile, options?: { isCustom?: boolean }) => {
    const isSelected = selectedProfileId === profile.id;
    const isCustomized = isSelected && hasCustomConfig;
    const isCustom = options?.isCustom === true;
    const Icon = iconMap[profile.icon || 'Brain'] || Brain;

    return (
      <div key={profile.id} className="relative w-full">
        <button
          type="button"
          onClick={() => handleSelectProfile(profile.id)}
          className={cn(
            'relative w-full rounded-lg border p-4 text-left transition-all duration-200',
            'hover:border-primary/50 hover:shadow-sm',
            isSelected
              ? 'border-primary bg-primary/5'
              : 'border-border bg-card'
          )}
        >
          {/* Selected indicator */}
          {isSelected && (
            <div className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-primary">
              <Check className="h-3 w-3 text-primary-foreground" />
            </div>
          )}

          {/* Profile content */}
          <div className="flex items-start gap-3">
            <div
              className={cn(
                'flex h-10 w-10 items-center justify-center rounded-lg shrink-0',
                isSelected ? 'bg-primary/10' : 'bg-muted'
              )}
            >
              <Icon
                className={cn(
                  'h-5 w-5',
                  isSelected ? 'text-primary' : 'text-muted-foreground'
                )}
              />
            </div>

            <div className="flex-1 min-w-0 pr-6">
              <div className="flex items-center gap-2">
                <h3 className="font-medium text-sm text-foreground">{profile.name}</h3>
                {isCustom && (
                  <span className="inline-flex items-center rounded bg-muted px-1.5 py-0.5 text-[9px] font-medium text-muted-foreground">
                    {t('agentProfile.customProfiles.badge')}
                  </span>
                )}
                {isCustomized && (
                  <span className="inline-flex items-center rounded bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-medium text-amber-600 dark:text-amber-400">
                    {t('agentProfile.customized')}
                  </span>
                )}
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                {profile.description}
              </p>

              {/* Model and thinking level badges */}
              <div className="mt-2 flex flex-wrap gap-1.5">
                <span className="inline-flex items-center rounded bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                  {getModelLabel(profile.model)}
                </span>
                <span className="inline-flex items-center rounded bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                  {getThinkingLabel(profile.thinkingLevel)} {t('agentProfile.thinking')}
                </span>
              </div>
            </div>
          </div>
        </button>

        {/* Custom profile actions */}
        {isCustom && (
          <div className="absolute bottom-3 right-3 flex items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => openEditProfileDialog(profile.id)}
              title={t('agentProfile.customProfiles.edit')}
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>

            <AlertDialog
              open={deleteConfirmProfileId === profile.id}
              onOpenChange={(open) => setDeleteConfirmProfileId(open ? profile.id : null)}
            >
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-destructive hover:text-destructive"
                onClick={() => setDeleteConfirmProfileId(profile.id)}
                title={t('agentProfile.customProfiles.delete')}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t('agentProfile.customProfiles.deleteTitle')}</AlertDialogTitle>
                  <AlertDialogDescription>
                    {t('agentProfile.customProfiles.deleteDescription', { name: profile.name })}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{t('common:buttons.cancel')}</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={async () => {
                      await handleDeleteProfile(profile.id);
                      setDeleteConfirmProfileId(null);
                    }}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    {t('common:buttons.delete')}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        )}
      </div>
    );
  };

  return (
    <SettingsSection
      title={t('agentProfile.title')}
      description={t('agentProfile.sectionDescription')}
    >
      <div className="space-y-4">
        {/* Description */}
        <div className="rounded-lg bg-muted/50 p-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <p className="text-xs text-muted-foreground">
              {t('agentProfile.profilesInfo')}
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 text-xs"
              onClick={openCreateProfileDialog}
            >
              <Plus className="h-3.5 w-3.5 mr-1.5" />
              {t('agentProfile.customProfiles.add')}
            </Button>
          </div>
        </div>

        {/* Profile cards - 2 column grid on larger screens */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {DEFAULT_AGENT_PROFILES.map((p) => renderProfileCard(p))}
          {customProfiles.map((p) => renderProfileCard(p, { isCustom: true }))}
        </div>

        {/* Phase Configuration - shown for all profiles */}
        <div className="mt-6 rounded-lg border border-border bg-card">
          {/* Header - Collapsible */}
          <button
            type="button"
            onClick={() => setShowPhaseConfig(!showPhaseConfig)}
            className="flex w-full items-center justify-between p-4 text-left hover:bg-muted/50 transition-colors rounded-t-lg"
          >
            <div>
              <h4 className="font-medium text-sm text-foreground">{t('agentProfile.phaseConfiguration')}</h4>
              <p className="text-xs text-muted-foreground mt-0.5">
                {t('agentProfile.phaseConfigurationDescription')}
              </p>
            </div>
            {showPhaseConfig ? (
              <ChevronUp className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </button>

          {/* Phase Configuration Content */}
          {showPhaseConfig && (
            <div className="border-t border-border p-4 space-y-4">
              {/* Reset button - shown when customized */}
              {isAutoProfile && hasCustomConfig && (
                <div className="flex justify-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleResetToProfileDefaults}
                    className="text-xs h-7"
                  >
                    <RotateCcw className="h-3 w-3 mr-1.5" />
                    {t('agentProfile.resetToProfileDefaults', { profile: selectedProfile.name })}
                  </Button>
                </div>
              )}

              {/* Phase Configuration Grid */}
              <div className="space-y-4">
                {PHASE_KEYS.map((phase) => (
                  <div key={phase} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label className="text-sm font-medium text-foreground">
                        {t(`agentProfile.phases.${phase}.label`)}
                      </Label>
                      <span className="text-xs text-muted-foreground">
                        {t(`agentProfile.phases.${phase}.description`)}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      {/* Model Select */}
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">{t('agentProfile.model')}</Label>
                        <Select
                          value={currentPhaseModels[phase]}
                          onValueChange={(value) => handlePhaseModelChange(phase, value as ModelTypeShort)}
                          disabled={!phaseEditingEnabled}
                        >
                          <SelectTrigger className="h-9">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {AVAILABLE_MODELS.map((m) => (
                              <SelectItem key={m.value} value={m.value}>
                                {m.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      {/* Thinking Level Select */}
                      <div className="space-y-1">
                        <Label className="text-xs text-muted-foreground">{t('agentProfile.thinkingLevel')}</Label>
                        <Select
                          value={currentPhaseThinking[phase]}
                          onValueChange={(value) => handlePhaseThinkingChange(phase, value as ThinkingLevel)}
                          disabled={!phaseEditingEnabled}
                        >
                          <SelectTrigger className="h-9">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {THINKING_LEVELS.map((level) => (
                              <SelectItem key={level.value} value={level.value}>
                                {level.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {!phaseEditingEnabled && (
                <p className="text-[10px] text-muted-foreground">
                  {t('agentProfile.customProfiles.readOnlyHint')}
                </p>
              )}

              {/* Info note */}
              <p className="text-[10px] text-muted-foreground mt-4 pt-3 border-t border-border">
                {t('agentProfile.phaseConfigNote')}
              </p>
            </div>
          )}
        </div>

        {/* Add/Edit Custom Profile Dialog */}
        <Dialog open={profileDialogOpen} onOpenChange={setProfileDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {editingProfileId ? t('agentProfile.customProfiles.editTitle') : t('agentProfile.customProfiles.addTitle')}
              </DialogTitle>
              <DialogDescription>
                {t('agentProfile.customProfiles.dialogDescription')}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 overflow-y-auto pr-1">
              <div className="space-y-2">
                <Label htmlFor="custom-profile-name">{t('agentProfile.customProfiles.fields.name')}</Label>
                <Input
                  id="custom-profile-name"
                  value={profileDraftName}
                  onChange={(e) => setProfileDraftName(e.target.value)}
                  placeholder={t('agentProfile.customProfiles.fields.namePlaceholder')}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="custom-profile-description">{t('agentProfile.customProfiles.fields.description')}</Label>
                <Textarea
                  id="custom-profile-description"
                  value={profileDraftDescription}
                  onChange={(e) => setProfileDraftDescription(e.target.value)}
                  placeholder={t('agentProfile.customProfiles.fields.descriptionPlaceholder')}
                />
              </div>

              <div className="rounded-lg border border-border bg-muted/30 p-3 space-y-4">
                <div>
                  <h4 className="font-medium text-sm text-foreground">{t('agentProfile.phaseConfiguration')}</h4>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {t('agentProfile.phaseConfigurationDescription')}
                  </p>
                </div>

                <div className="space-y-4">
                  {PHASE_KEYS.map((phase) => (
                    <div key={`custom-${phase}`} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label className="text-sm font-medium text-foreground">
                          {t(`agentProfile.phases.${phase}.label`)}
                        </Label>
                        <span className="text-xs text-muted-foreground">
                          {t(`agentProfile.phases.${phase}.description`)}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs text-muted-foreground">{t('agentProfile.model')}</Label>
                          <Select
                            value={profileDraftPhaseModels[phase]}
                            onValueChange={(value) => {
                              setProfileDraftPhaseModels((prev) => ({ ...prev, [phase]: value as ModelTypeShort }));
                            }}
                          >
                            <SelectTrigger className="h-9">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {AVAILABLE_MODELS.map((m) => (
                                <SelectItem key={`custom-${phase}-${m.value}`} value={m.value}>
                                  {m.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="space-y-1">
                          <Label className="text-xs text-muted-foreground">{t('agentProfile.thinkingLevel')}</Label>
                          <Select
                            value={profileDraftPhaseThinking[phase]}
                            onValueChange={(value) => {
                              setProfileDraftPhaseThinking((prev) => ({ ...prev, [phase]: value as ThinkingLevel }));
                            }}
                          >
                            <SelectTrigger className="h-9">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {THINKING_LEVELS.map((level) => (
                                <SelectItem key={`custom-${phase}-${level.value}`} value={level.value}>
                                  {level.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {profileDraftError && (
                <p className="text-xs text-destructive">{profileDraftError}</p>
              )}
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setProfileDialogOpen(false)}>
                {t('common:buttons.cancel')}
              </Button>
              <Button type="button" onClick={handleSaveProfile}>
                {t('common:buttons.save')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

      </div>
    </SettingsSection>
  );
}
