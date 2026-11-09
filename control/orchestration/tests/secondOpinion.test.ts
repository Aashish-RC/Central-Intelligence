/**
 * Tests for Second-Opinion Trigger on Accuracy Score (Task 12.14, Feature 8.15 — DEF-03 UNBLOCKED)
 */

import { test, describe } from 'node:test';
import assert from 'node:assert';
import {
  maybeTriggerSecondOpinion,
  CognitiveRoutingPolicyEngine,
  type TaskExecutionContext,
} from '../engine/index.js';

describe('Second-Opinion Trigger on Accuracy Score (Feature 8.15 / DEF-03)', () => {
  const engine = new CognitiveRoutingPolicyEngine();

  test('1. Score < 0.50 triggers rerun on frontier model', () => {
    const task: TaskExecutionContext = {
      taskId: 'task_001',
      currentModel: 'openai/gpt-4o-mini',
      userPreferences: {
        enableSecondOpinions: true,
      },
    };

    const lowScore = { composite: 0.38, confidence: 0.9 };
    const result = maybeTriggerSecondOpinion(lowScore, task);

    assert.strictEqual(result.triggered, true);
    assert.strictEqual(result.recommendedModel, 'anthropic/claude-3-7-sonnet-20250219');
    assert.ok(result.reason.includes('fell below 0.50 threshold'));
  });

  test('2. Score >= 0.50 does not trigger rerun', () => {
    const task: TaskExecutionContext = {
      taskId: 'task_002',
      currentModel: 'openai/gpt-4o-mini',
      userPreferences: {
        enableSecondOpinions: true,
      },
    };

    const goodScore = { composite: 0.75, confidence: 0.95 };
    const result = maybeTriggerSecondOpinion(goodScore, task);

    assert.strictEqual(result.triggered, false);
    assert.ok(result.reason.includes('satisfies quality threshold'));
    assert.strictEqual(result.recommendedModel, undefined);
  });

  test('3. User disabled setting suppresses rerun even when score < 0.50', () => {
    const task: TaskExecutionContext = {
      taskId: 'task_003',
      currentModel: 'ollama/llama3.2',
      userPreferences: {
        enableSecondOpinions: false,
      },
    };

    const veryLowScore = { composite: 0.15 };
    const result = maybeTriggerSecondOpinion(veryLowScore, task);

    assert.strictEqual(result.triggered, false);
    assert.ok(result.reason.includes('disabled by user preferences'));
  });

  test('4. Model escalation upgrades frontier model to reasoning tier (o3-mini)', () => {
    const task: TaskExecutionContext = {
      taskId: 'task_004',
      currentModel: 'anthropic/claude-3-7-sonnet-20250219',
      userPreferences: {
        enableSecondOpinions: true,
      },
    };

    const lowScore = { composite: 0.45 };
    const result = engine.maybeTriggerSecondOpinion(lowScore, task);

    assert.strictEqual(result.triggered, true);
    assert.strictEqual(result.recommendedModel, 'openai/o3-mini');
  });
});

