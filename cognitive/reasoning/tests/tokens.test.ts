import { describe, expect, it } from 'vitest';
import { createGatewayApp } from '../src/core/server.js';
import { TokenCounter } from '../src/telemetry/tokens.js';

describe('Feature 25: Token Counting API (/v1/tokenize & /v1/messages/count_tokens)', () => {
  it('counts tokens for raw text prompts using TokenCounter', () => {
    const text = 'Hello world! This is a test of the token counting algorithm.';
    const tokens = TokenCounter.countTokens(text, 'gpt-4o');
    expect(tokens).toBeGreaterThan(5);
    expect(tokens).toBeLessThan(25);
  });

  it('counts multi-message chat tokens including per-message overhead', () => {
    const messages = [
      { role: 'system', content: 'You are a helpful assistant.' },
      { role: 'user', content: 'What is the speed of light?' },
    ];

    const result = TokenCounter.countMessageTokens(messages, 'gpt-4o');
    expect(result.totalTokens).toBeGreaterThan(10);
    expect(result.messageDetails.length).toBe(2);
    expect(result.messageDetails[0].role).toBe('system');
  });

  it('serves HTTP POST /v1/tokenize and returns count and character_count', async () => {
    const { app } = createGatewayApp();
    const res = await app.request('/v1/tokenize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'gpt-4o',
        prompt: 'Testing the tokenize API endpoint.',
      }),
    });

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.count).toBeGreaterThan(0);
    expect(data.model).toBe('gpt-4o');
    expect(data.character_count).toBe('Testing the tokenize API endpoint.'.length);
  });

  it('serves HTTP POST /v1/messages/count_tokens and returns input_tokens', async () => {
    const { app } = createGatewayApp();
    const res = await app.request('/v1/messages/count_tokens', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'claude-3-5-sonnet',
        messages: [{ role: 'user', content: 'Tell me a three sentence story.' }],
      }),
    });

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.input_tokens).toBeGreaterThan(0);
    expect(data.model).toBe('claude-3-5-sonnet');
    expect(data.details.length).toBe(1);
  });
});
