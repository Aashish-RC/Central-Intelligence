import { describe, expect, it } from 'vitest';
import { createGatewayApp } from '../src/core/server.js';

describe('Extended Standard Gateway Endpoints (Embeddings, Completions, Messages, Metrics, Translations)', () => {
  const { app } = createGatewayApp();

  it('serves POST /v1/embeddings returning standardized vector embeddings', async () => {
    const res = await app.request('/v1/embeddings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'text-embedding-3-small',
        input: ['hello world', 'enterprise AI model gateway'],
        dimensions: 32,
      }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.object).toBe('list');
    expect(body.data.length).toBe(2);
    expect(body.data[0].embedding.length).toBe(32);
    expect(body.usage.prompt_tokens).toBeGreaterThan(0);
  });

  it('serves POST /v1/completions (legacy text completions)', async () => {
    const res = await app.request('/v1/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'gpt-3.5-turbo-instruct',
        prompt: 'Explain quantum computing in one sentence',
      }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.object).toBe('text_completion');
    expect(body.choices.length).toBe(1);
    expect(body.choices[0].text).toContain('Completion output');
  });

  it('serves POST /v1/messages (Anthropic native messages format)', async () => {
    const res = await app.request('/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'claude-3-5-sonnet-20241022',
        messages: [{ role: 'user', content: 'What is the speed of light?' }],
        max_tokens: 100,
      }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.type).toBe('message');
    expect(body.role).toBe('assistant');
    expect(body.content[0].type).toBe('text');
  });

  it('serves POST /v1/images/edits and POST /v1/audio/translations', async () => {
    const imgRes = await app.request('/v1/images/edits', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: 'Add a sunset in background' }),
    });
    expect(imgRes.status).toBe(200);
    const imgBody = await imgRes.json();
    expect(imgBody.data.length).toBeGreaterThan(0);

    const audioRes = await app.request('/v1/audio/translations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'whisper-1' }),
    });
    expect(audioRes.status).toBe(200);
    const audioBody = await audioRes.json();
    expect(audioBody.task).toBe('translate');
  });

  it('serves GET /metrics in Prometheus exposition format and health probes', async () => {
    const metricsRes = await app.request('/metrics');
    expect(metricsRes.status).toBe(200);
    expect(metricsRes.headers.get('content-type')).toContain('text/plain');
    const text = await metricsRes.text();
    expect(text).toContain('gateway_requests_total');
    expect(text).toContain('gateway_tokens_total');

    const liveRes = await app.request('/health/liveness');
    expect(liveRes.status).toBe(200);

    const readyRes = await app.request('/health/readiness');
    expect(readyRes.status).toBe(200);
  });
});
