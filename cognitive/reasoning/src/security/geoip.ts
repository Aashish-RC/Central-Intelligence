import type { MiddlewareHandler } from 'hono';

export interface GeoIPConfig {
  allowedCountries?: string[];
  deniedCountries?: string[];
  blockedIps?: string[];
  blockedCidrs?: string[];
  strictMode?: boolean;
}

export interface GeoIPEvaluationResult {
  allowed: boolean;
  statusCode: number;
  reason?: string;
  error?: {
    error: {
      message: string;
      type: string;
      code: number;
    };
  };
}

interface ParsedCidrV4 {
  version: 4;
  network: bigint;
  mask: bigint;
}

interface ParsedCidrV6 {
  version: 6;
  network: bigint;
  mask: bigint;
}

type ParsedCidr = ParsedCidrV4 | ParsedCidrV6;

interface DynamicBan {
  ip: string;
  expiresAt: number;
}

/**
 * GeoIP and Abuse IP Filtering Subsystem.
 * Enforces geographic residency constraints and blocks malicious/abusive client IPs.
 */
export class GeoIPFilter {
  private allowedCountries: Set<string> | null = null;
  private deniedCountries: Set<string> | null = null;
  private blockedIps: Set<string> = new Set();
  private parsedCidrs: ParsedCidr[] = [];
  private strictMode: boolean;
  private dynamicBans: Map<string, DynamicBan> = new Map();

  constructor(config: GeoIPConfig = {}) {
    this.strictMode = config.strictMode ?? false;

    if (config.allowedCountries && config.allowedCountries.length > 0) {
      this.allowedCountries = new Set(
        config.allowedCountries.map((c) => c.trim().toUpperCase()).filter(Boolean),
      );
    }

    if (config.deniedCountries && config.deniedCountries.length > 0) {
      this.deniedCountries = new Set(
        config.deniedCountries.map((c) => c.trim().toUpperCase()).filter(Boolean),
      );
    }

    if (config.blockedIps) {
      for (const rawIp of config.blockedIps) {
        const normalized = this.normalizeIp(rawIp);
        if (normalized) {
          this.blockedIps.add(normalized);
        }
      }
    }

    if (config.blockedCidrs) {
      for (const rawCidr of config.blockedCidrs) {
        const parsed = this.parseCidr(rawCidr.trim());
        if (parsed) {
          this.parsedCidrs.push(parsed);
        }
      }
    }
  }

  public isEnabled(): boolean {
    return process.env.FEATURE_GEOIP === 'true';
  }

  /**
   * Normalize IP string and handle IPv4-mapped IPv6 notation.
   */
  public normalizeIp(rawIp: string): string | null {
    if (!rawIp) return null;
    let ip = rawIp.trim();

    // Remove IPv6 zone index if present (e.g. fe80::1%eth0)
    const zoneIndex = ip.indexOf('%');
    if (zoneIndex !== -1) {
      ip = ip.substring(0, zoneIndex);
    }

    // Check for IPv4-mapped IPv6: ::ffff:192.0.2.1
    const ipv4MappedMatch = /^::ffff:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$/i.exec(ip);
    if (ipv4MappedMatch) {
      ip = ipv4MappedMatch[1];
    }

    // Validate IPv4
    if (this.isValidIpv4(ip)) {
      return ip;
    }

    // Validate IPv6
    if (this.isValidIpv6(ip)) {
      return this.canonicalizeIpv6(ip);
    }

    return null;
  }

  public banIp(ip: string, ttlMs: number): void {
    const normalized = this.normalizeIp(ip);
    if (!normalized) return;
    this.dynamicBans.set(normalized, {
      ip: normalized,
      expiresAt: Date.now() + ttlMs,
    });
  }

