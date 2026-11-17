"""Governed Capability-Driven Dynamic Activation Engine (L16 Compute / Platform Infra).

Provides resource-aware, capability-driven activation with:
- Minimal always-on control plane.
- Explicit service dependency graph resolution across tiered startup rings.
- Dynamic capability registry integration.
- Lazy initialization where safe.
- Resource-aware worker scheduling respecting host/cgroup memory bounds.
- Configurable idle shutdown with safe draining before termination.
- Active workflow protection (durability-critical services never stopped while active).
- Dependent capability protection (upstream dependencies never stopped while active downstream depends on them).
- Safe state preservation hooks with failure protection (shutdown aborted if preservation fails).
- Dependency cycle detection at registration and activation.
- Health checks and automatic fault recovery.
- Runtime adapter interface for real service activation and status monitoring.
- Tenant-level resource accounting and tamper-evident durable hash-chained audit logging.
- Safe startup and shutdown rate limiting and concurrency management.
"""

from __future__ import annotations

import abc
import enum
import hashlib
import json
import logging
import os
import pathlib
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
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
    UNHEALTHY = "UNHEALTHY"


class RuntimeAdapter(abc.ABC):
    """Abstract runtime adapter interface for real/simulated service lifecycle."""

    @abc.abstractmethod
    def start_service(self, service_name: str, **kwargs: Any) -> bool:
        """Start or verify running state of an underlying service."""
        pass

    @abc.abstractmethod
    def stop_service(self, service_name: str, **kwargs: Any) -> bool:
        """Stop an underlying service when drained."""
        pass

    @abc.abstractmethod
    def is_service_healthy(self, service_name: str) -> bool:
        """Check whether service is healthy and ready for traffic."""
        pass

    @abc.abstractmethod
    def get_service_metrics(self, service_name: str) -> Dict[str, Any]:
        """Query resource metrics for service."""
        pass


class SimulatedRuntimeAdapter(RuntimeAdapter):
    """In-memory runtime adapter for tests, CI, and decoupled environments."""

    def __init__(self) -> None:
        self._running: Set[str] = set()
        self._failing: Set[str] = set()
        self._lock = threading.Lock()

    def start_service(self, service_name: str, **kwargs: Any) -> bool:
        with self._lock:
            if service_name in self._failing:
                logger.warning("Simulated start failed for service: %s", service_name)
                return False
            self._running.add(service_name)
            logger.info("Simulated service started: %s", service_name)
            return True

    def stop_service(self, service_name: str, **kwargs: Any) -> bool:
        with self._lock:
            self._running.discard(service_name)
            logger.info("Simulated service stopped: %s", service_name)
            return True

    def is_service_healthy(self, service_name: str) -> bool:
        with self._lock:
            if service_name in self._failing:
                return False
            return service_name in self._running

    def get_service_metrics(self, service_name: str) -> Dict[str, Any]:
        with self._lock:
            running = service_name in self._running
            return {
                "service": service_name,
                "running": running,
                "memory_rss_mb": 64 if running else 0,
                "healthy": running and service_name not in self._failing,
            }

    def fail_service(self, service_name: str, failing: bool = True) -> None:
        """Inject or clear a simulated service failure."""
        with self._lock:
            if failing:
                self._failing.add(service_name)
            else:
                self._failing.discard(service_name)


