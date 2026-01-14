import { DEFAULT_PHASE_PROVIDERS } from '../constants/models';
import type { PhaseProviderConfig, ProviderId } from '../types/settings';
import type { TaskMetadata } from '../types/task';

export const getProviderForPhase = (
  phase: keyof PhaseProviderConfig,
  provider?: ProviderId,
  phaseProviders?: PhaseProviderConfig
): ProviderId => {
  if (phaseProviders) {
    const resolvedPhaseProviders = { ...DEFAULT_PHASE_PROVIDERS, ...phaseProviders };
    return resolvedPhaseProviders[phase] || provider || DEFAULT_PHASE_PROVIDERS[phase];
  }
  return provider || DEFAULT_PHASE_PROVIDERS[phase];
};

export const taskUsesClaude = (metadata?: TaskMetadata): boolean => {
  if (!metadata) return true;
  const provider = metadata.provider;
  const phaseProviders = metadata.phaseProviders;
  if (!provider && !phaseProviders) return true;
  if (provider === 'claude') return true;
  if (!phaseProviders) return false;
  const resolvedPhaseProviders = { ...DEFAULT_PHASE_PROVIDERS, ...phaseProviders };
  return Object.values(resolvedPhaseProviders).some((value) => value === 'claude');
};
