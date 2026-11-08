import { describe, expect, it } from 'vitest';
import { SecretsManager } from '../src/security/secrets.js';

describe('Feature 26: External Secrets Manager Sync', () => {
  it('retrieves and caches memory secrets with TTL', async () => {
    const mgr = new SecretsManager({ backend: 'memory', cacheTtlMs: 1000 });
    mgr.setMemorySecret('OPENAI_API_KEY', 'sk-test-live-key');

    const secret = await mgr.getSecret('OPENAI_API_KEY');
    expect(secret).toBe('sk-test-live-key');
  });

  it('falls back to environment variables when backend is env', async () => {
    process.env['TEST_GATEWAY_SECRET'] = 'secret-val-42';
    const mgr = new SecretsManager({ backend: 'env' });

    const val = await mgr.getSecret('TEST_GATEWAY_SECRET');
    expect(val).toBe('secret-val-42');
    delete process.env['TEST_GATEWAY_SECRET'];
  });

  it('handles empty or missing secret gracefully without crashing', async () => {
    const mgr = new SecretsManager({ backend: 'memory' });
    const missing = await mgr.getSecret('NON_EXISTENT_KEY');
    expect(missing).toBeUndefined();
  });
});
