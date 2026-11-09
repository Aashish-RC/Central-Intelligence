/**
 * Paperclip Adapter: Agent Fleet Management & Governance Engine
 *
 * Provides hierarchical organizational structure (org charts, reporting chains),
 * per-agent and per-team budget allocation/caps, approval threshold gates (pausing
 * execution until an authorized human or supervisor signs off), and fleet telemetry.
 *
 * Features: 8.18 (Fleet Hierarchy), 8.48 (Governance & Budget Caps)
 * Repo: https://github.com/paperclip-ai/paperclip
 * License: MIT
 */

import { BudgetExceededError } from '../governance/budgetTracker.js';

export type AgentStatus = 'idle' | 'running' | 'paused_for_approval' | 'completed' | 'terminated';

export interface AgentNode {
  id: string;
  name: string;
  role: string;
  reportsTo?: string;
  budgetUSD: number;
  currentSpendUSD: number;
  approvalThresholdUSD: number;
  status: AgentStatus;
  allowedCapabilities: string[];
  metadata?: Record<string, unknown>;
}

export interface ApprovalRequest {
  id: string;
  agentId: string;
  actionName: string;
  estimatedCostUSD: number;
  justification?: string;
  requiredApproverId?: string;
  status: 'pending' | 'approved' | 'rejected';
  createdAt: number;
  resolvedAt?: number;
  resolvedBy?: string;
  rejectionReason?: string;
}

export interface FleetOrgConfig {
  orgId: string;
  name: string;
  totalBudgetUSD: number;
}

export interface FleetSummary {
  orgId: string;
  name: string;
  totalBudgetUSD: number;
  totalSpendUSD: number;
  remainingBudgetUSD: number;
  totalAgents: number;
  activeAgents: number;
  pausedAgents: number;
  pendingApprovals: number;
}

export class PaperclipGovernanceAdapter {
  readonly orgId: string;
  readonly name: string;
  readonly totalBudgetUSD: number;
  private currentSpendUSD: number = 0;
  private agents: Map<string, AgentNode> = new Map();
  private approvalRequests: Map<string, ApprovalRequest> = new Map();
  private pendingTasks: Map<string, { agentId: string; task: string; estimatedCostUSD: number }> = new Map();

  constructor(config: FleetOrgConfig) {
    this.orgId = config.orgId;
    this.name = config.name;
    this.totalBudgetUSD = config.totalBudgetUSD;
  }

  /**
   * Register an agent into the organization chart.
   */
  registerAgent(agent: AgentNode): void {
    if (this.agents.has(agent.id)) {
      throw new Error(`Agent with ID '${agent.id}' is already registered in org '${this.orgId}'.`);
    }
    if (agent.reportsTo && !this.agents.has(agent.reportsTo)) {
      throw new Error(`Supervisor agent '${agent.reportsTo}' does not exist in org '${this.orgId}'.`);
    }
    this.agents.set(agent.id, { ...agent });
  }

  /**
   * Retrieve an agent by ID.
   */
  getAgent(agentId: string): AgentNode | undefined {
    return this.agents.get(agentId);
  }

  /**
   * Get all registered fleet agents.
   */
  getFleet(): AgentNode[] {
    return Array.from(this.agents.values());
  }

  /**
   * Traverse the reporting chain upward to the organizational head.
   */
  getReportingChain(agentId: string): AgentNode[] {
    const chain: AgentNode[] = [];
    let current = this.agents.get(agentId);

    while (current && current.reportsTo) {
      const supervisor = this.agents.get(current.reportsTo);
      if (supervisor) {
        chain.push(supervisor);
        current = supervisor;
      } else {
        break;
      }
    }

    return chain;
  }

  /**
   * Retrieve all immediate subordinates reporting to this agent.
   */
  getSubordinates(agentId: string): AgentNode[] {
    return Array.from(this.agents.values()).filter((a) => a.reportsTo === agentId);
  }

  /**
   * Record spend against an agent and the organizational overall budget.
   * Throws BudgetExceededError if either agent or organization cap is violated.
   */
  recordSpend(agentId: string, amountUSD: number): void {
    const agent = this.agents.get(agentId);
    if (!agent) {
      throw new Error(`Agent '${agentId}' not found.`);
    }

    // Check organization overall cap
    if (this.currentSpendUSD + amountUSD > this.totalBudgetUSD) {
      throw new BudgetExceededError(this.orgId, this.currentSpendUSD, this.totalBudgetUSD);
    }

    // Check agent specific cap
    if (agent.currentSpendUSD + amountUSD > agent.budgetUSD) {
      throw new BudgetExceededError(agent.id, agent.currentSpendUSD, agent.budgetUSD);
    }

    agent.currentSpendUSD += amountUSD;
    this.currentSpendUSD += amountUSD;
  }

