import { describe, expect, it } from 'vitest';
import { ClaimDecomposer } from '../../src/synthesis/claimDecomposer.js';

describe('Sub-module B: Claim Decomposition Engine (4.08, 11.14)', () => {
  it('decomposes composite statements into atomic propositions', async () => {
    const decomposer = new ClaimDecomposer();
    const text = 'Paris is the capital of France and also it is located in Europe. Tokyo is the capital of Japan.';
    const claims = await decomposer.decompose(text);

    expect(claims.length).toBeGreaterThanOrEqual(2);
    expect(claims.some((c) => c.includes('Paris'))).toBe(true);
    expect(claims.some((c) => c.includes('Tokyo'))).toBe(true);
  });

  it('verifies supported claims and flags uncorroborated claims', async () => {
    const decomposer = new ClaimDecomposer({ reliabilityThreshold: 0.7 });
    const text = 'Paris is the capital of France. The moon is made of green cheese.';
    const knowledge = [
      'France is a country in Europe. Paris is the capital city of France.',
      'The moon is composed of silicate rock and iron core.',
    ];

    const result = await decomposer.decomposeAndVerify(text, knowledge);

    expect(result.claims.length).toBe(2);
    // Paris claim is corroborated
    const parisClaim = result.claims.find((c) => c.claim.includes('Paris'));
    expect(parisClaim?.verified).toBe(true);
    expect(parisClaim?.confidence).toBeGreaterThanOrEqual(0.5);

    // Green cheese claim is unverified
    const moonClaim = result.claims.find((c) => c.claim.includes('cheese'));
    expect(moonClaim?.verified).toBe(false);
    expect(result.unverifiedClaims.length).toBe(1);
    expect(result.isReliable).toBe(false); // 1 out of 2 is 50%, below 70% threshold
  });

  it('supports custom LLM decomposer and verifier hooks', async () => {
    const decomposer = new ClaimDecomposer({
      decomposeFn: async (t) => t.split('|').map((s) => s.trim()),
      verifierFn: async (c) => ({
        verified: !c.includes('hallucination'),
        confidence: c.includes('hallucination') ? 0.1 : 0.99,
      }),
    });

    const result = await decomposer.decomposeAndVerify('Claim A | Claim B hallucination');
    expect(result.claims.length).toBe(2);
    expect(result.claims[0].verified).toBe(true);
    expect(result.claims[1].verified).toBe(false);
    expect(result.supportedRatio).toBe(0.5);
  });
});