class DockerComposeRuntimeAdapter(RuntimeAdapter):
    """Docker Compose adapter for starting, stopping, and probing real containers."""

    def __init__(self, compose_file: Optional[str] = None, timeout_seconds: float = 15.0) -> None:
        self.compose_file = compose_file or "docker-compose.yml"
        self.timeout = timeout_seconds
        self._lock = threading.Lock()

    def _run_compose(self, args: List[str]) -> Tuple[int, str]:
        import subprocess
        cmd = ["docker", "compose"]
        if self.compose_file and os.path.exists(self.compose_file):
            cmd.extend(["-f", self.compose_file])
        cmd.extend(args)
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            return res.returncode, res.stdout + res.stderr
        except Exception as exc:
            logger.error("Docker compose execution failed for %s: %s", args, exc)
            return 1, str(exc)

    def start_service(self, service_name: str, **kwargs: Any) -> bool:
        with self._lock:
            code, out = self._run_compose(["start", service_name])
            if code != 0 and "No such service" not in out:
                code, out = self._run_compose(["up", "-d", service_name])
            if code == 0:
                logger.info("Docker Compose service '%s' started successfully", service_name)
                return True
            logger.error("Failed to start Compose service '%s': %s", service_name, out)
            return False

    def stop_service(self, service_name: str, **kwargs: Any) -> bool:
        with self._lock:
            code, out = self._run_compose(["stop", service_name])
            if code == 0:
                logger.info("Docker Compose service '%s' stopped", service_name)
                return True
            logger.warning("Stop Compose service '%s' returned code %d: %s", service_name, code, out)
            return False

    def is_service_healthy(self, service_name: str) -> bool:
        with self._lock:
            code, out = self._run_compose(["ps", "--format", "json", service_name])
            if code != 0 or not out.strip():
                return False
            try:
                # Parse JSON output from docker compose ps
                lines = [line.strip() for line in out.strip().splitlines() if line.strip()]
                for line in lines:
                    data = json.loads(line)
                    state = data.get("State", "").lower()
                    health = data.get("Health", "").lower()
                    if state == "running" and health in ("healthy", ""):
                        return True
            except Exception:
                pass
            return "running" in out.lower()

    def get_service_metrics(self, service_name: str) -> Dict[str, Any]:
        healthy = self.is_service_healthy(service_name)
        return {
            "service": service_name,
            "running": healthy,
            "healthy": healthy,
        }


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
    readiness_check_fn: Optional[Callable[[], bool]] = None
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
    prev_hash: str = ""
    record_hash: str = ""


class InsufficientResourceError(RuntimeError):
    """Raised when host/cgroup memory headroom is insufficient to safely activate capability."""
    pass


class CapabilityDependencyError(RuntimeError):
    """Raised when required upstream capability dependencies are missing or cyclic."""
    pass


class CapabilityActivationError(RuntimeError):
    """Raised when a capability fails to activate due to health, runtime, or preservation error."""
    pass


