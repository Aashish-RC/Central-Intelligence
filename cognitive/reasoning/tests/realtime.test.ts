import { describe, expect, it } from 'vitest';
import { createGatewayApp } from '../src/core/server.js';
import { RealtimeGateway } from '../src/realtime/gateway.js';

describe('Feature 20: Realtime Voice/Audio WebSocket API', () => {
  const { app } = createGatewayApp();

  it('initializes a realtime session via HTTP POST /v1/realtime/sessions', async () => {
    const res = await app.request('/v1/realtime/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        modalities: ['text', 'audio'],
        voice: 'alloy',
        temperature: 0.8,
      }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toMatch(/^sess_/);
    expect(body.config.voice).toBe('alloy');
  });

  it('processes realtime event lifecycle in gateway session', () => {
    const gateway = new RealtimeGateway();
    const session = gateway.createSession({ voice: 'echo' });

    const responses = session.processClientEvent({
      type: 'session.update',
      session: { temperature: 0.9 },
    });

    expect(responses.length).toBe(1);
    expect(responses[0].type).toBe('session.updated');
    expect(session.config.temperature).toBe(0.9);

    const commitResponses = session.processClientEvent({
      type: 'input_audio_buffer.commit',
    });
    expect(commitResponses[0].type).toBe('input_audio_buffer.committed');

    const completionResponses = session.processClientEvent({
      type: 'response.create',
    });
    expect(completionResponses.some((r) => r.type === 'response.done')).toBe(true);
  });
});
