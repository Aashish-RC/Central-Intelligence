import { describe, expect, it } from 'vitest';
import { AudioRouter } from '../src/audio/speech.js';
import { createGatewayApp } from '../src/core/server.js';

describe('Feature 22: Audio Speech (TTS) & Transcription (STT) API', () => {
  const { app } = createGatewayApp();

  it('synthesizes speech binary payload with content-type audio/mpeg', async () => {
    const res = await app.request('/v1/audio/speech', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'tts-1',
        input: 'The quick brown fox jumps over the lazy dog.',
        voice: 'alloy',
        response_format: 'mp3',
      }),
    });

    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toBe('audio/mpeg');
    const bytes = await res.arrayBuffer();
    expect(bytes.byteLength).toBeGreaterThan(0);
  });

  it('transcribes audio to structured text', async () => {
    const res = await app.request('/v1/audio/transcriptions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'whisper-1',
        language: 'en',
      }),
    });

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.task).toBe('transcribe');
    expect(data.language).toBe('en');
    expect(typeof data.text).toBe('string');
  });

  it('rejects invalid speech request missing input or model', async () => {
    const res = await app.request('/v1/audio/speech', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: '',
      }),
    });

    expect(res.status).toBe(400);
  });
});
