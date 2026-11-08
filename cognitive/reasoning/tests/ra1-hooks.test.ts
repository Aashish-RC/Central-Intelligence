import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { GatewayEngine } from '../src/core/engine.js';
import { ProviderRegistry } from '../src/providers/registry.js';
import { CooldownTracker } from '../src/resilience/cooldown.js';
import { ModelRouter } from '../src/routing/router.js';
import { SSRFGuard, createFakeDnsResolver } from '../src/security/ssrf.js';
import { type AuditRecord, PermissionDecision, ScopedCredential } from '../src/types/ra1.js';

describe('ra1 Integration Hooks (H1 to H4)', () => {
  beforeEach(() => {
    SSRFGuard.setResolver(
      createFakeDnsResolver({
        'api.openai.com': ['93.184.216.34'],
      }),
    );
  });

  afterEach(() => {
    SSRFGuard.resetResolver();
  });
  it('H2 Permission Hook: blocks request when decision is deny', async () => {
    const tracker = new CooldownTracker();
    const router = new ModelRouter(tracker);
    const engine = new GatewayEngine({
      router,
      cooldownTracker: tracker,
      defaultPermissionHook: async (req, ctx) => {
        if (req.model === 'restricted-model') {
          return { action: 'deny', reason: 'Model access prohibited for actor', statusCode: 403 };
        }
        return { action: 'allow' };
      },
    });

    try {
      await engine.chatCompletion({
        model: 'restricted-model',
        messages: [{ role: 'user', content: 'hello' }],
      });
      expect(true).toBe(false); // should not reach
    } catch (err: any) {
      expect(err.statusCode).toBe(403);
      expect(err.message).toContain('Permission denied');
    }
  });

  it('H2 Permission Hook: triggers human approval challenge when decision is ask-human', async () => {
    const tracker = new CooldownTracker();
    const router = new ModelRouter(tracker);
    const engine = new GatewayEngine({
      router,
      cooldownTracker: tracker,
      defaultPermissionHook: async () => {
        return {
          action: 'ask-human',
          reason: 'High-cost model execution',
          challengeId: 'chal-992',
        };
      },
    });

    try {
      await engine.chatCompletion({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'execute transfer' }],
      });
      expect(true).toBe(false);
    } catch (err: any) {
      expect(err.statusCode).toBe(428);
      expect(err.challengeId).toBe('chal-992');
    }
  });

  it('H3 Vault Key Hook & H4 Audit Hook: injects scoped key and emits complete audit record', async () => {
    const tracker = new CooldownTracker();
    const router = new ModelRouter(tracker);

    // Mock fetch for target
    const capturedHeaders: Record<string, string> = {};
    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      if (url.includes('/chat/completions')) {
        const headers = init?.headers as Record<string, string>;
        Object.assign(capturedHeaders, headers);
        return new Response(
          JSON.stringify({
            id: 'chatcmpl-mock',
            object: 'chat.completion',
            created: 123456,
            model: 'gpt-4o',
            choices: [
              {
                index: 0,
                message: { role: 'assistant', content: 'Hello!' },
                finish_reason: 'stop',
              },
            ],
            usage: { prompt_tokens: 15, completion_tokens: 5, total_tokens: 20 },
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        );
      }
      return originalFetch(url, init);
    }) as any;

    try {
      router.registerRoute({
        alias: 'gpt-4o',
        targets: [
          {
            id: 'openai-sec',
            provider: 'openai',
            model: 'gpt-4o',
            config: { id: 'cfg1', name: 'OpenAI', baseUrl: 'https://api.openai.com/v1' }, // no static key
          },
        ],
      });

      const auditRecords: AuditRecord[] = [];

      const engine = new GatewayEngine({
        router,
        cooldownTracker: tracker,
        defaultKeyLookupHook: async (provider, model, ctx) => {
          return {
            apiKey: 'vault-scoped-credential-xyz',
            provider,
            source: 'vault',
          };
        },
        defaultAuditHook: async (record) => {
          auditRecords.push(record);
        },
      });

      const res = await engine.chatCompletion(
        {
          model: 'gpt-4o',
          messages: [{ role: 'user', content: 'Hello' }],
        },
        {
          context: {
            actor: 'user-charlie',
            traceId: 'trace-abc-123',
          },
        },
      );

      expect(res.choices[0].message.content).toBe('Hello!');
      // H3: Credential was injected dynamically from vault!
      expect(capturedHeaders['authorization']).toBe('Bearer vault-scoped-credential-xyz');

      // H4: Audit record emitted with complete telemetry
      expect(auditRecords.length).toBe(1);
      const audit = auditRecords[0];
      expect(audit.actor).toBe('user-charlie');
      expect(audit.traceId).toBe('trace-abc-123');
      expect(audit.model).toBe('gpt-4o');
      expect(audit.provider).toBe('openai');
      expect(audit.outcome).toBe('success');
      expect(audit.tokens.totalTokens).toBe(20);
      expect(audit.cost!.totalCost).toBeGreaterThan(0);
      // Raw secret key is never leaked in the audit record!
      expect(JSON.stringify(audit)).not.toContain('vault-scoped-credential-xyz');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('H2 Identity Hook: spoofed x-actor-id or authorization headers do not change actor (defaults to anonymous)', async () => {
    let capturedActor = '';
    const { app, router } = await import('../src/core/server.js').then((m) =>
      m.createGatewayApp({
        auditHook: (record) => {
          capturedActor = record.actor;
        },
      }),
    );

    router.registerRoute({
      alias: 'gpt-4o',
      targets: [
        {
          id: 'mock-target',
          provider: 'openai',
          model: 'gpt-4o',
          config: {
            id: 'cfg',
            name: 'OpenAI',
            baseUrl: 'https://api.openai.com/v1',
            apiKey: 'test-key',
          },
        },
      ],
    });

    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async () => {
      return new Response(
        JSON.stringify({
          id: 'chatcmpl-mock',
          object: 'chat.completion',
          created: 123456,
          model: 'gpt-4o',
          choices: [
            { index: 0, message: { role: 'assistant', content: 'OK' }, finish_reason: 'stop' },
          ],
          usage: { prompt_tokens: 10, completion_tokens: 2, total_tokens: 12 },
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      );
    }) as any;

    try {
      const res = await app.request('/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-actor-id': 'spoofed-admin-actor',
          Authorization: 'Bearer spoofed-token',
        },
        body: JSON.stringify({
          model: 'gpt-4o',
          messages: [{ role: 'user', content: 'test' }],
        }),
      });

      expect(res.status).toBe(200);
      expect(capturedActor).toBe('anonymous');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('H2 Identity Hook: accepts verified actor from identity hook', async () => {
    let capturedActor = '';
    const { app, router } = await import('../src/core/server.js').then((m) =>
      m.createGatewayApp({
        identityHook: async () => 'verified-user-123',
        auditHook: (record) => {
          capturedActor = record.actor;
        },
      }),
    );

    router.registerRoute({
      alias: 'gpt-4o',
      targets: [
        {
          id: 'mock-target',
          provider: 'openai',
          model: 'gpt-4o',
          config: {
            id: 'cfg',
            name: 'OpenAI',
            baseUrl: 'https://api.openai.com/v1',
            apiKey: 'test-key',
          },
        },
      ],
    });

    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async () => {
      return new Response(
        JSON.stringify({
          id: 'chatcmpl-mock',
          object: 'chat.completion',
          created: 123456,
          model: 'gpt-4o',
          choices: [
            { index: 0, message: { role: 'assistant', content: 'OK' }, finish_reason: 'stop' },
          ],
          usage: { prompt_tokens: 10, completion_tokens: 2, total_tokens: 12 },
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      );
    }) as any;

    try {
      const res = await app.request('/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: 'gpt-4o',
          messages: [{ role: 'user', content: 'test' }],
        }),
      });

      expect(res.status).toBe(200);
      expect(capturedActor).toBe('verified-user-123');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
