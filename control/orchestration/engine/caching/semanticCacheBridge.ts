/**
 * Semantic Vector Cache Bridge for L8 Orchestration Engine
 * Feature: 8.44 (Semantic Vector Caching in Orchestration)
 *
 * Prevents redundant LLM calls across agent workflows by caching responses
 * and matching incoming user/agent prompts based on cosine vector similarity.
 */

import { ExecutionRequest, ExecutionResponse } from '../types.js';

export interface SemanticCacheEntry {
  prompt: string;
  embedding: number[];
  response: ExecutionResponse;
  createdAt: number;
  expiresAt: number;
}

export interface SemanticCacheConfig {
  similarityThreshold?: number; // 0.0 to 1.0 (default: 0.90)
  ttlMs?: number; // default: 1 hour (3600000 ms)
}

export class SemanticCacheBridge {
  private entries: SemanticCacheEntry[] = [];
  readonly similarityThreshold: number;
  readonly ttlMs: number;

  constructor(config?: SemanticCacheConfig) {
    this.similarityThreshold = config?.similarityThreshold ?? 0.90;
    this.ttlMs = config?.ttlMs ?? 3600000;
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
   * Deterministic zero-dependency token bag-of-words embedding generator.
   */
  public static generateEmbedding(text: string, dimensions = 64): number[] {
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
      const idx = Math.abs(hash) % dimensions;
      vector[idx] += 1;
    }

    const norm = Math.sqrt(vector.reduce((sum, val) => sum + val * val, 0));
    return norm === 0 ? vector : vector.map((v) => v / norm);
  }

  /**
   * Extracts the primary prompt text from an ExecutionRequest.
   */
  public extractPrompt(request: ExecutionRequest): string {
    const userMsgs = request.messages.filter((m) => m.role === 'user');
    if (userMsgs.length > 0) {
      return userMsgs[userMsgs.length - 1].content;
    }
    return request.messages.map((m) => m.content).join('\n');
  }

  /**
   * Lookup matching cached response based on semantic similarity.
   */
  public get(request: ExecutionRequest): { response: ExecutionResponse; similarity: number } | null {
    const prompt = this.extractPrompt(request);
    if (!prompt) return null;

    const now = Date.now();
    // Prune expired
    this.entries = this.entries.filter((e) => e.expiresAt > now);

    const queryEmbedding = SemanticCacheBridge.generateEmbedding(prompt);

    let bestMatch: SemanticCacheEntry | null = null;
    let highestSim = 0;

    for (const entry of this.entries) {
      const sim = SemanticCacheBridge.cosineSimilarity(queryEmbedding, entry.embedding);
      if (sim > highestSim) {
        highestSim = sim;
        bestMatch = entry;
      }
    }

    if (bestMatch && highestSim >= this.similarityThreshold) {
      const cached = { ...bestMatch.response };
      cached.routeUsed = 'semantic-cache' as any;
      cached.cached = true;
      cached.similarityScore = highestSim;
      return { response: cached, similarity: highestSim };
    }

    return null;
  }

  /**
   * Store execution response in the semantic cache.
   */
  public set(request: ExecutionRequest, response: ExecutionResponse): void {
    const prompt = this.extractPrompt(request);
    if (!prompt) return;

    const embedding = SemanticCacheBridge.generateEmbedding(prompt);
    const now = Date.now();

    this.entries.push({
      prompt,
      embedding,
      response,
      createdAt: now,
      expiresAt: now + this.ttlMs,
    });
  }

  /**
   * Clear cache entries.
   */
  public clear(): void {
    this.entries = [];
  }

  public get size(): number {
    return this.entries.length;
  }
}