  public evaluate(input: { ip: string; country?: string }): GeoIPEvaluationResult {
    // Feature flag OFF by default: bypasses filtering
    if (!this.isEnabled()) {
      return { allowed: true, statusCode: 200 };
    }

    const rawIp = input.ip;
    const normalizedIp = this.normalizeIp(rawIp);

    // Malformed IP handling
    if (!normalizedIp) {
      if (this.strictMode) {
        return this.deny('Malformed or unresolvable client IP address in strict mode');
      }
      // Non-strict: ignore unverifiable IP header and admit
      return { allowed: true, statusCode: 200 };
    }

    // Check dynamic bans with TTL
    const dynamicBan = this.dynamicBans.get(normalizedIp);
    if (dynamicBan) {
      if (Date.now() < dynamicBan.expiresAt) {
        return this.deny('Client IP address is temporarily banned');
      } else {
        this.dynamicBans.delete(normalizedIp);
      }
    }

    // Check loopback / RFC 1918 / RFC 4193 private addresses:
    // They are permitted unless specifically blocked in blockedIps or blockedCidrs
    const isPrivateOrLoopback = this.isPrivateOrLoopback(normalizedIp);

    // Explicit IP blocklist
    if (this.blockedIps.has(normalizedIp)) {
      return this.deny('Client IP address is explicitly blocked');
    }

    // CIDR subnet blocklist
    for (const cidr of this.parsedCidrs) {
      if (this.matchesCidr(normalizedIp, cidr)) {
        return this.deny('Client IP belongs to a blocked subnet');
      }
    }

    // If private or loopback and not explicitly blocked by IP or CIDR, admit immediately
    if (isPrivateOrLoopback) {
      return { allowed: true, statusCode: 200 };
    }

    // Geographical filtering
    const country = input.country ? input.country.trim().toUpperCase() : null;

    if (country) {
      // Check denylist
      if (this.deniedCountries && this.deniedCountries.has(country)) {
        return this.deny(`Traffic from country '${country}' is denied by policy`);
      }

      // Check allowlist (if active)
      if (this.allowedCountries && !this.allowedCountries.has(country)) {
        return this.deny(`Traffic from country '${country}' is not on the allowed country list`);
      }
    }

    return { allowed: true, statusCode: 200 };
  }

  public evaluateFromHeaders(headers: Headers): GeoIPEvaluationResult {
    const ip = this.extractClientIp(headers);
    const country = this.extractCountry(headers);
    return this.evaluate({ ip, country });
  }

  public middleware(): MiddlewareHandler {
    return async (c, next) => {
      if (!this.isEnabled()) {
        return await next();
      }

      const headers = c.req.raw.headers;
      const result = this.evaluateFromHeaders(headers);

      if (!result.allowed) {
        return c.json(result.error, 403);
      }

      await next();
    };
  }

  private extractClientIp(headers: Headers): string {
    const xff = headers.get('x-forwarded-for');
    if (xff) {
      // First IP in list is client IP
      const firstIp = xff.split(',')[0].trim();
      if (firstIp) return firstIp;
    }

    const realIp = headers.get('x-real-ip');
    if (realIp) return realIp.trim();

    const cfConnectingIp = headers.get('cf-connecting-ip');
    if (cfConnectingIp) return cfConnectingIp.trim();

    return '127.0.0.1';
  }

  private extractCountry(headers: Headers): string | undefined {
    return (
      headers.get('cf-ipcountry') ||
      headers.get('x-country-code') ||
      headers.get('x-geoip-country') ||
      undefined
    );
  }

  private deny(reason: string): GeoIPEvaluationResult {
    return {
      allowed: false,
      statusCode: 403,
      reason,
      error: {
        error: {
          message: 'Access from client network or location is restricted',
          type: 'forbidden',
          code: 403,
        },
      },
    };
  }

  private isValidIpv4(ip: string): boolean {
    const parts = ip.split('.');
    if (parts.length !== 4) return false;
    for (const part of parts) {
      if (!/^\d{1,3}$/.test(part)) return false;
      const num = Number(part);
      if (num < 0 || num > 255) return false;
      if (part.length > 1 && part.startsWith('0')) return false; // No leading zeroes
    }
    return true;
  }

  private isValidIpv6(ip: string): boolean {
    if (!ip || ip.length > 39) return false;
    if (ip === '::') return true;
    const doubleColons = ip.split('::');
    if (doubleColons.length > 2) return false;

    if (doubleColons.length === 2) {
      const left = doubleColons[0] ? doubleColons[0].split(':') : [];
      const right = doubleColons[1] ? doubleColons[1].split(':') : [];
      if (left.length + right.length > 7) return false;
      for (const part of [...left, ...right]) {
        if (!/^[0-9a-fA-F]{1,4}$/.test(part)) return false;
      }
      return true;
    }

    const parts = ip.split(':');
    if (parts.length !== 8) return false;
    for (const part of parts) {
      if (!/^[0-9a-fA-F]{1,4}$/.test(part)) return false;
    }
    return true;
  }

