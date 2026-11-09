import { describe, expect, it } from 'vitest';
import { TieredActivationGate } from '../../src/synthesis/tieredActivation.js';

describe('Sub-module D: Tiered Activation Gate (4.08, 11.14)', () => {
  const gate = new TieredActivationGate();

  it('routes simple tasks directly to Tier 0 without synthesis overhead', async () => {
    const res = await gate.run({
      task: "what's 2+2",
    });

    expect(res.activatedTier).toBe(0);
    expect(res.escalatedToSecondOpinion).toBe(false);
    expect(res.finalText).toBe('4');
    expect(res.prmEvaluation).toBeUndefined();
    expect(res.moaFusion).toBeUndefined();
  });

  it('routes moderate tasks to Tier 1 with Claim Decomposition fact-checking', async () => {
    const res = await gate.run({
      task: 'Provide a concise overview of cognitive micro-architectures.',
      context: ['Micro-architectures organize cognitive loops into composable modular units.'],
    });

    expect(res.activatedTier).toBe(1);
    expect(res.claimVerification).toBeDefined();
    expect(res.moaFusion).toBeUndefined();
  });

  it('routes complex reasoning tasks to Tier 2 with PRM step verification', async () => {
    const res = await gate.run({
      task: 'Solve step by step and calculate the total permutation count.',
      steps: [
        'Step 1: Compute factorial of 5.',
        'Step 2: 5! = 5 * 4 * 3 * 2 * 1 = 120.',
        'Step 3: Therefore the total permutations is 120.',
      ],
      context: ['Permutations of n distinct elements is calculated by n factorial.'],
    });

    expect(res.activatedTier).toBe(2);
    expect(res.prmEvaluation).toBeDefined();
    expect(res.prmEvaluation?.isValidTrace).toBe(true);
    expect(res.claimVerification).toBeDefined();
  });

  it('routes high-stakes distributed architecture tasks to Tier 3 with full MoA fusion', async () => {
    const res = await gate.run({
      task: 'Design a distributed system architecture with multi-region consensus protocol and high stakes security audit.',
      candidateModels: ['claude-3-5-sonnet', 'gpt-4o', 'gemini-1.5-pro'],
    });

    expect(res.activatedTier).toBe(3);
    expect(res.moaFusion).toBeDefined();
    expect(res.moaFusion?.candidates.length).toBe(3);
    expect(res.prmEvaluation).toBeDefined();
    expect(res.claimVerification).toBeDefined();
  });

  it('escalates to Tier 3 when initial accuracy/confidence score is below 0.5 (second opinion)', async () => {
    const res = await gate.run({
      task: "what's 2+2",
      initialAccuracyScore: 0.35, // Low initial accuracy / confidence triggers second opinion
    });

    expect(res.activatedTier).toBe(3);
    expect(res.escalatedToSecondOpinion).toBe(true);
    expect(res.moaFusion).toBeDefined();
  });

  it('integrates with GatewayEngine via enableSynthesis request option', async () => {
    const { GatewayEngine } = await import('../../src/core/engine.js');
    const { ModelRouter } = await import('../../src/routing/router.js');
    const { CooldownTracker } = await import('../../src/resilience/cooldown.js');

    const cooldownTracker = new CooldownTracker();
    const router = new ModelRouter(cooldownTracker);
    const engine = new GatewayEngine({
      router,
      cooldownTracker,
      synthesisGate: gate,
    });

    const completion = await engine.chatCompletion(
      {
        model: 'smart-tier',
        messages: [{ role: 'user', content: "what's 2+2" }],
      },
      {
        enableSynthesis: true,
      },
    );

    expect(completion.choices[0].message.content).toBe('4');
    expect(completion.model).toBe('smart-tier');
  });
});
