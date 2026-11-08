import { describe, expect, it } from 'vitest';
import { StreamFailoverManager } from '../src/core/stream-failover.js';
import { OpenAIAdapter } from '../src/providers/openai.js';

describe('Feature 3 & 34: SSE Streaming Normalization & Failover (Bifrost + Portkey)', () => {
  const adapter = new OpenAIAdapter();
  const state = {
    id: 'test-id',
    model: 'gpt-4o',
    created: 123456,
    buffer: '',
  };

  it('Pre-first-byte: throws error before first byte if upstream throws immediately', async () => {
    const failingBody: any = {
      getReader: () => ({
        closed: Promise.resolve(),
        read: async () => {
          throw new Error('Immediate upstream disconnect before any byte');
        },
        cancel: async () => {},
      }),
    };

    // Pre-flight check MUST throw so the router can failover to the next healthy replica!
    await expect(
      StreamFailoverManager.createGuardedStream(failingBody, adapter, state),
    ).rejects.toThrow('Immediate upstream disconnect before any byte');
  });

  it('Post-first-byte: emits explicit SSE error event and closes stream when error occurs mid-stream', async () => {
    const encoder = new TextEncoder();
    let readCount = 0;

    // Upstream body that emits one valid chunk, then aborts/fails mid-stream
    const midFailingBody: any = {
      getReader: () => ({
        closed: Promise.resolve(),
        read: async () => {
          readCount++;
          if (readCount === 1) {
            return {
              done: false,
              value: encoder.encode(
                'data: {"id":"c1","choices":[{"delta":{"content":"Hello"}}]}\n\n',
              ),
            };
          }
          throw new Error('Network socket terminated abruptly mid-stream');
        },
        cancel: async () => {},
      }),
    };

    const { stream } = await StreamFailoverManager.createGuardedStream(
      midFailingBody,
      adapter,
      state,
    );

    // Now consume the stream as a client would
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    const receivedChunks: string[] = [];

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      receivedChunks.push(decoder.decode(value));
    }

    const fullResponse = receivedChunks.join('');

    // Verification of the critical Bifrost + Portkey rule:
    // 1. Initial valid chunk was delivered
    expect(fullResponse).toContain('data: {"id":"c1"');
    // 2. Explicit SSE error event was emitted to notify client
    expect(fullResponse).toContain('event: error');
    expect(fullResponse).toContain('stream_error');
    expect(fullResponse).toContain('Network socket terminated abruptly mid-stream');
    // 3. No silent restart or duplicate messages occurred
  });
});
