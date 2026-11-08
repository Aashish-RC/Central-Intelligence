import { beforeEach, describe, expect, it } from 'vitest';
import { ResponseCache } from '../src/caching/cache.js';
import type { ChatCompletionRequest, ChatCompletionResponse } from '../src/types/chat.js';

describe('Exact Response Cache (Clean-Room Spec)', () => {
  let mockTime = 1000000;
  const mockClock = () => mockTime;

  const baseRequest: ChatCompletionRequest = {
    model: 'gpt-4o',
    messages: [
      { role: 'system', content: 'You are an assistant' },
      { role: 'user', content: 'Hello world' },
    ],
    temperature: 0.7,
    top_p: 1.0,
    stop: ['\n'],
    seed: 42,
    tool_choice: 'auto',
    response_format: { type: 'text' },
  };

  const sampleResponse: ChatCompletionResponse = {
    id: 'chatcmpl-test-123',
    object: 'chat.completion',
    created: 1000000,
    model: 'gpt-4o',
    choices: [
      {
        index: 0,
        message: { role: 'assistant', content: 'Hello there!' },
        finish_reason: 'stop',
      },
    ],
    usage: {
      prompt_tokens: 10,
      completion_tokens: 5,
      total_tokens: 15,
    },
  };

  beforeEach(() => {
    mockTime = 1000000;
  });

  it('is disabled by default and enabled per config', () => {
    const defaultCache = new ResponseCache();
    expect(defaultCache.enabled).toBe(false);

    const enabledCache = new ResponseCache({ enabled: true });
    expect(enabledCache.enabled).toBe(true);
  });

  describe('Key Computation & Canonicalization', () => {
    it('produces identical SHA-256 keys for identical requests regardless of object key order', () => {
      const req1: ChatCompletionRequest = {
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'Hi' }],
        temperature: 0.5,
      };
      const req2: ChatCompletionRequest = {
        temperature: 0.5,
        messages: [{ role: 'user', content: 'Hi' }],
        model: 'gpt-4o',
      };

      const key1 = ResponseCache.computeKey(req1);
      const key2 = ResponseCache.computeKey(req2);
      expect(key1).toBe(key2);
      expect(key1).toMatch(/^[a-f0-9]{64}$/);
    });

    it('edge case: produces different keys for "Aa" and "BB" message content', () => {
      const reqAa: ChatCompletionRequest = {
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'Aa' }],
      };
      const reqBb: ChatCompletionRequest = {
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'BB' }],
      };

      expect(ResponseCache.computeKey(reqAa)).not.toBe(ResponseCache.computeKey(reqBb));
    });

    it('edge case: changing stop parameter alters cache key', () => {
      const key1 = ResponseCache.computeKey({ ...baseRequest, stop: ['END'] });
      const key2 = ResponseCache.computeKey({ ...baseRequest, stop: ['STOP'] });
      expect(key1).not.toBe(key2);
    });

    it('edge case: changing seed alters cache key', () => {
      const key1 = ResponseCache.computeKey({ ...baseRequest, seed: 100 });
      const key2 = ResponseCache.computeKey({ ...baseRequest, seed: 200 });
      expect(key1).not.toBe(key2);
    });

    it('edge case: changing tool_choice alters cache key', () => {
      const key1 = ResponseCache.computeKey({ ...baseRequest, tool_choice: 'none' });
      const key2 = ResponseCache.computeKey({ ...baseRequest, tool_choice: 'auto' });
      expect(key1).not.toBe(key2);
    });

    it('edge case: changing response_format alters cache key', () => {
      const key1 = ResponseCache.computeKey({ ...baseRequest, response_format: { type: 'text' } });
      const key2 = ResponseCache.computeKey({
        ...baseRequest,
        response_format: { type: 'json_object' },
      });
      expect(key1).not.toBe(key2);
    });

    it('edge case: cross-tenant isolation guarantees different tenants never share a key', () => {
      const tenantA = ResponseCache.computeKey(baseRequest, {
        tenantId: 'tenant-alpha',
        actor: 'user-1',
      });
      const tenantB = ResponseCache.computeKey(baseRequest, {
        tenantId: 'tenant-beta',
        actor: 'user-1',
      });
      expect(tenantA).not.toBe(tenantB);
    });

    it('cross-actor isolation ensures different actors in same tenant get distinct keys', () => {
      const actor1 = ResponseCache.computeKey(baseRequest, {
        tenantId: 'tenant-alpha',
        actor: 'user-1',
      });
      const actor2 = ResponseCache.computeKey(baseRequest, {
        tenantId: 'tenant-alpha',
        actor: 'user-2',
      });
      expect(actor1).not.toBe(actor2);
    });

    it('canonicalStringify recursively sorts object keys, preserves arrays, and omits undefined', () => {
      const complex = {
        z: 1,
        a: {
          beta: [3, 2, 1],
          alpha: 'hello',
          skipped: undefined,
        },
      };
      const str = ResponseCache.canonicalStringify(complex);
      expect(str).toBe('{"a":{"alpha":"hello","beta":[3,2,1]},"z":1}');
    });
  });

  describe('Storage, TTL Expiry & Eviction', () => {
    it('stores and retrieves a successful response', () => {
      const cache = new ResponseCache({ enabled: true });
      const key = ResponseCache.computeKey(baseRequest);

      expect(cache.get(key)).toBeUndefined();
      cache.set(key, sampleResponse);

      const retrieved = cache.get(key);
      expect(retrieved).toBeDefined();
      expect(retrieved?.id).toBe(sampleResponse.id);
      expect(cache.size()).toBe(1);
    });

    it('edge case: TTL expiry purges expired entries lazily on access', () => {
      const cache = new ResponseCache({
        enabled: true,
        defaultTtlSeconds: 300,
        clock: mockClock,
      } as any);

      const key = ResponseCache.computeKey(baseRequest);
      cache.set(key, sampleResponse, 300); // 300s TTL

      // At T+299 seconds -> still valid
      mockTime += 299 * 1000;
      expect(cache.get(key)).toBeDefined();

      // At T+301 seconds -> expired and evicted lazily
      mockTime += 2 * 1000;
      expect(cache.get(key)).toBeUndefined();
      expect(cache.size()).toBe(0);
    });

    it('edge case: LRU eviction purges the least recently accessed item when capacity is reached', () => {
      const cache = new ResponseCache({
        enabled: true,
        maxEntries: 2,
      } as any);

      const reqA: ChatCompletionRequest = {
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'A' }],
      };
      const reqB: ChatCompletionRequest = {
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'B' }],
      };
      const reqC: ChatCompletionRequest = {
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'C' }],
      };

      const keyA = ResponseCache.computeKey(reqA);
      const keyB = ResponseCache.computeKey(reqB);
      const keyC = ResponseCache.computeKey(reqC);

      cache.set(keyA, { ...sampleResponse, id: 'resp-A' });
      cache.set(keyB, { ...sampleResponse, id: 'resp-B' });

      // Access keyA to make it recently used
      expect(cache.get(keyA)?.id).toBe('resp-A');

      // Now insert keyC -> keyB should be evicted as least recently used
      cache.set(keyC, { ...sampleResponse, id: 'resp-C' });

      expect(cache.get(keyA)).toBeDefined();
      expect(cache.get(keyC)).toBeDefined();
      expect(cache.get(keyB)).toBeUndefined(); // evicted
      expect(cache.size()).toBe(2);
    });

    it('invalidate removes specific key and clear empties the entire cache', () => {
      const cache = new ResponseCache({ enabled: true });
      const key1 = ResponseCache.computeKey(baseRequest, { actor: 'u1' });
      const key2 = ResponseCache.computeKey(baseRequest, { actor: 'u2' });

      cache.set(key1, sampleResponse);
      cache.set(key2, sampleResponse);
      expect(cache.size()).toBe(2);

      cache.invalidate(key1);
      expect(cache.get(key1)).toBeUndefined();
      expect(cache.get(key2)).toBeDefined();
      expect(cache.size()).toBe(1);

      cache.clear();
      expect(cache.size()).toBe(0);
    });

    it('does not store or return when cache is disabled', () => {
      const cache = new ResponseCache({ enabled: false });
      const key = ResponseCache.computeKey(baseRequest);
      cache.set(key, sampleResponse);
      expect(cache.get(key)).toBeUndefined();
      expect(cache.size()).toBe(0);
    });
  });
});
