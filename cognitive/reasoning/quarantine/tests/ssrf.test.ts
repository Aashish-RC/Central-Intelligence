import { describe, expect, it } from 'vitest';
import { SSRFGuard } from '../src/security/ssrf.js';

describe('W6: SSRF Hardening & Range Validation', () => {
  it('blocks link-local IPv6 (fe80::/10)', () => {
    expect(SSRFGuard.isPrivateOrReservedIp('fe80::1', false)).toBe(true);
    expect(SSRFGuard.isPrivateOrReservedIp('fe80::200:5aee:feaa:20a2', false)).toBe(true);
  });

  it('blocks IPv4-mapped IPv6 (::ffff:10.0.0.1, ::ffff:192.168.1.1)', () => {
    expect(SSRFGuard.isPrivateOrReservedIp('::ffff:10.0.0.1', false)).toBe(true);
    expect(SSRFGuard.isPrivateOrReservedIp('::ffff:192.168.1.1', false)).toBe(true);
    expect(SSRFGuard.isPrivateOrReservedIp('::ffff:169.254.169.254', false)).toBe(true);
    // Public IPv4-mapped should be allowed
    expect(SSRFGuard.isPrivateOrReservedIp('::ffff:8.8.8.8', false)).toBe(false);
  });

  it('blocks Carrier-Grade NAT (100.64.0.0/10)', () => {
    expect(SSRFGuard.isPrivateOrReservedIp('100.64.0.1', false)).toBe(true);
    expect(SSRFGuard.isPrivateOrReservedIp('100.127.255.254', false)).toBe(true);
    // 100.128.0.1 is outside the /10 range (100.64.0.0 - 100.127.255.255)
    expect(SSRFGuard.isPrivateOrReservedIp('100.128.0.1', false)).toBe(false);
  });

  it('blocks benchmarking (198.18.0.0/15), multicast (224.0.0.0/4), and reserved (240.0.0.0/4)', () => {
    expect(SSRFGuard.isPrivateOrReservedIp('198.18.0.5', false)).toBe(true);
    expect(SSRFGuard.isPrivateOrReservedIp('198.19.255.1', false)).toBe(true);
    expect(SSRFGuard.isPrivateOrReservedIp('224.0.0.1', false)).toBe(true);
    expect(SSRFGuard.isPrivateOrReservedIp('240.0.0.1', false)).toBe(true);
  });

  it('fails closed when DNS resolution fails', async () => {
    // Non-existent TLD will fail DNS resolution
    await expect(SSRFGuard.validateUrl('https://this-domain-definitely-does-not-exist-xyz12399.invalid/v1'))
      .rejects.toThrow('SSRF Guard: DNS resolution failed');
  });

  it('allows verified public addresses', async () => {
    await expect(SSRFGuard.validateUrl('https://api.openai.com/v1/chat/completions')).resolves.toBeUndefined();
  });

  it('supports injectable resolver via static setter', async () => {
    const customResolver = async (host: string) => [{ address: '10.0.0.99', family: 4 }];
    (SSRFGuard as any).setResolver(customResolver);
    try {
      await expect(SSRFGuard.validateUrl('https://example-corp.com/api'))
        .rejects.toThrow('is a private or reserved network address');
    } finally {
      (SSRFGuard as any).resetResolver?.();
    }
  });

  it('supports injectable resolver via constructor instance', async () => {
    const customResolver = async (host: string) => [{ address: '93.184.216.34', family: 4 }];
    const guard = new (SSRFGuard as any)(customResolver);
    await expect(guard.validateUrl('https://example-corp.com/api')).resolves.toBeUndefined();
  });
});
