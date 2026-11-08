import { beforeEach, describe, expect, it } from 'vitest';
import { SlidingWindowRateLimiter } from '../src/resilience/ratelimit.js';

describe('Sliding Window Rate Limiter (Clean-Room Spec)', () => {
  let currentTime = 1000000;
  const mockClock = () => currentTime;

  beforeEach(() => {
    currentTime = 1000000;
  });

  it('allows requests within default quota and reports remaining correctly', () => {
    const limiter = new SlidingWindowRateLimiter(5, 60, { clock: mockClock } as any);
    const key = 'user-123';

    const r1 = limiter.check(key);
    expect(r1.allowed).toBe(true);
    expect(r1.limit).toBe(5);
    expect(r1.remaining).toBe(4);
    expect(r1.resetSeconds).toBeGreaterThanOrEqual(1);

    const r2 = limiter.check(key);
    expect(r2.allowed).toBe(true);
    expect(r2.remaining).toBe(3);
  });

  it('edge case: allows exactly N requests and denies the (N+1)-th request', () => {
    const limit = 3;
    const windowSec = 10;
    const limiter = new SlidingWindowRateLimiter(limit, windowSec, { clock: mockClock } as any);
    const key = 'tenant-42';

    // 1st request
    expect(limiter.check(key).allowed).toBe(true);
    // 2nd request
    expect(limiter.check(key).allowed).toBe(true);
    // 3rd request (quota exhausted)
    const r3 = limiter.check(key);
    expect(r3.allowed).toBe(true);
    expect(r3.remaining).toBe(0);

    // 4th request -> denied
    const r4 = limiter.check(key);
    expect(r4.allowed).toBe(false);
    expect(r4.remaining).toBe(0);
    expect(r4.resetSeconds).toBeGreaterThan(0);
  });

  it('edge case: request is allowed again right after the oldest one leaves the window', () => {
    const limiter = new SlidingWindowRateLimiter(2, 10, { clock: mockClock } as any);
    const key = 'actor-burst';

    // t = 1000: request 1
    currentTime = 1000000;
    expect(limiter.check(key).allowed).toBe(true);

    // t = 1002: request 2
    currentTime = 1002000;
    expect(limiter.check(key).allowed).toBe(true);

    // t = 1003: request 3 denied
    currentTime = 1003000;
    expect(limiter.check(key).allowed).toBe(false);

    // Advance clock past the 1st request window (1000s + 10s = 1010s)
    currentTime = 1010001; // 1ms after first request expired
    const rAfter = limiter.check(key);
    expect(rAfter.allowed).toBe(true);
    expect(rAfter.remaining).toBe(0); // 1 active from t=1002, 1 just consumed
  });

  it('edge case: denied requests do not consume quota or extend the sliding window', () => {
    const limiter = new SlidingWindowRateLimiter(1, 5, { clock: mockClock } as any);
    const key = 'user-spam';

    // Consume single allowed token at t = 1000
    currentTime = 1000000;
    expect(limiter.check(key).allowed).toBe(true);

    // Hammer with denied requests at t = 1001, 1002, 1003, 1004
    currentTime = 1001000;
    expect(limiter.check(key).allowed).toBe(false);
    currentTime = 1002000;
    expect(limiter.check(key).allowed).toBe(false);
    currentTime = 1003000;
    expect(limiter.check(key).allowed).toBe(false);
    currentTime = 1004000;
    expect(limiter.check(key).allowed).toBe(false);

    // At t = 1005001 (5s after allowed request), should be allowed despite intervening denied requests
    currentTime = 1005001;
    expect(limiter.check(key).allowed).toBe(true);
  });

  it('edge case: two distinct keys are completely independent', () => {
    const limiter = new SlidingWindowRateLimiter(2, 60, { clock: mockClock } as any);
    const keyA = 'client-A';
    const keyB = 'client-B';

    // Exhaust client A
    expect(limiter.check(keyA).allowed).toBe(true);
    expect(limiter.check(keyA).allowed).toBe(true);
    expect(limiter.check(keyA).allowed).toBe(false);

    // Client B still has full quota
    const resB1 = limiter.check(keyB);
    expect(resB1.allowed).toBe(true);
    expect(resB1.remaining).toBe(1);
  });

  it('edge case: concurrent calls in the same millisecond tick do not exceed N', () => {
    const limiter = new SlidingWindowRateLimiter(5, 60, { clock: mockClock } as any);
    const key = 'concurrent-caller';

    currentTime = 1000000;
    const results = [
      limiter.check(key),
      limiter.check(key),
      limiter.check(key),
      limiter.check(key),
      limiter.check(key),
      limiter.check(key), // 6th
      limiter.check(key), // 7th
    ];

    const allowedCount = results.filter((r) => r.allowed).length;
    const deniedCount = results.filter((r) => !r.allowed).length;

    expect(allowedCount).toBe(5);
    expect(deniedCount).toBe(2);
  });

  it('edge case: clock jump backwards does not grant extra quota', () => {
    const limiter = new SlidingWindowRateLimiter(2, 60, { clock: mockClock } as any);
    const key = 'time-traveler';

    currentTime = 2000000;
    expect(limiter.check(key).allowed).toBe(true);
    expect(limiter.check(key).allowed).toBe(true);
    expect(limiter.check(key).allowed).toBe(false);

    // System clock jumps backward by 100 seconds
    currentTime = 1900000;
    const resBackwards = limiter.check(key);
    expect(resBackwards.allowed).toBe(false);
  });

  it('limit 0 blocks all requests immediately', () => {
    const limiter = new SlidingWindowRateLimiter(0, 60, { clock: mockClock } as any);
    const res = limiter.check('anyone');
    expect(res.allowed).toBe(false);
    expect(res.limit).toBe(0);
    expect(res.remaining).toBe(0);
  });

  it('customLimit override takes precedence over default limit', () => {
    const limiter = new SlidingWindowRateLimiter(10, 60, { clock: mockClock } as any);
    // Custom limit of 1
    expect(limiter.check('vip', 1).allowed).toBe(true);
    expect(limiter.check('vip', 1).allowed).toBe(false);
  });

  it('reset clears the sliding window state for a specific key', () => {
    const limiter = new SlidingWindowRateLimiter(1, 60, { clock: mockClock } as any);
    const key = 'reset-me';

    expect(limiter.check(key).allowed).toBe(true);
    expect(limiter.check(key).allowed).toBe(false);

    limiter.reset(key);
    expect(limiter.check(key).allowed).toBe(true);
  });

  it('evicts idle keys when maximum tracked keys cap is reached', () => {
    const limiter = new SlidingWindowRateLimiter(5, 10, {
      clock: mockClock,
      maxTrackedKeys: 2,
    } as any);

    currentTime = 1000;
    limiter.check('key1');

    currentTime = 2000;
    limiter.check('key2');

    // Both keys tracked. Now advance time so key1 becomes older/idle
    currentTime = 15000; // key1 and key2 timestamps expired
    limiter.check('key2'); // touch key2

    // Now introduce key3 -> key1 was idle oldest, should be purged
    limiter.check('key3');

    // Key2 and Key3 are active
    expect(limiter.check('key2').allowed).toBe(true);
    expect(limiter.check('key3').allowed).toBe(true);
  });
});
