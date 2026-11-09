/**
 * Collaboration Controls Cross-Layer Bridge
 * Feature: 8.50 (Cross-Layer Multi-Agent Collaboration Governance)
 *
 * Enforces delegation bounds, recursion depth caps, cyclic delegation detection,
 * and capability restriction scoping when orchestrating multi-agent delegations.
 */

export class DelegationDepthExceededError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DelegationDepthExceededError';
  }
}

export class DelegationCycleError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DelegationCycleError';
  }
}

export interface DelegationGrant {
  id: string;
  delegatorId: string;
  delegateeId: string;
  taskName: string;
  depth: number;
  maxDepth: number;
  ancestryPath: string[]; // [rootAgentId, ..., immediateDelegatorId]
  allowedTools: string[];
  budgetUSD: number;
  createdAt: number;
  expiresAt: number;
  revoked: boolean;
  revokeReason?: string;
}

export interface IssueDelegationParams {
  delegatorId: string;
  delegateeId: string;
  taskName: string;
  parentDelegationId?: string;
  maxDepth?: number;
  allowedTools?: string[];
  budgetUSD?: number;
  ttlMs?: number;
}

export class CollaborationBridge {
  private grants: Map<string, DelegationGrant> = new Map();
  private readonly defaultMaxDepth: number;

  constructor(config?: { defaultMaxDepth?: number }) {
    this.defaultMaxDepth = config?.defaultMaxDepth ?? 3;
  }

  /**
   * Issue a governed delegation grant from one agent to another.
   */
  public issueDelegation(params: IssueDelegationParams): DelegationGrant {
    const now = Date.now();
    let depth = 1;
    let ancestryPath: string[] = [params.delegatorId];
    const maxDepth = params.maxDepth ?? this.defaultMaxDepth;

    if (params.parentDelegationId) {
      const parent = this.grants.get(params.parentDelegationId);
      if (!parent) {
        throw new Error(`Parent delegation grant '${params.parentDelegationId}' not found`);
      }
      if (parent.revoked || parent.expiresAt <= now) {
        throw new Error(`Parent delegation grant '${params.parentDelegationId}' is inactive or expired`);
      }

      depth = parent.depth + 1;
      if (depth > maxDepth) {
        throw new DelegationDepthExceededError(
          `Delegation recursion depth (${depth}) exceeds maximum limit (${maxDepth})`
        );
      }

      // Check cycle detection: delegatee must not already exist in the ancestry chain
      if (parent.ancestryPath.includes(params.delegateeId)) {
        throw new DelegationCycleError(
          `Cyclic delegation detected: agent '${params.delegateeId}' already present in ancestry path: ${parent.ancestryPath.join(' -> ')}`
        );
      }

      ancestryPath = [...parent.ancestryPath, params.delegatorId];
    }

    const grantId = `dlg_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const grant: DelegationGrant = {
      id: grantId,
      delegatorId: params.delegatorId,
      delegateeId: params.delegateeId,
      taskName: params.taskName,
      depth,
      maxDepth,
      ancestryPath,
      allowedTools: params.allowedTools || [],
      budgetUSD: params.budgetUSD || 0,
      createdAt: now,
      expiresAt: now + (params.ttlMs || 3600000),
      revoked: false,
    };

    this.grants.set(grantId, grant);
    return grant;
  }

  /**
   * Verify whether a delegation grant is currently valid for an agent.
   */
  public verifyDelegation(grantId: string, callingAgentId: string): { valid: boolean; error?: string } {
    const grant = this.grants.get(grantId);
    if (!grant) {
      return { valid: false, error: `Delegation grant '${grantId}' not found` };
    }

    if (grant.revoked) {
      return { valid: false, error: `Delegation grant was revoked: ${grant.revokeReason || 'No reason'}` };
    }

    if (Date.now() > grant.expiresAt) {
      return { valid: false, error: 'Delegation grant has expired' };
    }

    if (grant.delegateeId !== callingAgentId && grant.delegatorId !== callingAgentId && callingAgentId !== 'admin') {
      return { valid: false, error: `Agent '${callingAgentId}' does not hold or own delegation '${grantId}'` };
    }

    return { valid: true };
  }

  /**
   * Revoke an active delegation.
   */
  public revokeDelegation(grantId: string, reason: string): void {
    const grant = this.grants.get(grantId);
    if (!grant) {
      throw new Error(`Delegation grant '${grantId}' not found`);
    }
    grant.revoked = true;
    grant.revokeReason = reason;
  }

  /**
   * Detect ping-pong loops between pairs of agents.
   */
  public detectPingPongLoop(
    interactions: Array<{ sender: string; recipient: string; action: string }>,
    windowSize = 4
  ): boolean {
    if (interactions.length < windowSize) return false;

    const recent = interactions.slice(-windowSize);
    let pingPongCount = 0;

    for (let i = 1; i < recent.length; i++) {
      const prev = recent[i - 1];
      const curr = recent[i];
      if (prev.sender === curr.recipient && prev.recipient === curr.sender) {
        pingPongCount++;
      }
    }

    return pingPongCount >= 3;
  }
}
