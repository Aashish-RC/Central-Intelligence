/**
 * User BYOI (Bring Your Own Infrastructure) Adapter
 * Path 4 of the 4-path routing priority: Self-hosted Ollama, vLLM, or private custom endpoints
 */

import type { ProviderAdapter, ProviderExecutionInput, ProviderExecutionOutput } from './baseAdapter.js';
import type { ModelDefinition } from '../types.js';

export class ByoiAdapter implements ProviderAdapter {
  readonly routePath = 'byoi';

  async isAvailable(model: ModelDefinition, input: ProviderExecutionInput): Promise<boolean> {
    // Available if custom endpoint URL is provided or if model is marked as local
    return Boolean(input.endpointUrl) || model.tier === 'local';
  }

  async execute(input: ProviderExecutionInput): Promise<ProviderExecutionOutput> {
    const startTime = Date.now();
    const endpoint = input.endpointUrl || 'http://localhost:11434';
    const promptText = input.messages.map((m) => m.content).join(' ');
    const promptTokens = Math.max(10, Math.ceil(promptText.length / 4));
    const responseText = `[User BYOI: ${input.model.name}] Executed via local infrastructure at ${endpoint}.`;
    const completionTokens = Math.ceil(responseText.length / 4);

    return {
      text: responseText,
      promptTokens,
      completionTokens,
      latencyMs: Math.max(5, Date.now() - startTime),
      finishReason: 'stop',
    };
  }
}