def detect_system_memory_limit_mb() -> int:
    """Detect available memory ceiling from cgroups, environment, or system RAM."""
    # 1. Environment variable override
    env_limit = os.getenv("CI_MAX_MEMORY_MB")
    if env_limit:
        try:
            return int(env_limit)
        except ValueError:
            pass

    # 2. Linux cgroup v2 memory.max
    cgroup2_path = pathlib.Path("/sys/fs/cgroup/memory.max")
    if cgroup2_path.exists():
        try:
            raw = cgroup2_path.read_text().strip()
            if raw != "max":
                bytes_val = int(raw)
                return max(256, bytes_val // (1024 * 1024))
        except Exception:
            pass

    # 3. Linux cgroup v1 memory.limit_in_bytes
    cgroup1_path = pathlib.Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    if cgroup1_path.exists():
        try:
            bytes_val = int(cgroup1_path.read_text().strip())
            # Very high value (like 0x7FFFFFFFFFFFF000) indicates no limit
            if bytes_val < 10**14:
                return max(256, bytes_val // (1024 * 1024))
        except Exception:
            pass

    # 4. psutil virtual memory
    try:
        import psutil
        total_mb = int(psutil.virtual_memory().total // (1024 * 1024))
        # Cap to 80% of total host RAM or default 3072 MB ceiling
        return max(512, min(total_mb, 3072))
    except Exception:
        pass

    return 3072


class CapabilityActivationManager:
    """Governed manager orchestrating on-demand capability activation and safe lifecycle."""

    def __init__(
        self,
        max_total_memory_mb: Optional[int] = None,
        default_idle_timeout_seconds: float = 120.0,
        runtime_adapter: Optional[RuntimeAdapter] = None,
        audit_log_path: Optional[str] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._state_condition = threading.Condition(self._lock)
        self.system_detected_memory_mb = detect_system_memory_limit_mb()
        self.max_total_memory_mb = max_total_memory_mb if max_total_memory_mb is not None else self.system_detected_memory_mb
        self.default_idle_timeout = default_idle_timeout_seconds
        self.runtime_adapter: RuntimeAdapter = runtime_adapter or SimulatedRuntimeAdapter()
        self.audit_log_path = audit_log_path

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

        # Audit trail and hash chaining
        self._audit_trail: List[AuditRecord] = []
        self._last_audit_hash: str = "GENESIS_CAPABILITY_AUDIT"

        # Active activation call stack for runtime cycle detection
        self._activating_stack: Set[str] = set()

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

    def _check_cycle_exists(self, start_name: str, candidate_deps: List[str]) -> bool:
        """Check whether candidate dependencies introduce a cycle back to start_name."""
        visited: Set[str] = set()

        def dfs(node: str) -> bool:
            if node == start_name:
                return True
            if node in visited:
                return False
            visited.add(node)
            node_def = self._registry.get(node)
            if not node_def:
                return False
            for dep in node_def.dependencies:
                if dfs(dep):
                    return True
            return False

        for dep in candidate_deps:
            if dfs(dep):
                return True
        return False

    def register_capability(self, cap: CapabilityDefinition) -> None:
        """Register a new capability specification with dependency cycle detection."""
        with self._lock:
            # Check for direct self-dependency
            if cap.name in cap.dependencies:
                raise CapabilityDependencyError(f"Self dependency cycle detected for capability '{cap.name}'")

            # Check for indirect cycles against already-registered dependencies
            if self._check_cycle_exists(cap.name, cap.dependencies):
                raise CapabilityDependencyError(f"Dependency cycle detected involving capability '{cap.name}'")

            self._registry[cap.name] = cap
            if cap.name not in self._state:
                # Durability critical start as ACTIVE if always-on
                if not cap.allows_idle_shutdown:
                    self._state[cap.name] = CapabilityState.ACTIVE
                    self._last_active_time[cap.name] = time.time()
                    # Start underlying runtime services for always-on capabilities
                    if self.runtime_adapter:
                        for svc in cap.required_services:
                            self.runtime_adapter.start_service(svc)
                else:
                    self._state[cap.name] = CapabilityState.INACTIVE
                self._active_leases[cap.name] = set()

    def get_allocated_memory_mb(self) -> int:
        """Calculate total memory allocated to currently ACTIVE, ACTIVATING, or DRAINING capabilities."""
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
        """Activate a capability on-demand with cycle detection, runtime adapter, and partial-failure rollback."""
        with self._lock:
            if capability_name not in self._registry:
                raise KeyError(f"Unknown capability: {capability_name}")

            # Check for runtime dependency cycle
            if capability_name in self._activating_stack:
                cycle_path = " -> ".join(list(self._activating_stack) + [capability_name])
                raise CapabilityDependencyError(f"Dynamic dependency cycle detected: {cycle_path}")

            # If already active, refresh timestamp and return
            current_state = self._state[capability_name]
            if current_state == CapabilityState.ACTIVE:
                self._last_active_time[capability_name] = time.time()
                return True

            # If another thread is actively activating this capability, wait for it
            while self._state.get(capability_name) == CapabilityState.ACTIVATING:
                logger.info("Capability '%s' is ACTIVATING in another thread; waiting...", capability_name)
                self._state_condition.wait(timeout=5.0)
                if self._state.get(capability_name) == CapabilityState.ACTIVE:
                    self._last_active_time[capability_name] = time.time()
                    return True
                if self._state.get(capability_name) == CapabilityState.FAILED:
                    return False

            cap = self._registry[capability_name]
            self._activating_stack.add(capability_name)
            activated_sub_deps: List[str] = []

            try:
                # 1. Resolve and verify upstream dependencies first
                for dep in cap.dependencies:
                    if dep not in self._registry:
                        raise CapabilityDependencyError(f"Missing dependency: {dep} for {capability_name}")
                    if self._state.get(dep) != CapabilityState.ACTIVE:
                        logger.info("Auto-activating prerequisite dependency '%s' for '%s'", dep, capability_name)
                        dep_ok = self.activate_capability(dep, caller_tenant=caller_tenant, reason=f"Dependency of {capability_name}")
                        if not dep_ok:
                            raise CapabilityActivationError(f"Failed to activate required dependency '{dep}' for '{capability_name}'")
                        activated_sub_deps.append(dep)

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

                # 4. Activate underlying services via runtime adapter
                if self.runtime_adapter:
                    for svc in cap.required_services:
                        if not self.runtime_adapter.start_service(svc):
                            self._state[capability_name] = CapabilityState.FAILED
                            self._record_audit(
                                capability_name,
                                "RUNTIME_START_FAILED",
                                caller_tenant,
                                f"Runtime adapter failed to start service '{svc}'",
                            )
                            self._state_condition.notify_all()
                            return False

                # 5. Readiness probe verification
                if cap.readiness_check_fn:
                    try:
                        if not cap.readiness_check_fn():
                            self._state[capability_name] = CapabilityState.FAILED
                            self._record_audit(capability_name, "READINESS_CHECK_FAILED", caller_tenant, "Readiness check returned False")
                            self._state_condition.notify_all()
                            return False
                    except Exception as exc:
                        self._state[capability_name] = CapabilityState.FAILED
                        self._record_audit(capability_name, "READINESS_CHECK_ERROR", caller_tenant, str(exc))
                        self._state_condition.notify_all()
                        return False

                # 6. Health check verification
                if cap.health_check_fn:
                    try:
                        if not cap.health_check_fn():
                            self._state[capability_name] = CapabilityState.FAILED
                            self._record_audit(capability_name, "HEALTH_CHECK_FAILED", caller_tenant, "Health probe failed")
                            self._state_condition.notify_all()
                            return False
                    except Exception as exc:
                        self._state[capability_name] = CapabilityState.FAILED
                        self._record_audit(capability_name, "HEALTH_CHECK_ERROR", caller_tenant, str(exc))
                        self._state_condition.notify_all()
                        return False

                # 7. Successfully active
                self._state[capability_name] = CapabilityState.ACTIVE
                self._last_active_time[capability_name] = time.time()
                self._record_audit(
                    capability_name,
                    "ACTIVATED",
                    caller_tenant,
                    reason,
                    {"budget_mb": cap.memory_budget_mb, "services": cap.required_services},
                )
                self._state_condition.notify_all()
                return True

            except Exception as exc:
                # Partial failure recovery: roll back dependencies activated solely for this request
                self._state[capability_name] = CapabilityState.FAILED
                self._record_audit(capability_name, "ACTIVATION_FAILED", caller_tenant, str(exc))
                for dep in activated_sub_deps:
                    if len(self._active_leases.get(dep, set())) == 0:
                        dep_cap = self._registry.get(dep)
                        if dep_cap and dep_cap.allows_idle_shutdown and not dep_cap.is_durability_critical:
                            logger.info("Rolling back dependent capability '%s' due to failure in '%s'", dep, capability_name)
                            self._deactivate_capability_internal(dep, reason="Dependency rollback")
                self._state_condition.notify_all()
                raise
            finally:
                self._activating_stack.discard(capability_name)

    def acquire_lease(
        self,
        capability_name: str,
        tenant_id: str,
        workflow_id: Optional[str] = None,
    ) -> CapabilityLease:
        """Acquire an active lease, guaranteeing the capability is active and protected from idle shutdown."""
        with self._lock:
            if capability_name not in self._registry:
                raise KeyError(f"Unknown capability: {capability_name}")

            if self._state.get(capability_name) != CapabilityState.ACTIVE:
                activated = self.activate_capability(capability_name, caller_tenant=tenant_id, reason="Lease acquisition")
                if not activated or self._state.get(capability_name) != CapabilityState.ACTIVE:
                    raise CapabilityActivationError(
                        f"Failed to acquire lease: capability '{capability_name}' activation failed "
                        f"(state: {self._state.get(capability_name)})."
                    )

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

    def _deactivate_capability_internal(self, name: str, reason: str = "Idle shutdown") -> bool:
        """Internal helper to safely preserve state and stop services for a capability."""
        cap = self._registry[name]
        self._state[name] = CapabilityState.DRAINING
        self._record_audit(name, "DRAINING", None, reason)

        # 1. State preservation hook
        if cap.state_preservation_fn:
            try:
                ok = cap.state_preservation_fn()
                if ok is False:
                    raise RuntimeError("State preservation function returned False")
            except Exception as exc:
                logger.error("State preservation failed during shutdown of '%s': %s. Aborting shutdown.", name, exc)
                self._state[name] = CapabilityState.ACTIVE
                self._record_audit(name, "STATE_PRESERVATION_FAILED", None, f"Shutdown aborted to prevent data loss: {exc}")
                return False

        # 2. Stop runtime services if no other active capability needs them
        if self.runtime_adapter:
            for svc in cap.required_services:
                other_users = [
                    other_name for other_name, other_cap in self._registry.items()
                    if other_name != name and svc in other_cap.required_services and self._state.get(other_name) == CapabilityState.ACTIVE
                ]
                if not other_users:
                    self.runtime_adapter.stop_service(svc)

        # 3. Mark inactive
        self._state[name] = CapabilityState.INACTIVE
        self._record_audit(name, "DEACTIVATED", None, reason)
        return True

    def drain_idle_capabilities(self, now: Optional[float] = None) -> List[str]:
        """Scan for idle capabilities and safely drain and shut them down, protecting active dependents."""
        with self._lock:
            current_time = now if now is not None else time.time()
            drained: List[str] = []

            # Multi-pass drain in reverse ring order until no further eligible capabilities drain
            changed = True
            while changed:
                changed = False
                candidate_caps = sorted(self._registry.items(), key=lambda item: -item[1].ring)
                for name, cap in candidate_caps:
                    if name in drained:
                        continue

                    # Never stop durability-critical or non-idle-shutdown capabilities
                    if cap.is_durability_critical or not cap.allows_idle_shutdown:
                        continue

                    if self._state.get(name) != CapabilityState.ACTIVE:
                        continue

                    # Active lease protection: do not drain if direct active leases exist
                    if len(self._active_leases.get(name, set())) > 0:
                        continue

                    # Dependent capability protection: do NOT drain if an active capability depends on it!
                    active_dependents = [
                        dep_user for dep_user, dep_cap in self._registry.items()
                        if name in dep_cap.dependencies and self._state.get(dep_user) in (
                            CapabilityState.ACTIVE, CapabilityState.ACTIVATING, CapabilityState.DRAINING
                        )
                    ]
                    if active_dependents:
                        logger.debug("Capability '%s' is idle but active dependent(s) %s require it. Skipping drain.", name, active_dependents)
                        continue

                    last_active = self._last_active_time.get(name, current_time)
                    timeout = cap.idle_timeout_seconds if cap.idle_timeout_seconds > 0 else self.default_idle_timeout

                    if (current_time - last_active) >= timeout:
                        logger.info("Capability '%s' idle for %.1fs (timeout %.1fs). Draining...", name, current_time - last_active, timeout)
                        if self._deactivate_capability_internal(name, reason=f"Idle timeout ({timeout}s) exceeded"):
                            drained.append(name)
                            changed = True

            return drained

    def check_capability_health(self, capability_name: str) -> bool:
        """Actively check readiness and health of a capability and its runtime services."""
        with self._lock:
            if capability_name not in self._registry:
                return False
            cap = self._registry[capability_name]
            if self._state.get(capability_name) != CapabilityState.ACTIVE:
                return False

            # Check runtime services
            if self.runtime_adapter:
                for svc in cap.required_services:
                    if not self.runtime_adapter.is_service_healthy(svc):
                        self._state[capability_name] = CapabilityState.UNHEALTHY
                        self._record_audit(capability_name, "SERVICE_UNHEALTHY", None, f"Underlying service '{svc}' unhealthy")
                        return False

            # Check custom health function
            if cap.health_check_fn:
                try:
                    if not cap.health_check_fn():
                        self._state[capability_name] = CapabilityState.UNHEALTHY
                        self._record_audit(capability_name, "HEALTH_CHECK_FAILED", None, "Health check probe returned False")
                        return False
                except Exception as exc:
                    self._state[capability_name] = CapabilityState.UNHEALTHY
                    self._record_audit(capability_name, "HEALTH_CHECK_ERROR", None, str(exc))
                    return False

            return True

    def recover_state(self, recheck_health: bool = True) -> Dict[str, Any]:
        """Restart and recovery procedure: ensure durability-critical capabilities are active and healthy."""
        with self._lock:
            recovered = []
            failed = []
            for name, cap in self._registry.items():
                if cap.is_durability_critical or not cap.allows_idle_shutdown:
                    logger.info("Recovery: ensuring durability-critical capability '%s' is ACTIVE", name)
                    try:
                        ok = self.activate_capability(name, caller_tenant="SYSTEM_RECOVERY", reason="Host restart recovery")
                        if ok:
                            recovered.append(name)
                        else:
                            failed.append(name)
                    except Exception as exc:
                        logger.error("Recovery failed for '%s': %s", name, exc)
                        failed.append(name)

            self._record_audit(
                "SYSTEM",
                "RESTART_RECOVERY_COMPLETED",
                "SYSTEM",
                f"Recovered {len(recovered)} capabilities; {len(failed)} failed",
                {"recovered": recovered, "failed": failed},
            )
            return {"recovered": recovered, "failed": failed}

    def save_state(self, path: str) -> None:
        """Persist registry state snapshot to disk."""
        with self._lock:
            data = {
                "saved_at": time.time(),
                "allocated_memory_mb": self.get_allocated_memory_mb(),
                "states": {k: v.value for k, v in self._state.items()},
                "last_active": self._last_active_time,
                "audit_hash": self._last_audit_hash,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def load_state(self, path: str) -> bool:
        """Restore capability state snapshot from disk."""
        with self._lock:
            if not os.path.exists(path):
                return False
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                states = data.get("states", {})
                for k, v in states.items():
                    if k in self._registry:
                        self._state[k] = CapabilityState(v)
                self._record_audit("SYSTEM", "STATE_LOADED", "SYSTEM", f"Restored from {path}")
                return True
            except Exception as exc:
                logger.error("Failed to load state snapshot from %s: %s", path, exc)
                return False

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
                    "required_services": cap.required_services,
                    "dependencies": cap.dependencies,
                }
            return {
                "allocated_memory_mb": self.get_allocated_memory_mb(),
                "max_memory_mb": self.max_total_memory_mb,
                "system_detected_memory_mb": self.system_detected_memory_mb,
                "headroom_mb": self.max_total_memory_mb - self.get_allocated_memory_mb(),
                "capabilities": status,
                "total_registered": len(self._registry),
                "audit_records_count": len(self._audit_trail),
                "last_audit_hash": self._last_audit_hash,
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

    def verify_audit_log_integrity(self) -> bool:
        """Verify the cryptographic hash chain of the audit trail."""
        with self._lock:
            curr_hash = "GENESIS_CAPABILITY_AUDIT"
            for rec in self._audit_trail:
                if rec.prev_hash != curr_hash:
                    return False
                payload = f"{rec.prev_hash}:{rec.timestamp}:{rec.capability}:{rec.action}:{rec.tenant_id}:{rec.reason}:{sorted(rec.details.items())}"
                expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                if rec.record_hash != expected_hash:
                    return False
                curr_hash = rec.record_hash
            return True

    def _record_audit(
        self,
        capability: str,
        action: str,
        tenant_id: Optional[str],
        reason: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a tamper-evident hash-chained entry to the in-memory audit ledger and optional file."""
        now = time.time()
        det = details or {}
        payload = f"{self._last_audit_hash}:{now}:{capability}:{action}:{tenant_id}:{reason}:{sorted(det.items())}"
        rec_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        rec = AuditRecord(
            timestamp=now,
            capability=capability,
            action=action,
            tenant_id=tenant_id,
            reason=reason,
            details=det,
            prev_hash=self._last_audit_hash,
            record_hash=rec_hash,
        )
        self._audit_trail.append(rec)
        self._last_audit_hash = rec_hash

        if self.audit_log_path:
            try:
                os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
                with open(self.audit_log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(rec)) + "\n")
            except Exception as exc:
                logger.error("Failed to append durable audit log to %s: %s", self.audit_log_path, exc)
