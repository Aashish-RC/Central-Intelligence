import crypto from 'node:crypto';

export interface VaultTokenRecord {
  token: string;
  originalValue: string;
  entityType: string;
  createdAt: number;
  expiresAt: number;
}

export class TokenVault {
  private static instance: TokenVault;
  private tokenMap: Map<string, VaultTokenRecord> = new Map();
  private valueToTokenMap: Map<string, string> = new Map();
  private defaultTtlSeconds: number = 3600;

  constructor(ttlSeconds: number = 3600) {
    this.defaultTtlSeconds = ttlSeconds;
  }

  public static getInstance(): TokenVault {
    if (!TokenVault.instance) {
      TokenVault.instance = new TokenVault();
    }
    return TokenVault.instance;
  }

  /**
   * Generates a unique surrogate placeholder and stores mapping.
   * Format: [TOKEN_<TYPE>_<random_entropy>]
   */
  public store(originalValue: string, entityType: string, ttlSeconds?: number): string {
    const key = `${entityType}:${originalValue}`;
    const existingToken = this.valueToTokenMap.get(key);
    const now = Date.now();

    if (existingToken) {
      const record = this.tokenMap.get(existingToken);
      if (record && record.expiresAt > now) {
        return existingToken;
      }
    }

    const entropy = crypto.randomBytes(5).toString('hex');
    const token = `[TOKEN_${entityType.toUpperCase()}_${entropy}]`;
    const expiresAt = now + (ttlSeconds ?? this.defaultTtlSeconds) * 1000;

    const record: VaultTokenRecord = {
      token,
      originalValue,
      entityType,
      createdAt: now,
      expiresAt
    };

    this.tokenMap.set(token, record);
    this.valueToTokenMap.set(key, token);

    return token;
  }

  public get(token: string): VaultTokenRecord | undefined {
    const record = this.tokenMap.get(token);
    if (!record) return undefined;
    if (Date.now() > record.expiresAt) {
      this.evict(token);
      return undefined;
    }
    return record;
  }

  public evict(token: string): void {
    const record = this.tokenMap.get(token);
    if (record) {
      this.valueToTokenMap.delete(`${record.entityType}:${record.originalValue}`);
      this.tokenMap.delete(token);
    }
  }

  public clear(): void {
    this.tokenMap.clear();
    this.valueToTokenMap.clear();
  }

  public size(): number {
    return this.tokenMap.size;
  }
}
