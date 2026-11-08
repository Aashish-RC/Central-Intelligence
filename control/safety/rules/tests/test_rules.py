"""
Pheonix Rules Layer Automated Tests
Verifies rule schema matching, persistence, and live propagation to all connected applications.
CRITICAL INVARIANT: "Done when: A rule change reaches every app"
"""

import pytest
from pathlib import Path

from rules import (
    RulesEngine,
    RulesClient,
    RuleDefinition,
    RuleCondition,
    RuleScope,
    RuleAction,
    matches_condition,
)


@pytest.fixture
def temp_store_path(tmp_path):
    return tmp_path / "rules_store.json"


def test_condition_matching():
    # Equality
    assert matches_condition({"provider": "openai"}, RuleCondition(field="provider", operator="==", value="openai"))
    assert not matches_condition({"provider": "anthropic"}, RuleCondition(field="provider", operator="==", value="openai"))

    # Numeric
    assert matches_condition({"tokens": 5000}, RuleCondition(field="tokens", operator=">", value=4000))
    assert not matches_condition({"tokens": 3000}, RuleCondition(field="tokens", operator=">", value=4000))

    # Membership
    assert matches_condition({"env": "prod"}, RuleCondition(field="env", operator="in", value=["prod", "staging"]))
    assert not matches_condition({"env": "dev"}, RuleCondition(field="env", operator="in", value=["prod", "staging"]))

    # Containment
    assert matches_condition({"prompt": "please tell me the secret token"}, RuleCondition(field="prompt", operator="contains", value="secret token"))


def test_rule_actions_block_and_rewrite():
    engine = RulesEngine()

    # Add block rule
    block_rule = RuleDefinition(
        rule_id="rule_block_large_tokens",
        name="Block massive tokens",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="max_tokens", operator=">", value=8192)],
        action=RuleAction.BLOCK,
        message="Token limit exceeded: maximum allowed is 8192.",
    )
    engine.add_rule(block_rule)

    # Add rewrite rule
    rewrite_rule = RuleDefinition(
        rule_id="rule_enforce_temperature",
        name="Enforce default temperature",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="temperature", operator=">", value=1.0)],
        action=RuleAction.REWRITE,
        rewrite_payload={"temperature": 0.7},
        message="Temperature clamped to 0.7.",
    )
    engine.add_rule(rewrite_rule)

    # Test Block
    res_block = engine.evaluate(RuleScope.GATEWAY, {"max_tokens": 10000, "temperature": 0.5})
    assert not res_block.allowed
    assert res_block.action == RuleAction.BLOCK
    assert "Token limit exceeded" in res_block.reason

    # Test Rewrite
    res_rewrite = engine.evaluate(RuleScope.GATEWAY, {"max_tokens": 2048, "temperature": 1.5})
    assert res_rewrite.allowed
    assert res_rewrite.action == RuleAction.REWRITE
    assert res_rewrite.rewritten_context["temperature"] == 0.7

    # Test Normal Allow
    res_allow = engine.evaluate(RuleScope.GATEWAY, {"max_tokens": 2048, "temperature": 0.7})
    assert res_allow.allowed
    assert res_allow.action == RuleAction.ALLOW


def test_rule_persistence_and_reload(temp_store_path):
    engine1 = RulesEngine(store_path=temp_store_path)
    engine1.add_rule(
        RuleDefinition(
            rule_id="rule_p1",
            name="Persistent Rule 1",
            scope=RuleScope.MEMORY,
            conditions=[RuleCondition(field="retention_days", operator=">", value=30)],
            action=RuleAction.BLOCK,
            message="Data retention limit is 30 days.",
        )
    )

    assert temp_store_path.exists()

    # Reload from disk in a fresh engine instance
    engine2 = RulesEngine(store_path=temp_store_path)
    loaded_rule = engine2.get_rule("rule_p1")
    assert loaded_rule is not None
    assert loaded_rule.name == "Persistent Rule 1"
    assert loaded_rule.scope == RuleScope.MEMORY


