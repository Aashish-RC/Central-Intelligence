/**
 * Enterprise Direct Provider Adapter
 * Path 1 of the 4-path routing priority: Direct enterprise accounts
 */

import type { ProviderAdapter, ProviderExecutionInput, ProviderExecutionOutput } from './baseAdapter.js';
import type { ModelDefinition } from '../types.js';

export class EnterpriseDirectAdapter implements ProviderAdapter {
  readonly routePath = 'pooled-enterprise';
  private enterpriseKeys: Map<string, string> = new Map();
  private isQuotaExhausted = false;

  constructor(initialKeys?: Record<string, string>) {
    if (initialKeys) {
      for (const [provider, key] of Object.entries(initialKeys)) {
        this.enterpriseKeys.set(provider.toLowerCase(), key);
      }
    }
  }

  setEnterpriseKey(provider: string, key: string) {
    this.enterpriseKeys.set(provider.toLowerCase(), key);
  }

  setQuotaExhausted(exhausted: boolean) {
    this.isQuotaExhausted = exhausted;
  }

  async isAvailable(model: ModelDefinition, _input?: ProviderExecutionInput): Promise<boolean> {
    if (this.isQuotaExhausted) return false;
    // Available if an enterprise key is registered for this provider
    return this.enterpriseKeys.has(model.provider.toLowerCase());
  }

  async execute(input: ProviderExecutionInput): Promise<ProviderExecutionOutput> {
    if (this.isQuotaExhausted) {
      throw new Error(`Enterprise pooled quota is exhausted for provider ${input.model.provider}.`);
    }

    const startTime = Date.now();
    const promptText = input.messages.map((m) => m.content).join(' ');
    const promptTokens = Math.max(10, Math.ceil(promptText.length / 4));
    const responseText = `[Enterprise Direct: ${input.model.name}] Direct enterprise execution completed.`;
    const completionTokens = Math.ceil(responseText.length / 4);

    return {
      text: responseText,
      promptTokens,
      completionTokens,
      latencyMs: Math.max(10, Date.now() - startTime),
      finishReason: 'stop',
    };
  }
}
