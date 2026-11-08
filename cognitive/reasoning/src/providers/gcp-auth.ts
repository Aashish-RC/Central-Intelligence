import { createSign } from 'node:crypto';

export interface ServiceAccountKey {
  client_email: string;
  private_key: string;
  project_id?: string;
  token_uri?: string;
}

export interface CachedToken {
  accessToken: string;
  expiresAt: number;
}

export class GcpOAuth2Client {
  private serviceAccount?: ServiceAccountKey;
  private cachedToken?: CachedToken;
  private tokenUri: string;

  constructor(serviceAccount?: ServiceAccountKey) {
    this.serviceAccount = serviceAccount;
    this.tokenUri = serviceAccount?.token_uri || 'https://oauth2.googleapis.com/token';
  }

  /**
   * Generates a signed JWT grant for GCP OAuth2 using pure node:crypto
   */
  createSignedJwt(scopes: string[] = ['https://www.googleapis.com/auth/cloud-platform']): string {
    if (!this.serviceAccount) {
      throw new Error('GCP Service Account credentials not provided');
    }

    const now = Math.floor(Date.now() / 1000);
    const header = {
      alg: 'RS256',
      typ: 'JWT',
    };

    const payload = {
      iss: this.serviceAccount.client_email,
      sub: this.serviceAccount.client_email,
      aud: this.tokenUri,
      iat: now,
      exp: now + 3600, // 1 hour
      scope: scopes.join(' '),
    };

    const base64UrlEncode = (str: string) =>
      Buffer.from(str).toString('base64').replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');

    const encodedHeader = base64UrlEncode(JSON.stringify(header));
    const encodedPayload = base64UrlEncode(JSON.stringify(payload));
    const signingInput = `${encodedHeader}.${encodedPayload}`;

    const sign = createSign('RSA-SHA256');
    sign.update(signingInput);
    sign.end();

    const signature = sign
      .sign(this.serviceAccount.private_key, 'base64')
      .replace(/=/g, '')
      .replace(/\+/g, '-')
      .replace(/\//g, '_');

    return `${signingInput}.${signature}`;
  }

  /**
   * Gets or refreshes GCP Access Token with internal TTL caching
   */
  async getAccessToken(): Promise<string> {
    const now = Date.now();
    // Return cached token if valid for at least 5 more minutes
    if (this.cachedToken && this.cachedToken.expiresAt > now + 300_000) {
      return this.cachedToken.accessToken;
    }

    // If running in development/mock or no private key, return synthetic token
    if (!this.serviceAccount || !this.serviceAccount.private_key.includes('BEGIN PRIVATE KEY')) {
      const mockToken = `ya29.mock_gcp_token_${now}`;
      this.cachedToken = {
        accessToken: mockToken,
        expiresAt: now + 3600_000,
      };
      return mockToken;
    }

    const assertion = this.createSignedJwt();
    const params = new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion,
    });

    const res = await fetch(this.tokenUri, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params.toString(),
    });

    if (!res.ok) {
      throw new Error(`GCP OAuth2 token request failed: ${res.status} ${await res.text()}`);
    }

    const data = (await res.json()) as any;
    const token = data.access_token;
    const expiresIn = data.expires_in || 3600;

    this.cachedToken = {
      accessToken: token,
      expiresAt: now + expiresIn * 1000,
    };

    return token;
  }
}
