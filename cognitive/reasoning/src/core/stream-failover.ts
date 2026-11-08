import type { ProviderAdapter, StreamTransformState } from '../types/provider.js';

export interface GuardedStreamOptions {
  preflightTimeoutMs?: number;
}

export class StreamFailoverManager {
  /**
   * Creates an SSE stream that safely handles pre-first-byte and post-first-byte failures.
   * If a failure occurs before the first byte is emitted to the consumer, it throws so callers can failover.
   * If a failure occurs after the first byte is emitted, it writes an explicit SSE error event and closes the stream cleanly.
   */
  public static async createGuardedStream(
    upstreamBody: ReadableStream<Uint8Array>,
    adapter: ProviderAdapter,
    state: StreamTransformState,
    options?: GuardedStreamOptions,
  ): Promise<{ stream: ReadableStream<Uint8Array> }> {
    const reader = upstreamBody.getReader();
    // Catch unhandled rejection on reader.closed when upstream terminates
    reader.closed.catch(() => {});
    const encoder = new TextEncoder();
    const decoder = new TextDecoder();
    let residualBuffer = '';
    const initialChunks: Uint8Array[] = [];

    // Helper to format SSE error event
    const formatSSEError = (message: string, code = 500): Uint8Array => {
      const payload = JSON.stringify({
        error: {
          message,
          type: 'stream_error',
          code,
        },
      });
      return encoder.encode(`event: error\ndata: ${payload}\n\n`);
    };

    const preflightTimeout = options?.preflightTimeoutMs ?? 15000;

    // Pre-flight check with timeout: read until we have at least one transformed chunk or stream completes
    const readWithTimeout = async () => {
      let timer: any;
      const timeoutPromise = new Promise<never>((_, reject) => {
        timer = setTimeout(() => {
          reject(new Error(`Upstream stream pre-first-byte timed out after ${preflightTimeout}ms`));
        }, preflightTimeout);
      });

      try {
        while (initialChunks.length === 0) {
          const { done, value } = await Promise.race([reader.read(), timeoutPromise]);
          if (done) {
            if (residualBuffer.trim()) {
              const transformed = adapter.transformStreamChunk(residualBuffer.trim(), state);
              if (transformed) {
                initialChunks.push(encoder.encode(transformed));
              }
            }
            break;
          }

          residualBuffer += decoder.decode(value, { stream: true });
          const parts = residualBuffer.split('\n\n');
          residualBuffer = parts.pop() || '';

          for (const block of parts) {
            const trimmed = block.trim();
            if (!trimmed) continue;
            const transformed = adapter.transformStreamChunk(trimmed, state);
            if (transformed) {
              initialChunks.push(encoder.encode(transformed));
            }
          }
        }
      } finally {
        clearTimeout(timer);
      }
    };

    await readWithTimeout();

    // Now construct the response stream. Because initialChunks has data, firstByte has been emitted!
    let firstByteEmitted = initialChunks.length > 0;

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of initialChunks) {
          controller.enqueue(chunk);
        }
      },

      async pull(controller) {
        try {
          const { done, value } = await reader.read();
          if (done) {
            if (residualBuffer.trim()) {
              const transformed = adapter.transformStreamChunk(residualBuffer.trim(), state);
              if (transformed) {
                controller.enqueue(encoder.encode(transformed));
              }
            }
            controller.close();
            return;
          }

          residualBuffer += decoder.decode(value, { stream: true });
          const parts = residualBuffer.split('\n\n');
          residualBuffer = parts.pop() || '';

          for (const block of parts) {
            const trimmed = block.trim();
            if (!trimmed) continue;
            const transformed = adapter.transformStreamChunk(trimmed, state);
            if (transformed) {
              controller.enqueue(encoder.encode(transformed));
              firstByteEmitted = true;
            }
          }
        } catch (err: any) {
          if (firstByteEmitted) {
            // Post-first-byte failure: MUST emit explicit SSE error event and never re-send or restart
            controller.enqueue(
              formatSSEError(err?.message || 'Upstream stream interrupted mid-transmission'),
            );
            controller.close();
          } else {
            controller.error(err);
          }
        }
      },

      async cancel(reason) {
        await reader.cancel(reason);
      },
    });

    return { stream };
  }
}
