import { describe, expect, it } from 'vitest';
import { createGatewayApp } from '../src/core/server.js';

describe('Feature 39: File Management & Fine-Tuning API (/v1/files, /v1/fine_tuning)', () => {
  const { app } = createGatewayApp();
  let fileId = '';
  let fineTuneJobId = '';

  it('uploads a training dataset file', async () => {
    const res = await app.request('/v1/files', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: 'train_qa.jsonl',
        purpose: 'fine-tune',
        content: '{"prompt": "hello", "completion": "world"}\n',
      }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toMatch(/^file-/);
    expect(body.filename).toBe('train_qa.jsonl');
    expect(body.bytes).toBeGreaterThan(0);
    fileId = body.id;
  });

  it('retrieves uploaded file metadata', async () => {
    const res = await app.request(`/v1/files/${fileId}`);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toBe(fileId);
  });

  it('creates and tracks fine-tuning job', async () => {
    const res = await app.request('/v1/fine_tuning/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        training_file: fileId,
        model: 'gpt-4o-mini',
        suffix: 'legal-bot',
      }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toMatch(/^ftjob-/);
    fineTuneJobId = body.id;

    const getRes = await app.request(`/v1/fine_tuning/jobs/${fineTuneJobId}`);
    expect(getRes.status).toBe(200);
    const job = await getRes.json();
    expect(job.status).toBe('succeeded');
    expect(job.fine_tuned_model).toContain('legal-bot');
  });
});
