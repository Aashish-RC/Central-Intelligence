import dns from 'node:dns/promises';

export interface DnsLookupRecord {
  address: string;
  family?: number;
}

export type DnsResolver = (hostname: string) => Promise<DnsLookupRecord[]>;

export const defaultDnsResolver: DnsResolver = async (
  hostname: string,
): Promise<DnsLookupRecord[]> => {
  const records = await dns.lookup(hostname, { all: true });
  return records.map((r) => ({ address: r.address, family: r.family }));
};

export function createFakeDnsResolver(customRecords: Record<string, string[]> = {}): DnsResolver {
  return async (hostname: string): Promise<DnsLookupRecord[]> => {
    const lower = hostname.toLowerCase();
    const ips = customRecords[lower];
    if (!ips) {
      // If hostname is already an IP, return it directly
      return [{ address: hostname, family: hostname.includes(':') ? 6 : 4 }];
    }
    return ips.map((ip) => ({ address: ip, family: ip.includes(':') ? 6 : 4 }));
  };
}

export class SSRFGuard {
  private static globalResolver: DnsResolver = defaultDnsResolver;
  private instanceResolver?: DnsResolver;

  constructor(resolver?: DnsResolver) {
    this.instanceResolver = resolver;
  }

  public static setResolver(resolver: DnsResolver): void {
    SSRFGuard.globalResolver = resolver;
  }

  public static resetResolver(): void {
    SSRFGuard.globalResolver = defaultDnsResolver;
  }

  public static getResolver(): DnsResolver {
    return SSRFGuard.globalResolver;
  }

  public async validateUrl(urlString: string, allowLocalhost = false): Promise<void> {
    const resolver = this.instanceResolver || SSRFGuard.globalResolver;
    await SSRFGuard.validateUrl(urlString, allowLocalhost, resolver);
  }

  /**
   * Validates target URL against SSRF protection rules.
   */
  public static async validateUrl(
    urlString: string,
    allowLocalhost = false,
    customResolver?: DnsResolver,
  ): Promise<void> {
    let parsed: URL;
    try {
      parsed = new URL(urlString);
    } catch {
      throw new Error(`Invalid URL: ${urlString}`);
    }

    // Rule 1: Protocol must be http: or https:
    const protocol = parsed.protocol.toLowerCase();
    if (protocol !== 'http:' && protocol !== 'https:') {
      throw new Error(
        `SSRF Guard: Prohibited URL protocol '${protocol}'. Only http and https are allowed.`,
      );
    }

    // Rule 2: Reject URLs with embedded credentials (userinfo)
    if (parsed.username || parsed.password) {
      throw new Error(
        'SSRF Guard: URLs containing embedded user credentials are strictly forbidden.',
      );
    }

    let rawHostname = parsed.hostname;
    // Strip IPv6 square brackets e.g. [::1] -> ::1
    if (rawHostname.startsWith('[') && rawHostname.endsWith(']')) {
      rawHostname = rawHostname.slice(1, -1);
    }

    // Rule 5: Normalize numeric IPv4 representations (decimal, hex, octal, short forms)
    const normalizedIp = SSRFGuard.normalizeNumericIpv4(rawHostname);
    const targetHost = normalizedIp || rawHostname;

    // Check if targetHost is already an IP address
    const isDirectIp = SSRFGuard.isValidIpAddress(targetHost);

    if (isDirectIp) {
      if (SSRFGuard.isPrivateOrReservedIp(targetHost, allowLocalhost)) {
        throw new Error(
          `SSRF Guard: Connection to private or reserved IP address '${targetHost}' is blocked.`,
        );
      }
      return;
    }

    // Check for explicit localhost hostname bypass
    if (targetHost.toLowerCase() === 'localhost') {
      if (!allowLocalhost) {
        throw new Error(`SSRF Guard: Localhost domain '${targetHost}' is blocked.`);
      }
    }

    // Rule 3: Resolve hostname and verify EVERY returned address (Rule 6: Fail closed)
    const resolver = customResolver || SSRFGuard.globalResolver;
    let records: DnsLookupRecord[];
    try {
      records = await resolver(targetHost);
    } catch (err: any) {
      throw new Error(`SSRF Guard: DNS lookup failed for host '${targetHost}': ${err.message}`);
    }

    if (!records || records.length === 0) {
      throw new Error(
        `SSRF Guard: DNS lookup returned empty address list for host '${targetHost}'.`,
      );
    }

    for (const record of records) {
      const address = record.address;
      const normalizedAddress = SSRFGuard.normalizeNumericIpv4(address) || address;
      if (SSRFGuard.isPrivateOrReservedIp(normalizedAddress, allowLocalhost)) {
        throw new Error(
          `SSRF Guard: Host '${targetHost}' resolved to private or reserved address '${address}'. Access denied.`,
        );
      }
    }
  }

