// Belongs to Layer 0 vault. Temporarily hosted in the gateway. To be moved out.

export interface SecretConfig {
  backend: 'env' | 'vault' | 'infisical' | 'memory';
  vaultUrl?: string;
  vaultToken?: string;
  infisicalWorkspaceId?: string;
  infisicalToken?: string;
  cacheTtlMs?: number;
}

export interface CachedSecret {
  value: string;
  expiresAt: number;
}

export class SecretsManager {
  private config: SecretConfig;
  private cache: Map<string, CachedSecret> = new Map();
  private memorySecrets: Map<string, string> = new Map();

  constructor(config: Partial<SecretConfig> = {}) {
    this.config = {
      backend: config.backend || 'env',
      cacheTtlMs: config.cacheTtlMs ?? 300_000, // 5 minutes default
      ...config,
    };
  }

  setMemorySecret(key: string, value: string): void {
    this.memorySecrets.set(key, value);
    this.cache.set(key, {
      value,
      expiresAt: Date.now() + this.config.cacheTtlMs!,
    });
  }

  async getSecret(key: string): Promise<string | undefined> {
    const now = Date.now();
    const cached = this.cache.get(key);
    if (cached && cached.expiresAt > now) {
      return cached.value;
    }

    let value: string | undefined;

    switch (this.config.backend) {
      case 'memory':
        value = this.memorySecrets.get(key);
        break;

      case 'env':
        value = process.env[key] || this.memorySecrets.get(key);
        break;

      case 'vault':
        value = await this.fetchVaultSecret(key);
        break;

      case 'infisical':
        value = await this.fetchInfisicalSecret(key);
        break;

      default:
        value = process.env[key];
    }

    if (value) {
      this.cache.set(key, {
        value,
        expiresAt: now + (this.config.cacheTtlMs || 300_000),
      });
    }

    return value;
  }

  private async fetchVaultSecret(key: string): Promise<string | undefined> {
    // If vault credentials are not set, fallback to memory/env
    if (!this.config.vaultUrl || !this.config.vaultToken) {
      return this.memorySecrets.get(key) || process.env[key];
    }
    try {
      const res = await fetch(`${this.config.vaultUrl}/v1/secret/data/${key}`, {
        headers: {
          'X-Vault-Token': this.config.vaultToken,
        },
      });
      if (!res.ok) return undefined;
      const data = (await res.json()) as any;
      return data?.data?.data?.value;
    } catch {
      return undefined;
    }
  }

  private async fetchInfisicalSecret(key: string): Promise<string | undefined> {
    if (!this.config.infisicalToken) {
      return this.memorySecrets.get(key) || process.env[key];
    }
    try {
      const res = await fetch(`https://app.infisical.com/api/v3/secrets/raw/${key}`, {
        headers: {
          Authorization: `Bearer ${this.config.infisicalToken}`,
        },
      });
      if (!res.ok) return undefined;
      const data = (await res.json()) as any;
      return data?.secret?.secretValue;
    } catch {
      return undefined;
    }
  }

  clearCache(): void {
    this.cache.clear();
  }
}
