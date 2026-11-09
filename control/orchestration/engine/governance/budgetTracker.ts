/**
 * Budget Tracker & Graceful Degradation Engine
 * Native TypeScript implementation inspired by LiteLLM's budget cap pattern.
 * Enforces spending caps per user, team, or key with automatic reset periods,
 * multi-tier proactive alerts (50%, 80%, 90%, 100%), and graceful model degradation.
 *
 * Feature ID: 8.48
 */

import type { BudgetRecord } from '../types.js';

export type DegradationAction = 'none' | 'alert_only' | 'downgrade_model' | 'reject';

export interface BudgetAlert {
  id: string;
  entityId: string;
  thresholdPercent: number;
  currentSpendUSD: number;
  maxSpendUSD: number;
  degradationAction: DegradationAction;
  suggestedFallbackModel?: string;
  timestamp: number;
}

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
  private firedThresholds: Map<string, Set<number>> = new Map();
  private alertListeners: Array<(alert: BudgetAlert) => void> = [];
  private alertHistory: BudgetAlert[] = [];

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
    this.firedThresholds.set(params.entityId, new Set());
    return record;
  }

  getBudget(entityId: string): BudgetRecord | undefined {
    const record = this.budgets.get(entityId);
    if (!record) return undefined;

    // Check if period needs reset
    this.checkAndResetPeriod(record);
    return record;
  }

  /**
   * Registers a callback listener for budget alert threshold events.
   */
  onAlert(listener: (alert: BudgetAlert) => void): () => void {
    this.alertListeners.push(listener);
    return () => {
      this.alertListeners = this.alertListeners.filter((l) => l !== listener);
    };
  }

  /**
   * Check budget with proactive alerts and optional graceful degradation.
   */
  checkBudgetWithDegradation(
    entityId: string,
    estimatedCostUSD: number = 0,
    requestedModel: string = 'openai/gpt-4o'
  ): {
    allowed: boolean;
    action: DegradationAction;
    suggestedModel?: string;
    alert?: BudgetAlert;
  } {
    const record = this.getBudget(entityId);
    if (!record) {
      return { allowed: true, action: 'none' };
    }

    const projectedSpend = record.currentSpendUSD + estimatedCostUSD;
    const usageRatio = projectedSpend / record.maxSpendUSD;
    const usagePercent = Math.round(usageRatio * 100);

    // Hard ceiling breach
    if (projectedSpend > record.maxSpendUSD) {
      // Suggest downgrade if requested model is premium
      const isPremium = !requestedModel.includes('mini') && !requestedModel.includes('llama');
      const suggestedModel = isPremium ? 'openai/gpt-4o-mini' : 'ollama/llama3.2';

      const alert: BudgetAlert = {
        id: `alert_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
        entityId,
        thresholdPercent: 100,
        currentSpendUSD: record.currentSpendUSD,
        maxSpendUSD: record.maxSpendUSD,
        degradationAction: 'downgrade_model',
        suggestedFallbackModel: suggestedModel,
        timestamp: Date.now(),
      };

      this.emitAlert(alert);
      return {
        allowed: false,
        action: 'downgrade_model',
        suggestedModel,
        alert,
      };
    }

    // Proactive threshold alerts (50%, 80%, 90%)
    for (const thresh of [90, 80, 50]) {
      if (usagePercent >= thresh) {
        const fired = this.firedThresholds.get(entityId) || new Set();
        if (!fired.has(thresh)) {
          fired.add(thresh);
          this.firedThresholds.set(entityId, fired);

          const alert: BudgetAlert = {
            id: `alert_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
            entityId,
            thresholdPercent: thresh,
            currentSpendUSD: record.currentSpendUSD,
            maxSpendUSD: record.maxSpendUSD,
            degradationAction: thresh >= 90 ? 'alert_only' : 'none',
            timestamp: Date.now(),
          };
          this.emitAlert(alert);
          return { allowed: true, action: thresh >= 90 ? 'alert_only' : 'none', alert };
        }
      }
    }

    return { allowed: true, action: 'none' };
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

    // Trigger proactive alert thresholds if newly crossed
    const ratio = record.currentSpendUSD / record.maxSpendUSD;
    const percent = Math.round(ratio * 100);

    for (const thresh of [50, 80, 90, 100]) {
      if (percent >= thresh) {
        const fired = this.firedThresholds.get(entityId) || new Set();
        if (!fired.has(thresh)) {
          fired.add(thresh);
          this.firedThresholds.set(entityId, fired);

          const alert: BudgetAlert = {
            id: `alert_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
            entityId,
            thresholdPercent: thresh,
            currentSpendUSD: record.currentSpendUSD,
            maxSpendUSD: record.maxSpendUSD,
            degradationAction: thresh >= 100 ? 'reject' : 'none',
            timestamp: Date.now(),
          };
          this.emitAlert(alert);
        }
      }
    }
  }

  getAlertHistory(entityId?: string): BudgetAlert[] {
    if (entityId) {
      return this.alertHistory.filter((a) => a.entityId === entityId);
    }
    return [...this.alertHistory];
  }

  private emitAlert(alert: BudgetAlert): void {
    this.alertHistory.push(alert);
    for (const listener of this.alertListeners) {
      try {
        listener(alert);
      } catch {
        // Suppress listener error
      }
    }
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
      this.firedThresholds.get(record.entityId)?.clear();
    }
  }
}
