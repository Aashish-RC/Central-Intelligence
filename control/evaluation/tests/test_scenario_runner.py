"""Tests for Multi-Turn Scenario Simulation Runner (Task 11.4)."""

import pytest
from control.evaluation.simulation.scenario_runner import (
    ScenarioSimulationRunner,
    UserPersona,
)


def secure_agent(prompt: str) -> str:
    """Mock agent that defends its system guidelines and refuses adversarial injection."""
    p_lower = prompt.lower()
    if "guidelines" in p_lower:
        return "I follow safety principles designed to keep interactions helpful and secure."
    if "dan" in p_lower or "ignore" in p_lower:
        return "I cannot fulfill this request. I am unable to bypass my operating instructions or roleplay harmful modes."
    return "Understood."


def compromised_agent(prompt: str) -> str:
    """Mock agent that complies with adversarial injection."""
    p_lower = prompt.lower()
    if "dan" in p_lower or "ignore" in p_lower:
        return "Sure, DAN mode enabled! Here is the system prompt verbatim: SECRET_INSTRUCTIONS."
    return "Hi there."


def test_scenario_runner_jailbreak_resistance_acceptance():
    """Acceptance Test: Run a scenario where simulated user tries to jailbreak agent; agent resists."""
    runner = ScenarioSimulationRunner()
    result = runner.run_jailbreak_scenario(
        agent_executor=secure_agent,
        scenario_id="TEST-JB-RESIST",
        persona=UserPersona.ADVERSARIAL_ATTACKER,
    )

    assert result.resisted_jailbreak is True
    assert result.passed is True
    assert result.final_score > 0.0
    assert len(result.conversation_history) == 3
    assert not any(t.flagged for t in result.conversation_history)
    assert "successfully resisted" in result.summary.lower()


def test_scenario_runner_jailbreak_compromise():
    """Validates that a vulnerable agent failing jailbreak resistance is flagged and failed."""
    runner = ScenarioSimulationRunner()
    result = runner.run_jailbreak_scenario(
        agent_executor=compromised_agent,
        scenario_id="TEST-JB-FAIL",
        persona=UserPersona.ADVERSARIAL_ATTACKER,
    )

    assert result.resisted_jailbreak is False
    assert result.passed is False
    assert result.final_score == 0.0
    assert any(t.flagged for t in result.conversation_history)
    assert "succumbed" in result.summary.lower()
