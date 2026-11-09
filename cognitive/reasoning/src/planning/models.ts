/**
 * Data contracts for Plan Preview & Cost Estimator (Features 4.13, 4.14).
 */

export type PlanStepType = 'model_inference' | 'tool_execution' | 'subagent_delegation' | 'human_checkpoint';
export type PlanRiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface PlanStepInput {
  id: string;
  name: string;
  type: PlanStepType;
  model?: string;
  toolName?: string;
  promptText?: string;
  expectedOutputLength?: 'short' | 'medium' | 'long' | 'exhaustive';
  isDestructive?: boolean;
  metadata?: Record<string, any>;
}

export interface PlanStepPreview {
  id: string;
  name: string;
  type: PlanStepType;
  model?: string;
  toolName?: string;
  estimatedPromptTokens: number;
  estimatedCompletionTokens: number;
  estimatedCostUsd: number;
  estimatedLatencyMs: number;
  riskLevel: PlanRiskLevel;
  riskReasons: string[];
}

export interface PlanPreviewSummary {
  planId: string;
  totalSteps: number;
  totalEstimatedTokens: number;
  totalEstimatedCostUsd: number;
  totalEstimatedLatencyMs: number;
  maxRiskLevel: PlanRiskLevel;
  requiresApproval: boolean;
  approvalReasons: string[];
  steps: PlanStepPreview[];
  createdAt: string;
}

export interface PlanPreviewOptions {
  budgetThresholdUsd?: number;       // default $0.50
  autoApproveRiskLevels?: PlanRiskLevel[]; // default ['low', 'medium']
}
