import { describe, expect, it } from 'vitest';
import { type CelContext, CelEvaluator } from '../src/routing/cel.js';

describe('Feature 43: Common Expression Language (CEL) Engine', () => {
  const context: CelContext = {
    request: {
      model: 'gpt-4o',
      temperature: 0.7,
      max_tokens: 4096,
      messages_count: 5,
    },
    response: {
      input_tokens: 1000,
      output_tokens: 500,
      latency_ms: 250,
    },
    user: {
      tier: 'enterprise',
      spend_usd: 12.5,
    },
  };

  it('evaluates boolean equality, comparison, and nested path checks', () => {
    expect(CelEvaluator.evaluateCondition("request.model == 'gpt-4o'", context)).toBe(true);
    expect(CelEvaluator.evaluateCondition("request.model == 'claude-3-5-sonnet'", context)).toBe(
      false,
    );
    expect(CelEvaluator.evaluateCondition('response.input_tokens > 500', context)).toBe(true);
    expect(CelEvaluator.evaluateCondition('user.tier == "enterprise"', context)).toBe(true);
  });

  it('evaluates logical AND (&&) and logical OR (||) expressions', () => {
    expect(
      CelEvaluator.evaluateCondition(
        "request.model == 'gpt-4o' && response.input_tokens >= 1000",
        context,
      ),
    ).toBe(true);

    expect(
      CelEvaluator.evaluateCondition(
        "request.model == 'unknown' || response.latency_ms < 500",
        context,
      ),
    ).toBe(true);
  });

  it('evaluates dynamic arithmetic cost formulas accurately', () => {
    // Formula: input_tokens * 0.000005 + output_tokens * 0.000015
    // 1000 * 0.000005 = 0.005
    // 500 * 0.000015 = 0.0075
    // Total = 0.0125
    const cost = CelEvaluator.evaluateNumericFormula(
      'response.input_tokens * 0.000005 + response.output_tokens * 0.000015',
      context,
    );
    expect(cost).toBeCloseTo(0.0125, 5);
  });
});
