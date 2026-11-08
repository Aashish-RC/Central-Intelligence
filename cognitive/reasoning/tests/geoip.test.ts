import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { GeoIPConfig, GeoIPFilter } from '../src/security/geoip.js';

describe('GeoIP & Abuse IP Blocking Subsystem', () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    delete process.env.FEATURE_GEOIP;
  });

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  // Feature flag check
  it('Rule G17: Feature flag OFF by default bypasses filter and admits traffic', () => {
    const filter = new GeoIPFilter({
      blockedIps: ['198.51.100.1'],
      deniedCountries: ['XX'],
    });
    // Even if IP and country are blocked, flag off admits
    const result = filter.evaluate({ ip: '198.51.100.1', country: 'XX' });
    expect(result.allowed).toBe(true);
    expect(result.statusCode).toBe(200);
  });

  it('Rule G17: Feature flag ON enforces blocking rules', () => {
    process.env.FEATURE_GEOIP = 'true';
    const filter = new GeoIPFilter({
      blockedIps: ['198.51.100.1'],
    });
    const result = filter.evaluate({ ip: '198.51.100.1' });
    expect(result.allowed).toBe(false);
    expect(result.statusCode).toBe(403);
    expect(result.error?.error.message).toContain(
      'Access from client network or location is restricted',
    );
  });

  describe('When FEATURE_GEOIP is enabled', () => {
    beforeEach(() => {
      process.env.FEATURE_GEOIP = 'true';
    });

    it('Rule G1: Identifies client IP from headers (x-forwarded-for, x-real-ip) or direct input', () => {
      const filter = new GeoIPFilter({
        blockedIps: ['203.0.113.19'],
      });

      // Direct IP
      expect(filter.evaluate({ ip: '203.0.113.19' }).allowed).toBe(false);

      // From x-forwarded-for header (first untrusted client IP in chain)
      const headersXff = new Headers({ 'x-forwarded-for': '203.0.113.19, 10.0.0.1' });
      expect(filter.evaluateFromHeaders(headersXff).allowed).toBe(false);

      // From x-real-ip
      const headersReal = new Headers({ 'x-real-ip': '203.0.113.19' });
      expect(filter.evaluateFromHeaders(headersReal).allowed).toBe(false);

      // Unblocked IP in header
      const headersClean = new Headers({ 'x-forwarded-for': '198.51.100.5' });
      expect(filter.evaluateFromHeaders(headersClean).allowed).toBe(true);
    });

    it('Rule G2 & G13: Identifies country code from headers and normalizes case-insensitively', () => {
      const filter = new GeoIPFilter({
        deniedCountries: ['KP', 'IR'],
      });

      const headersCf = new Headers({
        'x-forwarded-for': '198.51.100.1',
        'cf-ipcountry': 'kp', // lowercase
      });
      const res = filter.evaluateFromHeaders(headersCf);
      expect(res.allowed).toBe(false);
      expect(res.statusCode).toBe(403);

      const headersXCountry = new Headers({
        'x-forwarded-for': '198.51.100.1',
        'x-country-code': 'Ir', // mixed case
      });
      expect(filter.evaluateFromHeaders(headersXCountry).allowed).toBe(false);
    });

    it('Rule G3: Filtering policy country allowlist permits allowed countries and blocks others', () => {
      const filter = new GeoIPFilter({
        allowedCountries: ['US', 'CA', 'GB'],
      });

      expect(filter.evaluate({ ip: '198.51.100.1', country: 'US' }).allowed).toBe(true);
      expect(filter.evaluate({ ip: '198.51.100.1', country: 'ca' }).allowed).toBe(true);

      const deniedRes = filter.evaluate({ ip: '198.51.100.1', country: 'FR' });
      expect(deniedRes.allowed).toBe(false);
      expect(deniedRes.statusCode).toBe(403);
    });

    it('Rule G4: Filtering policy country denylist blocks listed countries and admits unlisted', () => {
      const filter = new GeoIPFilter({
        deniedCountries: ['SY', 'CU'],
      });

      expect(filter.evaluate({ ip: '198.51.100.1', country: 'DE' }).allowed).toBe(true);
      expect(filter.evaluate({ ip: '198.51.100.1', country: 'sy' }).allowed).toBe(false);
    });

    it('Rule G5: Explicit blocked individual IPv4 and IPv6 addresses', () => {
      const filter = new GeoIPFilter({
        blockedIps: ['192.0.2.1', '2001:db8::dead:beef'],
      });

      expect(filter.evaluate({ ip: '192.0.2.1' }).allowed).toBe(false);
      expect(filter.evaluate({ ip: '192.0.2.2' }).allowed).toBe(true);
      expect(filter.evaluate({ ip: '2001:db8::dead:beef' }).allowed).toBe(false);
      expect(filter.evaluate({ ip: '2001:db8::dead:cafe' }).allowed).toBe(true);
    });

    it('Rule G6 & G12: Explicit blocked subnet CIDR network prefixes (IPv4 and IPv6 boundary matching)', () => {
      const filter = new GeoIPFilter({
        blockedCidrs: ['198.51.100.0/24', '2001:db8:abcd::/48'],
      });

      // IPv4 CIDR boundaries: first, middle, last
      expect(filter.evaluate({ ip: '198.51.100.0' }).allowed).toBe(false);
      expect(filter.evaluate({ ip: '198.51.100.128' }).allowed).toBe(false);
      expect(filter.evaluate({ ip: '198.51.100.255' }).allowed).toBe(false);
      // Just outside boundary
      expect(filter.evaluate({ ip: '198.51.99.255' }).allowed).toBe(true);
      expect(filter.evaluate({ ip: '198.51.101.0' }).allowed).toBe(true);

      // IPv6 CIDR boundaries
      expect(filter.evaluate({ ip: '2001:db8:abcd:0000::1' }).allowed).toBe(false);
      expect(filter.evaluate({ ip: '2001:db8:abcd:ffff:ffff:ffff:ffff:ffff' }).allowed).toBe(false);
      expect(filter.evaluate({ ip: '2001:db8:abce::1' }).allowed).toBe(true);
    });

    it('Rule G7 & G8: Admit returns 200, Deny returns 403 clean JSON without leaking server internals', () => {
      const filter = new GeoIPFilter({
        blockedIps: ['1.2.3.4'],
      });

      const allowed = filter.evaluate({ ip: '5.6.7.8' });
      expect(allowed.allowed).toBe(true);
      expect(allowed.statusCode).toBe(200);

      const denied = filter.evaluate({ ip: '1.2.3.4' });
      expect(denied.allowed).toBe(false);
      expect(denied.statusCode).toBe(403);
      expect(denied.error).toEqual({
        error: {
          message: 'Access from client network or location is restricted',
          type: 'forbidden',
          code: 403,
        },
      });
      // Ensure no internal info leaked
      const jsonStr = JSON.stringify(denied);
      expect(jsonStr).not.toContain('node');
      expect(jsonStr).not.toContain('linux');
      expect(jsonStr).not.toContain('windows');
      expect(jsonStr).not.toContain('stack');
    });

    it('Rule G9: Static in-memory lookup structures normalized', () => {
      const filter = new GeoIPFilter({
        blockedIps: [' 192.0.2.1 '],
        allowedCountries: ['us', 'ca '],
        blockedCidrs: ['10.50.0.0/16'],
      });

      expect(filter.evaluate({ ip: '192.0.2.1', country: 'US' }).allowed).toBe(false);
      expect(filter.evaluate({ ip: '8.8.8.8', country: 'CA' }).allowed).toBe(true);
    });

    it('Rule G10: Loopback and RFC 1918 / RFC 4193 private networks are permitted by default', () => {
      const filter = new GeoIPFilter({
        deniedCountries: ['XX'],
      });

      // Loopback
      expect(filter.evaluate({ ip: '127.0.0.1' }).allowed).toBe(true);
      expect(filter.evaluate({ ip: '::1' }).allowed).toBe(true);

      // RFC 1918 Private ranges
      expect(filter.evaluate({ ip: '10.1.2.3' }).allowed).toBe(true);
      expect(filter.evaluate({ ip: '172.16.5.6' }).allowed).toBe(true);
      expect(filter.evaluate({ ip: '192.168.1.100' }).allowed).toBe(true);

      // RFC 4193 IPv6 Unique Local Address
      expect(filter.evaluate({ ip: 'fd00::1' }).allowed).toBe(true);
    });

    it('Rule G11: IPv4-Mapped IPv6 addresses are normalized to standard IPv4', () => {
      const filter = new GeoIPFilter({
        blockedIps: ['192.0.2.33'],
        blockedCidrs: ['198.51.100.0/24'],
      });

      // IPv4-mapped IPv6 exact IP
      expect(filter.evaluate({ ip: '::ffff:192.0.2.33' }).allowed).toBe(false);
      // IPv4-mapped IPv6 within CIDR
      expect(filter.evaluate({ ip: '::ffff:198.51.100.44' }).allowed).toBe(false);
      // IPv4-mapped IPv6 unblocked
      expect(filter.evaluate({ ip: '::ffff:8.8.8.8' }).allowed).toBe(true);
    });

    it('Rule G14: Missing country header admits IP by default when IP is not blocked', () => {
      const filter = new GeoIPFilter({
        deniedCountries: ['CN', 'RU'],
      });

      // Country header missing (undefined or empty)
      expect(filter.evaluate({ ip: '93.184.216.34' }).allowed).toBe(true);
      expect(filter.evaluate({ ip: '93.184.216.34', country: '' }).allowed).toBe(true);
    });

    it('Rule G15: Dynamic temporary IP bans expire after TTL', async () => {
      const filter = new GeoIPFilter({});

      expect(filter.evaluate({ ip: '198.51.100.99' }).allowed).toBe(true);

      // Ban for 50ms
      filter.banIp('198.51.100.99', 50);
      expect(filter.evaluate({ ip: '198.51.100.99' }).allowed).toBe(false);

      // Wait 60ms for TTL expiry
      await new Promise((resolve) => setTimeout(resolve, 60));
      expect(filter.evaluate({ ip: '198.51.100.99' }).allowed).toBe(true);
    });

    it('Rule G16: Malformed IP strings fail closed in strict mode, ignored in non-strict mode', () => {
      const strictFilter = new GeoIPFilter({ strictMode: true });
      expect(strictFilter.evaluate({ ip: 'invalid-ip-address' }).allowed).toBe(false);
      expect(strictFilter.evaluate({ ip: '999.999.999.999' }).allowed).toBe(false);

      const nonStrictFilter = new GeoIPFilter({ strictMode: false });
      expect(nonStrictFilter.evaluate({ ip: 'invalid-ip-address' }).allowed).toBe(true);
    });

    it('Hono middleware integration works seamlessly', async () => {
      const { Hono } = await import('hono');
      const app = new Hono();
      const filter = new GeoIPFilter({
        blockedIps: ['203.0.113.50'],
      });

      app.use('*', filter.middleware());
      app.get('/test', (c) => c.json({ ok: true }));

      // Blocked request
      const blockedRes = await app.request('/test', {
        headers: { 'x-forwarded-for': '203.0.113.50' },
      });
      expect(blockedRes.status).toBe(403);
      const blockedBody = await blockedRes.json();
      expect(blockedBody.error.code).toBe(403);

      // Admitted request
      const admittedRes = await app.request('/test', {
        headers: { 'x-forwarded-for': '198.51.100.1' },
      });
      expect(admittedRes.status).toBe(200);
      const admittedBody = await admittedRes.json();
      expect(admittedBody.ok).toBe(true);
    });
  });
});
