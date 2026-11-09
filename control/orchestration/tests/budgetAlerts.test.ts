/**
 * Tests for Budget Alerts & Graceful Degradation (Feature 8.48)
 */

import { test, describe } from 'node:test';
import assert from 'node:assert';
import {
  BudgetTracker,
  BudgetExceededError,
  type BudgetAlert,
} from '../engine/index.js';

describe('Budget Alerts & Graceful Degradation (Feature 8.48)', () => {
  test('1. Proactive alerts fire at 50% and 80% thresholds', () => {
    const tracker = new BudgetTracker();
    const alertsReceived: BudgetAlert[] = [];

    tracker.onAlert((alert) => {
      alertsReceived.push(alert);
    });

    tracker.setBudget({
      entityId: 'user_dev_1',
      entityType: 'user',
      maxSpendUSD: 10.0,
      resetPeriod: 'monthly',
    });

    // Spend 5.50 (55% threshold)
    tracker.recordSpend('user_dev_1', 5.5);
    assert.strictEqual(alertsReceived.length, 1);
    assert.strictEqual(alertsReceived[0].thresholdPercent, 50);

    // Spend additional 3.00 (85% threshold)
    tracker.recordSpend('user_dev_1', 3.0);
    assert.strictEqual(alertsReceived.length, 2);
    assert.strictEqual(alertsReceived[1].thresholdPercent, 80);
  });

  test('2. Graceful degradation suggests model downgrade when exceeding budget', () => {
    const tracker = new BudgetTracker();
    tracker.setBudget({
      entityId: 'key_prod_1',
      entityType: 'key',
      maxSpendUSD: 5.0,
      resetPeriod: 'daily',
    });

    tracker.recordSpend('key_prod_1', 4.8);

    // Projected spend of $0.50 with premium gpt-4o would exceed $5.00
    const decision = tracker.checkBudgetWithDegradation('key_prod_1', 0.5, 'openai/gpt-4o');
    assert.strictEqual(decision.allowed, false);
    assert.strictEqual(decision.action, 'downgrade_model');
    assert.strictEqual(decision.suggestedModel, 'openai/gpt-4o-mini');
    assert.ok(decision.alert !== undefined);
    assert.strictEqual(decision.alert?.thresholdPercent, 100);
  });

  test('3. Hard budget check throws BudgetExceededError when cap breached', () => {
    const tracker = new BudgetTracker();
    tracker.setBudget({
      entityId: 'team_sales',
      entityType: 'team',
      maxSpendUSD: 20.0,
    });

    tracker.recordSpend('team_sales', 20.0);

    assert.throws(
      () => {
        tracker.checkBudget('team_sales', 0.01);
      },
      (err: any) => err instanceof BudgetExceededError && err.entityId === 'team_sales'
    );
  });

  test('4. Alert history tracks entity alerts correctly', () => {
    const tracker = new BudgetTracker();
    tracker.setBudget({
      entityId: 'user_history_test',
      entityType: 'user',
      maxSpendUSD: 10.0,
    });

    tracker.recordSpend('user_history_test', 9.5); // Crosses 50, 80, 90
    const history = tracker.getAlertHistory('user_history_test');
    assert.ok(history.length >= 2);
    assert.ok(history.some((a) => a.thresholdPercent === 50));
    assert.ok(history.some((a) => a.thresholdPercent === 90));
  });
});
