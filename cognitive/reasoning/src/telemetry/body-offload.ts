import { createHash } from 'node:crypto';

export interface StorageOffloadConfig {
  thresholdBytes: number; // e.g. 50 * 1024 (50 KB)
  bucketName?: string;
  storageEndpoint?: string;
  enabled: boolean;
}

export interface OffloadResult {
  offloaded: boolean;
  referenceUrl?: string;
  sha256: string;
  byteSize: number;
  originalSnippet: string;
}

export interface ObjectStorageProvider {
  putObject(key: string, data: string | Uint8Array, contentType: string): Promise<string>;
}

export class MemoryObjectStorage implements ObjectStorageProvider {
  private store: Map<string, { data: string | Uint8Array; contentType: string }> = new Map();

  async putObject(key: string, data: string | Uint8Array, contentType: string): Promise<string> {
    this.store.set(key, { data, contentType });
    return `s3://mock-gateway-bucket/${key}`;
  }

  getObject(key: string): { data: string | Uint8Array; contentType: string } | undefined {
    return this.store.get(key);
  }
}

export class BodyOffloader {
  private config: StorageOffloadConfig;
  private storage: ObjectStorageProvider;

  constructor(config?: Partial<StorageOffloadConfig>, storage?: ObjectStorageProvider) {
    this.config = {
      thresholdBytes: config?.thresholdBytes ?? 50 * 1024,
      enabled: config?.enabled ?? true,
      bucketName: config?.bucketName || 'gateway-payloads',
      storageEndpoint: config?.storageEndpoint,
    };
    this.storage = storage || new MemoryObjectStorage();
  }

  async checkAndOffload(
    body: string | Record<string, any>,
    contextId: string,
  ): Promise<OffloadResult> {
    const rawString = typeof body === 'string' ? body : JSON.stringify(body);
    const byteSize = Buffer.byteLength(rawString, 'utf-8');
    const sha256 = createHash('sha256').update(rawString).digest('hex');

    if (!this.config.enabled || byteSize < this.config.thresholdBytes) {
      return {
        offloaded: false,
        sha256,
        byteSize,
        originalSnippet: rawString.slice(0, 100),
      };
    }

    const key = `payloads/${contextId}/${sha256}.json`;
    const referenceUrl = await this.storage.putObject(key, rawString, 'application/json');

    return {
      offloaded: true,
      referenceUrl,
      sha256,
      byteSize,
      originalSnippet: rawString.slice(0, 100) + '... [Offloaded to Object Storage]',
    };
  }
}
