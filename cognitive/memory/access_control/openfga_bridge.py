"""OpenFGA Memory Access Control Bridge (Layer 2 Memory, Feature 2.38 — DEF-01 UNBLOCKED).

Enforces relationship-based access control (ReBAC) over episodic, semantic,
and fact graph memory spaces prior to recall or storage.
"""

from __future__ import annotations

import logging
from typing import Optional

from control.identity.openfga_adapter import OpenFGAAdapter, default_openfga_adapter

logger = logging.getLogger("cognitive.memory.access_control")


class AccessDeniedError(PermissionError):
    """Raised when an actor lacks ReBAC permission to read or write a memory scope."""
    pass


def check_memory_access(
    user_id: str,
    action: str,  # "read" or "write"
    memory_scope: str,  # e.g., "bob", "user:bob", "org:acme"
    openfga_client: Optional[OpenFGAAdapter] = None,
) -> bool:
    """Checks OpenFGA ReBAC permissions for memory operations.

    Args:
        user_id: The identity making the request.
        action: Either 'read' (for recall) or 'write' (for remember).
        memory_scope: The target memory space (user or org ID).
        openfga_client: Optional custom OpenFGA client instance.

    Raises:
        AccessDeniedError: If the actor is not authorized.
    """
    client = openfga_client or default_openfga_adapter

    norm_scope = memory_scope.replace("user:", "")
    norm_user = user_id.replace("user:", "")

    # Self-access is inherently authorized for personal memory space
    if norm_user == norm_scope:
        return True

    # Otherwise query OpenFGA relationship graph
    # Object is memory:<scope>
    target_object = f"memory:{norm_scope}"
    actor = f"user:{norm_user}"

    allowed = client.check_permission(
        user=actor,
        action=action,
        resource=target_object,
    )

    if not allowed:
        raise AccessDeniedError(f"User {user_id} cannot {action} memory scope {memory_scope}")

    return True

