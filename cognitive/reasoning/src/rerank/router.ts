import crypto from 'node:crypto';
import { SemanticCache } from '../caching/semantic.js';

export interface RerankDocument {
  text?: string;
  [key: string]: unknown;
}

export interface RerankRequest {
  model: string;
  query: string;
  documents: Array<string | RerankDocument>;
  top_n?: number;
}

export interface RerankResultItem {
  index: number;
  document?: RerankDocument | string;
  relevance_score: number;
}

export interface RerankResponse {
  id: string;
  results: RerankResultItem[];
  meta: {
    billed_units: {
      search_units: number;
      total_documents: number;
    };
  };
}

export class RerankEngine {
  /**
   * Reranks candidate documents against a query string based on semantic relevance.
   */
  public static rerank(req: RerankRequest): RerankResponse {
    const { query, documents, top_n, model } = req;
    if (!documents || documents.length === 0) {
      return {
        id: `rerank-${crypto.randomUUID()}`,
        results: [],
        meta: {
          billed_units: { search_units: 1, total_documents: 0 },
        },
      };
    }

    const queryEmbedding = SemanticCache.generateSimpleEmbedding(query);

    const scored: RerankResultItem[] = documents.map((doc, index) => {
      const text = typeof doc === 'string' ? doc : doc.text || JSON.stringify(doc);
      const docEmbedding = SemanticCache.generateSimpleEmbedding(text);
      const score = Math.max(0, SemanticCache.cosineSimilarity(queryEmbedding, docEmbedding));

      return {
        index,
        document: doc,
        relevance_score: Number.parseFloat(score.toFixed(4)),
      };
    });

    // Sort descending by relevance score
    scored.sort((a, b) => b.relevance_score - a.relevance_score);

    const limit = top_n && top_n > 0 ? top_n : scored.length;
    const results = scored.slice(0, limit);

    return {
      id: `rerank-${crypto.randomUUID()}`,
      results,
      meta: {
        billed_units: {
          search_units: 1,
          total_documents: documents.length,
        },
      },
    };
  }
}
