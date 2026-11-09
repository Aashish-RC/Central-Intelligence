import { describe, expect, it } from 'vitest';
import { MoAFusionAggregator } from '../../src/synthesis/moaFusion.js';

describe('Sub-module C: Mixture of Agents (MoA) Fusion Aggregator (4.08, 11.14)', () => {
  it('fuses candidate outputs from 3+ models into a unified synthesis', async () => {
    const moa = new MoAFusionAggregator();
    const prompt = 'How do we design a highly available database cluster?';
    const candidates = [
      {
        model: 'claude-3-5-sonnet',
        content: 'Use Raft consensus for leader election. Configure multi-region active-passive replicas.',
        confidence: 0.9,
      },
      {
        model: 'gpt-4o',
        content: 'Implement write-ahead logging (WAL) for durability. Use connection pooling to prevent exhaustion.',
        confidence: 0.88,
      },
      {
        model: 'gemini-1.5-pro',
        content: 'Ensure automated failover with health checks. Implement distributed backup snapshots.',
        confidence: 0.85,
      },
    ];

    const knowledge = [
      'Database clustering uses consensus like Raft for leader election and active replicas.',
      'Durability relies on write-ahead logging and health-check driven failover.',
    ];

    const result = await moa.fuse(prompt, candidates, knowledge);

    expect(result.modelCount).toBe(3);
    expect(result.synthesizedText.length).toBeGreaterThan(50);
    // All 3 candidate concepts should be present in fused response
    expect(result.synthesizedText).toContain('Raft consensus');
    expect(result.synthesizedText).toContain('write-ahead logging');
    expect(result.synthesizedText).toContain('failover');
    expect(result.consensusScore).toBeGreaterThan(0.2);
    expect(result.claimVerification).toBeDefined();
    expect(result.claimVerification?.claims.length).toBeGreaterThan(0);
  });

  it('supports custom LLM aggregator function', async () => {
    const customMoA = new MoAFusionAggregator({
      aggregatorFn: async (_prompt, cands) => {
        return `Custom synthesized consensus across ${cands.length} models: ${cands.map((c) => c.model).join(', ')}.`;
      },
    });

    const result = await customMoA.fuse('Test query', [
      { model: 'model-a', content: 'A answer' },
      { model: 'model-b', content: 'B answer' },
    ]);

    expect(result.synthesizedText).toBe('Custom synthesized consensus across 2 models: model-a, model-b.');
    expect(result.modelCount).toBe(2);
  });

  it('returns candidate directly when only 1 candidate provided', async () => {
    const moa = new MoAFusionAggregator();
    const result = await moa.fuse('Simple prompt', [
      { model: 'fast-model', content: 'Direct simple response.' },
    ]);

    expect(result.modelCount).toBe(1);
    expect(result.synthesizedText).toBe('Direct simple response.');
    expect(result.consensusScore).toBe(1.0);
  });
});
