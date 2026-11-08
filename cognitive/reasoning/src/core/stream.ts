import type { ProviderAdapter, StreamTransformState } from '../types/provider.js';

export class StreamNormalizer {
  public static createTransformStream(
    adapter: ProviderAdapter,
    state: StreamTransformState,
  ): TransformStream<Uint8Array, Uint8Array> {
    const textDecoder = new TextDecoder();
    const textEncoder = new TextEncoder();
    let residualBuffer = '';

    return new TransformStream({
      transform(chunk, controller) {
        residualBuffer += textDecoder.decode(chunk, { stream: true });
        const lines = residualBuffer.split('\n\n');
        // The last segment may be incomplete, hold it in residualBuffer
        residualBuffer = lines.pop() || '';

        for (const block of lines) {
          const trimmed = block.trim();
          if (!trimmed) continue;

          // For standard SSE data lines
          const transformed = adapter.transformStreamChunk(trimmed, state);
          if (transformed) {
            controller.enqueue(textEncoder.encode(transformed));
          }
        }
      },
      flush(controller) {
        if (residualBuffer.trim()) {
          const transformed = adapter.transformStreamChunk(residualBuffer.trim(), state);
          if (transformed) {
            controller.enqueue(textEncoder.encode(transformed));
          }
        }
      },
    });
  }
}