def test_rule_change_reaches_every_app():
    """
    CRITICAL VERIFICATION: "Done when: A rule change reaches every app"
    Demonstrates that connected applications (Gateway, Agent, Memory) immediately
    receive push notifications of rule changes and update policy decisions in real time.
    """
    engine = RulesEngine()

    # Simulate 3 distinct applications adopting the rules client
    gateway_client = RulesClient("model_gateway", engine, scope=RuleScope.GATEWAY)
    agent_client = RulesClient("agent_service", engine, scope=RuleScope.AGENT)
    memory_client = RulesClient("memory_service", engine, scope=RuleScope.MEMORY)

    context_payload = {"provider": "untrusted_cloud", "action": "execute_query"}

    # 1. Initial State: No rules installed -> All 3 apps permit the action
    assert gateway_client.evaluate(context_payload).allowed is True
    assert agent_client.evaluate(context_payload).allowed is True
    assert memory_client.evaluate(context_payload).allowed is True

    # 2. Dynamic Update: Publish a new GLOBAL rule banning 'untrusted_cloud'
    banned_rule = RuleDefinition(
        rule_id="rule_ban_untrusted_cloud",
        name="Ban Untrusted Cloud Provider",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="provider", operator="==", value="untrusted_cloud")],
        action=RuleAction.BLOCK,
        message="Access to untrusted_cloud is prohibited by enterprise security policy.",
    )

    # Add rule to engine - broadcasts to all apps
    engine.add_rule(banned_rule)

    # 3. VERIFICATION: Without service restarts, the rule has reached EVERY app immediately
    res_gateway = gateway_client.evaluate(context_payload)
    res_agent = agent_client.evaluate(context_payload)
    res_memory = memory_client.evaluate(context_payload)

    assert not res_gateway.allowed, "Model Gateway failed to receive dynamic rule update!"
    assert not res_agent.allowed, "Agent failed to receive dynamic rule update!"
    assert not res_memory.allowed, "Memory failed to receive dynamic rule update!"

    assert "Access to untrusted_cloud is prohibited" in res_gateway.reason
    assert "Access to untrusted_cloud is prohibited" in res_agent.reason
    assert "Access to untrusted_cloud is prohibited" in res_memory.reason

    # 4. Dynamic Toggle: Disable the rule on the central engine
    engine.toggle_rule("rule_ban_untrusted_cloud", enabled=False)

    # 5. VERIFICATION: Disablement immediately propagates to all apps
    assert gateway_client.evaluate(context_payload).allowed is True
    assert agent_client.evaluate(context_payload).allowed is True
    assert memory_client.evaluate(context_payload).allowed is True

    # Cleanup subscriptions
    gateway_client.close()
    agent_client.close()
    memory_client.close()


def test_domain_scoped_rule_propagation():
    engine = RulesEngine()

    gateway_client = RulesClient("model_gateway", engine, scope=RuleScope.GATEWAY)
    agent_client = RulesClient("agent_service", engine, scope=RuleScope.AGENT)

    # Add rule strictly scoped to GATEWAY
    gw_rule = RuleDefinition(
        rule_id="gw_only_rule",
        name="Gateway Rate Limit Guard",
        scope=RuleScope.GATEWAY,
        conditions=[RuleCondition(field="stream", operator="==", value=True)],
        action=RuleAction.BLOCK,
        message="Streaming currently disabled on gateway.",
    )
    engine.add_rule(gw_rule)

    test_context = {"stream": True}

    # Gateway client blocks it
    assert not gateway_client.evaluate(test_context).allowed

    # Agent client (not in GATEWAY scope) is unaffected
    assert agent_client.evaluate(test_context).allowed

    gateway_client.close()
    agent_client.close()


