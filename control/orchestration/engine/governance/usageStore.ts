/**
 * Usage Store
 * Internal tracking and spend visibility for pooled quota and virtual keys.
 * Inspired by LiteLLM spend tracking patterns.
 */

import { nanoid } from 'nanoid';
import type { UsageAuditRecord, RoutingPath } from '../types.js';

export class UsageStore {
  private records: UsageAuditRecord[] = [];

  recordUsage(entry: {
    virtualKey?: string;
    userId?: string;
    teamId?: string;
    model: string;
    routeUsed: RoutingPath;
    promptTokens: number;
    completionTokens: number;
    costUSD: number;
    latencyMs: number;
    status: 'success' | 'failed';
    error?: string;
  }): UsageAuditRecord {
    const record: UsageAuditRecord = {
      id: `audit-${nanoid(12)}`,
      timestamp: Date.now(),
      ...entry,
    };
    this.records.push(record);
    return record;
  }

  getRecords(): UsageAuditRecord[] {
    return [...this.records];
  }

  getTotalSpendUSD(filter?: { virtualKey?: string; userId?: string; routeUsed?: RoutingPath }): number {
    let filtered = this.records;
    if (filter?.virtualKey) {
      filtered = filtered.filter((r) => r.virtualKey === filter.virtualKey);
    }
    if (filter?.userId) {
      filtered = filtered.filter((r) => r.userId === filter.userId);
    }
    if (filter?.routeUsed) {
      filtered = filtered.filter((r) => r.routeUsed === filter.routeUsed);
    }
    return filtered.reduce((sum, r) => sum + r.costUSD, 0);
  }

  getPooledSpendUSD(): number {
    return this.records
      .filter((r) => r.routeUsed === 'pooled-enterprise' || r.routeUsed === 'pooled-aggregator')
      .reduce((sum, r) => sum + r.costUSD, 0);
  }
}
