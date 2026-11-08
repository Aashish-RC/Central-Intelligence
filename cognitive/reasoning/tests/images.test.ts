import { describe, expect, it } from 'vitest';
import { createGatewayApp } from '../src/core/server.js';

describe('Feature 23: Image Generations & Edits API', () => {
  const { app } = createGatewayApp();

  it('generates standard image URLs for prompt', async () => {
    const res = await app.request('/v1/images/generations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: 'A cyberpunk cat resting on neon glowing circuits',
        model: 'dall-e-3',
        n: 1,
        size: '1024x1024',
      }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.created).toBeDefined();
    expect(Array.isArray(body.data)).toBe(true);
    expect(body.data.length).toBe(1);
    expect(body.data[0].url).toContain('https://images.gateway.local');
    expect(body.data[0].revised_prompt).toContain('cyberpunk cat');
  });

  it('generates b64_json format when requested', async () => {
    const res = await app.request('/v1/images/generations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: 'Minimalist logo design',
        model: 'dall-e-3',
        response_format: 'b64_json',
      }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.data[0].b64_json).toBeDefined();
  });

  it('rejects invalid image generation request', async () => {
    const res = await app.request('/v1/images/generations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: '',
      }),
    });

    expect(res.status).toBe(400);
  });
});
