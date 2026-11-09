import { test } from 'node:test';
import assert from 'node:assert';
import { ProactiveInitiationEngine } from '../engine/index.js';

test('Feature 8.36: Autonomous Proactive Initiation Engine', async (t) => {
  await t.test('triggers proactive agent activation based on system event', () => {
    const engine = new ProactiveInitiationEngine();
    engine.registerRule({
      id: 'rule_incident_detected',
      name: 'Incident Auto-Triage',
      targetAgentId: 'sre_agent',
      triggerType: 'event',
      condition: { eventType: 'system.service_outage' },
      taskPayload: { action: 'triage_incident', priority: 'P1' },
      cooldownMs: 5000,
      enabled: true,
    });

    const triggers = engine.evaluateEvent({
      type: 'system.service_outage',
      payload: { service: 'payment_gateway', region: 'us-east-1' },
    });

    assert.strictEqual(triggers.length, 1);
    assert.strictEqual(triggers[0].targetAgentId, 'sre_agent');
    assert.strictEqual(triggers[0].ruleId, 'rule_incident_detected');
    assert.ok(triggers[0].reason.includes('Matched event type'));

    // Cooldown test - immediate duplicate event should not trigger
    const cooldownTriggers = engine.evaluateEvent({
      type: 'system.service_outage',
      payload: { service: 'payment_gateway' },
    });
    assert.strictEqual(cooldownTriggers.length, 0);
  });

  await t.test('evaluates metrics against threshold conditions', () => {
    const engine = new ProactiveInitiationEngine();
    engine.registerRule({
      id: 'rule_high_error_rate',
      name: 'High Error Rate Investigation',
      targetAgentId: 'observability_agent',
      triggerType: 'metric_threshold',
      condition: {
        metricName: 'http_5xx_rate',
        operator: 'gt',
        thresholdValue: 0.05,
      },
      taskPayload: { action: 'analyze_error_logs' },
      cooldownMs: 10000,
      enabled: true,
    });

    // Metric below threshold -> no trigger
    const trigLow = engine.evaluateMetrics({ http_5xx_rate: 0.02, cpu_usage: 45 });
    assert.strictEqual(trigLow.length, 0);

    // Metric above threshold -> triggers agent
    const trigHigh = engine.evaluateMetrics({ http_5xx_rate: 0.08, cpu_usage: 80 });
    assert.strictEqual(trigHigh.length, 1);
    assert.strictEqual(trigHigh[0].targetAgentId, 'observability_agent');
    assert.strictEqual(trigHigh[0].taskPayload.currentMetricValue, 0.08);
  });

  await t.test('detects memory staleness and prompts proactive refresher agent', () => {
    const engine = new ProactiveInitiationEngine();
    engine.registerRule({
      id: 'rule_knowledge_staleness',
      name: 'Agent Knowledge Base Refresh',
      targetAgentId: 'research_agent',
      triggerType: 'memory_staleness',
      condition: { staleDurationMs: 60000 }, // 1 minute
      taskPayload: { action: 'refresh_documentation_index' },
      cooldownMs: 30000,
      enabled: true,
    });

    const now = Date.now();
    const agentMemories = [
      { agentId: 'research_agent', lastUpdatedTimestamp: now - 120000 }, // 2 minutes old -> stale!
      { agentId: 'code_agent', lastUpdatedTimestamp: now - 10000 },
    ];

    const triggers = engine.evaluateMemoryStaleness(agentMemories);
    assert.strictEqual(triggers.length, 1);
    assert.strictEqual(triggers[0].targetAgentId, 'research_agent');
    assert.strictEqual(triggers[0].triggerType, 'memory_staleness');
  });
});
