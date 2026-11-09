"""Unit tests for Action Safety: Risk Classification, Approval Gates, Compensation, Blast Radius.

Features: 5.22, 5.23, 5.24, 5.27
"""

import pytest
from cognitive.action.safety import (
    ApprovalGate,
    BlastRadiusSimulator,
    CompensationManager,
    RiskClassifier,
    RiskLevel,
)


@pytest.fixture
def classifier():
    return RiskClassifier(approval_threshold=RiskLevel.HIGH)


@pytest.fixture
def gate():
    return ApprovalGate()


@pytest.fixture
def comp_mgr():
    return CompensationManager()


@pytest.fixture
def simulator():
    return BlastRadiusSimulator()


def test_risk_classification_tiers(classifier):
    # Low risk
    low = classifier.classify_action("read_file", {"path": "config.yaml"})
    assert low.risk_level == RiskLevel.LOW
    assert low.requires_approval is False

    # Medium risk (scratch write)
    med = classifier.classify_action("write_file", {"path": "/tmp/scratchpad.txt"})
    assert med.risk_level == RiskLevel.MEDIUM
    assert med.requires_approval is False

    # High risk (system write)
    high = classifier.classify_action("run_command", {"command": "npm publish"})
    assert high.risk_level == RiskLevel.HIGH
    assert high.requires_approval is True

    # Critical risk (destructive operation)
    crit = classifier.classify_action("execute_sql", {"sql": "DROP TABLE transactions"})
    assert crit.risk_level == RiskLevel.CRITICAL
    assert crit.requires_approval is True
    assert crit.is_reversible is False


def test_approval_gate_lifecycle(classifier, gate):
    assessment = classifier.classify_action("deploy_service", {"cluster": "production"})
    assert assessment.requires_approval is True

    # Request approval
    req = gate.request_approval(assessment, agent_id="agent_deployer")
    assert req.status == "pending"
    assert len(gate.get_pending()) == 1

    # Supervisor approves
    resolved = gate.resolve(req.gate_id, approved=True, approver="human_lead", decision_reason="Verified by QA")
    assert resolved.status == "approved"
    assert resolved.approver == "human_lead"
    assert len(gate.get_pending()) == 0
    assert len(gate.get_history()) == 1


def test_compensation_and_rollback(comp_mgr):
    state = {"files_created": []}

    def rollback_fn():
        state["files_created"].clear()
        return True

    state["files_created"].append("created.txt")
    hook_id = comp_mgr.register_compensation("create_file", rollback_fn, description="Remove created.txt")

    assert len(state["files_created"]) == 1
    # Rollback
    ok = comp_mgr.rollback(hook_id)
    assert ok is True
    assert len(state["files_created"]) == 0


def test_session_lifo_rollback(comp_mgr):
    execution_order = []

    comp_mgr.register_compensation("step1", lambda: execution_order.append("undo_1") or True, session_id="s1")
    comp_mgr.register_compensation("step2", lambda: execution_order.append("undo_2") or True, session_id="s1")

    count = comp_mgr.rollback_session("s1")
    assert count == 2
    assert execution_order == ["undo_2", "undo_1"]  # LIFO order


def test_blast_radius_simulator(simulator):
    # Non-destructive simulation
    rep = simulator.simulate(
        action_name="write_file",
        parameters={"path": "src/app.ts", "channel": "alerts", "url": "https://api.github.com"},
    )
    assert "src/app.ts" in rep.affected_files
    assert "chat:alerts" in rep.affected_services
    assert "http:https://api.github.com" in rep.affected_services
    assert rep.is_destructive is False
    assert rep.reversibility_guaranteed is True

    # Destructive simulation
    rep_dest = simulator.simulate(
        action_name="execute_sql",
        parameters={"sql": "DROP DATABASE production_db"},
    )
    assert rep_dest.is_destructive is True
    assert rep_dest.reversibility_guaranteed is False
