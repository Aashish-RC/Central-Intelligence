import { describe, expect, it } from 'vitest';
import { ManifestLoader } from '../src/config/manifest-loader.js';

describe('Feature 35: Declarative Config Manifest Loader', () => {
  it('parses valid manifest object and applies defaults', () => {
    const raw = {
      version: '1.0',
      server: { port: 3000 },
      providers: [
        { id: 'openai-main', type: 'openai', baseUrl: 'https://api.openai.com/v1' },
        { id: 'bedrock-us', type: 'bedrock', region: 'us-east-1' },
      ],
      virtualTiers: [
        {
          tierName: 'smart-tier',
          strategy: 'priority',
          candidates: ['gpt-4o', 'claude-3-5-sonnet'],
          fallbackChain: ['ollama-deepseek'],
        },
      ],
      budgets: [
        {
          id: 'team-engineering',
          scope: 'team',
          maxSpendUsd: 50.0,
          window: 'monthly',
        },
      ],
    };

    const manifest = ManifestLoader.loadFromObject(raw);
    expect(manifest.version).toBe('1.0');
    expect(manifest.server?.port).toBe(3000);
    expect(manifest.server?.host).toBe('0.0.0.0'); // default
    expect(manifest.providers.length).toBe(2);
    expect(manifest.virtualTiers[0].strategy).toBe('priority');
    expect(manifest.budgets[0].maxSpendUsd).toBe(50.0);
  });

  it('rejects invalid manifests with informative Zod validation error', () => {
    const invalid = {
      version: '1.0',
      virtualTiers: [
        {
          tierName: 'bad-tier',
          candidates: [], // Error: min 1 candidate required
        },
      ],
      budgets: [
        {
          id: 'bad-budget',
          scope: 'invalid-scope', // Error: invalid enum
          maxSpendUsd: -10, // Error: must be positive
          window: 'daily',
        },
      ],
    };

    expect(() => ManifestLoader.loadFromObject(invalid)).toThrow();
  });
});