  private ipv4ToBigInt(ip: string): bigint {
    const octets = ip.split('.').map(Number);
    return (
      (BigInt(octets[0]) << 24n) |
      (BigInt(octets[1]) << 16n) |
      (BigInt(octets[2]) << 8n) |
      BigInt(octets[3])
    );
  }

  private ipv6ToBigInt(ip: string): bigint {
    // Expand compressed IPv6
    let full = ip;
    if (full === '::') {
      full = '0:0:0:0:0:0:0:0';
    } else if (full.includes('::')) {
      const halves = full.split('::');
      const leftParts = halves[0] ? halves[0].split(':') : [];
      const rightParts = halves[1] ? halves[1].split(':') : [];
      const missingCount = 8 - (leftParts.length + rightParts.length);
      const middle = new Array(missingCount).fill('0');
      full = [...leftParts, ...middle, ...rightParts].join(':');
    }

    const groups = full.split(':').map((g) => Number.parseInt(g || '0', 16));
    let result = 0n;
    for (let i = 0; i < 8; i++) {
      result = (result << 16n) | BigInt(groups[i] || 0);
    }
    return result;
  }

  private canonicalizeIpv6(ip: string): string {
    const num = this.ipv6ToBigInt(ip);
    const groups: string[] = [];
    for (let i = 7; i >= 0; i--) {
      const grp = Number((num >> BigInt(i * 16)) & 0xffffn);
      groups.push(grp.toString(16));
    }
    return groups.join(':');
  }

  private parseCidr(cidr: string): ParsedCidr | null {
    const slashIdx = cidr.indexOf('/');
    if (slashIdx === -1) return null;

    const ipPart = cidr.substring(0, slashIdx).trim();
    const prefixLen = Number(cidr.substring(slashIdx + 1).trim());
    if (isNaN(prefixLen)) return null;

    const normalizedIp = this.normalizeIp(ipPart);
    if (!normalizedIp) return null;

    if (this.isValidIpv4(normalizedIp)) {
      if (prefixLen < 0 || prefixLen > 32) return null;
      const mask = prefixLen === 0 ? 0n : (0xffffffffn << BigInt(32 - prefixLen)) & 0xffffffffn;
      const network = this.ipv4ToBigInt(normalizedIp) & mask;
      return { version: 4, network, mask };
    } else {
      if (prefixLen < 0 || prefixLen > 128) return null;
      const allOnes = (1n << 128n) - 1n;
      const mask = prefixLen === 0 ? 0n : allOnes ^ ((1n << BigInt(128 - prefixLen)) - 1n);
      const network = this.ipv6ToBigInt(normalizedIp) & mask;
      return { version: 6, network, mask };
    }
  }

  private matchesCidr(normalizedIp: string, cidr: ParsedCidr): boolean {
    if (cidr.version === 4) {
      if (!this.isValidIpv4(normalizedIp)) return false;
      const ipBig = this.ipv4ToBigInt(normalizedIp);
      return (ipBig & cidr.mask) === cidr.network;
    } else {
      if (this.isValidIpv4(normalizedIp)) return false;
      const ipBig = this.ipv6ToBigInt(normalizedIp);
      return (ipBig & cidr.mask) === cidr.network;
    }
  }

  private isPrivateOrLoopback(normalizedIp: string): boolean {
    if (this.isValidIpv4(normalizedIp)) {
      const num = this.ipv4ToBigInt(normalizedIp);
      // 127.0.0.0/8
      if ((num & 0xff000000n) === 0x7f000000n) return true;
      // 10.0.0.0/8
      if ((num & 0xff000000n) === 0x0a000000n) return true;
      // 172.16.0.0/12
      if ((num & 0xfff00000n) === 0xac100000n) return true;
      // 192.168.0.0/16
      if ((num & 0xffff0000n) === 0xc0a80000n) return true;
      // 0.0.0.0/8
      if ((num & 0xff000000n) === 0x00000000n) return true;
    } else {
      const num = this.ipv6ToBigInt(normalizedIp);
      // ::1 (Loopback)
      if (num === 1n) return true;
      // fc00::/7 (Unique Local Address, RFC 4193)
      if (num >> 121n === 0x7en) return true;
      // fe80::/10 (Link-Local)
      if (num >> 118n === 0x3e8n) return true;
    }
    return false;
  }
}
