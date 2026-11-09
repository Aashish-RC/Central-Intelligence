"""OpenFGA Knowledge Search Access Control Bridge (Layer 3 Knowledge, Feature 3.36 — DEF-02 UNBLOCKED).

Filters retrieval and search results based on Relationship-Based Access Control (ReBAC)
and OpenFGA permissions prior to returning to the user.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from control.identity.openfga_adapter import OpenFGAAdapter, default_openfga_adapter

logger = logging.getLogger("cognitive.knowledge.access_control")


def check_document_access(
    user_id: str,
    action: str = "can_view",
    doc_id: str = "",
    doc_metadata: Optional[dict] = None,
    openfga_client: Optional[OpenFGAAdapter] = None,
) -> bool:
    """Checks whether a user is authorized to access/view a document.
    
    A document is viewable if:
    1. It is explicitly marked as public (metadata.get("public") is True or metadata.get("visibility") == "public")
    2. Or OpenFGA grants the user the action on resource `document:<doc_id>`
    """
    if doc_metadata:
        if doc_metadata.get("public") is True or doc_metadata.get("visibility") == "public":
            return True

    client = openfga_client or default_openfga_adapter
    norm_user = user_id.replace("user:", "")
    norm_doc = doc_id.replace("document:", "")

    # Query OpenFGA relationship graph
    actor = f"user:{norm_user}"
    target_object = f"document:{norm_doc}"

    return client.check_permission(
        user=actor,
        action=action,
        resource=target_object,
    )


def filter_results_by_permission(
    results: List[Any],
    user_id: Optional[str],
    action: str = "can_view",
    openfga_client: Optional[OpenFGAAdapter] = None,
) -> List[Any]:
    """Filters a list of SearchResult items to only those authorized for user_id.

    If user_id is None, returns the results unmodified (e.g. system or internal calls).
    """
    if not user_id:
        return results

    authorized: List[Any] = []
    for item in results:
        doc = getattr(item, "document", item)
        doc_id = getattr(doc, "id", str(doc))
        doc_meta = getattr(doc, "metadata", {}) or {}

        if check_document_access(
            user_id=user_id,
            action=action,
            doc_id=doc_id,
            doc_metadata=doc_meta,
            openfga_client=openfga_client,
        ):
            authorized.append(item)

    return authorized
