import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { SSRFGuard, createFakeDnsResolver } from '../src/security/ssrf.js';

describe('SSRF Guard (Clean-Room Spec)', () => {
  beforeEach(() => {
    SSRFGuard.resetResolver();
  });

  afterEach(() => {
    SSRFGuard.resetResolver();
  });

  describe('Rule 1: URL Protocol Validation', () => {
    it('allows valid http and https URLs with safe public IP', async () => {
      const resolver = createFakeDnsResolver({
        'api.openai.com': ['93.184.216.34'],
        'api.anthropic.com': ['104.18.2.1'],
      });

      await expect(
        SSRFGuard.validateUrl('https://api.openai.com/v1/chat', false, resolver),
      ).resolves.not.toThrow();
      await expect(
        SSRFGuard.validateUrl('http://api.anthropic.com/v1/messages', false, resolver),
      ).resolves.not.toThrow();
    });

    it('rejects unsupported protocols (file, ftp, gopher, data)', async () => {
      const forbidden = [
        'file:///etc/passwd',
        'ftp://example.com/file',
        'gopher://example.com/',
        'data:text/plain;base64,SGVsbG8=',
      ];

      for (const url of forbidden) {
        await expect(SSRFGuard.validateUrl(url)).rejects.toThrow();
      }
    });
  });

  describe('Rule 2: URL Credentials', () => {
    it('rejects URLs containing embedded userinfo credentials', async () => {
      const resolver = createFakeDnsResolver({
        'api.example.com': ['93.184.216.34'],
      });

      await expect(
        SSRFGuard.validateUrl('https://user:pass@api.example.com/v1', false, resolver),
      ).rejects.toThrow(/credential/i);
      await expect(
        SSRFGuard.validateUrl('https://admin@api.example.com/v1', false, resolver),
      ).rejects.toThrow(/credential/i);
    });
  });

  describe('Rule 3 & 4: Unsafe IP Ranges & Resolution', () => {
    const unsafeIps = [
      // IPv4 loopback 127/8
      '127.0.0.1',
      '127.0.0.2',
      '127.255.255.255',
      // 0.0.0.0/8
      '0.0.0.0',
      '0.255.255.255',
      // Private 10/8
      '10.0.0.1',
      '10.255.255.255',
      // Private 172.16/12
      '172.16.0.1',
      '172.24.1.1',
      '172.31.255.255',
      // Private 192.168/16
      '192.168.0.1',
      '192.168.1.100',
      // Link-local & cloud metadata 169.254/16
      '169.254.169.254',
      '169.254.1.1',
      // Shared address space 100.64/10
      '100.64.0.1',
      '100.127.255.255',
      // Multicast 224/4
      '224.0.0.1',
      '239.255.255.255',
      // Reserved 240/4 & broadcast
      '240.0.0.1',
      '255.255.255.255',
      // IPv6 Loopback & Unspecified
      '::1',
      '::',
      // IPv6 Unique Local Address fc00::/7
      'fc00::1',
      'fd12:3456:789a::1',
      // IPv6 Link-Local fe80::/10
      'fe80::1',
      // IPv6 Multicast ff00::/8
      'ff02::1',
      // IPv4-mapped IPv6
      '::ffff:127.0.0.1',
      '::ffff:10.0.0.1',
      '::ffff:169.254.169.254',
      '::ffff:192.168.1.1',
    ];

    for (const ip of unsafeIps) {
      it(`rejects unsafe IP: ${ip}`, async () => {
        expect(SSRFGuard.isPrivateOrReservedIp(ip, false)).toBe(true);

        const resolver = createFakeDnsResolver({ 'target.local': [ip] });
        await expect(SSRFGuard.validateUrl(`http://${ip}/api`, false, resolver)).rejects.toThrow();
        await expect(
          SSRFGuard.validateUrl('http://target.local/api', false, resolver),
        ).rejects.toThrow();
      });
    }

    it('edge case: rejects hostname that resolves to one public and one private address', async () => {
      const resolver = createFakeDnsResolver({
        'mixed.example.com': ['93.184.216.34', '10.0.0.1'],
      });

      await expect(
        SSRFGuard.validateUrl('https://mixed.example.com/api', false, resolver),
      ).rejects.toThrow();
    });

    it('allows valid public IP and domain names', async () => {
      const publicIps = ['93.184.216.34', '8.8.8.8', '1.1.1.1', '2606:4700:4700::1111'];
      for (const ip of publicIps) {
        expect(SSRFGuard.isPrivateOrReservedIp(ip, false)).toBe(false);
      }
    });
  });

  describe('Rule 5: Numeric Forms Normalization', () => {
    it('edge case: normalises decimal integer IP representation', async () => {
      // 2130706433 is decimal representation of 127.0.0.1 (0x7F000001)
      await expect(SSRFGuard.validateUrl('http://2130706433/')).rejects.toThrow();
      // 16843009 is 1.1.1.1 (public) -> allowed
      const resolver = createFakeDnsResolver({ '1.1.1.1': ['1.1.1.1'] });
      await expect(
        SSRFGuard.validateUrl('http://16843009/', false, resolver),
      ).resolves.not.toThrow();
    });

    it('edge case: normalises hexadecimal IP representation', async () => {
      // 0x7f000001 is 127.0.0.1
      await expect(SSRFGuard.validateUrl('http://0x7f000001/')).rejects.toThrow();
      // 0x0a000001 is 10.0.0.1
      await expect(SSRFGuard.validateUrl('http://0x0a000001/')).rejects.toThrow();
    });

    it('edge case: normalises octal IP representation', async () => {
      // 0177.0.0.1 is 127.0.0.1
      await expect(SSRFGuard.validateUrl('http://0177.0.0.1/')).rejects.toThrow();
      // 012.0.0.1 is 10.0.0.1
      await expect(SSRFGuard.validateUrl('http://012.0.0.1/')).rejects.toThrow();
    });

    it('edge case: normalises short IP forms (e.g., 127.1)', async () => {
      // 127.1 expands to 127.0.0.1
      await expect(SSRFGuard.validateUrl('http://127.1/')).rejects.toThrow();
      // 10.1 expands to 10.0.0.1
      await expect(SSRFGuard.validateUrl('http://10.1/')).rejects.toThrow();
    });
  });

  describe('Rule 6: Fail Closed on DNS Issues', () => {
    it('edge case: DNS failure rejects', async () => {
      const resolver = async () => {
        throw new Error('ENOTFOUND domain does not exist');
      };
      await expect(
        SSRFGuard.validateUrl('https://nonexistent.invalid', false, resolver),
      ).rejects.toThrow();
    });

    it('edge case: DNS empty answer rejects', async () => {
      const resolver = async () => [];
      await expect(SSRFGuard.validateUrl('https://empty-dns.com', false, resolver)).rejects.toThrow(
        /empty/i,
      );
    });

    it('edge case: DNS timeout rejects', async () => {
      const resolver = async () => {
        throw new Error('ETIMEDOUT dns lookup timed out');
      };
      await expect(
        SSRFGuard.validateUrl('https://timeout-dns.com', false, resolver),
      ).rejects.toThrow();
    });
  });

  describe('Rule 7: Localhost Allow-List', () => {
    it('edge case: rejects localhost by default when allowLocalhost is false', async () => {
      const resolver = createFakeDnsResolver({ localhost: ['127.0.0.1'] });
      await expect(
        SSRFGuard.validateUrl('http://localhost:11434/v1', false, resolver),
      ).rejects.toThrow();
      await expect(
        SSRFGuard.validateUrl('http://127.0.0.1:11434/v1', false, resolver),
      ).rejects.toThrow();
    });

    it('edge case: permits localhost and 127.0.0.1 when allowLocalhost is explicitly true', async () => {
      const resolver = createFakeDnsResolver({ localhost: ['127.0.0.1'] });
      await expect(
        SSRFGuard.validateUrl('http://localhost:11434/v1', true, resolver),
      ).resolves.not.toThrow();
      await expect(
        SSRFGuard.validateUrl('http://127.0.0.1:11434/v1', true, resolver),
      ).resolves.not.toThrow();
    });

    it('does NOT permit other private ranges (10.x, 192.168.x) even when allowLocalhost is true', async () => {
      const resolver = createFakeDnsResolver({ 'internal.lan': ['192.168.1.50'] });
      await expect(
        SSRFGuard.validateUrl('http://192.168.1.50:8000', true, resolver),
      ).rejects.toThrow();
      await expect(
        SSRFGuard.validateUrl('http://internal.lan:8000', true, resolver),
      ).rejects.toThrow();
    });
  });

  describe('Rule 8: Redirect Safety Validation', () => {
    it('edge case: rejects redirect from https to http', () => {
      expect(() =>
        SSRFGuard.validateRedirect('https://example.com/orig', 'http://example.com/target'),
      ).toThrow(/https-to-http/i);
    });

    it('edge case: validates redirect hop count (max 3 hops)', () => {
      expect(() => SSRFGuard.checkHopCount(1)).not.toThrow();
      expect(() => SSRFGuard.checkHopCount(3)).not.toThrow();
      expect(() => SSRFGuard.checkHopCount(4)).toThrow(/maximum.*hops/i);
    });

    it('edge case: validates redirect target address is not private', async () => {
      const resolver = createFakeDnsResolver({
        'evil.com': ['93.184.216.34'],
        'internal.corp': ['10.0.0.5'],
      });

      // Target URL validation checks the redirect destination
      await expect(
        SSRFGuard.validateUrl('http://internal.corp/secret', false, resolver),
      ).rejects.toThrow();
    });
  });
});
