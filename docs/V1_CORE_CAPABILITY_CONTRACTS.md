# CENTRAL INTELLIGENCE V1 — CORE CAPABILITY CONTRACTS SPECIFICATION

**Author:** Staff Principal Architect, Security Lead & Platform Engineering Lead  
**Scope:** Formal Domain Contracts, Interfaces, Data Types, and Behavioral Requirements  
**Date:** 2026-11-18  
**Repository:** `Aashish-RC/Central-Intelligence`  
**Status:** **AUTHORITATIVE ARCHITECTURAL SPECIFICATION**  

---

## 1. Architectural Mandate & Abstraction Framework

Central Intelligence is engineered upon the fundamental decoupling principle:
> **A mandatory platform capability does not make any specific third-party implementation mandatory.**  
> Mandatory capabilities (authorization, secret vaulting, workflow execution, metering, persistence, sandboxing, and observability) must be defined as formal, engine-agnostic contracts. The platform must operate seamlessly across lightweight embedded engines, standard self-hosted stacks, and distributed enterprise backends without modifying business logic or weakening safety guarantees.

Every capability domain defined herein specifies:
1. **Abstract Contract (ABC):** Pure Python interface and typing definitions.
2. **Behavioral Invariants:** Fail-closed semantics, tenant isolation, and error contracts.
3. **Primary Reference Implementation:** Current enterprise/distributed driver.
4. **Lightweight Alternative Implementation:** Native, embedded, or zero-external-dependency driver.
5. **Acceptance Test Suite:** Equivalence tests ensuring any compliant engine meets identical functional and security bars.

---

## 2. Domain A: Authorization Engine Contract (ReBAC)

### 2.1 Domain Overview
The authorization domain provides Google Zanzibar-style Relationship-Based Access Control (ReBAC) supporting hierarchical inheritance, group memberships, document sharing, and delegated sub-agent execution.

### 2.2 Core Python Contract (`BaseAuthorizationEngine`)

```python
"""Domain contract for ReBAC authorization engine."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass(frozen=True)
class RelationshipTuple:
    user: str           # e.g., "user:usr_123" or "role:admin" or "user:*"
    relation: str       # e.g., "viewer", "editor", "owner", "member"
    object: str         # e.g., "document:doc_abc" or "workspace:ws_xyz"
    condition: Optional[str] = None
    condition_context: Optional[Dict[str, Any]] = None

@dataclass(frozen=True)
class DelegationGrant:
    delegation_id: str
    delegator: str
    delegatee: str
    scope: str
    expires_at: Optional[datetime] = None
    revoked: bool = False

@dataclass(frozen=True)
class AuthorizationCheckResult:
    allowed: bool
    resolution_path: List[str]  # Trace of tuples evaluated (auditability)
    cached: bool = False

class BaseAuthorizationEngine(ABC):
    """Abstract interface for all relationship-based authorization engines."""

    @abstractmethod
    def check_permission(
        self,
        user: str,
        relation: str,
        object: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AuthorizationCheckResult:
        """Evaluate whether user has relation to object. Must fail closed (False) on error."""
        ...

    @abstractmethod
    def write_tuples(self, tuples: List[RelationshipTuple], tenant_id: str) -> None:
        """Atomically persist relationship tuples under tenant namespace."""
        ...

    @abstractmethod
    def delete_tuples(self, tuples: List[RelationshipTuple], tenant_id: str) -> None:
        """Atomically remove relationship tuples under tenant namespace."""
        ...

    @abstractmethod
    def expand_users(self, relation: str, object: str, tenant_id: str) -> List[str]:
        """Expand all subjects possessing relation to object."""
        ...

    @abstractmethod
    def create_delegation(self, grant: DelegationGrant, tenant_id: str) -> None:
        """Record scoped, time-bounded delegation from one agent/user to another."""
        ...

    @abstractmethod
    def revoke_delegation(self, delegation_id: str, tenant_id: str) -> None:
        """Immediately revoke a previously active delegation."""
        ...
```

### 2.3 Behavioral Invariants
1. **Fail-Closed Guarantee:** Any database timeout, network partition, or unhandled exception must evaluate to `allowed=False` and log a security audit event.
2. **Tenant Isolation:** All tuple writes, reads, and graph traversals are strictly bound to `tenant_id`. No cross-tenant inheritance or wildcard leakage is permitted.
3. **Cycles & Loop Safety:** Graph expansion must enforce a maximum recursion depth of 16 to prevent infinite loop exhaustion.

### 2.4 Implementation Implementations
- **Enterprise Provider:** `OpenFGAProvider` interfacing with OpenFGA Go daemon over HTTP REST/gRPC.
- **Embedded / Lightweight Provider:** `NativeSqlZanzibarProvider` executing recursive Common Table Expressions (CTE) over SQLite or PostgreSQL table `rebac_tuples(tenant_id, user_str, relation, object_str, created_at)`.

---

## 3. Domain B: Secret Management Contract (Vault)

### 3.1 Domain Overview
The secret management domain guarantees authenticated envelope encryption, zero-plaintext storage, key rotation, and tamper-evident access auditing for LLM API keys and BYOK credentials.

