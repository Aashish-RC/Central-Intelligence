export interface GeoIpConfig {
  blockedCountries?: string[]; // e.g. ['XX', 'T1']
  blockedIps?: string[];       // exact IP strings e.g. ['198.51.100.1']
  blockedCidrs?: string[];     // e.g. ['203.0.113.0/24']
}

export interface ClientGeoInfo {
  ip: string;
  country?: string;
  isBlocked: boolean;
  blockReason?: 'country_blocked' | 'ip_blacklisted' | 'cidr_blacklisted';
}

export class GeoIpFilter {
  private blockedCountries: Set<string>;
  private blockedIps: Set<string>;
  private blockedCidrs: string[];

  constructor(config: GeoIpConfig = {}) {
    this.blockedCountries = new Set((config.blockedCountries || []).map((c) => c.toUpperCase()));
    this.blockedIps = new Set(config.blockedIps || []);
    this.blockedCidrs = config.blockedCidrs || [];
  }

  extractClientIp(headers: Headers | Record<string, string | undefined>): string {
    const get = (name: string): string | undefined => {
      if (headers instanceof Headers) {
        return headers.get(name) || undefined;
      }
      return headers[name] || headers[name.toLowerCase()];
    };

    const forwarded = get('x-forwarded-for');
    if (forwarded) {
      return forwarded.split(',')[0].trim();
    }
    return get('cf-connecting-ip') || get('x-real-ip') || '127.0.0.1';
  }

  extractCountry(headers: Headers | Record<string, string | undefined>): string | undefined {
    const get = (name: string): string | undefined => {
      if (headers instanceof Headers) {
        return headers.get(name) || undefined;
      }
      return headers[name] || headers[name.toLowerCase()];
    };
    return get('cf-ipcountry') || get('x-country-code') || undefined;
  }

  evaluate(headers: Headers | Record<string, string | undefined>): ClientGeoInfo {
    const ip = this.extractClientIp(headers);
    const country = this.extractCountry(headers)?.toUpperCase();

    // 1. Check IP direct blacklist
    if (this.blockedIps.has(ip)) {
      return { ip, country, isBlocked: true, blockReason: 'ip_blacklisted' };
    }

    // 2. Check CIDRs
    for (const cidr of this.blockedCidrs) {
      if (this.ipInCidr(ip, cidr)) {
        return { ip, country, isBlocked: true, blockReason: 'cidr_blacklisted' };
      }
    }

    // 3. Check Country code
    if (country && this.blockedCountries.has(country)) {
      return { ip, country, isBlocked: true, blockReason: 'country_blocked' };
    }

    return { ip, country, isBlocked: false };
  }

  private ipInCidr(ip: string, cidr: string): boolean {
    const [range, bits = '32'] = cidr.split('/');
    const mask = ~(2 ** (32 - parseInt(bits, 10)) - 1);
    const ipToLong = (dot: string) =>
      dot.split('.').reduce((acc, oct) => ((acc << 8) + parseInt(oct, 10)) >>> 0, 0);

    try {
      return (ipToLong(ip) & mask) === (ipToLong(range) & mask);
    } catch {
      return false;
    }
  }

  addBlockedIp(ip: string): void {
    this.blockedIps.add(ip);
  }

  addBlockedCountry(country: string): void {
    this.blockedCountries.add(country.toUpperCase());
  }
}
