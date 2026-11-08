/**
 * RAG Embedder — converts text chunks into embedding vectors.
 *
 * Real path: calls text-embedding-ada-002 via OpenRouter aggregator
 *   when OPENROUTER_API_KEY or AGGREGATOR_API_KEY is set.
 *
 * Stub path (test mode / no key): produces a deterministic local fingerprint
 *   vector of dimension 1536, sufficient for cosine similarity ranking.
 *
 * Reference: AnythingLLM document ingestion pattern (pattern reference, no code copied).
 */

import type { Chunk } from './chunker.js';
import type { EmbeddedChunk } from './vectorStore.js';

const EMBEDDING_DIM = 1536;
const OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/embeddings';
const EMBEDDING_MODEL = 'openai/text-embedding-ada-002';

/**
 * Embed a batch of text chunks.
 * Automatically switches between real and stub mode based on environment.
 */
export async function embedChunks(chunks: Chunk[]): Promise<EmbeddedChunk[]> {
  const env = typeof process !== 'undefined' && process.env ? process.env : {} as Record<string, string | undefined>;
  const apiKey = env.OPENROUTER_API_KEY || env.AGGREGATOR_API_KEY;

  if (apiKey) {
    return embedChunksReal(chunks, apiKey);
  } else {
    return embedChunksStub(chunks);
  }
}

/**
 * Real embedding via OpenRouter aggregator (text-embedding-ada-002).
 * Batches up to 20 chunks per request to respect rate limits.
 */
async function embedChunksReal(chunks: Chunk[], apiKey: string): Promise<EmbeddedChunk[]> {
  const results: EmbeddedChunk[] = [];
  const batchSize = 20;

  for (let i = 0; i < chunks.length; i += batchSize) {
    const batch = chunks.slice(i, i + batchSize);
    const texts = batch.map((c) => c.text);

    const res = await fetch(OPENROUTER_API_URL, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://ra1.local',
        'X-Title': 'Ra1 RAG Pipeline',
      },
      body: JSON.stringify({ input: texts, model: EMBEDDING_MODEL }),
    });

    if (!res.ok) {
      console.warn(`[embedder] Embedding API returned ${res.status}, falling back to stub for batch`);
      const stubbed = await embedChunksStub(batch);
      results.push(...stubbed);
      continue;
    }

    const data = (await res.json()) as { data: Array<{ embedding: number[] }> };

    for (let j = 0; j < batch.length; j++) {
      results.push({
        ...batch[j],
        vector: data.data[j].embedding,
      });
    }
  }

  return results;
}

/**
 * Deterministic stub embedding: produces a pseudo-embedding from char codes.
 * Not semantically meaningful, but supports cosine similarity tests without API.
 */
async function embedChunksStub(chunks: Chunk[]): Promise<EmbeddedChunk[]> {
  return chunks.map((chunk) => ({
    ...chunk,
    vector: stubVector(chunk.text),
  }));
}

function stubVector(text: string): number[] {
  const vec = new Array<number>(EMBEDDING_DIM).fill(0);
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    vec[i % EMBEDDING_DIM] += code / 127;
  }
  // Normalize to unit vector
  const mag = Math.sqrt(vec.reduce((s, v) => s + v * v, 0));
  return mag === 0 ? vec : vec.map((v) => v / mag);
}
