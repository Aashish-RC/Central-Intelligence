import { beforeEach, describe, expect, it } from 'vitest';
import { HierarchicalBudgetManager } from '../src/resilience/budgets.js';

describe('Feature 27: Multi-Tier Hierarchical Budget & Quota Engine', () => {
  let budgetManager: HierarchicalBudgetManager;

  beforeEach(() => {
    budgetManager = HierarchicalBudgetManager.getInstance();
    budgetManager.clear();
  });

  it('allows requests when within registered budget limits', () => {
    budgetManager.registerBudget({
      id: 'org-acme',
      scope: 'organization',
      maxSpendUsd: 100.0,
      window: 'monthly',
    });

    budgetManager.registerBudget({
      id: 'team-backend',
      scope: 'team',
      maxSpendUsd: 25.0,
      window: 'daily',
    });

    const check = budgetManager.checkBudget({
      orgId: 'org-acme',
      teamId: 'team-backend',
    });

    expect(check.allowed).toBe(true);
  });

  it('records spend and enforces budget limits accurately', () => {
    budgetManager.registerBudget({
      id: 'key-dev-1',
      scope: 'key',
      maxSpendUsd: 0.05, // $0.05 budget
      window: 'daily',
    });

    // Request 1: $0.03 spend
    budgetManager.recordSpend({ keyId: 'key-dev-1' }, 0.03);
    let check = budgetManager.checkBudget({ keyId: 'key-dev-1' });
    expect(check.allowed).toBe(true);

    const status1 = budgetManager.getBudgetStatus('key', 'key-dev-1');
    expect(status1?.currentSpend).toBeCloseTo(0.03);
    expect(status1?.remaining).toBeCloseTo(0.02);

    // Request 2: $0.025 spend -> exceeds $0.05 limit
    budgetManager.recordSpend({ keyId: 'key-dev-1' }, 0.025);
    check = budgetManager.checkBudget({ keyId: 'key-dev-1' });
    expect(check.allowed).toBe(false);
    expect(check.reason).toContain("Budget cap of $0.05 reached for key 'key-dev-1'");
  });

  it('blocks request if higher tier in hierarchy is exhausted even if child tier has budget', () => {
    budgetManager.registerBudget({
      id: 'org-global',
      scope: 'organization',
      maxSpendUsd: 5.0,
      window: 'monthly',
    });

    budgetManager.registerBudget({
      id: 'team-rnd',
      scope: 'team',
      maxSpendUsd: 20.0, // Team has more than Org
      window: 'monthly',
    });

    // Exhaust Org limit
    budgetManager.recordSpend({ orgId: 'org-global' }, 5.5);

    const check = budgetManager.checkBudget({
      orgId: 'org-global',
      teamId: 'team-rnd',
    });

    expect(check.allowed).toBe(false);
    expect(check.reason).toContain("organization 'org-global'");
  });
});