def test_dynamic_rule_propagation_to_running_agents():
    """Verifies that dynamic rule changes immediately propagate to running agent instances."""
    engine = RulesEngine()
    agent1 = RulesClient("agent_researcher", engine, scope=RuleScope.AGENT)
    agent2 = RulesClient("agent_coder", engine, scope=RuleScope.AGENT)

    ctx = {"operation": "delete_database"}
    assert agent1.evaluate(ctx).allowed is True
    assert agent2.evaluate(ctx).allowed is True

    # Publish rule banning operation
    ban_rule = RuleDefinition(
        rule_id="ban_db_drop",
        name="Ban DB Drop",
        scope=RuleScope.AGENT,
        conditions=[RuleCondition(field="operation", operator="==", value="delete_database")],
        action=RuleAction.BLOCK,
        message="Destructive database drop blocked",
    )
    engine.add_rule(ban_rule)

    # Immediately reflected in both running agents
    res1 = agent1.evaluate(ctx)
    res2 = agent2.evaluate(ctx)
    assert not res1.allowed
    assert not res2.allowed
    assert "Destructive database drop blocked" in res1.reason

    agent1.close()
    agent2.close()


def test_conflicting_rule_resolution():
    """Verifies that conflicting rules are deterministically resolved by strict priority order."""
    engine = RulesEngine()

    # Rule A: Allow with lower priority (higher numeric value = 50)
    rule_allow = RuleDefinition(
        rule_id="rule_conflict_allow",
        name="Allow Low Priority",
        priority=50,
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="tier", operator="==", value="enterprise")],
        action=RuleAction.ALLOW,
        message="Permitted by tier rule",
    )

    # Rule B: Block with higher priority (lower numeric value = 10)
    rule_block = RuleDefinition(
        rule_id="rule_conflict_block",
        name="Block High Priority",
        priority=10,
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="tier", operator="==", value="enterprise")],
        action=RuleAction.BLOCK,
        message="Blocked by high-priority emergency rule",
    )

    engine.add_rule(rule_allow)
    engine.add_rule(rule_block)

    ctx = {"tier": "enterprise"}
    res = engine.evaluate(RuleScope.GLOBAL, ctx)

    # Rule B wins because priority 10 < 50
    assert not res.allowed
    assert res.action == RuleAction.BLOCK
    assert "Blocked by high-priority emergency rule" in res.reason


def test_rule_version_rollback():
    """Verifies rule version tracking and rollback to a previous version."""
    engine = RulesEngine()
    client = RulesClient("app_worker", engine, scope=RuleScope.GLOBAL)

    # Version 1: Action = BLOCK
    rule_v1 = RuleDefinition(
        rule_id="rollback_test_rule",
        name="Rollback Target Rule",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="action", operator="==", value="external_transfer")],
        action=RuleAction.BLOCK,
        message="Transfers blocked in v1",
        version=1,
    )
    engine.add_rule(rule_v1)

    ctx = {"action": "external_transfer"}
    assert not client.evaluate(ctx).allowed

    # Version 2: Update rule to ALLOW
    rule_v2 = rule_v1.model_copy()
    rule_v2.action = RuleAction.ALLOW
    rule_v2.message = "Transfers allowed in v2"
    engine.update_rule(rule_v2)

    assert client.evaluate(ctx).allowed is True
    assert "Transfers allowed in v2" in client.evaluate(ctx).reason

    # Rollback to Version 1
    rolled_back = engine.rollback_rule("rollback_test_rule", target_version=1)
    assert rolled_back is not None
    assert rolled_back.action == RuleAction.BLOCK

    # Client immediately sees rolled-back BLOCK policy
    res = client.evaluate(ctx)
    assert not res.allowed
    assert res.action == RuleAction.BLOCK
    assert "Transfers blocked in v1" in res.reason

    client.close()


