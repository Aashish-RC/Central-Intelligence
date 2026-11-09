import { test } from 'node:test';
import assert from 'node:assert';
import {
  CollaborationBridge,
  DelegationDepthExceededError,
  DelegationCycleError,
} from '../engine/index.js';

test('Feature 8.50: Cross-Layer Multi-Agent Collaboration Governance', async (t) => {
  await t.test('issues and verifies a valid multi-agent delegation grant', () => {
    const bridge = new CollaborationBridge();
    const grant = bridge.issueDelegation({
      delegatorId: 'coordinator_agent',
      delegateeId: 'worker_agent_01',
      taskName: 'Generate Database Report',
      allowedTools: ['mcp:sql:query', 'mcp:fs:write'],
      budgetUSD: 0.50,
    });

    assert.ok(grant.id.startsWith('dlg_'));
    assert.strictEqual(grant.depth, 1);
    assert.strictEqual(grant.delegatorId, 'coordinator_agent');
    assert.strictEqual(grant.delegateeId, 'worker_agent_01');

    const check = bridge.verifyDelegation(grant.id, 'worker_agent_01');
    assert.strictEqual(check.valid, true);
  });

  await t.test('blocks delegation when max recursion depth is exceeded', () => {
    const bridge = new CollaborationBridge({ defaultMaxDepth: 2 });

    const grant1 = bridge.issueDelegation({
      delegatorId: 'agent_root',
      delegateeId: 'agent_lvl1',
      taskName: 'Root task',
    });
    assert.strictEqual(grant1.depth, 1);

    const grant2 = bridge.issueDelegation({
      delegatorId: 'agent_lvl1',
      delegateeId: 'agent_lvl2',
      taskName: 'Subtask 1',
      parentDelegationId: grant1.id,
    });
    assert.strictEqual(grant2.depth, 2);

    // Depth 3 should fail
    assert.throws(
      () =>
        bridge.issueDelegation({
          delegatorId: 'agent_lvl2',
          delegateeId: 'agent_lvl3',
          taskName: 'Subtask 2',
          parentDelegationId: grant2.id,
        }),
      DelegationDepthExceededError
    );
  });

  await t.test('detects and blocks cyclic delegation loops', () => {
    const bridge = new CollaborationBridge({ defaultMaxDepth: 5 });

    const g1 = bridge.issueDelegation({
      delegatorId: 'agent_A',
      delegateeId: 'agent_B',
      taskName: 'Task A->B',
    });

    const g2 = bridge.issueDelegation({
      delegatorId: 'agent_B',
      delegateeId: 'agent_C',
      taskName: 'Task B->C',
      parentDelegationId: g1.id,
    });

    // Agent C attempts to delegate back to Agent A (cycle!)
    assert.throws(
      () =>
        bridge.issueDelegation({
          delegatorId: 'agent_C',
          delegateeId: 'agent_A',
          taskName: 'Task C->A (Cycle)',
          parentDelegationId: g2.id,
        }),
      DelegationCycleError
    );
  });

  await t.test('handles token revocation and ping-pong loop detection', () => {
    const bridge = new CollaborationBridge();
    const grant = bridge.issueDelegation({
      delegatorId: 'supervisor',
      delegateeId: 'sub_agent',
      taskName: 'Scratchpad Write',
    });

    bridge.revokeDelegation(grant.id, 'Unauthorized file access pattern observed');
    const check = bridge.verifyDelegation(grant.id, 'sub_agent');
    assert.strictEqual(check.valid, false);
    assert.ok(check.error?.includes('revoked'));

    // Ping-pong loop
    const history = [
      { sender: 'agent_A', recipient: 'agent_B', action: 'query' },
      { sender: 'agent_B', recipient: 'agent_A', action: 'reply' },
      { sender: 'agent_A', recipient: 'agent_B', action: 'query' },
      { sender: 'agent_B', recipient: 'agent_A', action: 'reply' },
    ];
    assert.strictEqual(bridge.detectPingPongLoop(history), true);
  });
});
