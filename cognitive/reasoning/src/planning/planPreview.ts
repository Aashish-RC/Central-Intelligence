/**
 * Plan Preview Generator (Features 4.13, 4.14).
 *
 * Pre-execution preview detailing costs, token budgets, execution latency,
 * and security risk gates before an agent plan runs.
 */

import { CostEstimator } from './costEstimator.js';
import type {
  PlanPreviewOptions,
  PlanPreviewSummary,
  PlanRiskLevel,
  PlanStepInput,
  PlanStepPreview,
} from './models.js';

export class PlanPreviewGenerator {
  private estimator: CostEstimator;
  private defaultBudgetThreshold: number;
  private autoApproveRisks: Set<PlanRiskLevel>;

  constructor(options?: PlanPreviewOptions) {
    this.estimator = new CostEstimator();
    this.defaultBudgetThreshold = options?.budgetThresholdUsd ?? 0.50;
    this.autoApproveRisks = new Set<PlanRiskLevel>(options?.autoApproveRiskLevels ?? ['low', 'medium']);
  }

  /**
   * Evaluates planned execution steps and produces a comprehensive preview summary.
   */
  public generatePreview(
    planId: string,
    steps: PlanStepInput[],
    options?: PlanPreviewOptions,
  ): PlanPreviewSummary {
    const budgetThreshold = options?.budgetThresholdUsd ?? this.defaultBudgetThreshold;
    const evaluatedSteps: PlanStepPreview[] = [];
    let totalTokens = 0;
    let totalCost = 0;
    let totalLatency = 0;

    const riskSeverityOrder: Record<PlanRiskLevel, number> = {
      low: 1,
      medium: 2,
      high: 3,
      critical: 4,
    };

    let maxSeverity = 1;
    let maxRisk: PlanRiskLevel = 'low';
    const approvalReasons: string[] = [];

    for (const step of steps) {
      const stepPreview = this.estimator.estimateStep(step);
      evaluatedSteps.push(stepPreview);

      totalTokens += stepPreview.estimatedPromptTokens + stepPreview.estimatedCompletionTokens;
      totalCost += stepPreview.estimatedCostUsd;
      totalLatency += stepPreview.estimatedLatencyMs;

      const severity = riskSeverityOrder[stepPreview.riskLevel];
      if (severity > maxSeverity) {
        maxSeverity = severity;
        maxRisk = stepPreview.riskLevel;
      }
    }

    // Determine if plan requires explicit human approval
    let requiresApproval = false;

    if (totalCost > budgetThreshold) {
      requiresApproval = true;
      approvalReasons.push(`Total estimated cost ($${totalCost.toFixed(4)}) exceeds budget limit ($${budgetThreshold.toFixed(2)})`);
    }

    if (!this.autoApproveRisks.has(maxRisk)) {
      requiresApproval = true;
      approvalReasons.push(`Plan risk level (${maxRisk.toUpperCase()}) exceeds auto-approval boundary`);
    }

    return {
      planId,
      totalSteps: steps.length,
      totalEstimatedTokens: totalTokens,
      totalEstimatedCostUsd: Number(totalCost.toFixed(4)),
      totalEstimatedLatencyMs: totalLatency,
      maxRiskLevel: maxRisk,
      requiresApproval,
      approvalReasons,
      steps: evaluatedSteps,
      createdAt: new Date().toISOString(),
    };
  }
}
