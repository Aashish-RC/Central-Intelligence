/**
 * RAG Retriever — embeds a query and retrieves the most relevant chunks.
 * Returns structured Citation objects for inline rendering in chat.
 */

import { embedChunks } from './embedder.js';
import { vectorStore } from './vectorStore.js';
import type { Citation } from '../chat/chatService.js';

/**
 * Retrieve topK most relevant chunks for a given query string.
 * Returns empty array if vector store is empty.
 */
export async function retrieve(
  query: string,
  topK = 5,
  filter?: { userId?: string; spaceId?: string }
): Promise<Citation[]> {
  if (vectorStore.size === 0) return [];

  // Embed the query using the same embedder (real or stub)
  const [queryEmbedded] = await embedChunks([
    {
      id: 'query',
      text: query,
      sourceFile: '__query__',
      charOffset: 0,
    },
  ]);

  const scored = vectorStore.query(queryEmbedded.vector, topK, filter);

  return scored.map((s, i) => ({
    index: i + 1,
    chunkId: s.chunk.id,
    sourceFile: s.chunk.sourceFile,
    pageNumber: s.chunk.pageNumber,
    charOffset: s.chunk.charOffset,
    excerpt: s.chunk.text.slice(0, 200) + (s.chunk.text.length > 200 ? '…' : ''),
    score: s.score,
  }));
}
