export interface RateLimitResult {
  allowed: boolean;
  limit: number;
  remaining: number;
  resetSeconds: number;
}

export class SlidingWindowRateLimiter {
  private windows = new Map<string, number[]>();
  private defaultLimit: number;
  private windowDurationSeconds: number;

  constructor(defaultLimit: number = 60, windowDurationSeconds: number = 60) {
    this.defaultLimit = defaultLimit;
    this.windowDurationSeconds = windowDurationSeconds;
  }

  public check(key: string, customLimit?: number): RateLimitResult {
    const limit = customLimit ?? this.defaultLimit;
    const now = Date.now();
    const windowStart = now - (this.windowDurationSeconds * 1000);

    let timestamps = this.windows.get(key) || [];
    // Discard timestamps older than windowStart
    timestamps = timestamps.filter((t) => t > windowStart);

    if (timestamps.length >= limit) {
      const oldestInWindow = timestamps[0];
      const resetSeconds = Math.max(1, Math.ceil((oldestInWindow + (this.windowDurationSeconds * 1000) - now) / 1000));
      return {
        allowed: false,
        limit,
        remaining: 0,
        resetSeconds
      };
    }

    // Record this request
    timestamps.push(now);
    this.windows.set(key, timestamps);

    return {
      allowed: true,
      limit,
      remaining: Math.max(0, limit - timestamps.length),
      resetSeconds: this.windowDurationSeconds
    };
  }

  public reset(key: string): void {
    this.windows.delete(key);
  }
}
