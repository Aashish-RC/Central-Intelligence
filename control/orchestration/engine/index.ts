/**
 * Unified Model Engine Facade
 * Integrates:
 * - Governance Layer (Virtual Keys, Budgets, Rate Limits, Audit)
 * - OmniRoute Core (4-Path Priority, Task-Aware Auto Selection, Allow/Deny Rules)
 * - OpenRouter Aggregator Default Provider
 *
 * Sourced & inspired by OmniRoute (MIT) and LiteLLM (MIT conceptual patterns)
 */

import type {
  ExecutionRequest,
  ExecutionResponse,
  VirtualKey,
  BudgetRecord,
} from './types.js';
import { OmniRouter, type RouterConfig } from './routing/router.js';
import { VirtualKeyManager } from './governance/virtualKeyManager.js';
import { BudgetTracker } from './governance/budgetTracker.js';
import { RateLimiter, type RateLimitConfig } from './governance/rateLimiter.js';
import { UsageStore } from './governance/usageStore.js';
import { MODEL_CATALOG, getModelById } from './catalog.js';

export interface ModelEngineConfig {
  routerConfig?: RouterConfig;
}

export class ModelEngine {
  readonly router: OmniRouter;
  readonly keyManager: VirtualKeyManager;
  readonly budgetTracker: BudgetTracker;
  readonly rateLimiter: RateLimiter;
  readonly usageStore: UsageStore;

  constructor(config?: ModelEngineConfig) {
    this.router = new OmniRouter(config?.routerConfig);
    this.keyManager = new VirtualKeyManager();
    this.budgetTracker = new BudgetTracker();
    this.rateLimiter = new RateLimiter();
    this.usageStore = new UsageStore();
  }

  // --- Governance Facade Methods ---

  issueVirtualKey(params: {
    userId: string;
    teamId?: string;
    name?: string;
    expiresInDays?: number;
    rateLimitRPM?: number;
    rateLimitTPM?: number;
    maxSpendUSD?: number;
    allowedModels?: string[];
    deniedModels?: string[];
  }): VirtualKey {
    const vk = this.keyManager.createKey(params);

    // If limits or budget provided, configure them
    if (params.rateLimitRPM || params.rateLimitTPM) {
      this.rateLimiter.setLimits(vk.key, {
        maxRPM: params.rateLimitRPM || 60,
        maxTPM: params.rateLimitTPM || 100000,
      });
    }

    if (params.maxSpendUSD) {
      this.budgetTracker.setBudget({
        entityId: vk.key,
        entityType: 'key',
        maxSpendUSD: params.maxSpendUSD,
        resetPeriod: 'monthly',
      });
    }

    return vk;
  }

  setUserBudget(userId: string, maxSpendUSD: number, resetPeriod: 'daily' | 'monthly' | 'lifetime' = 'monthly'): BudgetRecord {
    return this.budgetTracker.setBudget({
      entityId: userId,
      entityType: 'user',
      maxSpendUSD,
      resetPeriod,
    });
  }

  setUserRateLimits(userId: string, config: RateLimitConfig): void {
    this.rateLimiter.setLimits(userId, config);
  }

  // --- Execution Facade Method ---

  async execute(request: ExecutionRequest): Promise<ExecutionResponse> {
    let activeKey: VirtualKey | undefined;

    // 1. Governance: Validate Virtual Key if present
    if (request.virtualKey) {
      activeKey = this.keyManager.validateKey(request.virtualKey);

      // Merge allowed/denied models from key permissions
      if (activeKey.allowedModels && activeKey.allowedModels.length > 0) {
        request.allowList = Array.from(
          new Set([...(request.allowList || []), ...activeKey.allowedModels])
        );
      }
      if (activeKey.deniedModels && activeKey.deniedModels.length > 0) {
        request.denyList = Array.from(
          new Set([...(request.denyList || []), ...activeKey.deniedModels])
        );
      }

      // Check key-level Rate Limits
      this.rateLimiter.checkAndIncrement(activeKey.key);

      // Check key-level Budget
      this.budgetTracker.checkBudget(activeKey.key);
    }

    // 2. Governance: Check User-level Rate Limits and Budget if user context provided
    const userId = request.userContext?.userId || activeKey?.userId;
    if (userId) {
      this.rateLimiter.checkAndIncrement(userId);
      this.budgetTracker.checkBudget(userId);
    }

    // 3. Routing: Dispatch to OmniRouter (handles 4-path priority & fallbacks)
    let response: ExecutionResponse;
    try {
      response = await this.router.execute(request);
    } catch (err) {
      // Record failure audit
      this.usageStore.recordUsage({
        virtualKey: request.virtualKey,
        userId,
        teamId: request.userContext?.teamId || activeKey?.teamId,
        model: request.model || 'auto',
        routeUsed: 'pooled-aggregator',
        promptTokens: 0,
        completionTokens: 0,
        costUSD: 0,
        latencyMs: 0,
        status: 'failed',
        error: err instanceof Error ? err.message : String(err),
      });
      throw err;
    }

    // 4. Governance: Record Spend and Audit Logs
    if (activeKey) {
      this.budgetTracker.recordSpend(activeKey.key, response.usage.costUSD);
    }
    if (userId) {
      this.budgetTracker.recordSpend(userId, response.usage.costUSD);
    }

    this.usageStore.recordUsage({
      virtualKey: request.virtualKey,
      userId,
      teamId: request.userContext?.teamId || activeKey?.teamId,
      model: response.model,
      routeUsed: response.routeUsed,
      promptTokens: response.usage.promptTokens,
      completionTokens: response.usage.completionTokens,
      costUSD: response.usage.costUSD,
      latencyMs: response.latencyMs,
      status: 'success',
    });

    return response;
  }
}

export * from './types.js';
export { MODEL_CATALOG, getModelById } from './catalog.js';
export { OmniRouter } from './routing/router.js';
export { selectModel, searchModels } from './routing/selector.js';
export { classifyTask } from './routing/taskClassifier.js';
export {
  CognitiveRoutingPolicyEngine,
  type TaskComplexity,
  type RoutingObjective,
  type PolicyRule,
  type CognitiveRoutingDecision,
} from './routing/cognitivePolicy.js';
export {
  HumanEscalationProtocol,
  type EscalationUrgency,
  type EscalationStatus,
  type EscalationTrigger,
} from './escalation/humanProtocol.js';
export {
  SharedWorkspace,
  type WorkspaceArtifact,
  type WorkspaceBranch,
  type MergeConflict,
} from './sharedState/workspace.js';
export { VirtualKeyManager } from './governance/virtualKeyManager.js';
export { BudgetTracker, BudgetExceededError } from './governance/budgetTracker.js';
export { RateLimiter, RateLimitExceededError } from './governance/rateLimiter.js';
export { UsageStore } from './governance/usageStore.js';
export { OpenRouterAggregatorAdapter } from './providers/openRouterAggregator.js';
export { EnterpriseDirectAdapter } from './providers/enterpriseDirect.js';
export { ByokAdapter } from './providers/byokAdapter.js';
export { ByoiAdapter } from './providers/byoiAdapter.js';
export { MockAdapter } from './providers/mockAdapter.js';
export {
  PaperclipGovernanceAdapter,
  type AgentNode,
  type AgentStatus,
  type ApprovalRequest,
  type FleetOrgConfig,
  type FleetSummary,
} from './fleet/paperclipAdapter.js';
