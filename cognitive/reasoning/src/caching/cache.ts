import { createHash } from 'node:crypto';
import type { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';

export interface ResponseCacheOptions {
  enabled?: boolean;
  defaultTtlSeconds?: number;
  maxEntries?: number;
  clock?: () => number;
}

interface CacheEntry {
  response: ChatCompletionResponse;
  expiresAt: number;
}

export class ResponseCache {
  public enabled: boolean;
  private defaultTtlSeconds: number;
  private maxEntries: number;
  private clock: () => number;
  private store: Map<string, CacheEntry>;

  constructor(options: ResponseCacheOptions = {}) {
    this.enabled = options.enabled ?? false;
    this.defaultTtlSeconds = options.defaultTtlSeconds ?? 300; // 5 minutes default
    this.maxEntries = options.maxEntries ?? 1000;
    this.clock = options.clock ?? (() => Date.now());
    this.store = new Map<string, CacheEntry>();
  }

  /**
   * Recursively canonicalizes an object by sorting object keys alphabetically,
   * keeping arrays in original order, and omitting undefined values.
   */
  public static canonicalStringify(obj: any): string {
    if (obj === null || obj === undefined) {
      return 'null';
    }
    if (typeof obj !== 'object') {
      return JSON.stringify(obj);
    }
    if (Array.isArray(obj)) {
      return '[' + obj.map((item) => ResponseCache.canonicalStringify(item)).join(',') + ']';
    }

    const keys = Object.keys(obj).sort();
    const parts: string[] = [];
    for (const key of keys) {
      const val = obj[key];
      if (val !== undefined) {
        parts.push(JSON.stringify(key) + ':' + ResponseCache.canonicalStringify(val));
      }
    }
    return '{' + parts.join(',') + '}';
  }

  /**
   * Computes a SHA-256 hex digest for a request, capturing all fields that influence
   * output generation and scoping to tenantId and actorId.
   */
  public static computeKey(
    req: ChatCompletionRequest,
    scope?: { actor?: string; tenantId?: string },
  ): string {
    const keyPayload = {
      model: req.model,
      messages: req.messages,
      temperature: req.temperature,
      top_p: req.top_p,
      max_tokens: req.max_tokens,
      max_completion_tokens: req.max_completion_tokens,
      stop: req.stop,
      seed: req.seed,
      n: req.n,
      presence_penalty: req.presence_penalty,
      frequency_penalty: req.frequency_penalty,
      tools: req.tools,
      tool_choice: req.tool_choice,
      response_format: req.response_format,
      user: req.user,
      scope: {
        tenantId: scope?.tenantId || null,
        actor: scope?.actor || null,
      },
    };

    const canonicalJson = ResponseCache.canonicalStringify(keyPayload);
    return createHash('sha256').update(canonicalJson).digest('hex');
  }

  public get(key: string): ChatCompletionResponse | undefined {
    if (!this.enabled) return undefined;

    const entry = this.store.get(key);
    if (!entry) return undefined;

    const now = this.clock();
    if (now >= entry.expiresAt) {
      this.store.delete(key);
      return undefined;
    }

    // Refresh LRU ordering: delete and re-insert
    this.store.delete(key);
    this.store.set(key, entry);

    // Return a clone to prevent external mutations
    return JSON.parse(JSON.stringify(entry.response));
  }

  public set(
    key: string,
    response: ChatCompletionResponse,
    ttlSeconds?: number,
    _scope?: { actor?: string; tenantId?: string },
  ): void {
    if (!this.enabled) return;

    const ttl = (ttlSeconds ?? this.defaultTtlSeconds) * 1000;
    const now = this.clock();
    const expiresAt = now + ttl;

    // Purge expired entries lazily
    for (const [k, v] of this.store.entries()) {
      if (now >= v.expiresAt) {
        this.store.delete(k);
      }
    }

    // Evict least recently used if capacity exceeded
    if (this.store.has(key)) {
      this.store.delete(key);
    } else if (this.store.size >= this.maxEntries) {
      const oldestKey = this.store.keys().next().value;
      if (oldestKey !== undefined) {
        this.store.delete(oldestKey);
      }
    }

    this.store.set(key, {
      response: JSON.parse(JSON.stringify(response)),
      expiresAt,
    });
  }

  public invalidate(key: string): void {
    this.store.delete(key);
  }

  public clear(): void {
    this.store.clear();
  }

  public size(): number {
    const now = this.clock();
    let count = 0;
    for (const [key, entry] of this.store.entries()) {
      if (now < entry.expiresAt) {
        count++;
      } else {
        this.store.delete(key);
      }
    }
    return count;
  }
}
