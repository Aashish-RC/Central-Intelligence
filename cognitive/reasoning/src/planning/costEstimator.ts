/**
 * Cost, Token, and Latency Estimator (Features 4.13, 4.14).
 */

import type { PlanStepInput, PlanStepPreview, PlanRiskLevel } from './models.js';

interface ModelPricing {
  promptPerMillion: number;
  completionPerMillion: number;
  baseLatencyMs: number;
}

const PRICING_REGISTRY: Record<string, ModelPricing> = {
  'claude-3-7-sonnet-20250219': { promptPerMillion: 3.0, completionPerMillion: 15.0, baseLatencyMs: 1200 },
  'claude-3-5-sonnet': { promptPerMillion: 3.0, completionPerMillion: 15.0, baseLatencyMs: 1000 },
  'claude-3-5-haiku': { promptPerMillion: 0.8, completionPerMillion: 4.0, baseLatencyMs: 400 },
  'gpt-4o': { promptPerMillion: 2.5, completionPerMillion: 10.0, baseLatencyMs: 900 },
  'gpt-4o-mini': { promptPerMillion: 0.15, completionPerMillion: 0.60, baseLatencyMs: 350 },
  'gemini-1.5-pro': { promptPerMillion: 3.5, completionPerMillion: 10.5, baseLatencyMs: 1100 },
  'gemini-1.5-flash': { promptPerMillion: 0.075, completionPerMillion: 0.30, baseLatencyMs: 300 },
};

const DEFAULT_PRICING: ModelPricing = { promptPerMillion: 1.5, completionPerMillion: 6.0, baseLatencyMs: 800 };

export class CostEstimator {
  /**
   * Estimates token consumption, financial cost, and execution duration for an individual plan step.
   */
  public estimateStep(step: PlanStepInput): PlanStepPreview {
    let estimatedPromptTokens = 0;
    let estimatedCompletionTokens = 0;
    let estimatedCostUsd = 0;
    let estimatedLatencyMs = 0;
    const riskReasons: string[] = [];
    let riskLevel: PlanRiskLevel = 'low';

    // 1. Calculate tokens based on prompt text and output expectations
    if (step.type === 'model_inference' || step.type === 'subagent_delegation') {
      const modelKey = (step.model || 'gpt-4o').toLowerCase();
      const pricing = this.resolvePricing(modelKey);

      // Estimate prompt tokens (~4 chars per token)
      const promptChars = (step.promptText || step.name || '').length;
      estimatedPromptTokens = Math.max(20, Math.ceil(promptChars / 4));

      // Estimate completion tokens
      switch (step.expectedOutputLength) {
        case 'short':
          estimatedCompletionTokens = 150;
          break;
        case 'long':
          estimatedCompletionTokens = 1500;
          break;
        case 'exhaustive':
          estimatedCompletionTokens = 3500;
          break;
        case 'medium':
        default:
          estimatedCompletionTokens = 500;
          break;
      }

      // Cost calculation
      const promptCost = (estimatedPromptTokens / 1_000_000) * pricing.promptPerMillion;
      const completionCost = (estimatedCompletionTokens / 1_000_000) * pricing.completionPerMillion;
      estimatedCostUsd = promptCost + completionCost;

      // Latency calculation
      estimatedLatencyMs = pricing.baseLatencyMs + Math.ceil(estimatedCompletionTokens * 1.5);
    } else if (step.type === 'tool_execution') {
      estimatedLatencyMs = 600;
      estimatedCostUsd = 0.002; // Baseline compute / API cost
      estimatedPromptTokens = 50;
      estimatedCompletionTokens = 100;
    } else if (step.type === 'human_checkpoint') {
      estimatedLatencyMs = 0;
      estimatedCostUsd = 0;
      estimatedPromptTokens = 0;
      estimatedCompletionTokens = 0;
    }

    // 2. Assess Risk Profile
    if (step.isDestructive) {
      riskLevel = 'critical';
      riskReasons.push('Step flagged as destructive modification (e.g. disk write, delete, database mutation)');
    } else if (step.toolName && /(delete|drop|terminate|kill|rmdir|unlink|transfer|grant|revoke)/i.test(step.toolName)) {
      riskLevel = 'high';
      riskReasons.push(`High risk tool action invoked: ${step.toolName}`);
    } else if (step.type === 'subagent_delegation') {
      riskLevel = 'medium';
      riskReasons.push('Autonomous sub-agent delegation expands execution surface');
    }

    if (estimatedCostUsd > 0.10) {
      if (riskLevel === 'low') riskLevel = 'medium';
      riskReasons.push(`High estimated step cost: $${estimatedCostUsd.toFixed(4)}`);
    }

    return {
      id: step.id,
      name: step.name,
      type: step.type,
      model: step.model,
      toolName: step.toolName,
      estimatedPromptTokens,
      estimatedCompletionTokens,
      estimatedCostUsd: Number(estimatedCostUsd.toFixed(5)),
      estimatedLatencyMs,
      riskLevel,
      riskReasons,
    };
  }

  private resolvePricing(modelName: string): ModelPricing {
    for (const [key, p] of Object.entries(PRICING_REGISTRY)) {
      if (modelName.includes(key) || key.includes(modelName)) {
        return p;
      }
    }
    return DEFAULT_PRICING;
  }
}
