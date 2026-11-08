import { URL } from 'node:url';
import dns from 'node:dns/promises';

export interface DnsLookupRecord {
  address: string;
  family?: number;
}

export type DnsResolver = (hostname: string) => Promise<DnsLookupRecord[]>;

export const defaultDnsResolver: DnsResolver = async (hostname: string) => {
  const records = await dns.lookup(hostname, { all: true });
  return records.map((r) => ({ address: r.address, family: r.family }));
};

export function createFakeDnsResolver(customRecords?: Record<string, string[]>): DnsResolver {
  return async (hostname: string) => {
    if (customRecords && customRecords[hostname]) {
      return customRecords[hostname].map((ip) => ({ address: ip, family: 4 }));
    }
    if (hostname.endsWith('.invalid') || hostname.includes('does-not-exist')) {
      throw new Error(`getaddrinfo ENOTFOUND ${hostname}`);
    }
    if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(hostname) || hostname.includes(':')) {
      return [{ address: hostname, family: hostname.includes(':') ? 6 : 4 }];
    }
    if (hostname === 'localhost') {
      return [{ address: '127.0.0.1', family: 4 }];
    }
    return [{ address: '93.184.216.34', family: 4 }];
  };
}

/**
 * SSRF Guard (Zero-Trust Outbound Address Validator)
 * 
 * Protects against server-side request forgery by validating destination URLs,
 * resolving DNS, blocking private/internal/cloud metadata IP ranges, and failing closed.
 * 
 * Residual Risk Notice (DNS Rebinding):
 * Standard Web-standard `fetch` executes an internal DNS resolution during connection establishment.
 * Without custom socket-level IP dialing (such as via an egress proxy or specialized undici Dispatcher),
 * a theoretical TOCTOU window exists between validateUrl() and fetch(). For high-security environments,
 * configure an egress firewall or dedicated forward proxy.
 */
export class SSRFGuard {
  private static globalResolver: DnsResolver = defaultDnsResolver;
  private instanceResolver?: DnsResolver;

  constructor(resolver?: DnsResolver) {
    if (resolver) {
      this.instanceResolver = resolver;
    }
  }

  public static setResolver(resolver: DnsResolver): void {
    this.globalResolver = resolver;
  }

  public static resetResolver(): void {
    this.globalResolver = defaultDnsResolver;
  }

  public static getResolver(): DnsResolver {
    return this.globalResolver;
  }

  public async validateUrl(urlString: string, allowLocalhost: boolean = false): Promise<void> {
    return SSRFGuard.validateUrl(urlString, allowLocalhost, this.instanceResolver);
  }

  public static async validateUrl(
    urlString: string,
    allowLocalhost: boolean = false,
    customResolver?: DnsResolver
  ): Promise<void> {
    let parsed: URL;
    try {
      parsed = new URL(urlString);
    } catch {
      throw new Error(`SSRF Guard: Invalid target URL "${urlString}"`);
    }

    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      throw new Error(`SSRF Guard: Unsupported protocol "${parsed.protocol}"`);
    }

    const hostname = parsed.hostname;

    // Check direct loopback strings
    if (!allowLocalhost && (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1')) {
      throw new Error(`SSRF Guard: Access to loopback/localhost is forbidden`);
    }

    // Resolve DNS to verify destination IP (Fail-Closed)
    try {
      const resolver = customResolver || this.globalResolver || defaultDnsResolver;
      const records = await resolver(hostname);
      if (!records || records.length === 0) {
        throw new Error(`SSRF Guard: DNS resolution returned no addresses for "${hostname}" (fail-closed)`);
      }

      for (const rec of records) {
        if (this.isPrivateOrReservedIp(rec.address, allowLocalhost)) {
          throw new Error(
            `SSRF Guard: Resolved destination ${hostname} -> ${rec.address} is a private or reserved network address`
          );
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.message.startsWith('SSRF Guard:')) {
        throw err;
      }
      // Fail closed: If DNS resolution fails, block request immediately
      const errMsg = err instanceof Error ? err.message : String(err);
      throw new Error(`SSRF Guard: DNS resolution failed for "${hostname}" (fail-closed): ${errMsg}`);
    }
  }

  public static isPrivateOrReservedIp(ip: string, allowLocalhost: boolean): boolean {
    const cleanIp = ip.trim().toLowerCase();

    // Check IPv4-mapped IPv6 (e.g. ::ffff:192.168.1.1 or ::ffff:10.0.0.1)
    if (cleanIp.startsWith('::ffff:')) {
      const mappedIpv4 = cleanIp.slice(7);
      if (mappedIpv4.includes('.')) {
        return this.isPrivateOrReservedIp(mappedIpv4, allowLocalhost);
      }
    }

    // IPv6 checks
    if (cleanIp === '::1') {
      return !allowLocalhost;
    }
    if (cleanIp === '::') {
      return true;
    }
    // fe80::/10 (Link-local IPv6)
    if (/^fe[89ab][0-9a-f]:/i.test(cleanIp) || cleanIp.startsWith('fe80:')) {
      return true;
    }
    // fc00::/7 (Unique local IPv6)
    if (cleanIp.startsWith('fc') || cleanIp.startsWith('fd')) {
      return true;
    }
    // ff00::/8 (Multicast IPv6)
    if (cleanIp.startsWith('ff')) {
      return true;
    }

    // IPv4 checks
    const parts = cleanIp.split('.').map((p) => parseInt(p, 10));
    if (parts.length === 4 && parts.every((p) => !isNaN(p) && p >= 0 && p <= 255)) {
      // 127.0.0.0/8 (Loopback)
      if (parts[0] === 127) {
        return !allowLocalhost;
      }
      // 10.0.0.0/8 (Private)
      if (parts[0] === 10) return true;
      // 100.64.0.0/10 (Carrier-Grade NAT / Shared Address Space RFC 6598)
      if (parts[0] === 100 && parts[1] >= 64 && parts[1] <= 127) return true;
      // 172.16.0.0/12 (Private RFC 1918)
      if (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) return true;
      // 192.168.0.0/16 (Private RFC 1918)
      if (parts[0] === 192 && parts[1] === 168) return true;
      // 169.254.0.0/16 (Link-local & Cloud Metadata 169.254.169.254)
      if (parts[0] === 169 && parts[1] === 254) return true;
      // 192.0.0.0/24 (IETF Protocol Assignments)
      if (parts[0] === 192 && parts[1] === 0 && parts[2] === 0) return true;
      // 192.0.2.0/24 (TEST-NET-1)
      if (parts[0] === 192 && parts[1] === 0 && parts[2] === 2) return true;
      // 198.18.0.0/15 (Benchmarking RFC 2544)
      if (parts[0] === 198 && (parts[1] === 18 || parts[1] === 19)) return true;
      // 198.51.100.0/24 (TEST-NET-2)
      if (parts[0] === 198 && parts[1] === 51 && parts[2] === 100) return true;
      // 203.0.113.0/24 (TEST-NET-3)
      if (parts[0] === 203 && parts[1] === 0 && parts[2] === 113) return true;
      // 224.0.0.0/4 (Multicast RFC 5771)
      if (parts[0] >= 224 && parts[0] <= 239) return true;
      // 240.0.0.0/4 (Reserved RFC 1112)
      if (parts[0] >= 240) return true;
      // 0.0.0.0/8 (Broadcast/source)
      if (parts[0] === 0) return true;
    }

    return false;
  }
}
