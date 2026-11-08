import { describe, expect, it } from 'vitest';
import { GcpOAuth2Client } from '../src/providers/gcp-auth.js';

describe('Feature 36: GCP Workload Identity / OAuth2 Token Refresher', () => {
  it('returns valid mock token when no private key configured', async () => {
    const client = new GcpOAuth2Client();
    const token = await client.getAccessToken();

    expect(token).toMatch(/^ya29\.mock_gcp_token_/);
  });

  it('reuses cached token within expiration window', async () => {
    const client = new GcpOAuth2Client();
    const token1 = await client.getAccessToken();
    const token2 = await client.getAccessToken();

    expect(token1).toBe(token2);
  });
});
