import { describe, expect, it } from 'vitest';
import { ProcessRewardVerifier } from '../../src/synthesis/prmVerifier.js';

describe('Sub-module A: Process Reward Verifier (PRM) (4.08, 11.14)', () => {
  it('approves coherent, high-confidence intermediate reasoning steps', async () => {
    const prm = new ProcessRewardVerifier();
    const result = await prm.verifyStep({
      task: 'Calculate the total price after 20% discount on $100',
      step: 'First, calculate the discount amount: 100 * 0.20 = 20. Therefore the discount is 20.',
      priorSteps: [],
    });

    expect(result.valid).toBe(true);
    expect(result.action).toBe('continue');
    expect(result.score).toBeGreaterThanOrEqual(0.8);
  });

  it('prunes invalid or contradictory intermediate reasoning steps (< 0.5)', async () => {
    const prm = new ProcessRewardVerifier();
    const result = await prm.verifyStep({
      task: 'Solve for x: 2x = 10',
      step: 'Divide both sides by 2, leading to 2 + 2 = 5 and impossible division by zero',
      priorSteps: ['Given 2x = 10'],
    });

    expect(result.valid).toBe(false);
    expect(result.action).toBe('prune');
    expect(result.score).toBeLessThan(0.5);
  });

  it('verifies a full multi-step reasoning trace and stops at the first pruned step', async () => {
    const prm = new ProcessRewardVerifier();
    const trace = [
      'Step 1: Identify all prime factors of 28.',
      'Step 2: 28 = 2 * 14 = 2 * 2 * 7.',
      'Step 3: Contradiction occurs because undefined value appears and gives up',
      'Step 4: Conclude primes are 2 and 7.',
    ];

    const evalResult = await prm.verifyReasoningTrace('Find primes of 28', trace);

    expect(evalResult.isValidTrace).toBe(false);
    expect(evalResult.prunedSteps.length).toBe(1);
    expect(evalResult.prunedSteps[0].text).toContain('Contradiction');
    // Steps evaluated should stop at step 3
    expect(evalResult.steps.length).toBe(3);
  });

  it('supports custom pluggable scoring function', async () => {
    const customPRM = new ProcessRewardVerifier({
      scoringFn: async (_task, step) => {
        if (step.includes('flawed')) {
          return { score: 0.1, rationale: 'Custom rejected flawed logic' };
        }
        return { score: 0.95, rationale: 'Custom verified' };
      },
    });

    const validStep = await customPRM.verifyStep({
      task: 'test',
      step: 'This is sound reasoning',
    });
    expect(validStep.score).toBe(0.95);
    expect(validStep.valid).toBe(true);

    const invalidStep = await customPRM.verifyStep({
      task: 'test',
      step: 'This is flawed reasoning',
    });
    expect(invalidStep.score).toBe(0.1);
    expect(invalidStep.valid).toBe(false);
    expect(invalidStep.action).toBe('prune');
  });
});
