import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { GatewayEngine } from '../src/core/engine.js';
import { CooldownTracker } from '../src/resilience/cooldown.js';
import { ModelRouter } from '../src/routing/router.js';
import { SSRFGuard, createFakeDnsResolver } from '../src/security/ssrf.js';
import type { AuditRecord } from '../src/types/ra1.js';

describe('W2: Engine Failover & Error Classification Invariants', () => {
  beforeEach(() => {
    SSRFGuard.setResolver(
      createFakeDnsResolver({
        'target-a.com': ['93.184.216.34'],
        'target-b.com': ['93.184.216.34'],
      }),
    );
  });

  afterEach(() => {
    SSRFGuard.resetResolver();
  });

  it('does NOT fail over on non-retryable 400 context length error and does NOT cooldown target', async () => {
    const tracker = new CooldownTracker();
    const router = new ModelRouter(tracker);
    const auditRecords: AuditRecord[] = [];

    let targetACalls = 0;
    let targetBCalls = 0;

    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async (url: string) => {
      if (url.includes('target-a')) {
        targetACalls++;
        return new Response(
          JSON.stringify({
            error: {
              message:
                "This model's maximum context length is 128000 tokens. However, your messages resulted in 130000 tokens.",
              type: 'invalid_request_error',
              code: 'context_length_exceeded',
            },
          }),
          { status: 400, headers: { 'content-type': 'application/json' } },
        );
      }
      if (url.includes('target-b')) {
        targetBCalls++;
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      return originalFetch(url);
    }) as any;

    try {
      router.registerRoute({
        alias: 'test-model',
        targets: [
          {
            id: 'target-a',
            provider: 'openai',
            model: 'gpt-4o',
            config: { id: 'cfg-a', name: 'Target A', baseUrl: 'https://target-a.com/v1' },
          },
          {
            id: 'target-b',
            provider: 'openai',
            model: 'gpt-4o',
            config: { id: 'cfg-b', name: 'Target B', baseUrl: 'https://target-b.com/v1' },
          },
        ],
      });

      const engine = new GatewayEngine({
        router,
        cooldownTracker: tracker,
        defaultAuditHook: (record) => {
          auditRecords.push(record);
        },
      });

      // Execute request
      let caughtErr: any = null;
      try {
        await engine.chatCompletion({
          model: 'test-model',
          messages: [{ role: 'user', content: 'huge context prompt' }],
        });
      } catch (err: any) {
        caughtErr = err;
      }

      // Assertions for W2 requirements:
      // 1. Non-retryable error is returned to caller immediately
      expect(caughtErr).toBeDefined();
      expect(caughtErr.statusCode).toBe(400);
      expect(caughtErr.openAIError.error.type).toBe('invalid_request_error');

      // 2. Next target is NOT tried
      expect(targetACalls).toBe(1);
      expect(targetBCalls).toBe(0);

      // 3. Client errors (4xx other than 429 and 408) do NOT count against target cooldown
      const targetAHealth = tracker.getHealth('target-a');
      expect(targetAHealth.isInCooldown).toBe(false);
      expect(targetAHealth.consecutiveFailures).toBe(0);

      // 4. In-flight counters are incremented and decremented exactly once (use finally)
      expect(tracker.getInFlight('target-a')).toBe(0);
      expect(tracker.getInFlight('target-b')).toBe(0);

      // 5. Exactly ONE audit record emitted for the request with final outcome
      expect(auditRecords.length).toBe(1);
      expect(auditRecords[0].outcome).toBe('error');
      expect(auditRecords[0].statusCode).toBe(400);
      expect(auditRecords[0].targetId).toBe('target-a');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('does NOT fail over on non-retryable 401 auth failure', async () => {
    const tracker = new CooldownTracker();
    const router = new ModelRouter(tracker);
    const auditRecords: AuditRecord[] = [];

    let targetACalls = 0;
    let targetBCalls = 0;

    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async (url: string) => {
      if (url.includes('target-a')) {
        targetACalls++;
        return new Response(
          JSON.stringify({
            error: {
              message: 'Incorrect API key provided',
              type: 'invalid_request_error',
              code: 'invalid_api_key',
            },
          }),
          { status: 401, headers: { 'content-type': 'application/json' } },
        );
      }
      if (url.includes('target-b')) {
        targetBCalls++;
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }
      return originalFetch(url);
    }) as any;

    try {
      router.registerRoute({
        alias: 'auth-test',
        targets: [
          {
            id: 'target-a',
            provider: 'openai',
            model: 'gpt-4o',
            config: { id: 'cfg-a', name: 'Target A', baseUrl: 'https://target-a.com/v1' },
          },
          {
            id: 'target-b',
            provider: 'openai',
            model: 'gpt-4o',
            config: { id: 'cfg-b', name: 'Target B', baseUrl: 'https://target-b.com/v1' },
          },
        ],
      });

      const engine = new GatewayEngine({
        router,
        cooldownTracker: tracker,
        defaultAuditHook: (record) => {
          auditRecords.push(record);
        },
      });

      let caughtErr: any = null;
      try {
        await engine.chatCompletion({
          model: 'auth-test',
          messages: [{ role: 'user', content: 'hi' }],
        });
      } catch (err: any) {
        caughtErr = err;
      }

      expect(caughtErr).toBeDefined();
      expect(caughtErr.statusCode).toBe(401);
      expect(targetACalls).toBe(1);
      expect(targetBCalls).toBe(0);
      expect(tracker.getInFlight('target-a')).toBe(0);
      expect(auditRecords.length).toBe(1);
      expect(auditRecords[0].statusCode).toBe(401);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('SSRF failure emits exactly one audit record with 403', async () => {
    const tracker = new CooldownTracker();
    const router = new ModelRouter(tracker);
    const auditRecords: AuditRecord[] = [];

    router.registerRoute({
      alias: 'ssrf-test',
      targets: [
        {
          id: 'internal-target',
          provider: 'openai',
          model: 'gpt-4o',
          config: { id: 'cfg-meta', name: 'AWS Meta', baseUrl: 'http://169.254.169.254/v1' },
        },
      ],
    });

    const engine = new GatewayEngine({
      router,
      cooldownTracker: tracker,
      defaultAuditHook: (record) => {
        auditRecords.push(record);
      },
    });

    await expect(
      engine.chatCompletion({
        model: 'ssrf-test',
        messages: [{ role: 'user', content: 'test' }],
      }),
    ).rejects.toThrow();

    expect(auditRecords.length).toBe(1);
    expect(auditRecords[0].statusCode).toBe(403);
    expect(auditRecords[0].outcome).toBe('error');
    expect(auditRecords[0].errorMessage).toContain('SSRF Guard');
  });

  it('ask-human approval path emits exactly one audit record with 428', async () => {
    const tracker = new CooldownTracker();
    const router = new ModelRouter(tracker);
    const auditRecords: AuditRecord[] = [];

    const engine = new GatewayEngine({
      router,
      cooldownTracker: tracker,
      defaultPermissionHook: async () => ({
        action: 'ask-human',
        reason: 'Approval needed for high-risk tool call',
        challengeId: 'chal-443',
      }),
      defaultAuditHook: (record) => {
        auditRecords.push(record);
      },
    });

    await expect(
      engine.chatCompletion({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'delete database' }],
      }),
    ).rejects.toThrow();

    expect(auditRecords.length).toBe(1);
    expect(auditRecords[0].statusCode).toBe(428);
    expect(auditRecords[0].outcome).toBe('denied');
    expect(auditRecords[0].metadata?.challengeId).toBe('chal-443');
  });
});
