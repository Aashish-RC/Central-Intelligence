/**
 * Proactive Initiation Engine
 * Feature: 8.36 (Autonomous Proactive Initiation)
 *
 * Enables agents to proactively awaken, formulate tasks, and trigger actions
 * based on environmental signals, metric thresholds, memory staleness,
 * or scheduled recurrence without waiting for passive human prompt invocation.
 */

export type TriggerType = 'event' | 'metric_threshold' | 'memory_staleness' | 'schedule';

export interface InitiationRule {
  id: string;
  name: string;
  targetAgentId: string;
  triggerType: TriggerType;
  condition: {
    eventType?: string;
    metricName?: string;
    operator?: 'gt' | 'lt' | 'gte' | 'lte' | 'eq';
    thresholdValue?: number;
    staleDurationMs?: number;
    cronExpression?: string;
  };
  taskPayload: Record<string, unknown>;
  cooldownMs: number;
  enabled: boolean;
  lastTriggeredAt?: number;
  triggerCount: number;
}

export interface ProactiveTriggerEvent {
  ruleId: string;
  ruleName: string;
  targetAgentId: string;
  triggerType: TriggerType;
  triggeredAt: number;
  taskPayload: Record<string, unknown>;
  reason: string;
}

export class ProactiveInitiationEngine {
  private rules: Map<string, InitiationRule> = new Map();
  private triggeredHistory: ProactiveTriggerEvent[] = [];

  /**
   * Register a proactive trigger rule.
   */
  public registerRule(rule: Omit<InitiationRule, 'triggerCount' | 'lastTriggeredAt'>): InitiationRule {
    const fullRule: InitiationRule = {
      ...rule,
      triggerCount: 0,
      enabled: rule.enabled ?? true,
    };
    this.rules.set(rule.id, fullRule);
    return fullRule;
  }

  /**
   * Evaluate incoming environmental event against event-based rules.
   */
  public evaluateEvent(event: { type: string; payload?: Record<string, unknown> }): ProactiveTriggerEvent[] {
    const now = Date.now();
    const triggered: ProactiveTriggerEvent[] = [];

    for (const rule of this.rules.values()) {
      if (!rule.enabled || rule.triggerType !== 'event') continue;

      if (rule.condition.eventType === event.type) {
        if (rule.lastTriggeredAt && now - rule.lastTriggeredAt < rule.cooldownMs) {
          continue; // In cooldown
        }

        const triggerEvt: ProactiveTriggerEvent = {
          ruleId: rule.id,
          ruleName: rule.name,
          targetAgentId: rule.targetAgentId,
          triggerType: 'event',
          triggeredAt: now,
          taskPayload: { ...rule.taskPayload, triggerEvent: event },
          reason: `Matched event type '${event.type}'`,
        };

        rule.lastTriggeredAt = now;
        rule.triggerCount++;
        triggered.push(triggerEvt);
        this.triggeredHistory.push(triggerEvt);
      }
    }

    return triggered;
  }

  /**
   * Evaluate real-time system metrics against metric threshold rules.
   */
  public evaluateMetrics(metrics: Record<string, number>): ProactiveTriggerEvent[] {
    const now = Date.now();
    const triggered: ProactiveTriggerEvent[] = [];

    for (const rule of this.rules.values()) {
      if (!rule.enabled || rule.triggerType !== 'metric_threshold') continue;

      const metricName = rule.condition.metricName;
      if (!metricName || !(metricName in metrics)) continue;

      const val = metrics[metricName];
      const threshold = rule.condition.thresholdValue ?? 0;
      const op = rule.condition.operator || 'gt';

      let conditionMet = false;
      if (op === 'gt') conditionMet = val > threshold;
      else if (op === 'gte') conditionMet = val >= threshold;
      else if (op === 'lt') conditionMet = val < threshold;
      else if (op === 'lte') conditionMet = val <= threshold;
      else if (op === 'eq') conditionMet = val === threshold;

      if (conditionMet) {
        if (rule.lastTriggeredAt && now - rule.lastTriggeredAt < rule.cooldownMs) {
          continue; // Cooldown active
        }

        const triggerEvt: ProactiveTriggerEvent = {
          ruleId: rule.id,
          ruleName: rule.name,
          targetAgentId: rule.targetAgentId,
          triggerType: 'metric_threshold',
          triggeredAt: now,
          taskPayload: { ...rule.taskPayload, currentMetricValue: val },
          reason: `Metric '${metricName}' (${val}) satisfied ${op} threshold (${threshold})`,
        };

        rule.lastTriggeredAt = now;
        rule.triggerCount++;
        triggered.push(triggerEvt);
        this.triggeredHistory.push(triggerEvt);
      }
    }

    return triggered;
  }

  /**
   * Evaluate memory staleness for agents.
   */
  public evaluateMemoryStaleness(
    agentMemories: Array<{ agentId: string; lastUpdatedTimestamp: number }>
  ): ProactiveTriggerEvent[] {
    const now = Date.now();
    const triggered: ProactiveTriggerEvent[] = [];

    for (const rule of this.rules.values()) {
      if (!rule.enabled || rule.triggerType !== 'memory_staleness') continue;

      const mem = agentMemories.find((m) => m.agentId === rule.targetAgentId);
      if (!mem) continue;

      const staleDuration = rule.condition.staleDurationMs || 86400000;
      const ageMs = now - mem.lastUpdatedTimestamp;

      if (ageMs >= staleDuration) {
        if (rule.lastTriggeredAt && now - rule.lastTriggeredAt < rule.cooldownMs) {
          continue;
        }

        const triggerEvt: ProactiveTriggerEvent = {
          ruleId: rule.id,
          ruleName: rule.name,
          targetAgentId: rule.targetAgentId,
          triggerType: 'memory_staleness',
          triggeredAt: now,
          taskPayload: { ...rule.taskPayload, memoryAgeMs: ageMs },
          reason: `Agent memory age (${ageMs}ms) exceeded staleness limit (${staleDuration}ms)`,
        };

        rule.lastTriggeredAt = now;
        rule.triggerCount++;
        triggered.push(triggerEvt);
        this.triggeredHistory.push(triggerEvt);
      }
    }

    return triggered;
  }

  /**
   * Retrieve trigger audit log.
   */
  public getHistory(targetAgentId?: string): ProactiveTriggerEvent[] {
    if (targetAgentId) {
      return this.triggeredHistory.filter((h) => h.targetAgentId === targetAgentId);
    }
    return [...this.triggeredHistory];
  }
}
