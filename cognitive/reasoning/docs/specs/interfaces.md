# Module Interface Contracts

### `src/caching/cache.ts`

```typescript
import { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';

export interface ResponseCacheOptions {
  enabled?: boolean;
  defaultTtlSeconds?: number;
}

export class ResponseCache {
  public enabled: boolean;
  constructor(options?: ResponseCacheOptions);
  public static canonicalStringify(obj: any): string;
  public static computeKey(
    req: ChatCompletionRequest,
    scope?: { actor?: string; tenantId?: string }
  ): string;
  public get(key: string): ChatCompletionResponse | undefined;
  public set(
    key: string,
    response: ChatCompletionResponse,
    ttlSeconds?: number,
    scope?: { actor?: string; tenantId?: string }
  ): void;
  public invalidate(key: string): void;
  public clear(): void;
  public size(): number;
}
```

---

### `src/resilience/ratelimit.ts`

```typescript
export interface RateLimitResult {
  allowed: boolean;
  limit: number;
  remaining: number;
  resetSeconds: number;
}

export class SlidingWindowRateLimiter {
  constructor(defaultLimit?: number, windowDurationSeconds?: number);
  public check(key: string, customLimit?: number): RateLimitResult;
  public reset(key: string): void;
}
```

---

### `src/security/ssrf.ts`

```typescript
export interface DnsLookupRecord {
  address: string;
  family?: number;
}

export type DnsResolver = (hostname: string) => Promise<DnsLookupRecord[]>;

export const defaultDnsResolver: DnsResolver;

export function createFakeDnsResolver(customRecords?: Record<string, string[]>): DnsResolver;

export class SSRFGuard {
  constructor(resolver?: DnsResolver);
  public static setResolver(resolver: DnsResolver): void;
  public static resetResolver(): void;
  public static getResolver(): DnsResolver;
  public validateUrl(urlString: string, allowLocalhost?: boolean): Promise<void>;
  public static validateUrl(
    urlString: string,
    allowLocalhost?: boolean,
    customResolver?: DnsResolver
  ): Promise<void>;
  public static isPrivateOrReservedIp(ip: string, allowLocalhost: boolean): boolean;
}
```

---

### `src/security/pii.ts`

```typescript
import { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';

export type MaskCategory = 'EMAIL' | 'PHONE' | 'SSN' | 'CREDIT_CARD' | 'IP_ADDRESS';
export type PIIEntityType = MaskCategory;

export interface MaskEntityMatch {
  type: MaskCategory;
  value: string;
  start: number;
  end: number;
}
export type PIIEntityMatch = MaskEntityMatch;

export interface MaskEngineOptions {
  enabledTypes?: MaskCategory[];
  vaultTtlSeconds?: number;
}
export type PIIEngineOptions = MaskEngineOptions;

export class PIIMaskingEngine {
  constructor(options?: MaskEngineOptions);
  public detect(text: string): MaskEntityMatch[];
  public maskText(text: string): string;
  public maskRequest(request: ChatCompletionRequest): ChatCompletionRequest;
  public unmaskText(text: string): string;
  public unmaskResponse(response: ChatCompletionResponse): ChatCompletionResponse;
  public createStreamDetokenizer(): (chunk: string) => string;
}
```

---

### `src/security/vault.ts`

```typescript
export interface VaultTokenRecord {
  token: string;
  originalValue: string;
  entityType: string;
  createdAt: number;
  expiresAt: number;
}

export class TokenVault {
  constructor(ttlSeconds?: number);
  public static getInstance(): TokenVault;
  public store(originalValue: string, entityType: string, ttlSeconds?: number): string;
  public get(token: string): VaultTokenRecord | undefined;
  public evict(token: string): void;
  public clear(): void;
  public size(): number;
}
```