  /**
   * Initiate an action approval gate when planned execution exceeds budget or authority.
   */
  requestActionApproval(params: {
    agentId: string;
    actionName: string;
    estimatedCostUSD: number;
    justification?: string;
  }): ApprovalRequest {
    const agent = this.agents.get(params.agentId);
    if (!agent) {
      throw new Error(`Agent '${params.agentId}' not found.`);
    }

    const requestId = `req_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const supervisor = agent.reportsTo ? this.agents.get(agent.reportsTo) : undefined;

    const request: ApprovalRequest = {
      id: requestId,
      agentId: agent.id,
      actionName: params.actionName,
      estimatedCostUSD: params.estimatedCostUSD,
      justification: params.justification,
      requiredApproverId: supervisor?.id,
      status: 'pending',
      createdAt: Date.now(),
    };

    this.approvalRequests.set(requestId, request);
    agent.status = 'paused_for_approval';
    return request;
  }

  /**
   * Approve a pending approval request.
   */
  approveRequest(requestId: string, approverId: string): ApprovalRequest {
    const request = this.approvalRequests.get(requestId);
    if (!request) {
      throw new Error(`Approval request '${requestId}' not found.`);
    }
    if (request.status !== 'pending') {
      throw new Error(`Approval request '${requestId}' is already resolved (${request.status}).`);
    }

    request.status = 'approved';
    request.resolvedAt = Date.now();
    request.resolvedBy = approverId;

    const agent = this.agents.get(request.agentId);
    if (agent && agent.status === 'paused_for_approval') {
      agent.status = 'running';
    }

    return request;
  }

  /**
   * Reject a pending approval request with a reason.
   */
  rejectRequest(requestId: string, approverId: string, reason?: string): ApprovalRequest {
    const request = this.approvalRequests.get(requestId);
    if (!request) {
      throw new Error(`Approval request '${requestId}' not found.`);
    }
    if (request.status !== 'pending') {
      throw new Error(`Approval request '${requestId}' is already resolved (${request.status}).`);
    }

    request.status = 'rejected';
    request.resolvedAt = Date.now();
    request.resolvedBy = approverId;
    request.rejectionReason = reason;

    const agent = this.agents.get(request.agentId);
    if (agent && agent.status === 'paused_for_approval') {
      agent.status = 'idle';
    }

    return request;
  }

  /**
   * List all currently pending approval requests across the fleet.
   */
  getPendingApprovals(): ApprovalRequest[] {
    return Array.from(this.approvalRequests.values()).filter((r) => r.status === 'pending');
  }

  /**
   * Dispatch a task to an agent, automatically evaluating approval gates and budget checks.
   */
  async dispatchTask(
    agentId: string,
    task: string,
    estimatedCostUSD: number = 0.01
  ): Promise<{ status: AgentStatus; taskId: string; requestId?: string; output?: string }> {
    const agent = this.agents.get(agentId);
    if (!agent) {
      throw new Error(`Agent '${agentId}' not found.`);
    }

    // Check budget cap upfront
    if (agent.currentSpendUSD + estimatedCostUSD > agent.budgetUSD) {
      throw new BudgetExceededError(agent.id, agent.currentSpendUSD, agent.budgetUSD);
    }

    // Check approval threshold: if estimated cost exceeds agent's autonomous limit, pause
    if (estimatedCostUSD > agent.approvalThresholdUSD) {
      const approval = this.requestActionApproval({
        agentId,
        actionName: `dispatch:${task.substring(0, 30)}`,
        estimatedCostUSD,
        justification: `Task estimated cost $${estimatedCostUSD} exceeds autonomous approval threshold $${agent.approvalThresholdUSD}`,
      });
      this.pendingTasks.set(approval.id, { agentId, task, estimatedCostUSD });
      return {
        status: 'paused_for_approval',
        taskId: approval.id,
        requestId: approval.id,
      };
    }

    // Autonomous execution
    agent.status = 'running';
    this.recordSpend(agentId, estimatedCostUSD);
    agent.status = 'completed';

    return {
      status: 'completed',
      taskId: `task_${Date.now()}`,
      output: `Executed '${task}' under autonomous authorization by ${agent.name} (${agent.role})`,
    };
  }

  /**
   * Resumes execution of a paused task after human or supervisor approval decision.
   */
  async resumePausedTask(
    requestId: string,
    approved: boolean,
    approverId: string,
    reason?: string
  ): Promise<{ status: AgentStatus; output?: string }> {
    const pending = this.pendingTasks.get(requestId);
    if (!pending) {
      throw new Error(`No pending task found for approval request '${requestId}'.`);
    }

    if (!approved) {
      this.rejectRequest(requestId, approverId, reason);
      this.pendingTasks.delete(requestId);
      return {
        status: 'idle',
        output: `Task execution was rejected by ${approverId}: ${reason || 'Denied'}`,
      };
    }

    this.approveRequest(requestId, approverId);
    const agent = this.agents.get(pending.agentId);
    if (!agent) {
      throw new Error(`Agent '${pending.agentId}' not found.`);
    }

    agent.status = 'running';
    this.recordSpend(agent.id, pending.estimatedCostUSD);
    agent.status = 'completed';
    this.pendingTasks.delete(requestId);

    return {
      status: 'completed',
      output: `Task '${pending.task}' resumed and completed following approval by ${approverId}.`,
    };
  }

  /**
   * Get an aggregated fleet health and budget summary.
   */
  getOrgSummary(): FleetSummary {
    const agents = Array.from(this.agents.values());
    const active = agents.filter((a) => a.status === 'running').length;
    const paused = agents.filter((a) => a.status === 'paused_for_approval').length;
    const pendingApprovals = Array.from(this.approvalRequests.values()).filter(
      (r) => r.status === 'pending'
    ).length;

    return {
      orgId: this.orgId,
      name: this.name,
      totalBudgetUSD: this.totalBudgetUSD,
      totalSpendUSD: this.currentSpendUSD,
      remainingBudgetUSD: Math.max(0, this.totalBudgetUSD - this.currentSpendUSD),
      totalAgents: agents.length,
      activeAgents: active,
      pausedAgents: paused,
      pendingApprovals,
    };
  }
}
