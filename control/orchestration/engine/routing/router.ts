/**
 * OmniRoute 4-Path Priority Router
 * Sourced & adapted from OmniRoute (src/lib/routing/adaptiveRouting.ts) - MIT License
 *
 * Enforces the 4-path routing hierarchy:
 * 1. Pooled Enterprise Direct Keys
 * 2. Pooled Aggregator (OpenRouter - default zero setup)
 * 3. User BYOK (Bring Your Own Key)
 * 4. User BYOI (Bring Your Own Infrastructure)
 */

import { nanoid } from 'nanoid';
import type {
  ExecutionRequest,
  ExecutionResponse,
  ModelDefinition,
  RoutingPath,
} from '../types.js';
import { selectModel, type SelectionResult } from './selector.js';
import type { ProviderAdapter, ProviderExecutionInput } from '../providers/baseAdapter.js';
import { EnterpriseDirectAdapter } from '../providers/enterpriseDirect.js';
import { OpenRouterAggregatorAdapter } from '../providers/openRouterAggregator.js';
import { ByokAdapter } from '../providers/byokAdapter.js';
import { ByoiAdapter } from '../providers/byoiAdapter.js';

export interface RouterConfig {
  enterpriseAdapter?: EnterpriseDirectAdapter;
  aggregatorAdapter?: OpenRouterAggregatorAdapter;
  byokAdapter?: ByokAdapter;
  byoiAdapter?: ByoiAdapter;
  customAdapters?: ProviderAdapter[];
}

export class OmniRouter {
  private enterpriseAdapter: EnterpriseDirectAdapter;
  private aggregatorAdapter: OpenRouterAggregatorAdapter;
  private byokAdapter: ByokAdapter;
  private byoiAdapter: ByoiAdapter;
  private customAdapters: ProviderAdapter[] = [];

  constructor(config?: RouterConfig) {
    this.enterpriseAdapter = config?.enterpriseAdapter || new EnterpriseDirectAdapter();
    this.aggregatorAdapter = config?.aggregatorAdapter || new OpenRouterAggregatorAdapter();
    this.byokAdapter = config?.byokAdapter || new ByokAdapter();
    this.byoiAdapter = config?.byoiAdapter || new ByoiAdapter();
    if (config?.customAdapters) {
      this.customAdapters = config.customAdapters;
    }
  }

  setEnterpriseAdapter(adapter: EnterpriseDirectAdapter) {
    this.enterpriseAdapter = adapter;
  }

  setAggregatorAdapter(adapter: OpenRouterAggregatorAdapter) {
    this.aggregatorAdapter = adapter;
  }

  setByokAdapter(adapter: ByokAdapter) {
    this.byokAdapter = adapter;
  }

  setByoiAdapter(adapter: ByoiAdapter) {
    this.byoiAdapter = adapter;
  }

  addCustomAdapter(adapter: ProviderAdapter) {
    this.customAdapters.push(adapter);
  }

  /**
   * Main execution dispatch following the 4-path routing priority and auto-fallback chains.
   */
  async execute(request: ExecutionRequest): Promise<ExecutionResponse> {
    const startTime = Date.now();

    // 1. Select Model using Selector (Dropdown, Search, or Auto with allow/deny rules)
    const selection = selectModel({
      mode: request.selectionMode,
      explicitModel: request.model,
      searchQuery: request.searchQuery,
      messages: request.messages,
      hasTools: Boolean(request.tools && request.tools.length > 0),
      allowList: request.allowList,
      denyList: request.denyList,
      flagPreference: request.flagPreference,
    });

    const candidatesToTry: ModelDefinition[] = [
      selection.selectedModel,
      ...selection.fallbackCandidates,
    ];

    const fallbackChain: string[] = [];
    let lastError: Error | null = null;
    let successfulResult: {
      text: string;
      model: ModelDefinition;
      routeUsed: RoutingPath;
      promptTokens: number;
      completionTokens: number;
      latencyMs: number;
    } | null = null;

    // 2. Iterate through candidate models (Auto-Fallback Chain)
    for (let i = 0; i < candidatesToTry.length; i++) {
      const candidateModel = candidatesToTry[i];
      const isFallback = i > 0;
      if (isFallback) {
        fallbackChain.push(candidateModel.id);
      }

      // Try 4-Path Routing Priority for candidateModel
      try {
        const routeResult = await this.tryFourPathExecution(candidateModel, request);
        if (routeResult) {
          successfulResult = {
            ...routeResult,
            model: candidateModel,
          };
          break;
        }
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        // Fall through to next candidate in chain
      }
    }

    if (!successfulResult) {
      throw (
        lastError ||
        new Error(
          `Execution failed across all available routes and fallback candidates for model "${selection.selectedModel.id}".`
        )
      );
    }

    // 3. Compute cost calculation
    const inputCost = (successfulResult.promptTokens / 1000) * successfulResult.model.costPer1kInputUSD;
    const outputCost = (successfulResult.completionTokens / 1000) * successfulResult.model.costPer1kOutputUSD;
    const totalCostUSD = Number((inputCost + outputCost).toFixed(6));

    const totalLatency = Date.now() - startTime;

    return {
      id: `exec-${nanoid(12)}`,
      text: successfulResult.text,
      model: successfulResult.model.id,
      routeUsed: successfulResult.routeUsed,
      fallbackTriggered: fallbackChain.length > 0,
      fallbackChain,
      notifications: selection.notifications,
      usage: {
        promptTokens: successfulResult.promptTokens,
        completionTokens: successfulResult.completionTokens,
        totalTokens: successfulResult.promptTokens + successfulResult.completionTokens,
        costUSD: totalCostUSD,
      },
      latencyMs: totalLatency,
    };
  }

