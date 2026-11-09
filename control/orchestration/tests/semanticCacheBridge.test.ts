import { test } from 'node:test';
import assert from 'node:assert';
import { ModelEngine, SemanticCacheBridge } from '../engine/index.js';
import { MockAdapter } from '../engine/providers/mockAdapter.js';

test('Feature 8.44: Semantic Vector Caching in L8 Orchestration', async (t) => {
  await t.test('computes cosine similarity and detects identical or similar queries', () => {
    const v1 = SemanticCacheBridge.generateEmbedding('How do I configure Redis cluster in production?');
    const v2 = SemanticCacheBridge.generateEmbedding('How do I configure Redis cluster in production?');
    const v3 = SemanticCacheBridge.generateEmbedding('Explain photosynthesis and plant biology chlorophyll.');

    const simIdentical = SemanticCacheBridge.cosineSimilarity(v1, v2);
    const simLow = SemanticCacheBridge.cosineSimilarity(v1, v3);

    assert.ok(Math.abs(simIdentical - 1.0) < 1e-4, `Expected 1.0, got ${simIdentical}`);
    assert.ok(simLow < 0.2, `Expected low similarity, got ${simLow}`);
  });

  await t.test('caches responses and serves cache hits on cached prompts', async () => {
    const mockAdapter = new MockAdapter('pooled-aggregator');

    const engine = new ModelEngine({
      enableSemanticCache: true,
      semanticCacheConfig: { similarityThreshold: 0.8 },
      routerConfig: {
        customAdapters: [mockAdapter],
        enterpriseAdapter: mockAdapter as any,
      },
    });

    // 1st request - Misses cache, calls mock adapter
    const req1 = {
      messages: [{ role: 'user' as const, content: 'How do I configure Redis cluster in production?' }],
      model: 'anthropic/claude-3-5-sonnet',
    };
    const res1 = await engine.execute(req1);
    assert.ok(res1.text.includes('Mock: Claude 3.5 Sonnet'));
    assert.strictEqual(res1.cached, undefined);

    // 2nd request with identical or high similarity wording - Serves from semantic cache
    const req2 = {
      messages: [{ role: 'user' as const, content: 'How do I configure Redis cluster in production?' }],
      model: 'anthropic/claude-3-5-sonnet',
    };
    const res2 = await engine.execute(req2);
    assert.strictEqual(res2.text, res1.text);
    assert.strictEqual(res2.cached, true);
    assert.strictEqual(res2.routeUsed, 'semantic-cache');
    assert.ok(res2.similarityScore! >= 0.8);
  });

  await t.test('misses cache for semantically unrelated requests', async () => {
    const mockAdapter = new MockAdapter('pooled-aggregator');
    const engine = new ModelEngine({
      enableSemanticCache: true,
      routerConfig: {
        customAdapters: [mockAdapter],
        enterpriseAdapter: mockAdapter as any,
      },
    });

    await engine.execute({
      messages: [{ role: 'user' as const, content: 'Python dictionary comprehension tutorial' }],
      model: 'anthropic/claude-3-5-sonnet',
    });

    const resUnrelated = await engine.execute({
      messages: [{ role: 'user' as const, content: 'Quantum computing qubit superposition' }],
      model: 'anthropic/claude-3-5-sonnet',
    });

    assert.strictEqual(resUnrelated.cached, undefined);
    assert.notStrictEqual(resUnrelated.routeUsed, 'semantic-cache');
  });
});
