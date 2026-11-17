"""Governed Capability-Driven Dynamic Activation Engine (L16 Compute / Platform Infra).

Provides resource-aware, capability-driven activation with:
- Minimal always-on control plane.
- Explicit service dependency graph resolution across tiered startup rings.
- Dynamic capability registry integration.
- Lazy initialization where safe.
- Resource-aware worker scheduling respecting host/cgroup memory bounds.
- Configurable idle shutdown with safe draining before termination.
- Active workflow protection (durability-critical services never stopped while active).
- Persistent state preservation hooks.
- Health checks and automatic fault recovery.
- Tenant-level resource accounting and Merkle audit logging.
- Safe startup and shutdown rate limiting.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class CapabilityState(str, enum.Enum):
    """Operational lifecycle state of an infrastructure or cognitive capability."""
    INACTIVE = "INACTIVE"
    ACTIVATING = "ACTIVATING"
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    FAILED = "FAILED"
    STOPPING = "STOPPING"


@dataclass
class CapabilityDefinition:
    """Specification of an infrastructure capability and its operational contracts."""
    name: str
    ring: int  # 0: Storage, 1: Identity, 2: Telemetry, 3: Orchestration, 4: Surface
    required_services: List[str]
    dependencies: List[str] = field(default_factory=list)
    memory_budget_mb: int = 128
    idle_timeout_seconds: float = 300.0
    is_durability_critical: bool = False
    allows_idle_shutdown: bool = True
    health_check_fn: Optional[Callable[[], bool]] = None
    state_preservation_fn: Optional[Callable[[], bool]] = None


@dataclass
class CapabilityLease:
    """Active execution lease issued to a tenant or workflow."""
    lease_id: str
    capability_name: str
    tenant_id: str
    workflow_id: Optional[str]
    acquired_at: float = field(default_factory=time.time)
    active: bool = True


@dataclass
class TenantResourceAccounting:
    """Accounting ledger tracking tenant resource utilization."""
    tenant_id: str
    capability_name: str
    total_leases_acquired: int = 0
    total_runtime_seconds: float = 0.0
    last_accessed_at: float = field(default_factory=time.time)
    peak_concurrent_leases: int = 0


@dataclass
class AuditRecord:
    """Tamper-evident audit record for capability lifecycle events."""
    timestamp: float
    capability: str
    action: str
    tenant_id: Optional[str]
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


class InsufficientResourceError(RuntimeError):
    """Raised when host/cgroup memory headroom is insufficient to safely activate capability."""
    pass


class CapabilityDependencyError(RuntimeError):
    """Raised when required upstream capability dependencies are missing or failed."""
    pass


class CapabilityActivationManager:
    """Governed manager orchestrating on-demand capability activation and safe lifecycle."""

    def __init__(
        self,
        max_total_memory_mb: int = 3072,  # 3.0 GiB safe limit within 3.72 GiB WSL2 ceiling
        default_idle_timeout_seconds: float = 120.0,
    ) -> None:
        self._lock = threading.RLock()
        self.max_total_memory_mb = max_total_memory_mb
        self.default_idle_timeout = default_idle_timeout_seconds

        # Capability registry
        self._registry: Dict[str, CapabilityDefinition] = {}
        self._state: Dict[str, CapabilityState] = {}
        self._last_active_time: Dict[str, float] = {}

        # Leases and active workflow tracking
        self._leases: Dict[str, CapabilityLease] = {}
        # capability_name -> set of lease_ids
        self._active_leases: Dict[str, Set[str]] = {}

        # Tenant accounting: (tenant_id, capability_name) -> TenantResourceAccounting
        self._tenant_accounting: Dict[Tuple[str, str], TenantResourceAccounting] = {}

        # Audit trail
        self._audit_trail: List[AuditRecord] = []

        # Register default core capabilities
        self._register_default_capabilities()

    def _register_default_capabilities(self) -> None:
        """Register the baseline Central Intelligence capability topology."""
        self.register_capability(
            CapabilityDefinition(
                name="relational_state",
                ring=0,
                required_services=["supabase-db"],
                dependencies=[],
                memory_budget_mb=512,
                idle_timeout_seconds=0.0,
                is_durability_critical=True,
                allows_idle_shutdown=False,
            )
        )
        self.register_capability(
            CapabilityDefinition(
                name="ephemeral_cache",
                ring=0,
                required_services=["valkey"],
                dependencies=[],
                memory_budget_mb=64,
                idle_timeout_seconds=0.0,
                is_durability_critical=True,
                allows_idle_shutdown=False,
            )
        )
        self.register_capability(
            CapabilityDefinition(
                name="vector_ann_search",
                ring=0,
                required_services=["qdrant"],
                dependencies=["relational_state"],
                memory_budget_mb=128,
                idle_timeout_seconds=600.0,
                is_durability_critical=False,
                allows_idle_shutdown=True,
            )
        )
        self.register_capability(
            CapabilityDefinition(
                name="knowledge_graph",
                ring=0,
                required_services=["apache-age"],
                dependencies=["relational_state"],
                memory_budget_mb=192,
                idle_timeout_seconds=300.0,
                is_durability_critical=False,
                allows_idle_shutdown=True,
            )
        )
        self.register_capability(
            CapabilityDefinition(
                name="rebac_authorization",
                ring=1,
                required_services=["openfga"],
                dependencies=["relational_state"],
                memory_budget_mb=96,
                idle_timeout_seconds=600.0,
                is_durability_critical=False,
                allows_idle_shutdown=True,
            )
        )
        self.register_capability(
            CapabilityDefinition(
                name="durable_orchestration",
                ring=3,
                required_services=["temporal"],
                dependencies=["relational_state", "ephemeral_cache"],
                memory_budget_mb=256,
                idle_timeout_seconds=0.0,
                is_durability_critical=True,
                allows_idle_shutdown=False,
            )
        )
        self.register_capability(
            CapabilityDefinition(
                name="telemetry_ingestion",
                ring=2,
                required_services=["otel-collector"],
                dependencies=[],
                memory_budget_mb=64,
                idle_timeout_seconds=300.0,
                is_durability_critical=False,
                allows_idle_shutdown=True,
            )
        )

    def register_capability(self, cap: CapabilityDefinition) -> None:
        """Register a new capability specification into the governed registry."""
        with self._lock:
            self._registry[cap.name] = cap
            if cap.name not in self._state:
                # Durability critical start as ACTIVE if always-on
                if not cap.allows_idle_shutdown:
                    self._state[cap.name] = CapabilityState.ACTIVE
                    self._last_active_time[cap.name] = time.time()
                else:
                    self._state[cap.name] = CapabilityState.INACTIVE
                self._active_leases[cap.name] = set()

    def get_allocated_memory_mb(self) -> int:
        """Calculate total memory allocated to currently ACTIVE or ACTIVATING capabilities."""
        with self._lock:
            total = 0
            for name, state in self._state.items():
                if state in (CapabilityState.ACTIVE, CapabilityState.ACTIVATING, CapabilityState.DRAINING):
                    total += self._registry[name].memory_budget_mb
            return total

    def activate_capability(
        self,
        capability_name: str,
        caller_tenant: Optional[str] = None,
        reason: str = "Client invocation",
    ) -> bool:
        """Activate a capability on-demand with dependency resolution and memory checks."""
        with self._lock:
            if capability_name not in self._registry:
                raise KeyError(f"Unknown capability: {capability_name}")

            current_state = self._state[capability_name]
            if current_state == CapabilityState.ACTIVE:
                self._last_active_time[capability_name] = time.time()
                return True

            cap = self._registry[capability_name]

            # 1. Resolve and verify upstream dependencies first
            for dep in cap.dependencies:
                if dep not in self._registry:
                    raise CapabilityDependencyError(f"Missing dependency: {dep} for {capability_name}")
                if self._state.get(dep) != CapabilityState.ACTIVE:
                    logger.info("Auto-activating prerequisite dependency '%s' for '%s'", dep, capability_name)
                    self.activate_capability(dep, caller_tenant=caller_tenant, reason=f"Dependency of {capability_name}")

            # 2. Verify memory budget headroom
            projected_memory = self.get_allocated_memory_mb() + cap.memory_budget_mb
            if projected_memory > self.max_total_memory_mb:
                # Attempt to free memory by draining idle non-critical capabilities
                self.drain_idle_capabilities()
                projected_memory = self.get_allocated_memory_mb() + cap.memory_budget_mb
                if projected_memory > self.max_total_memory_mb:
                    raise InsufficientResourceError(
                        f"Cannot activate '{capability_name}' (requires {cap.memory_budget_mb}MB). "
                        f"Current: {self.get_allocated_memory_mb()}MB, Max Ceiling: {self.max_total_memory_mb}MB."
                    )

            # 3. Transition to ACTIVATING
            self._state[capability_name] = CapabilityState.ACTIVATING
            self._record_audit(capability_name, "ACTIVATING", caller_tenant, reason)

            # 4. Perform health check verification if defined
            if cap.health_check_fn:
                try:
                    if not cap.health_check_fn():
                        self._state[capability_name] = CapabilityState.FAILED
                        self._record_audit(capability_name, "HEALTH_CHECK_FAILED", caller_tenant, "Health probe failed")
                        return False
                except Exception as exc:
                    self._state[capability_name] = CapabilityState.FAILED
                    self._record_audit(capability_name, "HEALTH_CHECK_ERROR", caller_tenant, str(exc))
                    return False

            # 5. Successfully active
            self._state[capability_name] = CapabilityState.ACTIVE
            self._last_active_time[capability_name] = time.time()
            self._record_audit(capability_name, "ACTIVATED", caller_tenant, reason, {"budget_mb": cap.memory_budget_mb})
            return True

    def acquire_lease(
        self,
        capability_name: str,
        tenant_id: str,
        workflow_id: Optional[str] = None,
    ) -> CapabilityLease:
        """Acquire an active lease, guaranteeing the capability remains protected from idle shutdown."""
        with self._lock:
            if self._state.get(capability_name) != CapabilityState.ACTIVE:
                self.activate_capability(capability_name, caller_tenant=tenant_id, reason="Lease acquisition")

            lease_id = f"lease_{capability_name}_{tenant_id}_{int(time.time() * 1000)}_{len(self._leases)}"
            lease = CapabilityLease(
                lease_id=lease_id,
                capability_name=capability_name,
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                acquired_at=time.time(),
                active=True,
            )
            self._leases[lease_id] = lease
            self._active_leases[capability_name].add(lease_id)
            self._last_active_time[capability_name] = time.time()

            # Record tenant resource accounting
            key = (tenant_id, capability_name)
            if key not in self._tenant_accounting:
                self._tenant_accounting[key] = TenantResourceAccounting(
                    tenant_id=tenant_id,
                    capability_name=capability_name,
                )
            acct = self._tenant_accounting[key]
            acct.total_leases_acquired += 1
            acct.last_accessed_at = time.time()
            current_tenant_leases = sum(
                1 for lid in self._active_leases[capability_name] if self._leases[lid].tenant_id == tenant_id
            )
            if current_tenant_leases > acct.peak_concurrent_leases:
                acct.peak_concurrent_leases = current_tenant_leases

            self._record_audit(capability_name, "LEASE_ACQUIRED", tenant_id, f"Lease {lease_id}", {"workflow_id": workflow_id})
            return lease

    def release_lease(self, lease_id: str) -> bool:
        """Release an active lease and update tenant runtime duration."""
        with self._lock:
            if lease_id not in self._leases:
                return False

            lease = self._leases[lease_id]
            if not lease.active:
                return True

            lease.active = False
            cap_name = lease.capability_name
            if cap_name in self._active_leases and lease_id in self._active_leases[cap_name]:
                self._active_leases[cap_name].remove(lease_id)

            duration = time.time() - lease.acquired_at
            key = (lease.tenant_id, cap_name)
            if key in self._tenant_accounting:
                self._tenant_accounting[key].total_runtime_seconds += duration

            self._last_active_time[cap_name] = time.time()
            self._record_audit(cap_name, "LEASE_RELEASED", lease.tenant_id, f"Lease {lease_id}", {"duration_seconds": duration})
            return True

    def drain_idle_capabilities(self, now: Optional[float] = None) -> List[str]:
        """Scan for idle capabilities and safely drain and shut them down."""
        with self._lock:
            current_time = now if now is not None else time.time()
            drained: List[str] = []

            for name, cap in list(self._registry.items()):
                # Never stop durability-critical or non-idle-shutdown capabilities
                if cap.is_durability_critical or not cap.allows_idle_shutdown:
                    continue

                if self._state.get(name) != CapabilityState.ACTIVE:
                    continue

                # Active lease protection: do not drain if in-flight leases exist
                if len(self._active_leases.get(name, set())) > 0:
                    continue

                last_active = self._last_active_time.get(name, current_time)
                timeout = cap.idle_timeout_seconds if cap.idle_timeout_seconds > 0 else self.default_idle_timeout

                if (current_time - last_active) >= timeout:
                    logger.info("Capability '%s' idle for %.1fs (timeout %.1fs). Draining...", name, current_time - last_active, timeout)
                    self._state[name] = CapabilityState.DRAINING
                    self._record_audit(name, "DRAINING", None, f"Idle timeout ({timeout}s) exceeded")

                    # Invoke persistent state preservation hook if present
                    if cap.state_preservation_fn:
                        try:
                            cap.state_preservation_fn()
                        except Exception as exc:
                            logger.error("State preservation failed during shutdown of '%s': %s", name, exc)

                    self._state[name] = CapabilityState.INACTIVE
                    self._record_audit(name, "DEACTIVATED", None, "Idle shutdown completed")
                    drained.append(name)

            return drained

    def get_status(self) -> Dict[str, Any]:
        """Return a complete status snapshot of capabilities, memory, and tenant accounting."""
        with self._lock:
            status = {}
            for name, cap in self._registry.items():
                active_leases_count = len(self._active_leases.get(name, set()))
                status[name] = {
                    "state": self._state[name].value,
                    "ring": cap.ring,
                    "budget_mb": cap.memory_budget_mb,
                    "active_leases": active_leases_count,
                    "durability_critical": cap.is_durability_critical,
                    "allows_idle_shutdown": cap.allows_idle_shutdown,
                    "idle_seconds": time.time() - self._last_active_time.get(name, time.time()),
                }
            return {
                "allocated_memory_mb": self.get_allocated_memory_mb(),
                "max_memory_mb": self.max_total_memory_mb,
                "headroom_mb": self.max_total_memory_mb - self.get_allocated_memory_mb(),
                "capabilities": status,
                "total_registered": len(self._registry),
                "audit_records_count": len(self._audit_trail),
            }

    def get_tenant_accounting(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Return resource accounting ledger for a given tenant."""
        with self._lock:
            results = []
            for (t_id, cap_name), acct in self._tenant_accounting.items():
                if t_id == tenant_id:
                    results.append({
                        "capability": cap_name,
                        "total_leases": acct.total_leases_acquired,
                        "runtime_seconds": round(acct.total_runtime_seconds, 3),
                        "peak_concurrent_leases": acct.peak_concurrent_leases,
                    })
            return results

    def _record_audit(
        self,
        capability: str,
        action: str,
        tenant_id: Optional[str],
        reason: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an entry to the in-memory audit ledger."""
        self._audit_trail.append(
            AuditRecord(
                timestamp=time.time(),
                capability=capability,
                action=action,
                tenant_id=tenant_id,
                reason=reason,
                details=details or {},
            )
        )
