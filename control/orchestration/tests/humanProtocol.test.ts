/**
 * Tests for Human Escalation Protocol & Intervention Control Plane (Features 8.30, 8.50)
 */

import { test, describe } from 'node:test';
import assert from 'node:assert';
import { HumanEscalationProtocol } from '../engine/index.js';

describe('Human Escalation Protocol (Features 8.30, 8.50)', () => {
  test('1. Trigger escalation creates pending escalation record with snapshot', () => {
    const protocol = new HumanEscalationProtocol();
    const trigger = protocol.triggerEscalation({
      workflowId: 'wf_prod_99',
      agentId: 'agent_migrator',
      title: 'Database Schema Migration Stalled',
      reason: 'Foreign key constraint violated on table users_v2',
      urgency: 'high',
      stateSnapshot: { currentStep: 4, table: 'users_v2', rowsMigrated: 14500 },
      suggestedActions: ['skip_table', 'retry_with_cascade', 'abort'],
    });

    assert.ok(trigger.id.startsWith('esc_'));
    assert.strictEqual(trigger.status, 'pending');
    assert.strictEqual(trigger.urgency, 'high');
    assert.strictEqual(trigger.stateSnapshot.rowsMigrated, 14500);
    assert.strictEqual(protocol.getActiveEscalations().length, 1);
  });

  test('2. Operator acknowledges and resolves with steering input', () => {
    const protocol = new HumanEscalationProtocol();
    const trigger = protocol.triggerEscalation({
      workflowId: 'wf_chat_1',
      agentId: 'agent_summarizer',
      title: 'Ambiguous User Intent',
      reason: 'User prompt contains conflicting requirements',
    });

    // Acknowledge
    const acked = protocol.acknowledgeEscalation(trigger.id, 'operator_sarah');
    assert.strictEqual(acked.status, 'acknowledged');
    assert.strictEqual(acked.operatorId, 'operator_sarah');

    // Resolve with steering input
    const resolved = protocol.resolveEscalation({
      triggerId: trigger.id,
      operatorId: 'operator_sarah',
      action: 'resume',
      steeringInput: 'Prioritize security compliance over response latency',
    });

    assert.strictEqual(resolved.status, 'resolved');
    assert.strictEqual(resolved.steeringInput, 'Prioritize security compliance over response latency');
    assert.strictEqual(protocol.getActiveEscalations().length, 0);
    assert.strictEqual(protocol.getEscalationHistory().length, 1);
  });

  test('3. Operator intervention overrides workflow state', () => {
    const protocol = new HumanEscalationProtocol();
    const trigger = protocol.triggerEscalation({
      workflowId: 'wf_build_22',
      agentId: 'agent_builder',
      title: 'Exceeded Max Retries',
      reason: 'Docker pull failure on base image',
    });

    const overridden = protocol.resolveEscalation({
      triggerId: trigger.id,
      operatorId: 'admin_dave',
      action: 'override',
      overrideState: { baseImage: 'node:20-alpine', retryCounter: 0 },
    });

    assert.strictEqual(overridden.status, 'overridden');
    assert.strictEqual(overridden.overrideState?.baseImage, 'node:20-alpine');
    assert.strictEqual(overridden.operatorId, 'admin_dave');
  });

  test('4. Timeout check auto-expires unhandled escalations', async () => {
    const protocol = new HumanEscalationProtocol();
    const trigger = protocol.triggerEscalation({
      workflowId: 'wf_quick_timeout',
      agentId: 'agent_fast',
      title: 'Quick Timeout Test',
      reason: 'Testing auto-timeout behavior',
      timeoutSeconds: 0.05,
    });

    await new Promise((r) => setTimeout(r, 80));

    const timedOut = protocol.checkTimeouts();
    assert.strictEqual(timedOut.length, 1);
    assert.strictEqual(timedOut[0].id, trigger.id);
    assert.strictEqual(timedOut[0].status, 'timed_out');
    assert.strictEqual(protocol.getActiveEscalations().length, 0);
  });
});
