/**
 * RAG Chunker — splits document text into overlapping chunks for embedding.
 * Reference: AnythingLLM workspace ingestion pattern (pattern reference only, no code copied).
 */

import { nanoid } from 'nanoid';

export interface Chunk {
  id: string;
  text: string;
  sourceFile: string;
  pageNumber?: number;
  charOffset: number;
  userId?: string;
  spaceId?: string;
}

/**
 * Splits text into overlapping chunks suitable for embedding.
 * @param text       Full document text
 * @param sourceFile Path or filename for citation
 * @param chunkSize  Target character count per chunk (default 500)
 * @param overlap    Character overlap between consecutive chunks (default 50)
 */
export function chunkText(
  text: string,
  sourceFile: string,
  chunkSize = 500,
  overlap = 50
): Chunk[] {
  if (!text || text.trim().length === 0) return [];

  const chunks: Chunk[] = [];
  let offset = 0;

  while (offset < text.length) {
    const end = Math.min(offset + chunkSize, text.length);
    const chunkText = text.slice(offset, end).trim();

    if (chunkText.length > 0) {
      chunks.push({
        id: `chunk-${nanoid(10)}`,
        text: chunkText,
        sourceFile,
        charOffset: offset,
      });
    }

    // Move forward by (chunkSize - overlap), but ensure progress
    offset += Math.max(1, chunkSize - overlap);

    if (end >= text.length) break;
  }

  return chunks;
}

/**
 * Splits text into page-aware chunks using form-feed (\f) as a page boundary.
 * PDF extractors typically emit a \f between pages.
 */
export function chunkByPages(text: string, sourceFile: string, chunkSize = 500, overlap = 50): Chunk[] {
  const pages = text.split('\f');
  const allChunks: Chunk[] = [];
  let globalOffset = 0;

  for (let pageIdx = 0; pageIdx < pages.length; pageIdx++) {
    const pageText = pages[pageIdx];
    const pageChunks = chunkText(pageText, sourceFile, chunkSize, overlap);

    for (const chunk of pageChunks) {
      allChunks.push({
        ...chunk,
        pageNumber: pageIdx + 1,
        charOffset: globalOffset + chunk.charOffset,
      });
    }

    globalOffset += pageText.length + 1; // +1 for \f
  }

  return allChunks;
}
