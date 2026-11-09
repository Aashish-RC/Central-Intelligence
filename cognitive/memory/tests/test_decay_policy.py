"""Unit tests for Decay & Compression Policy Engine (Features 2.13, 2.39, 2.40)."""

from datetime import datetime, timedelta, timezone
import pytest
from memory.core.models import FactCategory, FactItem, MemoryRecord, utc_now
from memory.consolidation.decay_policy import (
    DecayCompressionPolicyEngine,
    MemoryDecayPolicy,
)


@pytest.fixture
def policy_engine():
    policy = MemoryDecayPolicy(
        half_life_days=30.0,
        prune_threshold=0.15,
        exempt_categories={FactCategory.RULE, FactCategory.CONSTRAINT},
    )
    return DecayCompressionPolicyEngine(policy=policy)


def test_exempt_categories_do_not_decay(policy_engine):
    stale_date = utc_now() - timedelta(days=365)

    rule_score = policy_engine.calculate_relevance_score(
        last_accessed_at=stale_date,
        base_confidence=0.9,
        category=FactCategory.RULE,
    )
    assert rule_score == 1.0

    constraint_score = policy_engine.calculate_relevance_score(
        last_accessed_at=stale_date,
        base_confidence=0.8,
        category=FactCategory.CONSTRAINT,
    )
    assert constraint_score == 1.0


def test_exponential_decay_with_time(policy_engine):
    now = utc_now()
    recent_score = policy_engine.calculate_relevance_score(
        last_accessed_at=now,
        base_confidence=1.0,
        access_count=0,
        category=FactCategory.PREFERENCE,
        current_time=now,
    )
    assert recent_score == 1.0

    # 60 days ago (two half lives)
    stale_date = now - timedelta(days=60)
    stale_score = policy_engine.calculate_relevance_score(
        last_accessed_at=stale_date,
        base_confidence=1.0,
        access_count=0,
        category=FactCategory.PREFERENCE,
        current_time=now,
    )
    # 0.5^2 = 0.25 (scaled by freq bonus log2(2) = 1.0)
    assert 0.2 < stale_score < 0.3


def test_frequency_reinforcement_resists_decay(policy_engine):
    stale_date = utc_now() - timedelta(days=45)

    zero_access = policy_engine.calculate_relevance_score(
        last_accessed_at=stale_date,
        base_confidence=1.0,
        access_count=0,
        category=FactCategory.FACT,
    )

    high_access = policy_engine.calculate_relevance_score(
        last_accessed_at=stale_date,
        base_confidence=1.0,
        access_count=10,
        category=FactCategory.FACT,
    )

    assert high_access > zero_access


def test_identify_prune_candidates(policy_engine):
    now = utc_now()
    very_old = now - timedelta(days=120)

    f_active = FactItem(
        user_id="user1",
        category=FactCategory.PREFERENCE,
        key="theme",
        value="dark",
        confidence_score=1.0,
        updated_at=now,
    )
    f_stale = FactItem(
        user_id="user1",
        category=FactCategory.FACT,
        key="temp_ip",
        value="10.0.0.5",
        confidence_score=0.5,
        updated_at=very_old,
        last_accessed_at=very_old,
    )
    f_rule_old = FactItem(
        user_id="user1",
        category=FactCategory.RULE,
        key="safety_rule",
        value="Never commit secrets",
        confidence_score=1.0,
        updated_at=very_old,
        last_accessed_at=very_old,
    )

    candidates = policy_engine.identify_prune_candidates([f_active, f_stale, f_rule_old])
    assert len(candidates) == 1
    assert candidates[0].key == "temp_ip"


def test_compress_episodes(policy_engine):
    now = utc_now()
    records = [
        MemoryRecord(
            user_id="user1",
            text=f"Worked on microservice module {i}",
            created_at=now - timedelta(days=i),
        )
        for i in range(5)
    ]

    result = policy_engine.compress_episodes(records)
    assert result["records_compressed"] == 5
    assert "Episodic rollup" in result["summary"]
    assert result["token_estimate"] > 0


def test_execute_lifecycle_cycle(policy_engine):
    now = utc_now()
    facts = [
        FactItem(user_id="u1", category=FactCategory.PREFERENCE, key="k1", value="v1", updated_at=now),
        FactItem(
            user_id="u1",
            category=FactCategory.FACT,
            key="stale_k",
            value="stale_v",
            confidence_score=0.4,
            updated_at=now - timedelta(days=150),
            last_accessed_at=now - timedelta(days=150),
        ),
    ]
    records = [
        MemoryRecord(user_id="u1", text="Session item A", created_at=now),
    ]

    cycle = policy_engine.execute_lifecycle_cycle(facts, records)
    assert cycle["total_facts_evaluated"] == 2
    assert cycle["active_facts_retained"] == 1
    assert cycle["facts_pruned"] == 1
    assert "episodic_compression" in cycle
