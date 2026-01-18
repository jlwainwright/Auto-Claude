import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription
} from './ui/dialog';
import { Button } from './ui/button';
import { Label } from './ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from './ui/select';
import {
  AVAILABLE_MODELS,
  AVAILABLE_ZAI_MODELS,
  AVAILABLE_PROVIDERS,
  THINKING_LEVELS,
  DEFAULT_FEATURE_MODELS
} from '../../shared/constants';
import type { InsightsModelConfig } from '../../shared/types';
import type { ModelType, ThinkingLevel } from '../../shared/types';
import type { FeatureProvider } from '../../shared/types';

interface CustomModelModalProps {
  currentConfig?: InsightsModelConfig;
  onSave: (config: InsightsModelConfig) => void;
  onClose: () => void;
  open?: boolean;
}

export function CustomModelModal({ currentConfig, onSave, onClose, open = true }: CustomModelModalProps) {
  const { t } = useTranslation('dialogs');
  const [provider, setProvider] = useState<FeatureProvider>(
    currentConfig?.provider || 'claude'
  );
  const [model, setModel] = useState<ModelType>(
    currentConfig?.model || 'sonnet'
  );
  const [thinkingLevel, setThinkingLevel] = useState<ThinkingLevel>(
    currentConfig?.thinkingLevel || 'medium'
  );

  // Helper function to extract model shorthand from full ID
  const getModelShorthand = (model: string): string => {
    // If model is a full Claude model ID, extract the shorthand
    if (model.startsWith('claude-')) {
      if (model.includes('opus')) return 'opus';
      if (model.includes('sonnet')) return 'sonnet';
      if (model.includes('haiku')) return 'haiku';
    }
    return model;
  };

  // Get available models based on selected provider
  const modelOptions = provider === 'zai' ? AVAILABLE_ZAI_MODELS : AVAILABLE_MODELS;

  // Auto-switch provider when model changes (user switches between GLM models)
  useEffect(() => {
    const normalizedModel = getModelShorthand(model);
    const isZaiModel = AVAILABLE_ZAI_MODELS.some((m) => m.value === normalizedModel);
    const isClaudeModel = AVAILABLE_MODELS.some((m) => m.value === normalizedModel);

    if (isZaiModel && provider !== 'zai') {
      setProvider('zai');
    } else if (isClaudeModel && provider !== 'claude') {
      setProvider('claude');
    }
  }, [model]);

  // Sync internal state when modal opens or config changes
  useEffect(() => {
    if (open) {
      const configProvider = currentConfig?.provider || 'claude';
      let configModel = getModelShorthand(currentConfig?.model || 'sonnet');

      // Check if provider and model are compatible
      const isZaiModel = AVAILABLE_ZAI_MODELS.some((m) => m.value === configModel);
      const isClaudeModel = AVAILABLE_MODELS.some((m) => m.value === configModel);

      // FIX: If there's a mismatch, auto-correct the model
      if (configProvider === 'zai' && !isZaiModel) {
        // Provider is Z.AI but model is not a GLM model - fix it
        configModel = AVAILABLE_ZAI_MODELS[0].value;
      } else if (configProvider === 'claude' && !isClaudeModel) {
        // Provider is Claude but model is not a Claude model - fix it
        configModel = AVAILABLE_MODELS[0].value;
      }

      // Determine provider based on model
      const newProvider = isZaiModel ? 'zai' : (isClaudeModel ? 'claude' : configProvider);

      // Update state
      if (newProvider !== provider) {
        setProvider(newProvider);
      }
      if (configModel !== model) {
        setModel(configModel);
      }
      setThinkingLevel(currentConfig?.thinkingLevel || 'medium');
    }
  }, [open, currentConfig]);

  const handleSave = () => {
    onSave({
      profileId: 'custom',
      provider,
      model,
      thinkingLevel
    });
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('customModel.title')}</DialogTitle>
          <DialogDescription>
            {t('customModel.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="provider-select">{t('customModel.provider')}</Label>
            <Select
              value={provider}
              onValueChange={(v) => {
                const newProvider = v as FeatureProvider;
                setProvider(newProvider);
                // Auto-switch model when provider changes
                const isZaiModel = AVAILABLE_ZAI_MODELS.some((m) => m.value === model);
                if (newProvider === 'zai' && !isZaiModel) {
                  setModel(AVAILABLE_ZAI_MODELS[0].value as ModelType);
                } else if (newProvider === 'claude' && isZaiModel) {
                  setModel(DEFAULT_FEATURE_MODELS.insights);
                }
              }}
            >
              <SelectTrigger id="provider-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AVAILABLE_PROVIDERS.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="model-select">{t('customModel.model')}</Label>
            <Select value={model} onValueChange={(v) => setModel(v as ModelType)}>
              <SelectTrigger id="model-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {modelOptions.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="thinking-select">{t('customModel.thinkingLevel')}</Label>
            <Select value={thinkingLevel} onValueChange={(v) => setThinkingLevel(v as ThinkingLevel)}>
              <SelectTrigger id="thinking-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {THINKING_LEVELS.map((level) => (
                  <SelectItem key={level.value} value={level.value}>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{level.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {level.description}
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t('customModel.cancel')}
          </Button>
          <Button onClick={handleSave}>
            {t('customModel.apply')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
