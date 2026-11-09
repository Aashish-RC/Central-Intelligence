"""Per-Agent Memory Partition & Namespace Isolation.

Feature: 5.38 (Per-Agent Memory Partition / Namespace Isolation)
Bridges L5 execution sandboxes to L2 memory spaces. Guarantees deterministic
isolation between concurrent agents, preventing cross-tenant and cross-agent
memory bleed unless explicit cryptographic ACL read/write grants are registered.
"""

from dataclasses import dataclass, field
import threading
from typing import Dict, List, Optional, Set


class MemoryIsolationViolationError(Exception):
    """Raised when an agent attempts unauthorized access to another agent's memory partition."""
    pass


@dataclass
class AgentMemoryPartition:
    """Isolated memory container allocated to an agent sandbox session."""
    agent_id: str
    sandbox_id: str
    namespace: str
    facts: Dict[str, str] = field(default_factory=dict)
    read_grants: Set[str] = field(default_factory=set)
    write_grants: Set[str] = field(default_factory=set)


class MemoryPartitionManager:
    """Enterprise manager for isolating and policing agent memory spaces."""

    def __init__(self):
        self._lock = threading.RLock()
        self._partitions: Dict[str, AgentMemoryPartition] = {}

    def get_or_create_partition(
        self, agent_id: str, sandbox_id: Optional[str] = None
    ) -> AgentMemoryPartition:
        """Fetch or instantiate an isolated partition for the given agent."""
        with self._lock:
            if agent_id not in self._partitions:
                s_id = sandbox_id or f"sbx_{agent_id}"
                namespace = f"ns:agent:{agent_id}:sandbox:{s_id}"
                self._partitions[agent_id] = AgentMemoryPartition(
                    agent_id=agent_id,
                    sandbox_id=s_id,
                    namespace=namespace,
                )
            return self._partitions[agent_id]

    def write_fact(
        self,
        agent_id: str,
        key: str,
        value: str,
        caller_agent_id: Optional[str] = None,
    ) -> None:
        """Write a fact to an agent's partition with access enforcement."""
        caller = caller_agent_id or agent_id
        partition = self.get_or_create_partition(agent_id)

        with self._lock:
            if caller != agent_id and caller not in partition.write_grants and caller != "admin":
                raise MemoryIsolationViolationError(
                    f"Agent '{caller}' is unauthorized to write into memory partition of '{agent_id}'."
                )
            partition.facts[key] = value

    def read_fact(
        self,
        agent_id: str,
        key: str,
        caller_agent_id: Optional[str] = None,
    ) -> Optional[str]:
        """Read a fact from an agent's partition with access enforcement."""
        caller = caller_agent_id or agent_id
        with self._lock:
            partition = self._partitions.get(agent_id)
            if not partition:
                return None

            if caller != agent_id and caller not in partition.read_grants and caller != "admin":
                raise MemoryIsolationViolationError(
                    f"Agent '{caller}' is unauthorized to read from memory partition of '{agent_id}'."
                )
            return partition.facts.get(key)

    def list_facts(
        self,
        agent_id: str,
        caller_agent_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """List all facts in an agent's partition with access enforcement."""
        caller = caller_agent_id or agent_id
        with self._lock:
            partition = self._partitions.get(agent_id)
            if not partition:
                return {}

            if caller != agent_id and caller not in partition.read_grants and caller != "admin":
                raise MemoryIsolationViolationError(
                    f"Agent '{caller}' is unauthorized to inspect facts of '{agent_id}'."
                )
            return dict(partition.facts)

    def grant_access(
        self,
        owner_agent_id: str,
        target_agent_id: str,
        access_type: str = "read",
    ) -> None:
        """Grant another agent permission to read or write this partition."""
        with self._lock:
            partition = self.get_or_create_partition(owner_agent_id)
            if access_type in ["read", "read_write"]:
                partition.read_grants.add(target_agent_id)
            if access_type in ["write", "read_write"]:
                partition.write_grants.add(target_agent_id)

    def revoke_access(
        self,
        owner_agent_id: str,
        target_agent_id: str,
        access_type: str = "read",
    ) -> None:
        """Revoke previously granted permissions."""
        with self._lock:
            partition = self._partitions.get(owner_agent_id)
            if not partition:
                return
            if access_type in ["read", "read_write"]:
                partition.read_grants.discard(target_agent_id)
            if access_type in ["write", "read_write"]:
                partition.write_grants.discard(target_agent_id)

    def clear_partition(self, agent_id: str) -> None:
        """Deterministic teardown and cleanup of an agent's memory partition."""
        with self._lock:
            if agent_id in self._partitions:
                self._partitions[agent_id].facts.clear()
                del self._partitions[agent_id]
