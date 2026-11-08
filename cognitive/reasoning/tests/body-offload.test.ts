import { describe, expect, it } from 'vitest';
import { BodyOffloader, MemoryObjectStorage } from '../src/telemetry/body-offload.js';

describe('Feature 31: Asynchronous Large Body Offload to S3/R2', () => {
  it('does not offload small payloads below threshold', async () => {
    const offloader = new BodyOffloader({ thresholdBytes: 1024 });
    const result = await offloader.checkAndOffload({ message: 'small payload' }, 'req-1');

    expect(result.offloaded).toBe(false);
    expect(result.referenceUrl).toBeUndefined();
    expect(result.sha256).toBeDefined();
  });

  it('offloads large payloads exceeding threshold to object storage', async () => {
    const storage = new MemoryObjectStorage();
    const offloader = new BodyOffloader({ thresholdBytes: 500 }, storage);
    const largeText = 'A'.repeat(1200);

    const result = await offloader.checkAndOffload({ content: largeText }, 'req-2');
    expect(result.offloaded).toBe(true);
    expect(result.referenceUrl).toContain('s3://mock-gateway-bucket/payloads/req-2/');
    expect(result.originalSnippet).toContain('[Offloaded to Object Storage]');
  });
});
