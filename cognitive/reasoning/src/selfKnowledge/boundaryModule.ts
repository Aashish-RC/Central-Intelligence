/**
 * Self-Knowledge Boundary Module
 *
 * Calibrates agent epistemic uncertainty and capability awareness:
 * - Detects out-of-boundary queries before hallucinated execution.
 * - Enforces registered tool manifests and prohibits imaginary tool invocation.
 * - Prevents exceeding financial authorities or restricted actions.
 * - Injects concise epistemic boundaries into system context.
 *
 * Feature ID: 4.27
 */

export interface AgentCapabilityManifest {
  agentId: string;
  name: string;
  modelName: string;
  knowledgeCutoffDate?: string;
  registeredTools: string[];
  allowedDomains?: string[];
  sandboxEnabled: boolean;
  internetAccess: boolean;
  financialAuthorityUSD: number;
  restrictedActions?: string[];
}

export type BoundaryType =
  | 'within_boundary'
  | 'missing_tool'
  | 'restricted_action'
  | 'temporal_knowledge_cutoff'
  | 'financial_limit_exceeded'
  | 'unauthorized_domain';

export interface BoundaryEvaluationResult {
  canHandle: boolean;
  confidence: number;
  boundaryType: BoundaryType;
  reason: string;
  suggestedRemediation?: string;
  missingCapabilities?: string[];
}

export class SelfKnowledgeBoundaryModule {
  readonly manifest: AgentCapabilityManifest;

  constructor(manifest: AgentCapabilityManifest) {
    this.manifest = {
      ...manifest,
      registeredTools: [...manifest.registeredTools],
      allowedDomains: manifest.allowedDomains ? [...manifest.allowedDomains] : ['*'],
      restrictedActions: manifest.restrictedActions ? [...manifest.restrictedActions] : [],
    };
  }

  getManifest(): AgentCapabilityManifest {
    return { ...this.manifest };
  }

  /**
   * Pre-execution evaluation: assesses whether a query falls within the agent's verified boundaries.
   */
  evaluateQuery(query: string): BoundaryEvaluationResult {
    const qLower = query.toLowerCase();

    // 1. Check financial authority limits
    const moneyMatch = query.match(/\$\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?)/);
    if (moneyMatch) {
      const amount = parseFloat(moneyMatch[1].replace(/,/g, ''));
      if (amount > this.manifest.financialAuthorityUSD) {
        return {
          canHandle: false,
          confidence: 0.95,
          boundaryType: 'financial_limit_exceeded',
          reason: `Requested amount $${amount} exceeds autonomous financial limit of $${this.manifest.financialAuthorityUSD}.`,
          suggestedRemediation: 'Escalate to human supervisor for financial authorization.',
        };
      }
    }

    // 2. Check explicitly restricted actions
    if (this.manifest.restrictedActions) {
      for (const restricted of this.manifest.restrictedActions) {
        if (qLower.includes(restricted.toLowerCase())) {
          return {
            canHandle: false,
            confidence: 0.99,
            boundaryType: 'restricted_action',
            reason: `Action '${restricted}' is explicitly restricted by governance policy.`,
            suggestedRemediation: 'Request explicit administrative authorization or policy exception.',
          };
        }
      }
    }

    // 3. Check internet access requirements
    const liveWebKeywords = ['current stock price', 'latest news today', 'real-time weather', 'live exchange rate'];
    if (!this.manifest.internetAccess) {
      for (const kw of liveWebKeywords) {
        if (qLower.includes(kw)) {
          return {
            canHandle: false,
            confidence: 0.9,
            boundaryType: 'missing_tool',
            reason: `Query requires real-time web access ('${kw}'), but internet access is disabled for this agent.`,
            suggestedRemediation: 'Enable web search tool or connect search API.',
            missingCapabilities: ['web_search'],
          };
        }
      }
    }

    return {
      canHandle: true,
      confidence: 0.95,
      boundaryType: 'within_boundary',
      reason: 'Query is within certified epistemic and operational boundaries.',
    };
  }

  /**
   * Tool invocation guard: validates that the requested tool exists in registered manifest.
   */
  validateToolCall(toolName: string, params: Record<string, unknown> = {}): { valid: boolean; reason?: string } {
    if (!this.manifest.registeredTools.includes(toolName)) {
      return {
        valid: false,
        reason: `Tool '${toolName}' is not registered in the agent capability manifest. Available tools: [${this.manifest.registeredTools.join(', ')}].`,
      };
    }

    // Check financial params inside tool calls
    if (typeof params.amountUSD === 'number' && params.amountUSD > this.manifest.financialAuthorityUSD) {
      return {
        valid: false,
        reason: `Tool '${toolName}' requested spend $${params.amountUSD} exceeding financial authority limit of $${this.manifest.financialAuthorityUSD}.`,
      };
    }

    return { valid: true };
  }

  /**
   * Generates a concise system prompt injection enforcing self-knowledge boundaries.
   */
  formatBoundarySystemPrompt(): string {
    const tools = this.manifest.registeredTools.length > 0 ? this.manifest.registeredTools.join(', ') : 'none';
    const restricted = this.manifest.restrictedActions && this.manifest.restrictedActions.length > 0
      ? this.manifest.restrictedActions.join(', ')
      : 'none';

    return [
      `[SELF-KNOWLEDGE & CAPABILITY BOUNDARIES]`,
      `- Agent: ${this.manifest.name} (${this.manifest.agentId})`,
      `- Model: ${this.manifest.modelName}`,
      `- Internet Access: ${this.manifest.internetAccess ? 'Enabled' : 'Disabled'}`,
      `- Registered Tools: [${tools}]`,
      `- Financial Authority: $${this.manifest.financialAuthorityUSD.toFixed(2)} USD`,
      `- Restricted Operations: [${restricted}]`,
      `- Core Principle: Never hallucinate unlisted tools. State inability honestly when queried outside boundaries.`,
    ].join('\n');
  }
}
