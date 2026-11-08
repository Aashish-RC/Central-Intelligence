import { describe, expect, it } from 'vitest';
import { createGatewayApp } from '../src/core/server.js';

describe('Feature 24: Batch Processing API (/v1/batches)', () => {
  const { app } = createGatewayApp();

  let batchId = '';

  it('creates a new async batch inference job', async () => {
    const res = await app.request('/v1/batches', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        input_file_id: 'file-xyz123',
        endpoint: '/v1/chat/completions',
        completion_window: '24h',
        metadata: { customer: 'acme-corp' },
      }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toMatch(/^batch_/);
    expect(body.object).toBe('batch');
    expect(body.status).toBe('in_progress');
    batchId = body.id;
  });

  it('retrieves batch status and simulates progress', async () => {
    const res = await app.request(`/v1/batches/${batchId}`);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toBe(batchId);
    expect(body.request_counts.completed).toBeGreaterThan(0);
  });

  it('lists existing batches', async () => {
    const res = await app.request('/v1/batches');
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.object).toBe('list');
    expect(body.data.length).toBeGreaterThan(0);
  });

  it('cancels an active batch job', async () => {
    const res = await app.request(`/v1/batches/${batchId}/cancel`, {
      method: 'POST',
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(['cancelled', 'completed']).toContain(body.status);
  });
});
