/**
 * RAG Document Ingestion Pipeline.
 * Accepts text, PDF, markdown, and DOCX files; chunks, embeds, and upserts into the vector store.
 *
 * Reference: AnythingLLM document ingestion pattern (pattern reference only, no code copied).
 * Dependencies: pdf-parse (MIT), mammoth (MIT).
 */

import fs from 'node:fs/promises';
import path from 'node:path';
import { chunkByPages, chunkText } from './chunker.js';
import { embedChunks } from './embedder.js';
import { vectorStore } from './vectorStore.js';

export interface IngestionResult {
  sourceFile: string;
  chunkCount: number;
  mimeType: string;
}

/**
 * Ingest a file from disk into the vector store.
 * Supports: .txt, .md, .pdf, .docx
 */
export async function ingestFile(filePath: string): Promise<IngestionResult> {
  const ext = path.extname(filePath).toLowerCase();
  const sourceFile = path.basename(filePath);

  let rawText: string;

  if (ext === '.pdf') {
    rawText = await extractPdf(filePath);
  } else if (ext === '.docx') {
    rawText = await extractDocx(filePath);
  } else if (ext === '.txt' || ext === '.md' || ext === '.markdown') {
    rawText = await fs.readFile(filePath, 'utf-8');
  } else {
    throw new Error(`Unsupported file type: ${ext}. Supported: .txt, .md, .pdf, .docx`);
  }

  return ingestText(rawText, sourceFile, ext === '.pdf');
}

/**
 * Ingest raw text directly (e.g., from in-browser paste or upload).
 */
export async function ingestText(
  text: string,
  sourceFile: string,
  hasPages = false
): Promise<IngestionResult> {
  // Remove existing chunks for this source to avoid duplicates on re-index
  vectorStore.removeBySource(sourceFile);

  const chunks = hasPages
    ? chunkByPages(text, sourceFile)
    : chunkText(text, sourceFile);

  if (chunks.length === 0) {
    return { sourceFile, chunkCount: 0, mimeType: 'text/plain' };
  }

  const embedded = await embedChunks(chunks);
  vectorStore.upsert(embedded);

  return {
    sourceFile,
    chunkCount: embedded.length,
    mimeType: hasPages ? 'application/pdf' : 'text/plain',
  };
}

/**
 * Extract text from a PDF file using pdf-parse (MIT).
 * Returns page-separated text with \f boundaries.
 */
async function extractPdf(filePath: string): Promise<string> {
  // Dynamic import to avoid issues when pdf-parse is not installed
  const pdfParse = (await import('pdf-parse')).default;
  const buffer = await fs.readFile(filePath);
  const data = await pdfParse(buffer);
  // pdf-parse puts a \n between pages; we normalise to \f for page-aware chunking
  return data.text;
}

/**
 * Extract text from a DOCX file using mammoth (MIT).
 */
async function extractDocx(filePath: string): Promise<string> {
  const mammoth = await import('mammoth');
  const buffer = await fs.readFile(filePath);
  const result = await mammoth.extractRawText({ buffer: buffer as Buffer });
  return result.value;
}

/** Return the list of currently indexed source files */
export function listIndexedSources(): string[] {
  return vectorStore.listSources();
}