### 3.2 Core Python Contract (`BaseSecretVault`)

```python
"""Domain contract for secret vault and credential lifecycle."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass(frozen=True)
class ScopedSecret:
    key: str
    tenant_id: str
    app_id: Optional[str]
    value: str          # Decrypted value only exposed in-memory
    version: int
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]

@dataclass(frozen=True)
class SecretAuditRecord:
    timestamp: datetime
    action: str         # "READ", "WRITE", "ROTATE", "DELETE"
    key: str
    tenant_id: str
    actor_id: str
    success: bool
    ip_address: Optional[str] = None

class BaseSecretVault(ABC):
    """Abstract interface for cryptographic secret vaulting."""

    @abstractmethod
    def store_secret(
        self,
        key: str,
        value: str,
        tenant_id: str,
        app_id: Optional[str] = None,
        actor_id: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScopedSecret:
        """Encrypt and store secret under tenant scope."""
        ...

    @abstractmethod
    def get_secret(
        self,
        key: str,
        tenant_id: str,
        app_id: Optional[str] = None,
        actor_id: str = "system",
        version: Optional[int] = None,
    ) -> str:
        """Retrieve and decrypt secret value. Records an immutable audit log."""
        ...

    @abstractmethod
    def rotate_secret(
        self,
        key: str,
        new_value: str,
        tenant_id: str,
        actor_id: str = "system",
    ) -> ScopedSecret:
        """Create new secret version and increment version index atomically."""
        ...

    @abstractmethod
    def list_secrets(
        self,
        tenant_id: str,
        app_id: Optional[str] = None,
        actor_id: str = "system",
    ) -> List[Dict[str, Any]]:
        """List secret metadata (keys, versions, dates) without exposing values."""
        ...

    @abstractmethod
    def get_audit_trail(
        self,
        tenant_id: str,
        key: Optional[str] = None,
        limit: int = 100,
    ) -> List[SecretAuditRecord]:
        """Retrieve tamper-evident audit history."""
        ...
```

### 3.3 Behavioral Invariants
1. **Zero Plaintext Persistence:** Secrets must be encrypted before hitting storage media using AES-256-GCM or ChaCha20-Poly1305 with unique 96-bit initialization vectors (IVs).
2. **Master Key Protection:** Master decryption keys must be provided via environment (`MASTER_VAULT_KEY`) or cloud KMS (AWS KMS, GCP KMS). They must never be written to database tables or logs.
3. **Immutable Audit Trail:** Every secret read, rotation, or deletion must append an unmodifiable audit entry with timestamp, actor, and outcome.

### 3.4 Implementation Providers
- **Enterprise Provider:** `InfisicalProvider` interfacing with Infisical Machine Identity / Universal Auth over REST API v3.
- **Embedded / Lightweight Provider:** `NativeEnvelopeVaultProvider` storing encrypted JSON envelopes in SQLite (`vault.db`) or PostgreSQL `vault_secrets` table with local PBKDF2/Argon2 key derivation.

---

## 4. Domain C: Durable Workflow Execution Contract

### 4.1 Domain Overview
The workflow execution domain orchestrates multi-step agent DAGs, parallel tool calls, and delayed human-in-the-loop approvals, providing crash resiliency and deterministic replay.

### 4.2 Core Python Contract (`BaseWorkflowOrchestrator`)

```python
"""Domain contract for crash-resilient workflow execution."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum

class NodeExecutionState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

@dataclass
class WorkflowExecutionStatus:
    workflow_id: str
    phase: str
    nodes_total: int
    nodes_completed: int
    step_results: Dict[str, Any]
    error: Optional[str] = None

class BaseWorkflowOrchestrator(ABC):
    """Abstract interface for workflow engines supporting DAG execution and recovery."""

    @abstractmethod
    def submit_workflow(self, workflow_id: str, graph_def: Dict[str, Any], initial_input: Dict[str, Any]) -> str:
        """Submit DAG workflow for execution. Returns run ID."""
        ...

    @abstractmethod
    def get_status(self, run_id: str) -> WorkflowExecutionStatus:
        """Query execution progress and state of all completed nodes."""
        ...

    @abstractmethod
    def checkpoint_step(self, run_id: str, node_id: str, result: Any, state: NodeExecutionState) -> None:
        """Persist intermediate node output to durable storage."""
        ...

    @abstractmethod
    def resume_from_checkpoint(self, run_id: str) -> WorkflowExecutionStatus:
        """Recover execution following process crash without re-executing completed nodes."""
        ...

    @abstractmethod
    def cancel_workflow(self, run_id: str) -> bool:
        """Request graceful cancellation of pending nodes."""
        ...
```

### 4.3 Behavioral Invariants
1. **Idempotency & Non-Duplication:** Nodes that have reached `COMPLETED` state must never re-execute external side effects during recovery replay.
2. **Bounded Concurrency:** Concurrently executing DAG branches must obey tenant worker pool limits.

