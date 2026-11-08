/**
 * Mock Provider Adapter
 * For testing provider failures, circuit breaks, and fallback chain verification
 */

import type { ProviderAdapter, ProviderExecutionInput, ProviderExecutionOutput } from './baseAdapter.js';
import type { ModelDefinition, RoutingPath } from '../types.js';

export class MockAdapter implements ProviderAdapter {
  readonly routePath: RoutingPath;
  private failForModelIds: Set<string> = new Set();
  private failErrorMessage = 'Simulated provider connection failure (HTTP 503 Service Unavailable)';

  constructor(routePath: RoutingPath = 'pooled-aggregator') {
    this.routePath = routePath;
  }

  setFailingModel(modelId: string, shouldFail = true) {
    if (shouldFail) {
      this.failForModelIds.add(modelId.toLowerCase());
    } else {
      this.failForModelIds.delete(modelId.toLowerCase());
    }
  }

  async isAvailable(model: ModelDefinition, _input?: ProviderExecutionInput): Promise<boolean> {
    return true;
  }

  async execute(input: ProviderExecutionInput): Promise<ProviderExecutionOutput> {
    if (this.failForModelIds.has(input.model.id.toLowerCase())) {
      throw new Error(`${this.failErrorMessage} on ${input.model.id}`);
    }

    return {
      text: `[Mock: ${input.model.name}] Handled via ${this.routePath}.`,
      promptTokens: 25,
      completionTokens: 50,
      latencyMs: 15,
      finishReason: 'stop',
    };
  }
}
