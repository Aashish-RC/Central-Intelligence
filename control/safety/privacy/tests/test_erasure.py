"""
Tests for Universal Memory Erasure Propagator (10.31)
Verifies right-to-erasure cascade across L2, L3, Qdrant, Meilisearch, Redis, PII Scrubber,
and cryptographic compliance audit meta-record logging.
"""

import hashlib
import pytest
from control.safety.privacy.erasure_propagator import (
    ErasureReceipt,
    LegalHoldActiveError,
    UniversalMemoryErasurePropagator,
)
from control.safety.audit.ledger import UnifiedAuditLedger
from control.safety.pii import DataClass, FourTierPIIScrubber
from control.identity.lifecycle.account_manager import AccountLifecycleManager, AccountStatus


@pytest.fixture
def ledger():
    return UnifiedAuditLedger(db_path=":memory:")


@pytest.fixture
def scrubber(ledger):
    return FourTierPIIScrubber(unified_ledger=ledger)


@pytest.fixture
def propagator(scrubber, ledger):
    return UniversalMemoryErasurePropagator(
        pii_scrubber=scrubber,
        audit_ledger=ledger,
    )


def test_universal_erasure_purges_all_stores(propagator, scrubber, ledger):
    """Acceptance Test: User erasure -> all stores purged; audit ledger records erasure happened (meta-record)."""
    user_id = "user_to_erase_99"

    # Seed data into PII scrubber
    scrubber.scrub("User email alice@example.com", data_class=DataClass.TELEMETRY, user_id=user_id)
    scrubber.scrub("Diagnostic traceback with alice@example.com", data_class=DataClass.DIAGNOSTIC, user_id=user_id)

    # Seed data into mock stores
    propagator.register_test_data("l2_memory", user_id, ["memory_vector_1", "memory_vector_2"])
    propagator.register_test_data("l3_knowledge", user_id, ["rag_doc_101"])
    propagator.register_test_data("qdrant", user_id, ["pt_alpha", "pt_beta"])
    propagator.register_test_data("meilisearch", user_id, ["doc_search_1"])
    propagator.register_test_data("redis_cache", user_id, ["session_token", "cached_query"])
    propagator.register_test_data("l14_logs", user_id, ["log_entry_1", "log_entry_2"])

    # Execute universal erasure cascade
    receipt: ErasureReceipt = propagator.propagate_erasure(
        user_id=user_id,
        tenant_id="tenant_erasure_test",
        reason="GDPR Article 17 User Right to Erasure Request",
    )

    # 1. Receipt checks
    expected_pseudonym = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    assert receipt.user_pseudonym == expected_pseudonym
    assert receipt.status == "completed"
    assert receipt.total_records_purged > 0
    assert len(receipt.audit_meta_record_hash) == 64

    # 2. Verify all stores are empty for this user
    for store_name in ["l2_memory", "l3_knowledge", "qdrant", "meilisearch", "redis_cache", "l14_logs"]:
        assert user_id not in propagator._mock_stores[store_name]

    # 3. Verify PII Scrubber stores are purged
    assert len(scrubber.tier1.get_records(user_id=user_id)) == 0
    assert len(scrubber.tier2.get_records(user_id=user_id)) == 0

    # 4. Verify immutable compliance meta-record exists in Merkle ledger
    entries = ledger.query(action="universal_memory_erasure")
    assert len(entries) >= 1
    meta = entries[0]
    assert meta.user_id == expected_pseudonym  # Zero PII in ledger
    assert meta.status == "completed"
    assert ledger.verify_chain() is True


def test_account_manager_permanent_closure_integration(propagator):
    manager = AccountLifecycleManager()
    user_id = "user_account_closure"
    manager.create_account(user_id=user_id, email="close_me@example.com")

    propagator.register_test_data("l2_memory", user_id, ["memory_node_1"])

    receipt = manager.permanently_close_and_erase(user_id=user_id, erasure_propagator=propagator)

    assert manager.get_account(user_id).status == AccountStatus.PERMANENTLY_CLOSED
    assert receipt is not None
    assert receipt.status == "completed"
    assert user_id not in propagator._mock_stores["l2_memory"]


def test_legal_hold_blocks_erasure(propagator):
    class MockLegalHold:
        def is_held(self, user_id: str, tenant_id: str):
            return user_id == "user_subpoena"

    propagator.legal_hold_handler = MockLegalHold()

    with pytest.raises(LegalHoldActiveError) as exc_info:
        propagator.propagate_erasure(user_id="user_subpoena")

    assert "active legal hold" in str(exc_info.value).lower()
