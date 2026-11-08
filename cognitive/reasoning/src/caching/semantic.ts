import type { ChatCompletionResponse } from '../types/chat.js';

export interface SemanticCacheEntry {
  prompt: string;
  embedding: number[];
  response: ChatCompletionResponse;
  createdAt: number;
  expiresAt: number;
}

export interface SemanticCacheOptions {
  similarityThreshold?: number; // 0.0 to 1.0 (default 0.90)
  ttlMs?: number; // default 1 hour
}

export class SemanticCache {
  private entries: SemanticCacheEntry[] = [];
  private similarityThreshold: number;
  private defaultTtlMs: number;

  constructor(options: SemanticCacheOptions = {}) {
    this.similarityThreshold = options.similarityThreshold ?? 0.9;
    this.defaultTtlMs = options.ttlMs ?? 3600000;
  }

  /**
   * Computes cosine similarity between two numeric vectors.
   */
  public static cosineSimilarity(a: number[], b: number[]): number {
    if (a.length !== b.length || a.length === 0) return 0;

    let dot = 0;
    let normA = 0;
    let normB = 0;

    for (let i = 0; i < a.length; i++) {
      dot += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }

    if (normA === 0 || normB === 0) return 0;
    return dot / (Math.sqrt(normA) * Math.sqrt(normB));
  }

  /**
   * Deterministic zero-dependency character/token bag-of-words embedding generator for tests and local mode.
   */
  public static generateSimpleEmbedding(text: string, dimensions = 64): number[] {
    const vector = new Array(dimensions).fill(0);
    const tokens = text
      .toLowerCase()
      .replace(/[^\w\s]/g, '')
      .split(/\s+/)
      .filter(Boolean);

    for (const token of tokens) {
      let hash = 0;
      for (let i = 0; i < token.length; i++) {
        hash = (hash << 5) - hash + token.charCodeAt(i);
        hash |= 0;
      }
      const dim = Math.abs(hash) % dimensions;
      vector[dim] += 1;
    }

    // Normalize vector to unit length
    let norm = 0;
    for (let i = 0; i < dimensions; i++) {
      norm += vector[i] * vector[i];
    }
    if (norm > 0) {
      const sqrtNorm = Math.sqrt(norm);
      for (let i = 0; i < dimensions; i++) {
        vector[i] /= sqrtNorm;
      }
    }

    return vector;
  }

  public set(
    prompt: string,
    response: ChatCompletionResponse,
    customEmbedding?: number[],
    ttlMs?: number,
  ): void {
    const embedding = customEmbedding || SemanticCache.generateSimpleEmbedding(prompt);
    const now = Date.now();
    const expiresAt = now + (ttlMs ?? this.defaultTtlMs);

    this.entries.push({
      prompt,
      embedding,
      response,
      createdAt: now,
      expiresAt,
    });
  }

  public get(
    prompt: string,
    customEmbedding?: number[],
  ): { hit: boolean; response?: ChatCompletionResponse; similarity?: number } {
    const queryEmbedding = customEmbedding || SemanticCache.generateSimpleEmbedding(prompt);
    const now = Date.now();

    // Evict expired entries
    this.entries = this.entries.filter((e) => e.expiresAt > now);

    let bestSimilarity = -1;
    let bestEntry: SemanticCacheEntry | null = null;

    for (const entry of this.entries) {
      const sim = SemanticCache.cosineSimilarity(queryEmbedding, entry.embedding);
      if (sim > bestSimilarity) {
        bestSimilarity = sim;
        bestEntry = entry;
      }
    }

    if (bestEntry && bestSimilarity >= this.similarityThreshold) {
      return {
        hit: true,
        response: {
          ...bestEntry.response,
          // Tag cached response
          id: `${bestEntry.response.id}-semantic-cache`,
        },
        similarity: bestSimilarity,
      };
    }

    return { hit: false, similarity: bestSimilarity > 0 ? bestSimilarity : 0 };
  }

  public clear(): void {
    this.entries = [];
  }

  public size(): number {
    return this.entries.length;
  }
}
