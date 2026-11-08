import { beforeEach, describe, expect, it } from 'vitest';
import { TokenVault } from '../src/security/vault.js';

describe('TokenVault (Clean-Room Spec)', () => {
  let mockNow = 1000000;
  const mockClock = () => mockNow;

  beforeEach(() => {
    mockNow = 1000000;
    TokenVault.getInstance().clear();
  });

  it('stores a sensitive value, returns a formatted surrogate token, and retrieves the record', () => {
    const vault = new TokenVault(3600, { clock: mockClock } as any);
    const token = vault.store('user@example.com', 'EMAIL');

    expect(token).toMatch(/^\[(?:TOKEN|PII)_[A-Z_]+_[a-zA-Z0-9_-]+\]$/);
    const record = vault.get(token);
    expect(record).toBeDefined();
    expect(record?.originalValue).toBe('user@example.com');
    expect(record?.entityType).toBe('EMAIL');
    expect(record?.createdAt).toBe(mockNow);
    expect(record?.expiresAt).toBe(mockNow + 3600 * 1000);
    expect(vault.size()).toBe(1);
  });

  it('returns identical surrogate token for identical original value within the same session (reverse mapping)', () => {
    const vault = new TokenVault(3600, { clock: mockClock } as any);
    const token1 = vault.store('secret@domain.com', 'EMAIL');
    const token2 = vault.store('secret@domain.com', 'EMAIL');

    expect(token1).toBe(token2);
    expect(vault.size()).toBe(1);
  });

  it('generates distinct tokens for different entity types or values', () => {
    const vault = new TokenVault(3600, { clock: mockClock } as any);
    const tokenEmail = vault.store('user@test.com', 'EMAIL');
    const tokenPhone = vault.store('555-123-4567', 'PHONE');

    expect(tokenEmail).not.toBe(tokenPhone);
    expect(vault.size()).toBe(2);
  });

  it('edge case: surrogate token mapping expires after TTL and fails safe on lookup', () => {
    const ttlSeconds = 60;
    const vault = new TokenVault(ttlSeconds, { clock: mockClock } as any);
    const token = vault.store('555-0199', 'PHONE', ttlSeconds);

    expect(vault.get(token)).toBeDefined();

    // Advance time past TTL (61 seconds)
    mockNow += 61 * 1000;

    // Looking up expired token returns undefined without throwing
    expect(vault.get(token)).toBeUndefined();
    expect(vault.size()).toBe(0);
  });

  it('edge case: bounded capacity with least-recently-used eviction policy', () => {
    const vault = new TokenVault(3600, {
      clock: mockClock,
      maxEntries: 2,
    } as any);

    const token1 = vault.store('first@example.com', 'EMAIL');
    const token2 = vault.store('second@example.com', 'EMAIL');

    // Access token1 to make it most recently used
    expect(vault.get(token1)).toBeDefined();

    // Store third item -> should evict token2
    const token3 = vault.store('third@example.com', 'EMAIL');

    expect(vault.get(token1)).toBeDefined();
    expect(vault.get(token3)).toBeDefined();
    expect(vault.get(token2)).toBeUndefined(); // evicted
    expect(vault.size()).toBe(2);
  });

  it('evict removes specific token and clear resets entire vault', () => {
    const vault = new TokenVault(3600, { clock: mockClock } as any);
    const t1 = vault.store('v1', 'SSN');
    const t2 = vault.store('v2', 'SSN');

    expect(vault.size()).toBe(2);
    vault.evict(t1);
    expect(vault.get(t1)).toBeUndefined();
    expect(vault.get(t2)).toBeDefined();
    expect(vault.size()).toBe(1);

    vault.clear();
    expect(vault.size()).toBe(0);
  });

  it('getInstance returns a singleton instance', () => {
    const inst1 = TokenVault.getInstance();
    const inst2 = TokenVault.getInstance();
    expect(inst1).toBe(inst2);
  });
});
