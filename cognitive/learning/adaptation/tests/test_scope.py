"""Unit tests for Adaptation Scope Applier (Feature 7.15)."""

import pytest
from cognitive.learning.adaptation.scope_applier import (
    AdaptationScopeApplier,
    AdaptationScope,
    LearnedAdaptation,
)


def test_user_level_adaptation_doesnt_affect_other_users():
    applier = AdaptationScopeApplier()

    # User Alice has a personal learned adaptation: "Answer in Japanese only"
    alice_adaptation = LearnedAdaptation(
        id="adapt_user_alice_lang",
        scope=AdaptationScope.USER,
        target_id="alice",
        adaptation_type="style",
        payload={"prompt_suffix": "Always format answers in concise Japanese."},
        priority=10,
    )
    applier.register_adaptation(alice_adaptation)

    # Base prompt
    base = "Explain the system architecture."

    # When Alice queries, her adaptation is applied
    prompt_alice = applier.apply_to_prompt(base, user_id="alice")
    assert "concise Japanese" in prompt_alice
    assert "[USER:alice]" in prompt_alice

    # When Bob queries, Alice's adaptation is completely absent
    prompt_bob = applier.apply_to_prompt(base, user_id="bob")
    assert "Japanese" not in prompt_bob
    assert prompt_bob == base


def test_scope_hierarchy_precedence():
    applier = AdaptationScopeApplier()

    # Org-level adaptation
    applier.register_adaptation(
        LearnedAdaptation(
            id="adapt_org_finance",
            scope=AdaptationScope.ORG,
            target_id="org_fintech",
            adaptation_type="policy",
            payload={"prompt_suffix": "Enforce SOX compliance disclosures."},
            priority=5,
        )
    )

    # User-level adaptation
    applier.register_adaptation(
        LearnedAdaptation(
            id="adapt_user_dan",
            scope=AdaptationScope.USER,
            target_id="dan",
            adaptation_type="style",
            payload={"prompt_suffix": "Format using markdown tables."},
            priority=10,
        )
    )

    applicable = applier.get_applicable_adaptations(user_id="dan", org_id="org_fintech")
    assert len(applicable) == 2
    # User adaptation has higher precedence than Org adaptation
    assert applicable[0].scope == AdaptationScope.USER
    assert applicable[1].scope == AdaptationScope.ORG


def test_profession_and_app_scope_isolation():
    applier = AdaptationScopeApplier()

    applier.register_adaptation(
        LearnedAdaptation(
            id="adapt_prof_doctor",
            scope=AdaptationScope.PROFESSION,
            target_id="physician",
            adaptation_type="style",
            payload={"prompt_suffix": "Use ICD-10 clinical diagnosis terminology."},
        )
    )

    # For a doctor
    doc_prompt = applier.apply_to_prompt("Analyze symptoms", profession="physician")
    assert "ICD-10 clinical diagnosis" in doc_prompt

    # For an engineer
    eng_prompt = applier.apply_to_prompt("Analyze symptoms", profession="software_engineer")
    assert "ICD-10" not in eng_prompt
