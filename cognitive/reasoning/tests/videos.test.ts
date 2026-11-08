import { describe, expect, it } from 'vitest';
import { createGatewayApp } from '../src/core/server.js';

describe('Feature 37: Video Generation API (/v1/videos)', () => {
  const { app } = createGatewayApp();
  let videoJobId = '';

  it('submits a video generation job', async () => {
    const res = await app.request('/v1/videos/generations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: 'Time-lapse drone flyover of emerald alpine valley in morning mist',
        model: 'sora-1.0',
        duration_seconds: 5,
        resolution: '1080p',
      }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toMatch(/^vid_/);
    expect(body.object).toBe('video');
    expect(body.status).toBe('processing');
    videoJobId = body.id;
  });

  it('polls video job status until completed', async () => {
    let res = await app.request(`/v1/videos/${videoJobId}`);
    expect(res.status).toBe(200);
    let body = await res.json();
    expect(body.progress_percentage).toBeGreaterThan(25);

    // Poll until completed
    while (body.status !== 'completed') {
      res = await app.request(`/v1/videos/${videoJobId}`);
      body = await res.json();
    }

    expect(body.status).toBe('completed');
    expect(body.video_url).toContain('.mp4');
  });
});
