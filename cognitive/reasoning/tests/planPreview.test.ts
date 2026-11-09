import { describe, expect, it } from 'vitest';
import { PlanPreviewGenerator } from '../src/planning/planPreview.js';
import type { PlanStepInput } from '../src/planning/models.js';

describe('Plan Preview & Cost Estimator (Features 4.13, 4.14)', () => {
  const generator = new PlanPreviewGenerator({
    budgetThresholdUsd: 0.10,
    autoApproveRiskLevels: ['low', 'medium'],
  });

  it('computes pre-execution token, cost, and latency estimates for multi-step plan', () => {
    const steps: PlanStepInput[] = [
      {
        id: 's1',
        name: 'Analyze user requirements',
        type: 'model_inference',
        model: 'gpt-4o',
        promptText: 'Analyze requirements for multi-region authentication failover.',
        expectedOutputLength: 'medium',
      },
      {
        id: 's2',
        name: 'Query database schema',
        type: 'tool_execution',
        toolName: 'read_db_schema',
      },
    ];

    const preview = generator.generatePreview('plan-001', steps);

    expect(preview.totalSteps).toBe(2);
    expect(preview.totalEstimatedTokens).toBeGreaterThan(500);
    expect(preview.totalEstimatedCostUsd).toBeGreaterThan(0.001);
    expect(preview.totalEstimatedLatencyMs).toBeGreaterThan(500);
    expect(preview.maxRiskLevel).toBe('low');
    expect(preview.requiresApproval).toBe(false);
  });

  it('triggers approval requirement when estimated cost exceeds budget limit', () => {
    const expensiveSteps: PlanStepInput[] = [
      {
        id: 'step-heavy-1',
        name: 'Run exhaustive system synthesis',
        type: 'model_inference',
        model: 'claude-3-7-sonnet-20250219',
        promptText: 'A'.repeat(8000), // ~2000 prompt tokens
        expectedOutputLength: 'exhaustive', // ~3500 completion tokens
      },
      {
        id: 'step-heavy-2',
        name: 'Run second exhaustive pass',
        type: 'model_inference',
        model: 'claude-3-7-sonnet-20250219',
        promptText: 'B'.repeat(8000),
        expectedOutputLength: 'exhaustive',
      },
    ];

    // High threshold: $0.05
    const preview = generator.generatePreview('plan-expensive', expensiveSteps, {
      budgetThresholdUsd: 0.05,
    });

    expect(preview.totalEstimatedCostUsd).toBeGreaterThan(0.05);
    expect(preview.requiresApproval).toBe(true);
    expect(preview.approvalReasons.some((r) => r.includes('exceeds budget limit'))).toBe(true);
  });

  it('triggers approval requirement when a step is destructive or high risk', () => {
    const riskySteps: PlanStepInput[] = [
      {
        id: 'step-read',
        name: 'Inspect logs',
        type: 'tool_execution',
        toolName: 'read_logs',
      },
      {
        id: 'step-destruct',
        name: 'Purge old records',
        type: 'tool_execution',
        toolName: 'delete_database_partition',
        isDestructive: true,
      },
    ];

    const preview = generator.generatePreview('plan-risky', riskySteps);

    expect(preview.maxRiskLevel).toBe('critical');
    expect(preview.requiresApproval).toBe(true);
    expect(preview.approvalReasons.some((r) => r.includes('CRITICAL'))).toBe(true);
    expect(preview.steps[1].riskReasons.length).toBeGreaterThan(0);
  });
});
