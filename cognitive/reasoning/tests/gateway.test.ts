import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { GatewayEngine } from '../src/core/engine.js';
import { ErrorClassifier } from '../src/resilience/classifier.js';
import { CooldownTracker } from '../src/resilience/cooldown.js';
import { ModelRouter } from '../src/routing/router.js';
import { SSRFGuard, createFakeDnsResolver } from '../src/security/ssrf.js';
import { PricingEngine } from '../src/telemetry/pricing.js';

describe('ErrorClassifier (Bifrost-style Granular Classification)', () => {
  beforeEach(() => {
    SSRFGuard.setResolver(
      createFakeDnsResolver({
        'api.openai.com': ['93.184.216.34'],
        'api.anthropic.com': ['104.18.2.1'],
        'generativelanguage.googleapis.com': ['142.250.180.10'],
      }),
    );
  });

  afterEach(() => {
    SSRFGuard.resetResolver();
  });
  it('correctly classifies 429 rate limit errors as retryable with backoff', () => {
    const classified = ErrorClassifier.classify(429, {
      error: { message: 'Rate limit reached. Try again in 15s' },
    });
    expect(classified.category).toBe('RATE_LIMIT');
    expect(classified.isRetryable).toBe(true);
    expect(classified.statusCode).toBe(429);
    expect(classified.retryAfterSeconds).toBe(15);
  });

  it('correctly classifies context length exceeded as non-retryable 400', () => {
    const classified = ErrorClassifier.classify(400, {
      error: {
        message:
          "This model's maximum context length is 128000 tokens. However, your messages resulted in 130000 tokens.",
      },
    });
    expect(classified.category).toBe('CONTEXT_LENGTH_EXCEEDED');
    expect(classified.isRetryable).toBe(false);
    expect(classified.statusCode).toBe(400);
  });

  it('correctly classifies auth errors as non-retryable 401', () => {
    const classified = ErrorClassifier.classify(401, {
      error: { message: 'Incorrect API key provided' },
    });
    expect(classified.category).toBe('AUTH_FAILURE');
    expect(classified.isRetryable).toBe(false);
    expect(classified.statusCode).toBe(401);
  });

  it('correctly classifies 503 overloaded as retryable', () => {
    const classified = ErrorClassifier.classify(
      503,
      'upstream connect error or disconnect/reset before headers',
    );
    expect(classified.category).toBe('OVERLOADED');
    expect(classified.isRetryable).toBe(true);
  });
});

describe('SSRFGuard (Clean-room Zero-Trust Security)', () => {
  it('blocks private IP ranges (10.0.0.0/8, 192.168.0.0/16)', async () => {
    await expect(SSRFGuard.validateUrl('http://10.0.0.5/v1')).rejects.toThrow('SSRF Guard');
    await expect(SSRFGuard.validateUrl('http://192.168.1.1/api')).rejects.toThrow('SSRF Guard');
  });

  it('blocks cloud metadata endpoint (169.254.169.254)', async () => {
    await expect(SSRFGuard.validateUrl('http://169.254.169.254/latest/meta-data/')).rejects.toThrow(
      'SSRF Guard',
    );
  });

  it('allows public HTTPS endpoints', async () => {
    await expect(
      SSRFGuard.validateUrl('https://api.openai.com/v1/chat/completions'),
    ).resolves.toBeUndefined();
  });
});

