export interface TokenUsageEntry {
  timestamp: number;
  tokens: number;
}

export class SlidingWindowTPMLimiter {
  private static instance: SlidingWindowTPMLimiter;
  private windows: Map<string, TokenUsageEntry[]> = new Map();
  private readonly windowMs = 60000; // 1 minute sliding window

  public static getInstance(): SlidingWindowTPMLimiter {
    if (!SlidingWindowTPMLimiter.instance) {
      SlidingWindowTPMLimiter.instance = new SlidingWindowTPMLimiter();
    }
    return SlidingWindowTPMLimiter.instance;
  }

  private cleanOldEntries(key: string, now: number): TokenUsageEntry[] {
    const entries = this.windows.get(key) || [];
    const threshold = now - this.windowMs;
    const active = entries.filter((e) => e.timestamp > threshold);
    this.windows.set(key, active);
    return active;
  }

  /**
   * Checks whether the given token consumption can be accommodated within the TPM limit.
   */
  public checkLimit(
    key: string,
    maxTpm: number,
    estimatedTokens = 0,
  ): {
    allowed: boolean;
    currentTokens: number;
    remainingTokens: number;
    resetSec: number;
  } {
    const now = Date.now();
    const active = this.cleanOldEntries(key, now);
    const currentTokens = active.reduce((sum, e) => sum + e.tokens, 0);

    const remainingTokens = Math.max(0, maxTpm - currentTokens);
    const resetSec =
      active.length > 0
        ? Math.max(1, Math.ceil((active[0].timestamp + this.windowMs - now) / 1000))
        : 60;

    if (currentTokens + estimatedTokens > maxTpm) {
      return {
        allowed: false,
        currentTokens,
        remainingTokens,
        resetSec,
      };
    }

    return {
      allowed: true,
      currentTokens,
      remainingTokens: Math.max(0, remainingTokens - estimatedTokens),
      resetSec,
    };
  }

  /**
   * Atomically records actual tokens used upon request completion.
   */
  public recordUsage(key: string, tokens: number): void {
    if (tokens <= 0) return;
    const now = Date.now();
    const active = this.cleanOldEntries(key, now);
    active.push({ timestamp: now, tokens });
    this.windows.set(key, active);
  }

  /**
   * Emits standard HTTP token rate limit headers.
   */
  public getRateLimitHeaders(key: string, maxTpm: number): Record<string, string> {
    const check = this.checkLimit(key, maxTpm);
    return {
      'x-ratelimit-limit-tokens': maxTpm.toString(),
      'x-ratelimit-remaining-tokens': check.remainingTokens.toString(),
      'x-ratelimit-reset-tokens': check.resetSec.toString(),
    };
  }

  public clear(): void {
    this.windows.clear();
  }
}
