/**
 * Tests for Cognitive Routing Policy Engine (Features 8.09 - 8.15)
 */

import { test, describe } from 'node:test';
import assert from 'node:assert';
import {
  CognitiveRoutingPolicyEngine,
  MODEL_CATALOG,
  type ExecutionRequest,
  type PolicyRule,
} from '../engine/index.js';

describe('Cognitive Routing Policy Engine (Features 8.09 - 8.15)', () => {
  const engine = new CognitiveRoutingPolicyEngine();

  test('1. Simple greeting assessed as trivial/low complexity', () => {
    const req: ExecutionRequest = {
      messages: [{ role: 'user', content: 'Hello there!' }],
    };
    const assessment = engine.assessComplexity(req);
    assert.ok(assessment.complexity === 'trivial' || assessment.complexity === 'low');
    assert.ok(assessment.score < 0.2);

    const decision = engine.evaluateRouting(req, MODEL_CATALOG);
    assert.ok(decision.selectedModel.includes('llama') || decision.selectedModel.includes('mini'));
  });

  test('2. Complex multi-step coding task assessed as complex/expert', () => {
    const req: ExecutionRequest = {
      messages: [
        {
          role: 'user',
          content: `Please architect and implement step-by-step a distributed lock manager in TypeScript.
\`\`\`typescript
export interface LockLease { key: string; owner: string; }
\`\`\`
Prove the algorithm avoids deadlocks under race conditions.`,
        },
      ],
      tools: [{ name: 'write_file', description: 'Writes file' }],
    };
    const assessment = engine.assessComplexity(req);
    assert.ok(assessment.complexity === 'complex' || assessment.complexity === 'expert');
    assert.ok(assessment.score >= 0.6);
    assert.ok(assessment.factors.some((f) => f.includes('code') || f.includes('Tool')));

    const decision = engine.evaluateRouting(req, MODEL_CATALOG);
    assert.strictEqual(decision.selectedModel, 'anthropic/claude-3-7-sonnet-20250219');
  });

  test('3. Min-latency objective selects high-speed tier', () => {
    const req: ExecutionRequest = {
      messages: [
        {
          role: 'user',
          content: '```sql\nSELECT * FROM orders WHERE total > 100;\n```\nSynthesize the execution plan.',
        },
      ],
    };
    const decision = engine.evaluateRouting(req, MODEL_CATALOG, 'min_latency');
    assert.strictEqual(decision.selectedModel, 'anthropic/claude-3-5-haiku-20241022');
    assert.strictEqual(decision.objective, 'min_latency');
  });

  test('4. Declarative policy rule overrides dynamic routing', () => {
    const customEngine = new CognitiveRoutingPolicyEngine();
    const rule: PolicyRule = {
      id: 'compliance_audit_rule',
      name: 'Direct ISO Compliance Audits to GPT-4o',
      priority: 100,
      condition: (r) => r.messages.some((m) => m.content.includes('COMPLIANCE_AUDIT')),
      targetModel: 'openai/gpt-4o',
      reason: 'Strict compliance isolation policy',
    };
    customEngine.addPolicyRule(rule);

    const req: ExecutionRequest = {
      messages: [{ role: 'user', content: 'Run COMPLIANCE_AUDIT on Q3 financials' }],
    };
    const decision = customEngine.evaluateRouting(req, MODEL_CATALOG);
    assert.strictEqual(decision.selectedModel, 'openai/gpt-4o');
    assert.ok(decision.reasons.some((r) => r.includes('compliance_audit_rule') || r.includes('Direct ISO')));
  });
});
