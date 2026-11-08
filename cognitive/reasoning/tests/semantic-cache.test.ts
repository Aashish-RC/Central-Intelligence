import { beforeEach, describe, expect, it } from 'vitest';
import { SemanticCache } from '../src/caching/semantic.js';
import type { ChatCompletionResponse } from '../src/types/chat.js';

describe('Feature 21: Semantic Vector Similarity Caching', () => {
  let cache: SemanticCache;

  const mockResponse: ChatCompletionResponse = {
    id: 'chatcmpl-cached-1',
    object: 'chat.completion',
    created: 1729270000,
    model: 'gpt-4o',
    choices: [
      {
        index: 0,
        message: { role: 'assistant', content: 'Paris is the capital of France.' },
        finish_reason: 'stop',
      },
    ],
    usage: { prompt_tokens: 8, completion_tokens: 7, total_tokens: 15 },
  };

  beforeEach(() => {
    cache = new SemanticCache({ similarityThreshold: 0.85 });
    cache.clear();
  });

  it('computes mathematical cosine similarity accurately', () => {
    const v1 = [1, 0, 0];
    const v2 = [1, 0, 0];
    const v3 = [0, 1, 0];

    expect(SemanticCache.cosineSimilarity(v1, v2)).toBeCloseTo(1.0);
    expect(SemanticCache.cosineSimilarity(v1, v3)).toBeCloseTo(0.0);
  });

  it('serves cached response for semantically identical prompts', () => {
    cache.set('What is the capital city of France?', mockResponse);

    // Identical prompt
    const lookup1 = cache.get('What is the capital city of France?');
    expect(lookup1.hit).toBe(true);
    expect(lookup1.similarity).toBeCloseTo(1.0);
    expect(lookup1.response?.choices[0].message.content).toBe('Paris is the capital of France.');

    // Near identical wording
    const lookup2 = cache.get('what is the capital city of France');
    expect(lookup2.hit).toBe(true);
    expect(lookup2.similarity).toBeGreaterThanOrEqual(0.9);
  });

  it('misses cache for semantically unrelated queries', () => {
    cache.set('What is the capital of France?', mockResponse);

    const lookup = cache.get('How do quantum computers work with qubits?');
    expect(lookup.hit).toBe(false);
    expect(lookup.response).toBeUndefined();
  });
});
