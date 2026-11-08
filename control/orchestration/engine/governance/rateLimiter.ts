/**
 * Rate Limiter
 * Native TypeScript sliding-window rate limiting (RPM & TPM).
 * Inspired by LiteLLM rate-limiting patterns.
 */

import type { RateLimitStatus } from '../types.js';

export class RateLimitExceededError extends Error {
  readonly entityId: string;
  readonly limitType: 'RPM' | 'TPM';
  readonly current: number;
  readonly limit: number;

  constructor(entityId: string, limitType: 'RPM' | 'TPM', current: number, limit: number) {
    super(
      `Rate limit exceeded for ${entityId}: ${limitType} count (${current}) exceeded limit of ${limit}.`
    );
    this.name = 'RateLimitExceededError';
    this.entityId = entityId;
    this.limitType = limitType;
    this.current = current;
    this.limit = limit;
  }
}

export interface RateLimitConfig {
  maxRPM: number;
  maxTPM: number;
}

export class RateLimiter {
  private limits: Map<string, RateLimitConfig> = new Map();
  private windows: Map<string, RateLimitStatus> = new Map();

  setLimits(entityId: string, config: RateLimitConfig): void {
    this.limits.set(entityId, config);
  }

  checkAndIncrement(entityId: string, estimatedTokens = 100): void {
    const config = this.limits.get(entityId);
    if (!config) return;

    const now = Date.now();
    let status = this.windows.get(entityId);

    // Reset window after 60 seconds
    if (!status || now - status.windowStartMs >= 60000) {
      status = {
        requestsThisMinute: 0,
        tokensThisMinute: 0,
        windowStartMs: now,
      };
      this.windows.set(entityId, status);
    }

    if (status.requestsThisMinute + 1 > config.maxRPM) {
      throw new RateLimitExceededError(entityId, 'RPM', status.requestsThisMinute + 1, config.maxRPM);
    }

    if (status.tokensThisMinute + estimatedTokens > config.maxTPM) {
      throw new RateLimitExceededError(entityId, 'TPM', status.tokensThisMinute + estimatedTokens, config.maxTPM);
    }

    status.requestsThisMinute += 1;
    status.tokensThisMinute += estimatedTokens;
  }
}