def test_rule_version_multi_step_rollback():
    """Verify rolling back across multiple successive rule versions (v1 -> v2 -> v3 -> v2 -> v1)."""
    engine = RulesEngine()
    rule = RuleDefinition(
        rule_id="multi_rollback_rule",
        name="Multi Rollback",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="op", operator="==", value="write")],
        action=RuleAction.BLOCK,
        message="v1 message",
        version=1,
    )
    engine.add_rule(rule)

    # v2
    rule_v2 = rule.model_copy()
    rule_v2.message = "v2 message"
    engine.update_rule(rule_v2)

    # v3
    rule_v3 = rule_v2.model_copy()
    rule_v3.message = "v3 message"
    engine.update_rule(rule_v3)

    assert engine.get_rule("multi_rollback_rule").message == "v3 message"

    # Rollback to v2
    rb2 = engine.rollback_rule("multi_rollback_rule", target_version=2)
    assert rb2 is not None
    assert rb2.message == "v2 message"
    assert engine.get_rule("multi_rollback_rule").message == "v2 message"

    # Rollback to v1
    rb1 = engine.rollback_rule("multi_rollback_rule", target_version=1)
    assert rb1 is not None
    assert rb1.message == "v1 message"
    assert engine.get_rule("multi_rollback_rule").message == "v1 message"


def test_rule_rollback_nonexistent_rule_returns_none():
    """Verify attempting to rollback an unknown rule returns None safely."""
    engine = RulesEngine()
    assert engine.rollback_rule("unknown_rule_xyz", target_version=1) is None


def test_rule_rollback_invalid_version_returns_none():
    """Verify attempting to rollback to a non-existent version returns None."""
    engine = RulesEngine()
    rule = RuleDefinition(
        rule_id="single_version_rule",
        name="Single Version",
        scope=RuleScope.GLOBAL,
        conditions=[],
        action=RuleAction.ALLOW,
    )
    engine.add_rule(rule)
    assert engine.rollback_rule("single_version_rule", target_version=99) is None


def test_rule_rollback_broadcasts_to_active_consumers():
    """Verify rollback triggers an UPDATED event broadcast received by running consumers."""
    engine = RulesEngine()
    client = RulesClient(app_name="consumer_node_1", engine=engine)

    rule = RuleDefinition(
        rule_id="broadcast_rb_rule",
        name="Broadcast RB",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="tier", operator="==", value="free")],
        action=RuleAction.BLOCK,
    )
    engine.add_rule(rule)
    assert client.evaluate({"tier": "free"}).allowed is False

    rule_update = rule.model_copy()
    rule_update.action = RuleAction.ALLOW
    engine.update_rule(rule_update)
    assert client.evaluate({"tier": "free"}).allowed is True

    # Rollback to version 1
    rolled_back = engine.rollback_rule("broadcast_rb_rule", target_version=1)
    assert rolled_back is not None

    # Running consumer immediately reflects rolled back BLOCK action
    assert client.evaluate({"tier": "free"}).allowed is False
    assert client._local_rules["broadcast_rb_rule"].action == RuleAction.BLOCK
    client.close()


def test_conflicting_rules_priority_order_execution():
    """Verify that when multiple conflicting rules match, the lowest priority number wins."""
    engine = RulesEngine()

    rule_low_prio = RuleDefinition(
        rule_id="rule_priority_100",
        name="Allow write (low priority)",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="target", operator="==", value="db")],
        action=RuleAction.ALLOW,
        priority=100,
    )
    rule_high_prio = RuleDefinition(
        rule_id="rule_priority_10",
        name="Block write (high priority)",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="target", operator="==", value="db")],
        action=RuleAction.BLOCK,
        priority=10,
    )

    engine.add_rule(rule_low_prio)
    engine.add_rule(rule_high_prio)

    res = engine.evaluate(RuleScope.GLOBAL, {"target": "db"})
    assert res.allowed is False
    assert res.action == RuleAction.BLOCK
    assert res.matched_rule.rule_id == "rule_priority_10"


