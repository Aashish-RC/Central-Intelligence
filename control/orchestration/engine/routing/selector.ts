/**
 * Model Selector
 * Implements the 3 selection modes: dropdown, search-in-dropdown, and Auto mode
 * with priority allow-list, hard-deny exclusions, and configurable notification policies.
 * Inspired by OmniRoute (adaptiveRouting.ts) - MIT License
 */

import { MODEL_CATALOG, getModelById } from '../catalog.js';
import type {
  ModelDefinition,
  SelectionMode,
  FlagPreference,
  EngineMessage,
  ExecutionResponse,
} from '../types.js';
import { classifyTask } from './taskClassifier.js';

export interface SelectionResult {
  selectedModel: ModelDefinition;
  fallbackCandidates: ModelDefinition[];
  notifications: ExecutionResponse['notifications'];
  selectionReason: string;
}

export function searchModels(query: string, candidates = MODEL_CATALOG): ModelDefinition[] {
  const q = query.trim().toLowerCase();
  if (!q) return candidates;

  return candidates.filter(
    (m) =>
      m.id.toLowerCase().includes(q) ||
      m.name.toLowerCase().includes(q) ||
      m.provider.toLowerCase().includes(q) ||
      m.capabilities.some((c) => c.toLowerCase().includes(q))
  );
}

export function selectModel(options: {
  mode?: SelectionMode;
  explicitModel?: string;
  searchQuery?: string;
  messages: EngineMessage[];
  hasTools?: boolean;
  allowList?: string[];
  denyList?: string[];
  flagPreference?: FlagPreference;
}): SelectionResult {
  const mode = options.mode || 'dropdown';
  const allowList = options.allowList ? options.allowList.map((s) => s.toLowerCase()) : [];
  const denyList = options.denyList ? options.denyList.map((s) => s.toLowerCase()) : [];
  const flagPref: FlagPreference = options.flagPreference || 'cost-impacting';
  const notifications: ExecutionResponse['notifications'] = [];

  // Helper: check if model is strictly denied
  const isDenied = (m: ModelDefinition) =>
    denyList.includes(m.id.toLowerCase()) ||
    denyList.includes(m.name.toLowerCase()) ||
    denyList.includes(m.provider.toLowerCase());

  // Helper: check if model is allowed
  const isAllowed = (m: ModelDefinition) =>
    allowList.length === 0 ||
    allowList.includes(m.id.toLowerCase()) ||
    allowList.includes(m.name.toLowerCase()) ||
    allowList.includes(m.provider.toLowerCase());

  // Filter out any denied models right at the start - HARD EXCLUSION
  const nonDeniedCatalog = MODEL_CATALOG.filter((m) => !isDenied(m));

  if (nonDeniedCatalog.length === 0) {
    throw new Error('All models in catalog are excluded by the deny-list.');
  }

  // 1. Dropdown Selection Mode
  if (mode === 'dropdown' && options.explicitModel) {
    const requested = getModelById(options.explicitModel);
    if (!requested) {
      throw new Error(`Requested model "${options.explicitModel}" was not found in catalog.`);
    }
    if (isDenied(requested)) {
      throw new Error(
        `Requested model "${requested.name}" (${requested.id}) is forbidden by the deny-list.`
      );
    }
    return {
      selectedModel: requested,
      fallbackCandidates: nonDeniedCatalog.filter((m) => m.id !== requested.id),
      notifications: [],
      selectionReason: `Explicit dropdown selection: ${requested.name}`,
    };
  }

  // 2. Search-in-Dropdown Selection Mode
  if (mode === 'search') {
    const filtered = searchModels(options.searchQuery || '', nonDeniedCatalog);
    if (filtered.length === 0) {
      throw new Error(`No models matched search query "${options.searchQuery}".`);
    }
    const selected = options.explicitModel
      ? filtered.find((m) => m.id === options.explicitModel) || filtered[0]
      : filtered[0];

    return {
      selectedModel: selected,
      fallbackCandidates: filtered.filter((m) => m.id !== selected.id),
      notifications: [],
      selectionReason: `Search-in-dropdown query match for "${options.searchQuery}": ${selected.name}`,
    };
  }

  // 3. Auto Mode (Task-Aware Selection with Allow-List Priority & Hard-Deny)
  const classification = classifyTask(options.messages, options.hasTools);

  // Score each non-denied model
  const scored = nonDeniedCatalog.map((model) => {
    let score = model.benchmarkScore;

    // Multimodal requirement check
    if (classification.hasMultimodal) {
      if (!model.modalities.includes('image')) {
        score -= 60; // Severe penalty if cannot accept image inputs
      } else {
        score += 15;
      }
    }

    // Tools requirement check
    if (options.hasTools) {
      if (!model.capabilities.includes('tools')) {
        score -= 50;
      } else {
        score += 10;
      }
    }

    // Match primary task capability
    if (model.capabilities.includes(classification.primaryTask)) {
      score += 25;
    }

    // Complexity tier alignment
    if (classification.complexity === 'complex') {
      if (model.tier === 'flagship') score += 20;
      else if (model.tier === 'economy') score -= 20;
    } else if (classification.complexity === 'simple') {
      if (model.tier === 'economy' || model.tier === 'local') score += 20;
      else if (model.tier === 'flagship') score -= 15; // Don't overspend on simple prompts
    }

    // Priority signal: Allow-list provides a significant priority boost, but NOT a hard cap!
    const inAllowList = isAllowed(model);
    if (allowList.length > 0) {
      if (inAllowList) {
        score += 30; // Priority boost for models the user specified
      }
    }

    return {
      model,
      score,
      inAllowList,
    };
  });

  // Sort descending by score
  scored.sort((a, b) => b.score - a.score);

  const topChoice = scored[0];
  const selectedModel = topChoice.model;
  const fallbacks = scored.slice(1).map((s) => s.model);

  // Check if Auto selected outside user's allow-list
  if (allowList.length > 0 && !topChoice.inAllowList) {
    // Determine cost impact
    const allowedModels = MODEL_CATALOG.filter((m) => isAllowed(m) && !isDenied(m));
    const maxAllowedCost =
      allowedModels.length > 0
        ? Math.max(...allowedModels.map((m) => m.costPer1kOutputUSD))
        : 0;

    const isCostImpacting = selectedModel.costPer1kOutputUSD > maxAllowedCost;

    let shouldFlag = false;
    if (flagPref === 'always') {
      shouldFlag = true;
    } else if (flagPref === 'cost-impacting' && isCostImpacting) {
      shouldFlag = true;
    } else if (flagPref === 'never') {
      shouldFlag = false;
    }

    if (shouldFlag) {
      notifications.push({
        type: 'auto_selected_outside_allowlist',
        message: `Auto mode selected ${selectedModel.name} outside your allow-list because task requirements (${classification.primaryTask}) warranted superior capability.`,
        model: selectedModel.id,
        costImpactUSD: isCostImpacting
          ? selectedModel.costPer1kOutputUSD - maxAllowedCost
          : 0,
      });
    }
  }

  return {
    selectedModel,
    fallbackCandidates: fallbacks,
    notifications,
    selectionReason: `Auto mode task-aware selection for task "${classification.primaryTask}" (${classification.complexity}): ${selectedModel.name} (Score: ${topChoice.score.toFixed(1)})`,
  };
}
