/**
 * Human Escalation Protocol & Intervention Control Plane
 *
 * Provides human-in-the-loop intervention, escalation triggers, state snapshots,
 * operator steering injection, and timeout cascade management.
 *
 * Features: 8.30 (Human Escalation Protocol), 8.50 (Intervention & Override Control Plane)
 */

export type EscalationUrgency = 'low' | 'normal' | 'high' | 'critical';

export type EscalationStatus = 'pending' | 'acknowledged' | 'resolved' | 'timed_out' | 'overridden';

export interface EscalationTrigger {
  id: string;
  workflowId: string;
  agentId: string;
  urgency: EscalationUrgency;
  title: string;
  reason: string;
  stateSnapshot: Record<string, unknown>;
  suggestedActions: string[];
  timeoutSeconds: number;
  status: EscalationStatus;
  operatorId?: string;
  createdAt: number;
  resolvedAt?: number;
  resolutionAction?: 'resume' | 'override' | 'abort';
  steeringInput?: string;
  overrideState?: Record<string, unknown>;
}

export class HumanEscalationProtocol {
  private activeEscalations: Map<string, EscalationTrigger> = new Map();
  private history: EscalationTrigger[] = [];

  /**
   * Trigger an escalation pausing automated agent execution and alerting human operators.
   */
  triggerEscalation(params: {
    workflowId: string;
    agentId: string;
    title: string;
    reason: string;
    urgency?: EscalationUrgency;
    stateSnapshot?: Record<string, unknown>;
    suggestedActions?: string[];
    timeoutSeconds?: number;
  }): EscalationTrigger {
    const id = `esc_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const trigger: EscalationTrigger = {
      id,
      workflowId: params.workflowId,
      agentId: params.agentId,
      urgency: params.urgency || 'normal',
      title: params.title,
      reason: params.reason,
      stateSnapshot: params.stateSnapshot ? { ...params.stateSnapshot } : {},
      suggestedActions: params.suggestedActions ? [...params.suggestedActions] : ['resume', 'abort'],
      timeoutSeconds: params.timeoutSeconds || 300,
      status: 'pending',
      createdAt: Date.now(),
    };

    this.activeEscalations.set(id, trigger);
    return trigger;
  }

  /**
   * Human operator acknowledges engagement with an escalation.
   */
  acknowledgeEscalation(triggerId: string, operatorId: string): EscalationTrigger {
    const trigger = this.activeEscalations.get(triggerId);
    if (!trigger) {
      throw new Error(`Escalation trigger '${triggerId}' not found.`);
    }
    if (trigger.status !== 'pending') {
      throw new Error(`Escalation '${triggerId}' cannot be acknowledged with status '${trigger.status}'.`);
    }

    trigger.status = 'acknowledged';
    trigger.operatorId = operatorId;
    return trigger;
  }

  /**
   * Human operator resolves escalation with steering input or state override.
   */
  resolveEscalation(params: {
    triggerId: string;
    operatorId: string;
    action: 'resume' | 'override' | 'abort';
    steeringInput?: string;
    overrideState?: Record<string, unknown>;
  }): EscalationTrigger {
    const trigger = this.activeEscalations.get(params.triggerId);
    if (!trigger) {
      throw new Error(`Escalation trigger '${params.triggerId}' not found.`);
    }
    if (trigger.status === 'resolved' || trigger.status === 'overridden') {
      throw new Error(`Escalation '${params.triggerId}' is already resolved.`);
    }

    trigger.operatorId = params.operatorId;
    trigger.resolutionAction = params.action;
    trigger.steeringInput = params.steeringInput;
    trigger.overrideState = params.overrideState;
    trigger.resolvedAt = Date.now();
    trigger.status = params.action === 'override' ? 'overridden' : 'resolved';

    this.activeEscalations.delete(params.triggerId);
    this.history.push(trigger);
    return trigger;
  }

  /**
   * Sweeps pending escalations and transitions expired items to timed_out.
   */
  checkTimeouts(): EscalationTrigger[] {
    const now = Date.now();
    const timedOut: EscalationTrigger[] = [];

    for (const [id, trigger] of this.activeEscalations.entries()) {
      if (trigger.status === 'pending') {
        const elapsed = (now - trigger.createdAt) / 1000;
        if (elapsed > trigger.timeoutSeconds) {
          trigger.status = 'timed_out';
          trigger.resolvedAt = now;
          this.activeEscalations.delete(id);
          this.history.push(trigger);
          timedOut.push(trigger);
        }
      }
    }

    return timedOut;
  }

  getActiveEscalations(): EscalationTrigger[] {
    return Array.from(this.activeEscalations.values());
  }

  getEscalationHistory(): EscalationTrigger[] {
    return [...this.history];
  }
}
