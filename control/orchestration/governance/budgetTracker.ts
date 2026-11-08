/**
 * Budget Tracker
 * Native TypeScript implementation inspired by LiteLLM's budget cap pattern.
 * Enforces spending caps per user, team, or key with automatic reset periods.
 */

import type { BudgetRecord } from '../types.js';

export class BudgetExceededError extends Error {
  readonly entityId: string;
  readonly currentSpendUSD: number;
  readonly maxSpendUSD: number;

  constructor(entityId: string, currentSpendUSD: number, maxSpendUSD: number) {
    super(
      `Budget exceeded for ${entityId}: current spend $${currentSpendUSD.toFixed(4)} has reached or exceeded the cap of $${maxSpendUSD.toFixed(4)}.`
    );
    this.name = 'BudgetExceededError';
    this.entityId = entityId;
    this.currentSpendUSD = currentSpendUSD;
    this.maxSpendUSD = maxSpendUSD;
  }
}

export class BudgetTracker {
  private budgets: Map<string, BudgetRecord> = new Map();

  setBudget(params: {
    entityId: string;
    entityType: 'user' | 'team' | 'key';
    maxSpendUSD: number;
    resetPeriod?: 'daily' | 'monthly' | 'lifetime';
  }): BudgetRecord {
    const record: BudgetRecord = {
      entityId: params.entityId,
      entityType: params.entityType,
      maxSpendUSD: params.maxSpendUSD,
      currentSpendUSD: 0,
      resetPeriod: params.resetPeriod || 'monthly',
      periodStart: Date.now(),
    };
    this.budgets.set(params.entityId, record);
    return record;
  }

  getBudget(entityId: string): BudgetRecord | undefined {
    const record = this.budgets.get(entityId);
    if (!record) return undefined;

    // Check if period needs reset
    this.checkAndResetPeriod(record);
    return record;
  }

  checkBudget(entityId: string, estimatedCostUSD = 0): void {
    const record = this.getBudget(entityId);
    if (!record) return;

    if (record.currentSpendUSD + estimatedCostUSD > record.maxSpendUSD) {
      throw new BudgetExceededError(entityId, record.currentSpendUSD, record.maxSpendUSD);
    }
  }

  recordSpend(entityId: string, costUSD: number): void {
    const record = this.getBudget(entityId);
    if (!record) return;

    record.currentSpendUSD += costUSD;
  }

  private checkAndResetPeriod(record: BudgetRecord): void {
    if (record.resetPeriod === 'lifetime') return;

    const now = Date.now();
    const elapsedMs = now - record.periodStart;
    let resetThresholdMs = 24 * 60 * 60 * 1000; // 1 day

    if (record.resetPeriod === 'monthly') {
      resetThresholdMs = 30 * 24 * 60 * 60 * 1000; // 30 days
    }

    if (elapsedMs >= resetThresholdMs) {
      record.currentSpendUSD = 0;
      record.periodStart = now;
    }
  }
}
