import { createHash } from 'node:crypto';
import { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';

interface CacheEntry {
  response: ChatCompletionResponse;
  expiresAt: number;
  createdAt: number;
  scope?: { actor?: string; tenantId?: string };
}

export interface ResponseCacheOptions {
  enabled?: boolean;
  defaultTtlSeconds?: number;
}

export class ResponseCache {
  private store = new Map<string, CacheEntry>();
  private defaultTtlMs: number;
  public enabled: boolean;

  constructor(options: ResponseCacheOptions = {}) {
    this.enabled = options.enabled ?? false; // Default: disabled / off in R1
    this.defaultTtlMs = (options.defaultTtlSeconds ?? 300) * 1000;
  }

  /**
   * Generates a deterministic canonical JSON string with sorted keys
   */
  public static canonicalStringify(obj: any): string {
    if (obj === null || typeof obj !== 'object') {
      return JSON.stringify(obj);
    }
    if (Array.isArray(obj)) {
      return '[' + obj.map((item) => this.canonicalStringify(item)).join(',') + ']';
    }
    const keys = Object.keys(obj).sort();
    const parts = keys.map((key) => {
      const val = obj[key];
      if (val === undefined) return null;
      return JSON.stringify(key) + ':' + this.canonicalStringify(val);
    }).filter(Boolean);
    return '{' + parts.join(',') + '}';
  }

  /**
   * Computes a collision-resistant SHA-256 cache key including all fields
   * that can influence output, scoped by actor and tenant.
   */
  public static computeKey(
    req: ChatCompletionRequest,
    scope?: { actor?: string; tenantId?: string }
  ): string {
    const canonicalPayload = {
      model: req.model,
      messages: req.messages,
      temperature: req.temperature,
      top_p: req.top_p,
      n: req.n,
      stop: req.stop,
      max_tokens: req.max_tokens,
      max_completion_tokens: req.max_completion_tokens,
      presence_penalty: req.presence_penalty,
      frequency_penalty: req.frequency_penalty,
      user: req.user,
      tools: req.tools,
      tool_choice: req.tool_choice,
      seed: req.seed,
      response_format: req.response_format,
      // Scope fields
      _scope_actor: scope?.actor || '',
      _scope_tenant: scope?.tenantId || ''
    };

    const canonicalJson = this.canonicalStringify(canonicalPayload);
    const hash = createHash('sha256').update(canonicalJson).digest('hex');
    return `resp_cache:${req.model}:${hash}`;
  }

  public get(key: string): ChatCompletionResponse | undefined {
    if (!this.enabled) return undefined;

    const entry = this.store.get(key);
    if (!entry) return undefined;
    if (Date.now() > entry.expiresAt) {
      this.store.delete(key);
      return undefined;
    }
    return entry.response;
  }

  public set(
    key: string,
    response: ChatCompletionResponse,
    ttlSeconds?: number,
    scope?: { actor?: string; tenantId?: string }
  ): void {
    if (!this.enabled) return;

    const ttl = (ttlSeconds !== undefined ? ttlSeconds * 1000 : this.defaultTtlMs);
    this.store.set(key, {
      response,
      expiresAt: Date.now() + ttl,
      createdAt: Date.now(),
      scope
    });
  }

  public invalidate(key: string): void {
    this.store.delete(key);
  }

  public clear(): void {
    this.store.clear();
  }

  public size(): number {
    return this.store.size;
  }
}
