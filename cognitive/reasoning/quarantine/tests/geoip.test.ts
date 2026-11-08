import { describe, it, expect } from 'vitest';
import { GeoIpFilter } from '../geoip.js';

describe('Feature 38: GeoIP Country & Abuse IP Blacklisting', () => {
  it('allows benign traffic from authorized IP and country', () => {
    const filter = new GeoIpFilter({
      blockedCountries: ['KP', 'SY'],
      blockedIps: ['198.51.100.42'],
      blockedCidrs: ['203.0.113.0/24'],
    });

    const info = filter.evaluate({
      'x-forwarded-for': '1.2.3.4',
      'cf-ipcountry': 'US',
    });

    expect(info.isBlocked).toBe(false);
  });

  it('blocks request originating from blacklisted exact IP', () => {
    const filter = new GeoIpFilter({
      blockedIps: ['198.51.100.42'],
    });

    const info = filter.evaluate({
      'x-forwarded-for': '198.51.100.42',
    });

    expect(info.isBlocked).toBe(true);
    expect(info.blockReason).toBe('ip_blacklisted');
  });

  it('blocks request originating from sanctioned country code', () => {
    const filter = new GeoIpFilter({
      blockedCountries: ['KP'],
    });

    const info = filter.evaluate({
      'x-forwarded-for': '1.1.1.1',
      'cf-ipcountry': 'kp',
    });

    expect(info.isBlocked).toBe(true);
    expect(info.blockReason).toBe('country_blocked');
  });
});