  /**
   * Rule 4: Evaluates whether an IP address belongs to loopback, private, link-local,
   * multicast, or reserved ranges.
   */
  public static isPrivateOrReservedIp(ip: string, allowLocalhost: boolean): boolean {
    let cleanIp = ip.trim();
    if (cleanIp.startsWith('[') && cleanIp.endsWith(']')) {
      cleanIp = cleanIp.slice(1, -1);
    }

    // Handle IPv4-mapped IPv6 (::ffff:a.b.c.d)
    const ipv4MappedMatch = cleanIp.match(/^::ffff:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$/i);
    if (ipv4MappedMatch) {
      cleanIp = ipv4MappedMatch[1];
    }

    // Check IPv4
    if (cleanIp.includes('.')) {
      const parts = cleanIp.split('.').map((p) => Number.parseInt(p, 10));
      if (parts.length === 4 && parts.every((p) => !isNaN(p) && p >= 0 && p <= 255)) {
        const [o1, o2] = parts;

        // Loopback 127.0.0.0/8
        if (o1 === 127) {
          return !allowLocalhost;
        }

        // 0.0.0.0/8
        if (o1 === 0) {
          return true;
        }

        // Private 10.0.0.0/8
        if (o1 === 10) {
          return true;
        }

        // Shared address space 100.64.0.0/10 (100.64.0.0 - 100.127.255.255)
        if (o1 === 100 && o2 >= 64 && o2 <= 127) {
          return true;
        }

        // Link-local 169.254.0.0/16
        if (o1 === 169 && o2 === 254) {
          return true;
        }

        // Private 172.16.0.0/12 (172.16.0.0 - 172.31.255.255)
        if (o1 === 172 && o2 >= 16 && o2 <= 31) {
          return true;
        }

        // Private 192.168.0.0/16
        if (o1 === 192 && o2 === 168) {
          return true;
        }

        // Multicast 224.0.0.0/4 (224.0.0.0 - 239.255.255.255)
        if (o1 >= 224 && o1 <= 239) {
          return true;
        }

        // Reserved / Future Use 240.0.0.0/4 and Broadcast 255.255.255.255
        if (o1 >= 240) {
          return true;
        }

        return false;
      }
    }

    // Check IPv6
    if (cleanIp.includes(':')) {
      const lower = cleanIp.toLowerCase();

      // Loopback ::1
      if (lower === '::1' || lower === '0:0:0:0:0:0:0:1') {
        return !allowLocalhost;
      }

      // Unspecified ::
      if (lower === '::' || lower === '0:0:0:0:0:0:0:0') {
        return true;
      }

      // Unique local address fc00::/7 (fc00:: to fdff::)
      if (lower.startsWith('fc') || lower.startsWith('fd')) {
        return true;
      }

      // Link-local fe80::/10 (fe80:: to febf::)
      if (/^fe[89ab]/i.test(lower)) {
        return true;
      }

      // Multicast ff00::/8
      if (lower.startsWith('ff')) {
        return true;
      }

      return false;
    }

    return true;
  }

