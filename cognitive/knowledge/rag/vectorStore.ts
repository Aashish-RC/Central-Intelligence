/**
 * RAG Vector Store — in-memory cosine-similarity vector database.
 * Reference: AnythingLLM workspace pattern (pattern reference, no code copied).
 *
 * Design: pure Map<chunkId, EmbeddedChunk> with brute-force cosine similarity.
 * Suitable for Phase 3 demo scale (~thousands of chunks).
 */

import type { Chunk } from './chunker.js';

export interface EmbeddedChunk extends Chunk {
  vector: number[];
}

export interface ScoredChunk {
  chunk: EmbeddedChunk;
  score: number; // cosine similarity [0, 1]
}

class VectorStore {
  private store = new Map<string, EmbeddedChunk>();

  /** Insert or update chunks */
  upsert(chunks: EmbeddedChunk[]): void {
    for (const chunk of chunks) {
      this.store.set(chunk.id, chunk);
    }
  }

  /** Remove all chunks belonging to a source file */
  removeBySource(sourceFile: string): void {
    for (const [id, chunk] of this.store.entries()) {
      if (chunk.sourceFile === sourceFile) {
        this.store.delete(id);
      }
    }
  }

  /** Clear all stored chunks */
  clear(): void {
    this.store.clear();
  }

  /** Return total chunk count */
  get size(): number {
    return this.store.size;
  }

  /** Return all chunks for a source file */
  getBySource(sourceFile: string): EmbeddedChunk[] {
    return [...this.store.values()].filter((c) => c.sourceFile === sourceFile);
  }

  /**
   * Retrieve topK most similar chunks via brute-force cosine similarity.
   * @param queryVector Embedding vector for the user query
   * @param topK        Maximum results to return (default 5)
   * @param filter      Optional tenant filter by userId or spaceId
   */
  query(
    queryVector: number[],
    topK = 5,
    filter?: { userId?: string; spaceId?: string }
  ): ScoredChunk[] {
    if (this.store.size === 0) return [];

    const results: ScoredChunk[] = [];

    for (const chunk of this.store.values()) {
      // If user filtering is active, restrict access to own documents (or public unassigned docs)
      if (filter?.userId && chunk.userId && chunk.userId !== filter.userId) {
        continue;
      }
      if (filter?.spaceId && chunk.spaceId && chunk.spaceId !== filter.spaceId) {
        continue;
      }

      const score = cosineSimilarity(queryVector, chunk.vector);
      results.push({ chunk, score });
    }

    // Sort descending by score, return top K
    results.sort((a, b) => b.score - a.score);
    return results.slice(0, topK);
  }

  /** List all stored source files */
  listSources(): string[] {
    const sources = new Set<string>();
    for (const chunk of this.store.values()) {
      sources.add(chunk.sourceFile);
    }
    return [...sources];
  }
}

/**
 * Cosine similarity between two vectors of equal length.
 * Returns value in [-1, 1]; in practice embedding vectors yield [0, 1].
 */
function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length === 0 || b.length === 0) return 0;
  const len = Math.min(a.length, b.length);

  let dotProduct = 0;
  let magA = 0;
  let magB = 0;

  for (let i = 0; i < len; i++) {
    dotProduct += a[i] * b[i];
    magA += a[i] * a[i];
    magB += b[i] * b[i];
  }

  const denominator = Math.sqrt(magA) * Math.sqrt(magB);
  return denominator === 0 ? 0 : dotProduct / denominator;
}

// Global singleton store for the application session
export const vectorStore = new VectorStore();
