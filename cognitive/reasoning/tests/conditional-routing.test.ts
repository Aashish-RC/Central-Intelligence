import { beforeEach, describe, expect, it } from 'vitest';
import { ConditionalRouter } from '../src/routing/conditional.js';
import type { ChatCompletionRequest } from '../src/types/chat.js';

describe('Feature 28: Advanced Conditional Routing Engine', () => {
  let router: ConditionalRouter;

  beforeEach(() => {
    router = new ConditionalRouter([
      {
        name: 'enterprise-tier-header',
        condition: { header: { key: 'x-tier', equals: 'enterprise' } },
        targetModel: 'claude-3-5-sonnet',
      },
      {
        name: 'code-regex-detector',
        condition: { promptRegex: /```(?:python|typescript|go|rust)/i },
        targetModel: 'claude-3-7-sonnet',
      },
      {
        name: 'long-context-threshold',
        condition: { minPromptLength: 5000 },
        targetModel: 'gemini-1.5-pro',
      },
    ]);
  });

  it('routes to enterprise model when matching custom header is present', () => {
    const req: ChatCompletionRequest = {
      model: 'gpt-4o-mini',
      messages: [{ role: 'user', content: 'Standard query' }],
    };

    const result = router.resolveModel(req, { 'X-Tier': 'enterprise' });
    expect(result.model).toBe('claude-3-5-sonnet');
    expect(result.matchedRule).toBe('enterprise-tier-header');
  });

  it('routes to coding model when code block is present in prompt', () => {
    const req: ChatCompletionRequest = {
      model: 'gpt-4o-mini',
      messages: [{ role: 'user', content: 'Debug this:\n```python\ndef solve(): pass\n```' }],
    };

    const result = router.resolveModel(req, {});
    expect(result.model).toBe('claude-3-7-sonnet');
    expect(result.matchedRule).toBe('code-regex-detector');
  });

  it('routes to long context model when prompt length exceeds threshold', () => {
    const req: ChatCompletionRequest = {
      model: 'gpt-4o-mini',
      messages: [{ role: 'user', content: 'Document text: ' + 'A'.repeat(6000) }],
    };

    const result = router.resolveModel(req, {});
    expect(result.model).toBe('gemini-1.5-pro');
    expect(result.matchedRule).toBe('long-context-threshold');
  });

  it('preserves requested model when no rules match', () => {
    const req: ChatCompletionRequest = {
      model: 'gpt-4o-mini',
      messages: [{ role: 'user', content: 'Short plain query' }],
    };

    const result = router.resolveModel(req, {});
    expect(result.model).toBe('gpt-4o-mini');
    expect(result.matchedRule).toBeUndefined();
  });
});
