import { randomBytes } from 'node:crypto';

export interface VaultTokenRecord {
  token: string;
  originalValue: string;
  entityType: string;
  createdAt: number;
  expiresAt: number;
}

export interface TokenVaultOptions {
  clock?: () => number;
  maxEntries?: number;
}

export class TokenVault {
  private static instance?: TokenVault;
  private defaultTtlSeconds: number;
  private maxEntries: number;
  private clock: () => number;
  private tokenStore: Map<string, VaultTokenRecord>;
  private reverseLookup: Map<string, string>;

  constructor(ttlSeconds = 3600, options: TokenVaultOptions = {}) {
    this.defaultTtlSeconds = ttlSeconds;
    this.maxEntries = options.maxEntries ?? 50000;
    this.clock = options.clock ?? (() => Date.now());
    this.tokenStore = new Map<string, VaultTokenRecord>();
    this.reverseLookup = new Map<string, string>();
  }

  public static getInstance(): TokenVault {
    if (!TokenVault.instance) {
      TokenVault.instance = new TokenVault();
    }
    return TokenVault.instance;
  }

  /**
   * Stores a sensitive value and returns an opaque surrogate token.
   * If the identical value and entityType has already been stored and is unexpired,
   * returns the existing surrogate token (reverse mapping).
   */
  public store(originalValue: string, entityType: string, ttlSeconds?: number): string {
    const reverseKey = `${entityType}:${originalValue}`;
    const existingToken = this.reverseLookup.get(reverseKey);

    if (existingToken) {
      const existingRecord = this.get(existingToken);
      if (existingRecord) {
        return existingToken;
      }
      // Expired: reverse mapping will be replaced below
    }

    const now = this.clock();
    const effectiveTtl = (ttlSeconds ?? this.defaultTtlSeconds) * 1000;
    const expiresAt = now + effectiveTtl;

    // Purge expired tokens if approaching capacity
    if (this.tokenStore.size >= this.maxEntries) {
      for (const [t, rec] of this.tokenStore.entries()) {
        if (now >= rec.expiresAt) {
          this.evict(t);
        }
      }
    }

    // Evict least-recently-used entry under memory pressure
    if (this.tokenStore.size >= this.maxEntries) {
      const oldestToken = this.tokenStore.keys().next().value;
      if (oldestToken !== undefined) {
        this.evict(oldestToken);
      }
    }

    // Generate non-colliding bracketed surrogate token
    const uniqueId = randomBytes(6).toString('hex');
    const token = `[TOKEN_${entityType.toUpperCase()}_${uniqueId}]`;

    const record: VaultTokenRecord = {
      token,
      originalValue,
      entityType,
      createdAt: now,
      expiresAt,
    };

    this.tokenStore.set(token, record);
    this.reverseLookup.set(reverseKey, token);

    return token;
  }

  public get(token: string): VaultTokenRecord | undefined {
    const record = this.tokenStore.get(token);
    if (!record) return undefined;

    const now = this.clock();
    if (now >= record.expiresAt) {
      this.evict(token);
      return undefined;
    }

    // Refresh LRU order
    this.tokenStore.delete(token);
    this.tokenStore.set(token, record);

    return { ...record };
  }

  public evict(token: string): void {
    const record = this.tokenStore.get(token);
    if (record) {
      this.tokenStore.delete(token);
      const reverseKey = `${record.entityType}:${record.originalValue}`;
      if (this.reverseLookup.get(reverseKey) === token) {
        this.reverseLookup.delete(reverseKey);
      }
    }
  }

  public clear(): void {
    this.tokenStore.clear();
    this.reverseLookup.clear();
  }

  public size(): number {
    const now = this.clock();
    let count = 0;
    for (const [token, record] of this.tokenStore.entries()) {
      if (now < record.expiresAt) {
        count++;
      } else {
        this.evict(token);
      }
    }
    return count;
  }
}
