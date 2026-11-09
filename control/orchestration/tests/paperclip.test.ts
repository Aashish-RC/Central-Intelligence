/**
 * Tests for Paperclip Adapter: Agent Fleet Governance Engine (Features 8.18, 8.48)
 */

import { test, describe } from 'node:test';
import assert from 'node:assert';
import {
  PaperclipGovernanceAdapter,
  BudgetExceededError,
  type AgentNode,
} from '../engine/index.js';

describe('Paperclip Adapter: Agent Fleet Governance (Layer 8)', () => {
  const setupOrg = () => {
    const adapter = new PaperclipGovernanceAdapter({
      orgId: 'aevum-org-1',
      name: 'Aevum Autonomous Systems',
      totalBudgetUSD: 100.0,
    });

    const ceo: AgentNode = {
      id: 'agent_ceo',
      name: 'Executive Strategist',
      role: 'CEO',
      budgetUSD: 50.0,
      currentSpendUSD: 0,
      approvalThresholdUSD: 20.0,
      status: 'idle',
      allowedCapabilities: ['strategic_planning', 'governance_override'],
    };

    const techLead: AgentNode = {
      id: 'agent_lead',
      name: 'System Architect',
      role: 'Tech Lead',
      reportsTo: 'agent_ceo',
      budgetUSD: 30.0,
      currentSpendUSD: 0,
      approvalThresholdUSD: 5.0,
      status: 'idle',
      allowedCapabilities: ['architecture_design', 'code_review'],
    };

    const juniorCoder: AgentNode = {
      id: 'agent_coder',
      name: 'Implementation Bot',
      role: 'Junior Engineer',
      reportsTo: 'agent_lead',
      budgetUSD: 10.0,
      currentSpendUSD: 0,
      approvalThresholdUSD: 0.5,
      status: 'idle',
      allowedCapabilities: ['code_generation', 'unit_testing'],
    };

    adapter.registerAgent(ceo);
    adapter.registerAgent(techLead);
    adapter.registerAgent(juniorCoder);

    return { adapter, ceo, techLead, juniorCoder };
  };

  test('1. Org chart hierarchy and reporting chains resolve correctly', () => {
    const { adapter, ceo, techLead, juniorCoder } = setupOrg();

    const chain = adapter.getReportingChain(juniorCoder.id);
    assert.strictEqual(chain.length, 2);
    assert.strictEqual(chain[0].id, techLead.id);
    assert.strictEqual(chain[1].id, ceo.id);

    const subordinates = adapter.getSubordinates(techLead.id);
    assert.strictEqual(subordinates.length, 1);
    assert.strictEqual(subordinates[0].id, juniorCoder.id);
  });

  test('2. Budget cap enforces spend limits and throws BudgetExceededError', () => {
    const { adapter, juniorCoder } = setupOrg();

    // Spend under budget succeeds
    adapter.recordSpend(juniorCoder.id, 6.0);
    const agent = adapter.getAgent(juniorCoder.id);
    assert.strictEqual(agent?.currentSpendUSD, 6.0);

    // Exceeding agent budget cap throws BudgetExceededError
    assert.throws(
      () => {
        adapter.recordSpend(juniorCoder.id, 5.0);
      },
      (err: any) => err instanceof BudgetExceededError && err.entityId === juniorCoder.id
    );
  });

  test('3. Autonomous execution completes when cost is within approval threshold', async () => {
    const { adapter, juniorCoder } = setupOrg();

    const result = await adapter.dispatchTask(juniorCoder.id, 'Run lint checks', 0.25);
    assert.strictEqual(result.status, 'completed');
    assert.ok(result.output?.includes('Lint checks') || result.output?.includes('autonomous'));
    assert.strictEqual(adapter.getPendingApprovals().length, 0);
  });

  test('4. Approval threshold pauses execution until supervisor signs off', async () => {
    const { adapter, juniorCoder, techLead } = setupOrg();

    // Junior engineer requests action with cost $2.00 (threshold is $0.50)
    const result = await adapter.dispatchTask(juniorCoder.id, 'Deploy neural checkpoint', 2.0);
    assert.strictEqual(result.status, 'paused_for_approval');
    assert.ok(result.requestId);

    const pending = adapter.getPendingApprovals();
    assert.strictEqual(pending.length, 1);
    assert.strictEqual(pending[0].id, result.requestId);
    assert.strictEqual(pending[0].requiredApproverId, techLead.id);

    // Tech lead approves the pending request
    const resumed = await adapter.resumePausedTask(result.requestId!, true, techLead.id);
    assert.strictEqual(resumed.status, 'completed');
    assert.ok(resumed.output?.includes('resumed and completed'));

    // Check agent spend updated
    const coder = adapter.getAgent(juniorCoder.id);
    assert.strictEqual(coder?.currentSpendUSD, 2.0);
    assert.strictEqual(adapter.getPendingApprovals().length, 0);
  });

  test('5. Rejection by supervisor transitions agent back to idle with explanation', async () => {
    const { adapter, juniorCoder, techLead } = setupOrg();

    const result = await adapter.dispatchTask(juniorCoder.id, 'Wipe cluster logs', 1.5);
    assert.strictEqual(result.status, 'paused_for_approval');

    const resumed = await adapter.resumePausedTask(
      result.requestId!,
      false,
      techLead.id,
      'Dangerous operation prohibited by safety protocol'
    );

    assert.strictEqual(resumed.status, 'idle');
    assert.ok(resumed.output?.includes('rejected'));
    const coder = adapter.getAgent(juniorCoder.id);
    assert.strictEqual(coder?.status, 'idle');
    assert.strictEqual(coder?.currentSpendUSD, 0); // No spend incurred
  });

  test('6. Fleet summary aggregates health and telemetry metrics', () => {
    const { adapter, techLead } = setupOrg();

    adapter.recordSpend(techLead.id, 10.0);
    const summary = adapter.getOrgSummary();

    assert.strictEqual(summary.orgId, 'aevum-org-1');
    assert.strictEqual(summary.totalAgents, 3);
    assert.strictEqual(summary.totalSpendUSD, 10.0);
    assert.strictEqual(summary.remainingBudgetUSD, 90.0);
    assert.strictEqual(summary.pendingApprovals, 0);
  });
});
