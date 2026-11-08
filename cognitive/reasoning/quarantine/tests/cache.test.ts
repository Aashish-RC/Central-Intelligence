import { describe, expect, it } from 'vitest';
import { ResponseCache } from '../src/caching/cache.js';
import { GatewayEngine } from '../src/core/engine.js';
import { ModelRouter } from '../src/routing/router.js';
import { CooldownTracker } from '../src/resilience/cooldown.js';
import { AuditRecord } from '../src/types/ra1.js';

describe('W4: ResponseCache Hardening & Isolation', () => {
  it('prevents 32-bit hash collision for "Aa" vs "BB"', () => {
    const reqAa: any = {
      model: 'gpt-4o',
      messages: [{ role: 'user', content: 'Aa' }]
    };
    const reqBb: any = {
      model: 'gpt-4o',
      messages: [{ role: 'user', content: 'BB' }]
    };

    const keyAa = ResponseCache.computeKey(reqAa);
    const keyBb = ResponseCache.computeKey(reqBb);

    expect(keyAa).not.toBe(keyBb);
  });

  it('differentiates cache keys when previously-ignored fields change', () => {
    const baseReq: any = {
      model: 'gpt-4o',
      messages: [{ role: 'user', content: 'Tell me a story' }]
    };

    const keyBase = ResponseCache.computeKey(baseReq);

    // Stop sequence change
    const keyWithStop = ResponseCache.computeKey({ ...baseReq, stop: ['\n'] });
    expect(keyWithStop).not.toBe(keyBase);

    // Seed change
    const keyWithSeed = ResponseCache.computeKey({ ...baseReq, seed: 42 });
    expect(keyWithSeed).not.toBe(keyBase);

    // Tool choice change
    const keyWithToolChoice = ResponseCache.computeKey({ ...baseReq, tool_choice: 'required' });
    expect(keyWithToolChoice).not.toBe(keyBase);

    // Response format change
    const keyWithJsonFormat = ResponseCache.computeKey({ ...baseReq, response_format: { type: 'json_object' } });
    expect(keyWithJsonFormat).not.toBe(keyBase);
  });

  it('ensures cross-tenant isolation for identical prompts', () => {
    const req: any = {
      model: 'gpt-4o',
      messages: [{ role: 'user', content: 'Hello' }]
    };

    const keyTenant1 = ResponseCache.computeKey(req, { tenantId: 'tenant-1' });
    const keyTenant2 = ResponseCache.computeKey(req, { tenantId: 'tenant-2' });
    const keyNoTenant = ResponseCache.computeKey(req);

    expect(keyTenant1).not.toBe(keyTenant2);
    expect(keyTenant1).not.toBe(keyNoTenant);
  });

  it('emits an audit record with cached: true on cache hit', async () => {
    const tracker = new CooldownTracker();
    const router = new ModelRouter(tracker);
    const cache = new ResponseCache({ enabled: true });
    const auditRecords: AuditRecord[] = [];

    const req: any = {
      model: 'gpt-4o',
      messages: [{ role: 'user', content: 'Cached query' }]
    };

    // Pre-populate cache
    const cachedResponse: any = {
      id: 'chatcmpl-cached-123',
      object: 'chat.completion',
      created: 123456,
      model: 'gpt-4o',
      choices: [{ index: 0, message: { role: 'assistant', content: 'Cached answer' }, finish_reason: 'stop' }],
      usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 }
    };

    const cacheKey = ResponseCache.computeKey(req, { actor: 'alice', tenantId: 'tenant-a' });
    cache.set(cacheKey, cachedResponse);

    const engine = new GatewayEngine({
      router,
      cooldownTracker: tracker,
      cache,
      defaultAuditHook: (record) => {
        auditRecords.push(record);
      }
    });

    const res = await engine.chatCompletion(req, {
      context: { actor: 'alice', tenantId: 'tenant-a' }
    });

    expect(res.id).toBe('chatcmpl-cached-123');
    expect(auditRecords.length).toBe(1);
    expect(auditRecords[0].outcome).toBe('success');
    expect(auditRecords[0].cached).toBe(true);
    expect(auditRecords[0].provider).toBe('cache');
  });
});
