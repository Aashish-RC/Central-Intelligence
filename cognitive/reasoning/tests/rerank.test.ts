import { describe, expect, it } from 'vitest';
import { createGatewayApp } from '../src/core/server.js';
import { RerankEngine } from '../src/rerank/router.js';

describe('Feature 30: Semantic Reranking API (/v1/rerank for RAG)', () => {
  it('ranks documents according to semantic relevance and respects top_n', () => {
    const query = 'What is the capital of Japan?';
    const documents = [
      'Berlin is the capital of Germany.',
      'Tokyo is the capital and largest city of Japan.',
      'Ottawa is the capital of Canada.',
    ];

    const response = RerankEngine.rerank({
      model: 'bge-reranker-large',
      query,
      documents,
      top_n: 2,
    });

    expect(response.results.length).toBe(2);
    // Tokyo should be rank #1
    expect(response.results[0].index).toBe(1);
    expect(response.results[0].document).toBe('Tokyo is the capital and largest city of Japan.');
    expect(response.results[0].relevance_score).toBeGreaterThan(
      response.results[1].relevance_score,
    );
  });

  it('serves HTTP POST /v1/rerank with JSON documents and returns 200 OK', async () => {
    const { app } = createGatewayApp();
    const res = await app.request('/v1/rerank', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'bge-reranker-v2',
        query: 'machine learning algorithms',
        documents: [
          {
            text: 'Gradient boosting and random forests are tree-based machine learning algorithms.',
          },
          { text: 'A recipe for chocolate chip cookies with flour and sugar.' },
        ],
      }),
    });

    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.id).toMatch(/^rerank-/);
    expect(data.results[0].index).toBe(0);
    expect(data.results[0].relevance_score).toBeGreaterThan(data.results[1].relevance_score);
  });
});
