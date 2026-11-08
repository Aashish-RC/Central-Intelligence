import { describe, expect, it } from 'vitest';
import { ByokResolver } from '../src/security/byok.js';

describe('Feature 29: Bring Your Own Key (BYOK) Dynamic Header Routing', () => {
  const resolver = new ByokResolver();

  it('resolves direct provider specific key header', () => {
    const headers = {
      'x-openai-api-key': 'sk-user-custom-openai-token-12345',
    };
    const resolved = resolver.resolveKey(headers, 'openai');
    expect(resolved).not.toBeNull();
    expect(resolved?.apiKey).toBe('sk-user-custom-openai-token-12345');
    expect(resolved?.provider).toBe('openai');
    expect(resolved?.sourceHeader).toBe('x-openai-api-key');
  });

  it('resolves generic x-provider-api-key header', () => {
    const headers = {
      'x-provider-api-key': 'sk-anthropic-byok-test-999',
    };
    const resolved = resolver.resolveKey(headers, 'anthropic');
    expect(resolved?.apiKey).toBe('sk-anthropic-byok-test-999');
    expect(resolved?.provider).toBe('anthropic');
  });

  it('sanitizes and masks BYOK headers in telemetry logs', () => {
    const headers = {
      'content-type': 'application/json',
      'x-openai-api-key': 'sk-sensitive-secret-token-payload-xyz',
    };
    const sanitized = resolver.sanitizeHeaders(headers);
    expect(sanitized['content-type']).toBe('application/json');
    expect(sanitized['x-openai-api-key']).toContain('...');
    expect(sanitized['x-openai-api-key']).not.toBe(headers['x-openai-api-key']);
  });
});
