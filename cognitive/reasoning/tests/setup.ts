import { afterEach, beforeEach } from 'vitest';
import { SSRFGuard, createFakeDnsResolver } from '../src/security/ssrf.js';

// Hermetic testing: Set fake DNS resolver with public IPs for known provider hosts for every test
const KNOWN_PROVIDER_HOSTS: Record<string, string[]> = {
  'api.openai.com': ['93.184.216.34'],
  'api.anthropic.com': ['104.18.2.1'],
  'generativelanguage.googleapis.com': ['142.250.180.10'],
  'oauth2.googleapis.com': ['142.250.180.10'],
  'target-a.com': ['93.184.216.34'],
  'target-b.com': ['93.184.216.34'],
};

beforeEach(() => {
  SSRFGuard.setResolver(createFakeDnsResolver(KNOWN_PROVIDER_HOSTS));
});

afterEach(() => {
  SSRFGuard.resetResolver();
});
