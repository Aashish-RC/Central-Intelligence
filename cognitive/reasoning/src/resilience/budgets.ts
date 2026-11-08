export type BudgetWindow = 'daily' | 'monthly' | 'lifetime';

export interface BudgetConfig {
  id: string;
  scope: 'organization' | 'team' | 'user' | 'key';
  maxSpendUsd: number;
  window: BudgetWindow;
  currency?: string;
}

export interface BudgetState {
  currentSpendUsd: number;
  windowStart: number;
  windowEnd: number;
  totalRequests: number;
}

export class BudgetExceededError extends Error {
  public scope: string;
  public id: string;
  public currentSpend: number;
  public limit: number;

  constructor(scope: string, id: string, currentSpend: number, limit: number) {
    super(
      `Budget exceeded for ${scope} '${id}': spent $${currentSpend.toFixed(4)}, limit is $${limit.toFixed(4)}`,
    );
    this.name = 'BudgetExceededError';
    this.scope = scope;
    this.id = id;
    this.currentSpend = currentSpend;
    this.limit = limit;
  }
}

export class HierarchicalBudgetManager {
  private static instance: HierarchicalBudgetManager;
  private configs: Map<string, BudgetConfig> = new Map();
  private states: Map<string, BudgetState> = new Map();

  public static getInstance(): HierarchicalBudgetManager {
    if (!HierarchicalBudgetManager.instance) {
      HierarchicalBudgetManager.instance = new HierarchicalBudgetManager();
    }
    return HierarchicalBudgetManager.instance;
  }

  private computeWindowBounds(
    window: BudgetWindow,
    now: number = Date.now(),
  ): { start: number; end: number } {
    const date = new Date(now);
    if (window === 'daily') {
      const start = new Date(
        Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()),
      ).getTime();
      const end = start + 86400000;
      return { start, end };
    } else if (window === 'monthly') {
      const start = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1)).getTime();
      const nextMonth = new Date(
        Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 1),
      ).getTime();
      return { start, end: nextMonth };
    }
    return { start: 0, end: Number.MAX_SAFE_INTEGER };
  }

  public registerBudget(config: BudgetConfig): void {
    const key = `${config.scope}:${config.id}`;
    this.configs.set(key, config);
    const bounds = this.computeWindowBounds(config.window);
    if (!this.states.has(key)) {
      this.states.set(key, {
        currentSpendUsd: 0,
        windowStart: bounds.start,
        windowEnd: bounds.end,
        totalRequests: 0,
      });
    }
  }

  public checkBudget(identifiers: {
    orgId?: string;
    teamId?: string;
    userId?: string;
    keyId?: string;
  }): { allowed: boolean; reason?: string } {
    const checks: Array<{ scope: 'organization' | 'team' | 'user' | 'key'; id?: string }> = [
      { scope: 'organization', id: identifiers.orgId },
      { scope: 'team', id: identifiers.teamId },
      { scope: 'user', id: identifiers.userId },
      { scope: 'key', id: identifiers.keyId },
    ];

    const now = Date.now();

    for (const check of checks) {
      if (!check.id) continue;
      const key = `${check.scope}:${check.id}`;
      const config = this.configs.get(key);
      if (!config) continue;

      const state = this.states.get(key);
      if (!state) continue;

      // Check window rollover
      if (now >= state.windowEnd) {
        const bounds = this.computeWindowBounds(config.window, now);
        state.currentSpendUsd = 0;
        state.windowStart = bounds.start;
        state.windowEnd = bounds.end;
      }

      if (state.currentSpendUsd >= config.maxSpendUsd) {
        return {
          allowed: false,
          reason: `Budget cap of $${config.maxSpendUsd.toFixed(2)} reached for ${check.scope} '${check.id}' (current: $${state.currentSpendUsd.toFixed(4)})`,
        };
      }
    }

    return { allowed: true };
  }

  public recordSpend(
    identifiers: { orgId?: string; teamId?: string; userId?: string; keyId?: string },
    costUsd: number,
  ): void {
    const checks: Array<{ scope: 'organization' | 'team' | 'user' | 'key'; id?: string }> = [
      { scope: 'organization', id: identifiers.orgId },
      { scope: 'team', id: identifiers.teamId },
      { scope: 'user', id: identifiers.userId },
      { scope: 'key', id: identifiers.keyId },
    ];

    const now = Date.now();

    for (const check of checks) {
      if (!check.id) continue;
      const key = `${check.scope}:${check.id}`;
      const config = this.configs.get(key);
      if (!config) continue;

      let state = this.states.get(key);
      if (!state) {
        const bounds = this.computeWindowBounds(config.window, now);
        state = {
          currentSpendUsd: 0,
          windowStart: bounds.start,
          windowEnd: bounds.end,
          totalRequests: 0,
        };
        this.states.set(key, state);
      }

      if (now >= state.windowEnd) {
        const bounds = this.computeWindowBounds(config.window, now);
        state.currentSpendUsd = 0;
        state.windowStart = bounds.start;
        state.windowEnd = bounds.end;
      }

      state.currentSpendUsd += costUsd;
      state.totalRequests += 1;
    }
  }

  public getBudgetStatus(
    scope: 'organization' | 'team' | 'user' | 'key',
    id: string,
  ):
    | {
        limit: number;
        currentSpend: number;
        remaining: number;
        totalRequests: number;
      }
    | undefined {
    const key = `${scope}:${id}`;
    const config = this.configs.get(key);
    const state = this.states.get(key);
    if (!config || !state) return undefined;

    return {
      limit: config.maxSpendUsd,
      currentSpend: state.currentSpendUsd,
      remaining: Math.max(0, config.maxSpendUsd - state.currentSpendUsd),
      totalRequests: state.totalRequests,
    };
  }

  public clear(): void {
    this.configs.clear();
    this.states.clear();
  }
}
