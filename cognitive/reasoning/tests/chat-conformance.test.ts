import { describe, expect, it } from 'vitest';
import { createGatewayApp } from '../src/core/server.js';
import { ProviderRegistry } from '../src/providers/registry.js';
import { ErrorClassifier } from '../src/resilience/classifier.js';
import { TokenUsageAccounting } from '../src/telemetry/usage.js';

describe('Feature 1: Strict Zod Validation & OpenAI Chat Endpoint Conformance', () => {
  const { app } = createGatewayApp();

  it('rejects request with missing model field with 400', async () => {
    const res = await app.request('/v1/chat/completions', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        messages: [{ role: 'user', content: 'hi' }],
      }),
    });

    expect(res.status).toBe(400);
    const body: any = await res.json();
    expect(body.error.type).toBe('invalid_request_error');
    expect(body.error.message).toContain('Validation failed');
  });

  it('rejects request with empty messages array with 400', async () => {
    const res = await app.request('/v1/chat/completions', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        model: 'gpt-4o',
        messages: [],
      }),
    });

    expect(res.status).toBe(400);
    const body: any = await res.json();
    expect(body.error.type).toBe('invalid_request_error');
    expect(body.error.message).toContain('At least one message is required');
  });

  it('rejects invalid temperature > 2 with 400', async () => {
    const res = await app.request('/v1/chat/completions', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: 'test' }],
        temperature: 3.5,
      }),
    });

    expect(res.status).toBe(400);
    const body: any = await res.json();
    expect(body.error.type).toBe('invalid_request_error');
  });
});

describe('Feature 7: Unified Token Usage Accounting & Estimation', () => {
  it('extracts exact token counts from OpenAI response', () => {
    const usage = TokenUsageAccounting.extractUsage(
      {
        usage: {
          prompt_tokens: 100,
          completion_tokens: 50,
          total_tokens: 150,
          prompt_tokens_details: { cached_tokens: 40 },
          completion_tokens_details: { reasoning_tokens: 10 },
        },
      },
      'openai',
    );

    expect(usage.promptTokens).toBe(100);
    expect(usage.completionTokens).toBe(50);
    expect(usage.cachedPromptTokens).toBe(40);
    expect(usage.reasoningTokens).toBe(10);
    expect(usage.estimated).toBe(false);
  });

  it('extracts cache read/write tokens from Anthropic response', () => {
    const usage = TokenUsageAccounting.extractUsage(
      {
        input_tokens: 200,
        output_tokens: 80,
        cache_read_input_tokens: 150,
        cache_creation_input_tokens: 50,
      },
      'anthropic',
    );

    expect(usage.promptTokens).toBe(200);
    expect(usage.completionTokens).toBe(80);
    expect(usage.cachedPromptTokens).toBe(150);
    expect(usage.cacheWriteTokens).toBe(50);
    expect(usage.estimated).toBe(false);
  });

  it('falls back to estimation when usage is omitted by local provider', () => {
    const req = {
      model: 'llama.cpp',
      messages: [{ role: 'user', content: 'What is the capital of France?' }],
    };

    const usage = TokenUsageAccounting.extractUsage(
      {},
      'llama.cpp',
      req as any,
      'The capital of France is Paris.',
    );
    expect(usage.estimated).toBe(true);
    expect(usage.promptTokens).toBeGreaterThan(0);
    expect(usage.completionTokens).toBeGreaterThan(0);
    expect(usage.totalTokens).toBe(usage.promptTokens + usage.completionTokens);
  });
});

describe('Feature 10: Normalized Error Envelope Formatting', () => {
  it('converts classified errors to standard OpenAI error envelopes', () => {
    const classified = ErrorClassifier.classify(429, 'Rate limit exceeded');
    const openAIEnvelope = ErrorClassifier.toOpenAIError(classified);

    expect(openAIEnvelope.error).toBeDefined();
    expect(openAIEnvelope.error.type).toBe('rate_limit_error');
    expect(openAIEnvelope.error.code).toBe(429);
    expect(openAIEnvelope.error.param).toBeNull();
  });
});

describe('Feature 2: Local Runtimes via OpenAI-Compatible Interface', () => {
  it('registers llama.cpp and localai adapters in ProviderRegistry', () => {
    expect(ProviderRegistry.has('llama.cpp')).toBe(true);
    expect(ProviderRegistry.has('localai')).toBe(true);

    const llamaAdapter = ProviderRegistry.get('llama.cpp')!;
    const req = llamaAdapter.transformRequest(
      {
        model: 'default',
        messages: [{ role: 'user', content: 'hello local' }],
      },
      {
        id: 'cfg',
        name: 'Local',
        baseUrl: 'http://127.0.0.1:8080',
      },
    );

    expect(req.url).toBe('http://127.0.0.1:8080/v1/chat/completions');
    expect(req.method).toBe('POST');
  });
});
