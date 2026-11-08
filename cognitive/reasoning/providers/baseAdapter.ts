/**
 * Base Provider Adapter Contract
 * Sourced & adapted from OmniRoute (src/lib/providers/requestDefaults.ts) - MIT License
 */

import type {
  ModelDefinition,
  EngineMessage,
  RoutingPath,
  ToolDefinition,
} from '../types.js';

export interface ProviderExecutionInput {
  model: ModelDefinition;
  messages: EngineMessage[];
  routePath: RoutingPath;
  temperature?: number;
  maxTokens?: number;
  tools?: ToolDefinition[];
  apiKey?: string;
  endpointUrl?: string;
}

export interface ProviderExecutionOutput {
  text: string;
  promptTokens: number;
  completionTokens: number;
  latencyMs: number;
  finishReason?: string;
  providerResponse?: unknown;
}

export interface ProviderAdapter {
  readonly routePath: RoutingPath;
  isAvailable(model: ModelDefinition, input: ProviderExecutionInput): Promise<boolean>;
  execute(input: ProviderExecutionInput): Promise<ProviderExecutionOutput>;
}