describe('PricingEngine (Multi-Unit High-Precision Cost Calculation)', () => {
  it('accurately computes prompt, completion, and cache discounts', () => {
    const cost = PricingEngine.calculateCost('gpt-4o', {
      promptTokens: 10000,
      completionTokens: 2000,
      reasoningTokens: 0,
      cachedPromptTokens: 5000,
      totalTokens: 12000,
    });

    expect(cost).toBeDefined();
    expect(cost!.currency).toBe('USD');
    expect(cost!.totalCost).toBe(0.03875);
    expect(cost!.cacheDiscount).toBeGreaterThan(0);
  });

  it('returns null for unknown model and flags costEstimated with warning in audit record', async () => {
    const cost = PricingEngine.calculateCost('unknown-model-xyz', {
      promptTokens: 100,
      completionTokens: 50,
      reasoningTokens: 0,
      cachedPromptTokens: 0,
      totalTokens: 150,
    });
    expect(cost).toBeNull();

    let capturedAudit: any = null;
    const tracker = new CooldownTracker();
    const router = new ModelRouter(tracker);
    router.registerRoute({
      alias: 'unknown-model-xyz',
      targets: [
        {
          id: 'mock-target',
          provider: 'openai',
          model: 'unknown-model-xyz',
          config: { id: 'cfg', name: 'Mock', baseUrl: 'https://api.openai.com/v1', apiKey: 'key' },
        },
      ],
    });

    const engine = new GatewayEngine({
      router,
      cooldownTracker: tracker,
      defaultAuditHook: (record) => {
        capturedAudit = record;
      },
    });

    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async () => {
      return new Response(
        JSON.stringify({
          id: 'chatcmpl-mock',
          object: 'chat.completion',
          created: 123456,
          model: 'unknown-model-xyz',
          choices: [
            { index: 0, message: { role: 'assistant', content: 'hello' }, finish_reason: 'stop' },
          ],
          usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
        }),
        { status: 200, headers: { 'content-type': 'application/json' } },
      );
    }) as any;

    try {
      await engine.chatCompletion({
        model: 'unknown-model-xyz',
        messages: [{ role: 'user', content: 'hi' }],
      });

      expect(capturedAudit).toBeDefined();
      expect(capturedAudit.cost).toBeNull();
      expect(capturedAudit.costEstimated).toBe(true);
      expect(capturedAudit.warning).toContain('unknown-model-xyz');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

describe('ModelRouter & CooldownTracker (Escape Routes & Failover)', () => {
  it('activates Escape Route when all primary cloud endpoints are in cooldown', () => {
    const tracker = new CooldownTracker();
    const router = new ModelRouter(tracker);

    router.registerRoute({
      alias: 'smart-model',
      targets: [
        {
          id: 'cloud-primary',
          provider: 'anthropic',
          model: 'claude-3-7-sonnet',
          config: { id: 'c1', name: 'Anthropic', baseUrl: 'https://api.anthropic.com' },
        },
        {
          id: 'local-escape',
          provider: 'ollama',
          model: 'llama3.2',
          isEscapeRoute: true,
          config: { id: 'c2', name: 'Ollama', baseUrl: 'http://127.0.0.1:11434' },
        },
      ],
    });

    // Before failure: Primary is selected
    const initialTargets = router.resolveTargets('smart-model');
    expect(initialTargets[0].id).toBe('cloud-primary');

    // Simulate primary failure and cooldown
    tracker.recordFailure('cloud-primary', 60);

    // After failure: Escape Route automatically activates!
    const fallbackTargets = router.resolveTargets('smart-model');
    expect(fallbackTargets[0].id).toBe('local-escape');
  });

  it('implements Prompt-Cache Sticky Routing to same replica for identical prompt prefix', () => {
    const tracker = new CooldownTracker();
    const router = new ModelRouter(tracker);

    router.registerRoute({
      alias: 'prompt-cached-group',
      strategy: 'prompt-cache-affinity',
      targets: [
        {
          id: 'replica-1',
          provider: 'openai',
          model: 'gpt-4o',
          config: { id: 'r1', name: 'R1', baseUrl: 'https://api.openai.com/v1' },
        },
        {
          id: 'replica-2',
          provider: 'openai',
          model: 'gpt-4o',
          config: { id: 'r2', name: 'R2', baseUrl: 'https://api.openai.com/v1' },
        },
      ],
    });

    const prompt1 = 'You are an expert system with schema XYZ...';
    const resolution1 = router.resolveTargets('prompt-cached-group', prompt1);
    const resolution2 = router.resolveTargets('prompt-cached-group', prompt1);

    // Consecutive calls with identical prompt prefix stick to the exact same replica!
    expect(resolution1[0].id).toBe(resolution2[0].id);
  });
});

describe('ResponseCache (Exact Match Canonical Prompt Caching)', () => {
  it('stores and retrieves cached completions on identical requests when enabled', async () => {
    const { ResponseCache } = await import('../src/caching/cache.js');
    const cache = new ResponseCache({ enabled: true, defaultTtlSeconds: 60 });

    const req = {
      model: 'gpt-4o',
      messages: [{ role: 'user' as const, content: 'What is 2 + 2?' }],
    };
    const key = ResponseCache.computeKey(req as any);

    expect(cache.get(key)).toBeUndefined();

    const mockResp: any = {
      id: 'chatcmpl-cached',
      choices: [{ message: { role: 'assistant', content: '4' } }],
    };
    cache.set(key, mockResp);

    const hit = cache.get(key);
    expect(hit).toBeDefined();
    expect(hit?.id).toBe('chatcmpl-cached');
  });
});

describe('SlidingWindowRateLimiter (Traffic Bounding)', () => {
  it('allows requests within threshold and blocks when exceeded', async () => {
    const { SlidingWindowRateLimiter } = await import('../src/resilience/ratelimit.js');
    const limiter = new SlidingWindowRateLimiter(2, 10); // 2 requests per 10s

    const r1 = limiter.check('client-a');
    expect(r1.allowed).toBe(true);
    expect(r1.remaining).toBe(1);

    const r2 = limiter.check('client-a');
    expect(r2.allowed).toBe(true);
    expect(r2.remaining).toBe(0);

    const r3 = limiter.check('client-a');
    expect(r3.allowed).toBe(false);
    expect(r3.remaining).toBe(0);
    expect(r3.resetSeconds).toBeGreaterThan(0);
  });
});

describe('GeminiProviderAdapter (Google REST API Translation)', () => {
  it('transforms OpenAI chat requests to Gemini contents schema', async () => {
    const { GeminiProviderAdapter } = await import('../src/providers/gemini.js');
    const adapter = new GeminiProviderAdapter();

    const upstream = adapter.transformRequest(
      {
        model: 'gemini-1.5-pro',
        messages: [
          { role: 'system', content: 'You are helpful.' },
          { role: 'user', content: 'Hello Gemini!' },
        ],
        temperature: 0.5,
      },
      {
        id: 'cfg',
        name: 'Gemini Cfg',
        baseUrl: 'https://generativelanguage.googleapis.com',
        apiKey: 'fake-goog-key',
      },
    );

    expect(upstream.url).toContain('/v1beta/models/gemini-1.5-pro:generateContent');
    expect(upstream.headers['x-goog-api-key']).toBe('fake-goog-key');

    const parsed = JSON.parse(upstream.body!);
    expect(parsed.systemInstruction.parts[0].text).toBe('You are helpful.');
    expect(parsed.contents[0].role).toBe('user');
    expect(parsed.contents[0].parts[0].text).toBe('Hello Gemini!');
  });
});
