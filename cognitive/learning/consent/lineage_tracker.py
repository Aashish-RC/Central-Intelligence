"""Training Data Lineage Tracker (Feature 7.22)

Maintains cryptographic provenance and complete audit trails for every example
included in training or fine-tuning datasets, enabling verifiable GDPR deletion.
"""

from __future__ import annotations
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TrainingDataProvenance:
    """Cryptographic provenance record for a single training artifact."""
    example_id: str
    user_id: str
    consent_receipt_hash: str
    source_session_id: str
    content_hash: str
    timestamp: float = field(default_factory=time.time)
    lineage_signature: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class TrainingLineageTracker:
    """Tracks training example provenance from origin conversation to fine-tuning corpus."""

    def __init__(self) -> None:
        self.provenance_store: Dict[str, TrainingDataProvenance] = {}
        # user_id -> set of example_ids
        self.user_index: Dict[str, List[str]] = {}

    def record_provenance(
        self,
        example_id: str,
        user_id: str,
        content: str,
        consent_receipt_hash: str,
        source_session_id: str = "session_0",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TrainingDataProvenance:
        """Register provenance and cryptographic signature for a training sample."""
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        sig_raw = f"{example_id}:{user_id}:{content_hash}:{consent_receipt_hash}"
        signature = hashlib.sha256(sig_raw.encode("utf-8")).hexdigest()

        prov = TrainingDataProvenance(
            example_id=example_id,
            user_id=user_id,
            consent_receipt_hash=consent_receipt_hash,
            source_session_id=source_session_id,
            content_hash=content_hash,
            lineage_signature=signature,
            metadata=metadata or {},
        )

        self.provenance_store[example_id] = prov
        if user_id not in self.user_index:
            self.user_index[user_id] = []
        self.user_index[user_id].append(example_id)

        return prov

    def get_provenance(self, example_id: str) -> Optional[TrainingDataProvenance]:
        """Fetch provenance record for an example."""
        return self.provenance_store.get(example_id)

    def verify_lineage(self, example_id: str, content: str) -> bool:
        """Verify that an example's current content matches its recorded cryptographic lineage."""
        prov = self.provenance_store.get(example_id)
        if not prov:
            return False

        current_content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if current_content_hash != prov.content_hash:
            return False

        sig_raw = f"{example_id}:{prov.user_id}:{current_content_hash}:{prov.consent_receipt_hash}"
        expected_sig = hashlib.sha256(sig_raw.encode("utf-8")).hexdigest()
        return expected_sig == prov.lineage_signature

    def purge_user_data(self, user_id: str) -> List[str]:
        """Right to be forgotten: purge all training lineage records for a user."""
        purged_ids: List[str] = []
        example_ids = self.user_index.get(user_id, [])

        for ex_id in list(example_ids):
            if ex_id in self.provenance_store:
                del self.provenance_store[ex_id]
                purged_ids.append(ex_id)

        if user_id in self.user_index:
            del self.user_index[user_id]

        return purged_ids