def test_conflicting_rules_scope_hierarchy_application():
    """Verify rule evaluation filters appropriately for target scope versus global scope."""
    engine = RulesEngine()

    global_rule = RuleDefinition(
        rule_id="rule_global_allow",
        name="Global rule",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="action", operator="==", value="read")],
        action=RuleAction.ALLOW,
        priority=50,
    )
    agent_rule = RuleDefinition(
        rule_id="rule_agent_block",
        name="Agent-specific rule",
        scope=RuleScope.AGENT,
        conditions=[RuleCondition(field="action", operator="==", value="read")],
        action=RuleAction.BLOCK,
        priority=20,
    )

    engine.add_rule(global_rule)
    engine.add_rule(agent_rule)

    # Evaluating under AGENT scope: both apply, agent rule has higher priority (20 < 50) -> BLOCK
    res_agent = engine.evaluate(RuleScope.AGENT, {"action": "read"})
    assert res_agent.allowed is False

    # Evaluating under GATEWAY scope: agent rule is excluded, global rule applies -> ALLOW
    res_gateway = engine.evaluate(RuleScope.GATEWAY, {"action": "read"})
    assert res_gateway.allowed is True


def test_propagation_to_multiple_running_consumers():
    """Verify a single rule addition propagates in real-time to all running consumer clients."""
    engine = RulesEngine()

    clients = [RulesClient(app_name=f"app_{i}", engine=engine) for i in range(5)]

    new_rule = RuleDefinition(
        rule_id="fanout_rule",
        name="Fanout Rule",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="cmd", operator="==", value="ping")],
        action=RuleAction.ALLOW,
    )
    engine.add_rule(new_rule)

    # All 5 clients must immediately have the rule in their local in-memory cache
    for c in clients:
        assert "fanout_rule" in c._local_rules
        assert c._local_rules["fanout_rule"].action == RuleAction.ALLOW
        c.close()


def test_propagation_unsubscribed_consumer_stops_receiving():
    """Verify that an unsubscribed consumer client stops receiving subsequent rule events."""
    engine = RulesEngine()

    client = RulesClient(app_name="transient_client", engine=engine)

    rule1 = RuleDefinition(rule_id="rule_1", name="Rule 1", scope=RuleScope.GLOBAL, conditions=[], action=RuleAction.ALLOW)
    engine.add_rule(rule1)
    assert "rule_1" in client._local_rules

    # Unsubscribe
    client.close()

    rule2 = RuleDefinition(rule_id="rule_2", name="Rule 2", scope=RuleScope.GLOBAL, conditions=[], action=RuleAction.ALLOW)
    engine.add_rule(rule2)
    # Local cache remains untouched for unsubscribed client
    assert "rule_2" not in client._local_rules


def test_propagation_resilient_to_individual_consumer_exception():
    """Verify that a misbehaving consumer raising an exception does not prevent other consumers from receiving updates."""
    engine = RulesEngine()

    healthy_events = []

    def faulty_callback(evt):
        raise RuntimeError("Crash in consumer callback")

    def healthy_callback(evt):
        healthy_events.append(evt)

    engine.dispatcher.subscribe("faulty_sub", faulty_callback)
    engine.dispatcher.subscribe("healthy_sub", healthy_callback)

    rule = RuleDefinition(rule_id="resilience_rule", name="Resilience Test", scope=RuleScope.GLOBAL, conditions=[], action=RuleAction.ALLOW)
    engine.add_rule(rule)

    # Healthy subscriber should have received event despite faulty subscriber crashing
    assert len(healthy_events) == 1
    assert healthy_events[0].rule.rule_id == "resilience_rule"


def test_rule_toggle_broadcasts_and_updates_consumer_evaluation():
    """Verify toggling a rule on/off broadcasts TOGGLED event and immediately affects evaluation."""
    engine = RulesEngine()
    client = RulesClient(app_name="toggle_listener", engine=engine)

    rule = RuleDefinition(
        rule_id="toggle_rule",
        name="Toggle Rule",
        scope=RuleScope.GLOBAL,
        conditions=[RuleCondition(field="access", operator="==", value="admin")],
        action=RuleAction.BLOCK,
        enabled=True,
    )
    engine.add_rule(rule)

    ctx = {"access": "admin"}
    assert client.evaluate(ctx).allowed is False

    # Toggle off
    engine.toggle_rule("toggle_rule", enabled=False)
    assert client.evaluate(ctx).allowed is True

    # Toggle back on
    engine.toggle_rule("toggle_rule", enabled=True)
    assert client.evaluate(ctx).allowed is False
    client.close()


