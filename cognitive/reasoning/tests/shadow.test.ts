import { beforeEach, describe, expect, it } from 'vitest';
import { ShadowRouter } from '../src/routing/shadow.js';
import type { ChatCompletionRequest, ChatCompletionResponse } from '../src/types/chat.js';

describe('Feature 33: Shadow & Canary Traffic Emulation Router', () => {
  let router: ShadowRouter;

  const sampleReq: ChatCompletionRequest = {
    model: 'gpt-4o',
    messages: [{ role: 'user', content: 'Shadow test request.' }],
  };

  const primaryResp: ChatCompletionResponse = {
    id: 'chatcmpl-primary-1',
    object: 'chat.completion',
    created: 1729270000,
    model: 'gpt-4o',
    choices: [
      {
        index: 0,
        message: { role: 'assistant', content: 'Primary answer' },
        finish_reason: 'stop',
      },
    ],
    usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 },
  };

  const shadowResp: ChatCompletionResponse = {
    id: 'chatcmpl-shadow-1',
    object: 'chat.completion',
    created: 1729270000,
    model: 'deepseek-v3',
    choices: [
      { index: 0, message: { role: 'assistant', content: 'Shadow answer' }, finish_reason: 'stop' },
    ],
    usage: { prompt_tokens: 10, completion_tokens: 8, total_tokens: 18 },
  };

  beforeEach(() => {
    router = new ShadowRouter({
      shadowModel: 'deepseek-v3',
      samplePercentage: 100,
      enabled: true,
    });
    router.clear();
  });

  it('asynchronously mirrors request to shadow candidate and records metrics', async () => {
    let shadowCalled = false;

    const primaryDispatcher = async (_req: ChatCompletionRequest) => primaryResp;
    const shadowDispatcher = async (req: ChatCompletionRequest) => {
      shadowCalled = true;
      expect(req.model).toBe('deepseek-v3');
      return shadowResp;
    };

    const res = await router.executeWithShadow(
      sampleReq,
      'req-test-123',
      primaryDispatcher,
      shadowDispatcher,
    );

    // Primary response returns immediately
    expect(res.id).toBe('chatcmpl-primary-1');
    expect(shadowCalled).toBe(true);

    // Wait for shadow async promise completion
    await new Promise((r) => setTimeout(r, 20));

    const evals = router.getEvaluations();
    expect(evals.length).toBe(1);
    expect(evals[0].primaryModel).toBe('gpt-4o');
    expect(evals[0].shadowModel).toBe('deepseek-v3');
    expect(evals[0].shadowSuccess).toBe(true);
    expect(evals[0].shadowTokens).toBe(18);
  });

  it('protects primary response from shadow failure', async () => {
    const primaryDispatcher = async () => primaryResp;
    const shadowDispatcher = async () => {
      throw new Error('Shadow provider timeout');
    };

    const res = await router.executeWithShadow(
      sampleReq,
      'req-test-456',
      primaryDispatcher,
      shadowDispatcher,
    );

    expect(res.id).toBe('chatcmpl-primary-1');

    await new Promise((r) => setTimeout(r, 20));

    const evals = router.getEvaluations();
    expect(evals.length).toBe(1);
    expect(evals[0].shadowSuccess).toBe(false);
    expect(evals[0].shadowError).toContain('Shadow provider timeout');
  });
});
