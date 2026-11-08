import { beforeEach, describe, expect, it } from 'vitest';
import { SlidingWindowTPMLimiter } from '../src/resilience/tpm.js';

describe('Feature 15: Tokens Per Minute (TPM) Sliding-Window Limiter', () => {
  let limiter: SlidingWindowTPMLimiter;

  beforeEach(() => {
    limiter = SlidingWindowTPMLimiter.getInstance();
    limiter.clear();
  });

  it('allows token usage within TPM limits', () => {
    const key = 'user-key-1';
    const maxTpm = 1000;

    const check1 = limiter.checkLimit(key, maxTpm, 250);
    expect(check1.allowed).toBe(true);
    expect(check1.remainingTokens).toBe(750);

    limiter.recordUsage(key, 250);

    const check2 = limiter.checkLimit(key, maxTpm, 500);
    expect(check2.allowed).toBe(true);
    expect(check2.remainingTokens).toBe(250);
  });

  it('blocks requests when estimated or cumulative tokens exceed TPM cap', () => {
    const key = 'user-key-2';
    const maxTpm = 500;

    limiter.recordUsage(key, 400);

    // Request with 150 estimated tokens would reach 550 > 500
    const check = limiter.checkLimit(key, maxTpm, 150);
    expect(check.allowed).toBe(false);
    expect(check.remainingTokens).toBe(100);
    expect(check.currentTokens).toBe(400);
  });

  it('generates compliant HTTP rate limit headers', () => {
    const key = 'user-key-3';
    const maxTpm = 2000;

    limiter.recordUsage(key, 500);

    const headers = limiter.getRateLimitHeaders(key, maxTpm);
    expect(headers['x-ratelimit-limit-tokens']).toBe('2000');
    expect(headers['x-ratelimit-remaining-tokens']).toBe('1500');
    expect(Number(headers['x-ratelimit-reset-tokens'])).toBeGreaterThan(0);
    expect(Number(headers['x-ratelimit-reset-tokens'])).toBeLessThanOrEqual(60);
  });
});