  /**
   * Attempts execution across the 4 priority paths in strict order:
   * 1. Pooled Enterprise
   * 2. Pooled Aggregator
   * 3. User BYOK
   * 4. User BYOI
   */
  private async tryFourPathExecution(
    model: ModelDefinition,
    request: ExecutionRequest
  ): Promise<{
    text: string;
    routeUsed: RoutingPath;
    promptTokens: number;
    completionTokens: number;
    latencyMs: number;
  } | null> {
    const userKey = request.byokKeys ? request.byokKeys[model.provider.toLowerCase()] : undefined;
    const userEndpoint = request.byoiEndpoints
      ? request.byoiEndpoints[model.provider.toLowerCase()]?.endpointUrl
      : undefined;

    // Custom Adapters check first if registered (e.g. for mock testing)
    for (const custom of this.customAdapters) {
      const input: ProviderExecutionInput = {
        model,
        messages: request.messages,
        routePath: custom.routePath,
        temperature: request.temperature,
        maxTokens: request.maxTokens,
        tools: request.tools,
        apiKey: userKey,
        endpointUrl: userEndpoint,
      };
      if (await custom.isAvailable(model, input)) {
        const out = await custom.execute(input);
        return { ...out, routeUsed: custom.routePath };
      }
    }

    // --- Path 1: Pooled Enterprise Direct ---
    const enterpriseInput: ProviderExecutionInput = {
      model,
      messages: request.messages,
      routePath: 'pooled-enterprise',
      temperature: request.temperature,
      maxTokens: request.maxTokens,
      tools: request.tools,
    };
    if (await this.enterpriseAdapter.isAvailable(model, enterpriseInput)) {
      try {
        const out = await this.enterpriseAdapter.execute(enterpriseInput);
        return { ...out, routeUsed: 'pooled-enterprise' };
      } catch {
        // Fall through to Path 2
      }
    }

    // --- Path 2: Pooled Aggregator (OpenRouter) ---
    const aggregatorInput: ProviderExecutionInput = {
      model,
      messages: request.messages,
      routePath: 'pooled-aggregator',
      temperature: request.temperature,
      maxTokens: request.maxTokens,
      tools: request.tools,
    };
    if (await this.aggregatorAdapter.isAvailable(model, aggregatorInput)) {
      try {
        const out = await this.aggregatorAdapter.execute(aggregatorInput);
        return { ...out, routeUsed: 'pooled-aggregator' };
      } catch {
        // Fall through to Path 3
      }
    }

    // --- Path 3: User BYOK ---
    if (userKey) {
      const byokInput: ProviderExecutionInput = {
        model,
        messages: request.messages,
        routePath: 'byok',
        temperature: request.temperature,
        maxTokens: request.maxTokens,
        tools: request.tools,
        apiKey: userKey,
      };
      if (await this.byokAdapter.isAvailable(model, byokInput)) {
        try {
          const out = await this.byokAdapter.execute(byokInput);
          return { ...out, routeUsed: 'byok' };
        } catch {
          // Fall through to Path 4
        }
      }
    }

    // --- Path 4: User BYOI ---
    const byoiInput: ProviderExecutionInput = {
      model,
      messages: request.messages,
      routePath: 'byoi',
      temperature: request.temperature,
      maxTokens: request.maxTokens,
      tools: request.tools,
      endpointUrl: userEndpoint,
    };
    if (await this.byoiAdapter.isAvailable(model, byoiInput)) {
      const out = await this.byoiAdapter.execute(byoiInput);
      return { ...out, routeUsed: 'byoi' };
    }

    return null;
  }
}