  /**
   * Rule 5: Normalizes numeric IPv4 representations (e.g. 2130706433, 0x7f000001, 0177.0.0.1, 127.1)
   * into canonical dotted-decimal string.
   */
  public static normalizeNumericIpv4(host: string): string | null {
    const trimmed = host.trim();

    // Check for single integer (decimal, hex, octal) e.g. 2130706433, 0x7f000001
    if (/^(0x[0-9a-fA-F]+|\d+)$/.test(trimmed)) {
      try {
        let val: number;
        if (trimmed.startsWith('0x') || trimmed.startsWith('0X')) {
          val = Number.parseInt(trimmed, 16);
        } else if (
          trimmed.startsWith('0') &&
          trimmed.length > 1 &&
          !trimmed.includes('8') &&
          !trimmed.includes('9')
        ) {
          val = Number.parseInt(trimmed, 8);
        } else {
          val = Number.parseInt(trimmed, 10);
        }

        if (!isNaN(val) && val >= 0 && val <= 0xffffffff) {
          const o1 = (val >>> 24) & 0xff;
          const o2 = (val >>> 16) & 0xff;
          const o3 = (val >>> 8) & 0xff;
          const o4 = val & 0xff;
          return `${o1}.${o2}.${o3}.${o4}`;
        }
      } catch {
        return null;
      }
    }

    // Check dotted parts (1 to 4 parts) where parts can be hex, octal, or decimal
    const parts = trimmed.split('.');
    if (parts.length >= 2 && parts.length <= 4) {
      const parsedParts: number[] = [];
      for (const p of parts) {
        if (/^0x[0-9a-fA-F]+$/i.test(p)) {
          parsedParts.push(Number.parseInt(p, 16));
        } else if (/^0[0-7]+$/.test(p)) {
          parsedParts.push(Number.parseInt(p, 8));
        } else if (/^\d+$/.test(p)) {
          parsedParts.push(Number.parseInt(p, 10));
        } else {
          return null;
        }
      }

      if (parsedParts.length === 2) {
        // a.b: a is 8-bit, b is 24-bit (e.g. 127.1 -> 127.0.0.1)
        const [a, b] = parsedParts;
        if (a <= 255 && b <= 0xffffff) {
          const o1 = a;
          const o2 = (b >>> 16) & 0xff;
          const o3 = (b >>> 8) & 0xff;
          const o4 = b & 0xff;
          return `${o1}.${o2}.${o3}.${o4}`;
        }
      } else if (parsedParts.length === 3) {
        // a.b.c: a is 8-bit, b is 8-bit, c is 16-bit
        const [a, b, c] = parsedParts;
        if (a <= 255 && b <= 255 && c <= 0xffff) {
          const o1 = a;
          const o2 = b;
          const o3 = (c >>> 8) & 0xff;
          const o4 = c & 0xff;
          return `${o1}.${o2}.${o3}.${o4}`;
        }
      } else if (parsedParts.length === 4) {
        // a.b.c.d: all 8-bit
        if (parsedParts.every((p) => p <= 255)) {
          return parsedParts.join('.');
        }
      }
    }

    return null;
  }

  /**
   * Rule 8: Validates redirect targets. Disallows https -> http downgrade.
   */
  public static validateRedirect(fromUrl: string, toUrl: string): void {
    const from = new URL(fromUrl);
    const to = new URL(toUrl);

    if (from.protocol.toLowerCase() === 'https:' && to.protocol.toLowerCase() === 'http:') {
      throw new Error('SSRF Guard: Prohibited https-to-http redirect downgrade.');
    }
  }

  /**
   * Rule 8: Validates maximum allowed redirect hops (3 max).
   */
  public static checkHopCount(hopCount: number): void {
    if (hopCount > 3) {
      throw new Error('SSRF Guard: Maximum redirect hops (3) exceeded.');
    }
  }

  private static isValidIpAddress(host: string): boolean {
    if (host.includes('.')) {
      const parts = host.split('.');
      if (
        parts.length === 4 &&
        parts.every((p) => /^\d+$/.test(p) && Number.parseInt(p, 10) <= 255)
      ) {
        return true;
      }
    }
    if (host.includes(':')) {
      return true;
    }
    return false;
  }
}
