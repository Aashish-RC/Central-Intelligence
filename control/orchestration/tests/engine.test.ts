/**
 * Model Engine & Governance Layer Test Suite
 * Validates scenarios 1 through 14
 */

import { test, describe } from 'node:test';
import assert from 'node:assert';
import {
  ModelEngine,
  OmniRouter,
  searchModels,
  EnterpriseDirectAdapter,
  OpenRouterAggregatorAdapter,
  ByokAdapter,
  ByoiAdapter,
  MockAdapter,
  BudgetExceededError,
  RateLimitExceededError,
} from '../engine/index.js';

describe('Model Engine & Governance Layer (Scenarios 1-14)', () => {
  test('1. A request routes through pooled quota by default with no user key configured', async () => {
    const engine = new ModelEngine();
    const res = await engine.execute({
      messages: [{ role: 'user', content: 'What is the capital of France?' }],
      model: 'openai/gpt-4o-mini',
      selectionMode: 'dropdown',
    });

    assert.strictEqual(res.routeUsed, 'pooled-aggregator');
    assert.ok(res.text.length > 0);
    assert.ok(res.usage.costUSD >= 0);
  });

  test('2. A request falls back to BYOK when pooled quota is exhausted', async () => {
    // Setup router where enterprise direct is exhausted and aggregator fails/unavailable
    const enterprise = new EnterpriseDirectAdapter({ openai: 'sk-ent-key' });
    enterprise.setQuotaExhausted(true);

    const failingAggregator = new OpenRouterAggregatorAdapter('failing-key');
    // Simulate aggregator unavailable
    failingAggregator.isAvailable = async () => false;

    const router = new OmniRouter({
      enterpriseAdapter: enterprise,
      aggregatorAdapter: failingAggregator,
    });

    const engine = new ModelEngine({ routerConfig: { enterpriseAdapter: enterprise, aggregatorAdapter: failingAggregator } });

    const res = await engine.execute({
      messages: [{ role: 'user', content: 'Explain recursion' }],
      model: 'openai/gpt-4o',
      selectionMode: 'dropdown',
      byokKeys: {
        openai: 'sk-user-personal-openai-key',
      },
    });

    assert.strictEqual(res.routeUsed, 'byok');
    assert.ok(res.text.includes('[User BYOK:'));
  });

  test('3. A request falls back to BYOI when configured and applicable', async () => {
    // Setup router where pooled and BYOK are unavailable
    const enterprise = new EnterpriseDirectAdapter();
    enterprise.setQuotaExhausted(true);

    const failingAggregator = new OpenRouterAggregatorAdapter();
    failingAggregator.isAvailable = async () => false;

    const engine = new ModelEngine({
      routerConfig: {
        enterpriseAdapter: enterprise,
        aggregatorAdapter: failingAggregator,
      },
    });

    const res = await engine.execute({
      messages: [{ role: 'user', content: 'Run query on local cluster' }],
      model: 'ollama/llama-3.1-8b',
      selectionMode: 'dropdown',
      byoiEndpoints: {
        ollama: { endpointUrl: 'http://127.0.0.1:11434' },
      },
    });

    assert.strictEqual(res.routeUsed, 'byoi');
    assert.ok(res.text.includes('[User BYOI:'));
  });

  test('4. Dropdown model selection works', async () => {
    const engine = new ModelEngine();
    const res = await engine.execute({
      messages: [{ role: 'user', content: 'Analyze this poem' }],
      model: 'anthropic/claude-3-5-sonnet',
      selectionMode: 'dropdown',
    });

    assert.strictEqual(res.model, 'anthropic/claude-3-5-sonnet');
    assert.ok(res.text.includes('Claude 3.5 Sonnet'));
  });

  test('5. Search-in-dropdown filters correctly', () => {
    const geminiMatches = searchModels('gemini');
    assert.ok(geminiMatches.length >= 2);
    assert.ok(geminiMatches.every((m) => m.name.toLowerCase().includes('gemini') || m.id.includes('gemini')));

    const codeMatches = searchModels('code');
    assert.ok(codeMatches.some((m) => m.capabilities.includes('code')));

    const nonExistent = searchModels('nonexistentmodelxyz123');
    assert.strictEqual(nonExistent.length, 0);
  });

  test('6. Auto mode selects a model based on prompt content', async () => {
    const engine = new ModelEngine();

    // 1. Complex code task -> should select a flagship coding/reasoning model (e.g. Claude 3.5 Sonnet or DeepSeek R1)
    const codeRes = await engine.execute({
      messages: [
        {
          role: 'user',
          content: '```typescript\nasync function solveTSP(cities: Point[]): Promise<Path> {\n// optimize dynamic programming with bitmasking\n```',
        },
      ],
      selectionMode: 'auto',
    });
    assert.ok(['anthropic/claude-3-5-sonnet', 'deepseek/deepseek-r1', 'openai/gpt-4o'].includes(codeRes.model));

    // 2. Simple question -> should select an economy/fast model (e.g. gpt-4o-mini or gemini-1.5-flash)
    const simpleRes = await engine.execute({
      messages: [{ role: 'user', content: 'What is the capital of Peru?' }],
      selectionMode: 'auto',
    });
    assert.ok(['openai/gpt-4o-mini', 'google/gemini-1.5-flash', 'deepseek/deepseek-chat'].includes(simpleRes.model));
  });

  test('7. Auto mode respects allow-list as priority, not hard cap (selects outside list when justified)', async () => {
    const engine = new ModelEngine();

    // Allow-list only contains a lightweight economy model
    // But the prompt is a deeply complex mathematical theorem proof requiring high-end reasoning
    const res = await engine.execute({
      messages: [
        {
          role: 'user',
          content: 'Solve this complex arithmetic theorem proof step-by-step: evaluate the contour integral and matrix eigenvalues with topological invariants.',
        },
      ],
      selectionMode: 'auto',
      allowList: ['openai/gpt-4o-mini'], // Economy model
      flagPreference: 'always',
    });

    // Auto mode prioritizes the allow-list, but since the task demands high reasoning/math, it reaches outside to a flagship reasoning model
    assert.notStrictEqual(res.model, 'openai/gpt-4o-mini');
    assert.ok(res.notifications.some((n) => n.type === 'auto_selected_outside_allowlist'));
  });

  test('8. A denied model is never selected, including as a fallback', async () => {
    const engine = new ModelEngine();

    // Deny GPT-4o and Claude 3.5 Sonnet
    const res = await engine.execute({
      messages: [
        {
          role: 'user',
          content: 'Write an advanced compiler optimization pass in Rust with AST manipulation.',
        },
      ],
      selectionMode: 'auto',
      denyList: ['openai/gpt-4o', 'anthropic/claude-3-5-sonnet'],
    });

    // Verify neither denied model was selected
    assert.notStrictEqual(res.model, 'openai/gpt-4o');
    assert.notStrictEqual(res.model, 'anthropic/claude-3-5-sonnet');
    assert.ok(!res.fallbackChain.includes('openai/gpt-4o'));
    assert.ok(!res.fallbackChain.includes('anthropic/claude-3-5-sonnet'));

    // Attempt explicit dropdown selection of denied model -> should throw error
    await assert.rejects(
      async () => {
        await engine.execute({
          messages: [{ role: 'user', content: 'Hello' }],
          model: 'openai/gpt-4o',
          selectionMode: 'dropdown',
          denyList: ['openai/gpt-4o'],
        });
      },
      /forbidden by the deny-list/
    );
  });

  test('9. Notification fires (or doesn\'t) correctly per the user\'s configured flagging preference', async () => {
    const engine = new ModelEngine();
    const prompt = 'Solve this complex arithmetic theorem proof step-by-step with eigenvalues.';

    // 1. flagPreference: 'always' -> notification must fire
    const resAlways = await engine.execute({
      messages: [{ role: 'user', content: prompt }],
      selectionMode: 'auto',
      allowList: ['openai/gpt-4o-mini'],
      flagPreference: 'always',
    });
    assert.ok(resAlways.notifications.length > 0);
    assert.strictEqual(resAlways.notifications[0].type, 'auto_selected_outside_allowlist');

    // 2. flagPreference: 'never' -> no notification
    const resNever = await engine.execute({
      messages: [{ role: 'user', content: prompt }],
      selectionMode: 'auto',
      allowList: ['openai/gpt-4o-mini'],
      flagPreference: 'never',
    });
    assert.strictEqual(resNever.notifications.length, 0);

    // 3. flagPreference: 'cost-impacting' -> fires only if selected model is more expensive
    const resCost = await engine.execute({
      messages: [{ role: 'user', content: prompt }],
      selectionMode: 'auto',
      allowList: ['openai/gpt-4o-mini'],
      flagPreference: 'cost-impacting',
    });
    assert.ok(resCost.notifications.length > 0);
  });

  test('10. Virtual key issuance works per user', () => {
    const engine = new ModelEngine();

    const userKey = engine.issueVirtualKey({
      userId: 'user-alice-123',
      name: 'Alice Dev Key',
      rateLimitRPM: 30,
      maxSpendUSD: 50.0,
      allowedModels: ['openai/gpt-4o-mini', 'anthropic/claude-3-haiku'],
    });

    assert.ok(userKey.key.startsWith('vk-usr-'));
    assert.strictEqual(userKey.userId, 'user-alice-123');
    assert.strictEqual(userKey.maxSpendUSD, 50.0);
    assert.strictEqual(userKey.rateLimitRPM, 30);

    const teamKey = engine.issueVirtualKey({
      userId: 'user-bob-456',
      teamId: 'team-engineering',
      name: 'Engineering Team Key',
    });

    assert.ok(teamKey.key.startsWith('vk-team-'));
    assert.strictEqual(teamKey.teamId, 'team-engineering');
  });

  test('11. Budget cap blocks further requests once exceeded', async () => {
    const engine = new ModelEngine();

    // Set a very tight budget of $0.0001
    const key = engine.issueVirtualKey({
      userId: 'user-tight-budget',
      maxSpendUSD: 0.00001,
    });

    // First request should succeed and consume spend
    await engine.execute({
      messages: [{ role: 'user', content: 'Short query' }],
      model: 'openai/gpt-4o',
      selectionMode: 'dropdown',
      virtualKey: key.key,
    });

    // Second request must be blocked by budget cap
    await assert.rejects(
      async () => {
        await engine.execute({
          messages: [{ role: 'user', content: 'Another query' }],
          model: 'openai/gpt-4o',
          selectionMode: 'dropdown',
          virtualKey: key.key,
        });
      },
      (err: unknown) => err instanceof BudgetExceededError
    );
  });

  test('12. Rate limit (RPM/TPM) is enforced', async () => {
    const engine = new ModelEngine();

    // Set strict rate limit of 2 requests per minute
    const key = engine.issueVirtualKey({
      userId: 'user-rate-limited',
      rateLimitRPM: 2,
    });

    // Request 1: ok
    await engine.execute({
      messages: [{ role: 'user', content: 'Query 1' }],
      model: 'openai/gpt-4o-mini',
      selectionMode: 'dropdown',
      virtualKey: key.key,
    });

    // Request 2: ok
    await engine.execute({
      messages: [{ role: 'user', content: 'Query 2' }],
      model: 'openai/gpt-4o-mini',
      selectionMode: 'dropdown',
      virtualKey: key.key,
    });

    // Request 3: blocked by RPM limit
    await assert.rejects(
      async () => {
        await engine.execute({
          messages: [{ role: 'user', content: 'Query 3' }],
          model: 'openai/gpt-4o-mini',
          selectionMode: 'dropdown',
          virtualKey: key.key,
        });
      },
      (err: unknown) => err instanceof RateLimitExceededError && err.limitType === 'RPM'
    );
  });

  test('13. Aggregator path successfully completes a request end-to-end', async () => {
    const engine = new ModelEngine();

    const res = await engine.execute({
      messages: [{ role: 'user', content: 'Summarize the architecture of OmniRoute' }],
      model: 'meta/llama-3.1-70b-instruct',
      selectionMode: 'dropdown',
    });

    assert.strictEqual(res.routeUsed, 'pooled-aggregator');
    assert.strictEqual(res.model, 'meta/llama-3.1-70b-instruct');
    assert.ok(res.text.length > 0);
    assert.ok(res.usage.promptTokens > 0);
    assert.ok(res.usage.completionTokens > 0);
    assert.ok(res.usage.costUSD >= 0);
  });

  test('14. Auto-fallback chain triggers correctly on a simulated provider failure', async () => {
    // Setup router with a mock adapter that fails on the requested model
    const mock = new MockAdapter('pooled-aggregator');
    mock.setFailingModel('openai/gpt-4o', true); // GPT-4o fails

    const engine = new ModelEngine();
    engine.router.setAggregatorAdapter(mock as any);

    // Request gpt-4o which fails on provider
    const res = await engine.execute({
      messages: [{ role: 'user', content: 'Please analyze this system architecture' }],
      model: 'openai/gpt-4o',
      selectionMode: 'dropdown',
    });

    // Assert that fallback was triggered away from gpt-4o to a fallback candidate
    assert.strictEqual(res.fallbackTriggered, true);
    assert.notStrictEqual(res.model, 'openai/gpt-4o');
    assert.ok(res.fallbackChain.length > 0);
  });
});
