export interface RateLimitResult {
  allowed: boolean;
  limit: number;
  remaining: number;
  resetSeconds: number;
  resetAfterMs?: number;
  retryAfterMs?: number;
}

export interface RateLimiterOptions {
  clock?: () => number;
  maxTrackedKeys?: number;
}

export class SlidingWindowRateLimiter {
  private defaultLimit: number;
  private windowDurationMs: number;
  private clock: () => number;
  private maxTrackedKeys: number;
  private keyTimestamps: Map<string, number[]>;

  constructor(defaultLimit = 60, windowDurationSeconds = 60, options: RateLimiterOptions = {}) {
    this.defaultLimit = defaultLimit;
    this.windowDurationMs = windowDurationSeconds * 1000;
    this.clock = options.clock ?? (() => Date.now());
    this.maxTrackedKeys = options.maxTrackedKeys ?? 10000;
    this.keyTimestamps = new Map<string, number[]>();
  }

  /**
   * Evaluates rate limit using a true sliding window and atomically records
   * the request if allowed.
   */
  public check(key: string, customLimit?: number): RateLimitResult {
    const now = this.clock();
    const limit = customLimit !== undefined ? customLimit : this.defaultLimit;

    // Limit 0 means block all requests immediately
    if (limit === 0) {
      const resetSec = Math.max(1, Math.ceil(this.windowDurationMs / 1000));
      return {
        allowed: false,
        limit: 0,
        remaining: 0,
        resetSeconds: resetSec,
        resetAfterMs: this.windowDurationMs,
        retryAfterMs: this.windowDurationMs,
      };
    }

    const timestamps = this.keyTimestamps.get(key) || [];

    // Filter out expired timestamps:
    // A request recorded at timestamp t expires at t + windowDurationMs.
    // If the clock jumps backwards (now < t), t + windowDurationMs > now remains true,
    // ensuring backwards clock drift cannot be exploited to gain extra quota.
    const activeTimestamps = timestamps.filter((t) => t + this.windowDurationMs > now);

    if (activeTimestamps.length < limit) {
      // Allowed: atomically record current timestamp
      activeTimestamps.push(now);
      this.recordKey(key, activeTimestamps);

      const oldest = activeTimestamps[0];
      const resetAfterMs = Math.max(0, oldest + this.windowDurationMs - now);
      const resetSeconds = Math.max(1, Math.ceil(resetAfterMs / 1000));

      return {
        allowed: true,
        limit,
        remaining: limit - activeTimestamps.length,
        resetSeconds,
        resetAfterMs,
      };
    } else {
      // Denied: do not record, so window is not extended
      this.recordKey(key, activeTimestamps);

      const oldest = activeTimestamps[0];
      const retryAfterMs = Math.max(1, oldest + this.windowDurationMs - now);
      const resetSeconds = Math.max(1, Math.ceil(retryAfterMs / 1000));

      return {
        allowed: false,
        limit,
        remaining: 0,
        resetSeconds,
        resetAfterMs: retryAfterMs,
        retryAfterMs,
      };
    }
  }

  public reset(key: string): void {
    this.keyTimestamps.delete(key);
  }

  private recordKey(key: string, timestamps: number[]): void {
    // If key exists, update and refresh in LRU order
    if (this.keyTimestamps.has(key)) {
      this.keyTimestamps.delete(key);
      this.keyTimestamps.set(key, timestamps);
      return;
    }

    // If maxTrackedKeys reached, evict idle keys first
    if (this.keyTimestamps.size >= this.maxTrackedKeys) {
      const now = this.clock();
      let evicted = false;

      // Find an idle key with no active timestamps
      for (const [k, ts] of this.keyTimestamps.entries()) {
        const hasActive = ts.some((t) => t + this.windowDurationMs > now);
        if (!hasActive) {
          this.keyTimestamps.delete(k);
          evicted = true;
          break;
        }
      }

      // If no idle keys, evict least recently used key
      if (!evicted) {
        const oldestKey = this.keyTimestamps.keys().next().value;
        if (oldestKey !== undefined) {
          this.keyTimestamps.delete(oldestKey);
        }
      }
    }

    this.keyTimestamps.set(key, timestamps);
  }
}
