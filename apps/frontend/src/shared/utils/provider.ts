/**
 * Provider utility functions
 *
 * Utilities for checking which AI provider a task uses.
 */

/**
 * Phase provider configuration type
 */
export interface PhaseProviderConfig {
  spec?: string;
  planning?: string;
  coding?: string;
  qa?: string;
}

function isClaudeModel(model?: string): boolean {
  if (!model) return false;
  const m = model.toLowerCase();
  return m === 'haiku' || m === 'sonnet' || m === 'opus' || m.startsWith('claude-');
}

function isGlmModel(model?: string): boolean {
  if (!model) return false;
  return model.toLowerCase().startsWith('glm-');
}

/**
 * Check if a task uses Claude provider (requires OAuth authentication).
 *
 * A task uses Claude if:
 * 1. It has phaseProviders and any phase uses "claude"
 * 2. It has a single provider field set to "claude"
 * 3. No provider is specified (defaults to Claude for backward compatibility)
 *
 * @param metadata - Task metadata or spec creation metadata
 * @returns true if the task uses Claude, false otherwise
 */
export function taskUsesClaude(metadata?: unknown): boolean {
  if (!metadata) {
    // No metadata = default to Claude (backward compatibility)
    return true;
  }

  // Check for phaseProviders (per-phase provider configuration)
  const phaseProviders = (metadata as any).phaseProviders as PhaseProviderConfig | undefined;
  if (phaseProviders) {
    // If any phase uses Claude, the task uses Claude
    const phases = ['spec', 'planning', 'coding', 'qa'] as const;
    for (const phase of phases) {
      const provider = phaseProviders[phase];
      if (provider === 'claude') {
        return true;
      }
      // If provider is explicitly set to non-Claude, continue checking other phases
      // Only return false if ALL phases are explicitly non-Claude
    }
    // If phaseProviders exists but no phase is Claude, check if any is explicitly non-Claude
    const hasNonClaudeProvider = phases.some(phase => {
      const provider = phaseProviders[phase];
      return provider && provider !== 'claude' && provider !== undefined;
    });
    if (hasNonClaudeProvider) {
      // At least one phase uses non-Claude, but we need to check if ANY phase uses Claude
      // If no phase uses Claude, return false
      const hasClaudeProvider = phases.some(phase => phaseProviders[phase] === 'claude');
      return hasClaudeProvider;
    }
  }

  // Check for single provider field (legacy or non-auto profile)
  const provider = (metadata as any).provider as string | undefined;
  if (provider) {
    return provider.toLowerCase() === 'claude';
  }

  // Infer provider from model selection when explicit provider is absent.
  // This keeps older metadata working while allowing glm-* profiles to run
  // without requiring Claude authentication.
  const phaseModels = (metadata as any).phaseModels as Record<string, string | undefined> | undefined;
  if (phaseModels) {
    const phases = ['spec', 'planning', 'coding', 'qa'] as const;
    const models = phases.map((p) => phaseModels[p]).filter(Boolean) as string[];

    if (models.some(isClaudeModel)) {
      return true;
    }

    // Only treat as non-Claude if we have an explicit GLM model for every phase.
    const hasAllPhases = phases.every((p) => !!phaseModels[p]);
    if (hasAllPhases && models.length > 0 && models.every(isGlmModel)) {
      return false;
    }
  }

  const model = (metadata as any).model as string | undefined;
  if (isClaudeModel(model)) {
    return true;
  }
  if (isGlmModel(model)) {
    return false;
  }

  // No provider specified = default to Claude (backward compatibility)
  return true;
}