### 4.4 Implementation Providers
- **Enterprise Provider:** `TemporalWorkflowAdapter` wrapping Temporal Python SDK and Temporal Server cluster.
- **Embedded / Lightweight Provider:** `NativeDurableOrchestrator` using SQLite WAL checkpointing (`.workflow_checkpoints/runs.db`) to record node transitions before and after task execution.

---

## 5. Domain D: Metering & Usage Accounting Contract

### 5.1 Domain Overview
The metering domain ingests CloudEvents 1.0 token consumption records, tracks real-time usage against quotas, and calculates billing balances across models and tenants.

### 5.2 Core Python Contract (`BaseUsageMeter`)

```python
"""Domain contract for real-time token metering and quota checking."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime

@dataclass(frozen=True)
class TokenUsageEvent:
    event_id: str
    user_id: str
    tenant_id: str
    app_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

@dataclass(frozen=True)
class TenantUsageSummary:
    tenant_id: str
    user_id: Optional[str]
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost_usd: float
    event_count: int
    period_start: datetime
    period_end: datetime

class BaseUsageMeter(ABC):
    """Abstract interface for token metering and quota verification."""

    @abstractmethod
    def record_usage(self, event: TokenUsageEvent) -> bool:
        """Ingest token usage record. Returns True if successfully queued/written."""
        ...

    @abstractmethod
    def check_quota(self, tenant_id: str, requested_tokens: int) -> bool:
        """Check whether tenant has sufficient remaining quota. Fail-closed for paid accounts."""
        ...

    @abstractmethod
    def get_summary(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
        user_id: Optional[str] = None,
    ) -> TenantUsageSummary:
        """Aggregate usage metrics across a time window."""
        ...
```

### 5.3 Behavioral Invariants
1. **Financial Precision:** Token costs must be tracked as fixed-precision decimals or integer micros (\$0.000001) to prevent floating-point rounding drift.
2. **Asynchronous Non-Blocking Write:** Recording usage events must not add latency (>5ms) to the user's reasoning streaming loop.

### 5.4 Implementation Providers
- **Enterprise Provider:** `OpenMeterAdapter` posting CloudEvents to OpenMeter + Apache Kafka + ClickHouse cluster.
- **Embedded / Lightweight Provider:** `NativePostgresMeter` batching usage records into PostgreSQL partitioned table `metering_events` or SQLite local ledger.

---

## 6. Domain E: Telemetry & Observability Contract

### 6.1 Domain Overview
The telemetry domain provides OpenTelemetry-compliant trace generation, distributed span propagation, structured log correlation, and metric aggregation.

### 6.2 Core Python Contract (`BaseTelemetryBridge`)

```python
"""Domain contract for telemetry, tracing, and metrics."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from contextlib import contextmanager

class BaseTelemetryBridge(ABC):
    """Abstract interface for OpenTelemetry span export and metrics."""

    @abstractmethod
    @contextmanager
    def span(self, name: str, layer: str, attributes: Optional[Dict[str, Any]] = None):
        """Context manager creating a correlated distributed tracing span."""
        ...

    @abstractmethod
    def record_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a scalar counter, gauge, or histogram observation."""
        ...

    @abstractmethod
    def log_event(self, level: str, message: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Record a structured log event with active span and trace correlation IDs."""
        ...
```

### 6.3 Behavioral Invariants
1. **PII and Secret Redaction:** Prompts, completions, and headers must pass through the security scrubber (`control/safety/redactor.py`) before span serialization.
2. **Zero Ingestion Dependency:** Central Intelligence services must boot and operate normally even if the external telemetry collector is unreachable. Spans are buffered in memory or disk.

### 6.4 Implementation Providers
- **Enterprise Provider:** `SigNozAdapter` exporting OTLP traces over gRPC/HTTP to SigNoz ClickHouse collector.
- **Embedded / Lightweight Provider:** `StandardOtelBridge` writing to local JSON-L audit files or standard OTel Collector sidecar.

---

## 7. Equivalence Test Suite Requirements

To verify that any provider adheres to its capability contract, test suites under `tests/unit/contracts/` must run against both implementations:

| Domain | Contract File | Equivalence Test File | Validation Target |
|---|---|---|---|
| Authorization | `BaseAuthorizationEngine` | `test_contract_authz_equivalence.py` | OpenFGA vs NativeSqlZanzibar |
| Secrets | `BaseSecretVault` | `test_contract_secrets_equivalence.py` | Infisical vs NativeEnvelopeVault |
| Workflows | `BaseWorkflowOrchestrator` | `test_contract_workflow_equivalence.py` | Temporal vs NativeDurableOrchestrator |
| Metering | `BaseUsageMeter` | `test_contract_metering_equivalence.py` | OpenMeter vs NativePostgresMeter |
| Telemetry | `BaseTelemetryBridge` | `test_contract_telemetry_equivalence.py` | SigNoz vs StandardOtelBridge |

All five contract test suites verify:
1. Normal happy-path CRUD operations.
2. Concurrent access safety.
3. Process restart durability.
4. Error conditions and fail-closed safety.
5. Strict tenant boundary isolation.
