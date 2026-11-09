# Central-Intelligence: Deferred Engineering Items & Dependency Matrix

This document tracks items intentionally deferred per the Central-Intelligence monorepo work plan, their upstream layer blockers, and the conditions required to unlock them.

---

## 1. Summary Status Table

| Item ID | Layer | Feature | Title / Description | Upstream Dependency | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DEF-01** | **L2** | 2.38 | **Memory Access Control Bridge** | **L12 (IAM / Permify / OpenFGA)** | **Deferred** (Waits on L12) |
| **DEF-02** | **L3** | 3.36 | **Permission-Filtered Retrieval** | **L12 (IAM / Permify / OpenFGA)** | **Deferred** (Waits on L12) |
| **DEF-03** | **L8** | 8.15 | **Second-Opinion Trigger** | **L11 (Evaluation / Accuracy Score)** | **Deferred** (Waits on L11) |
| **DEF-04** | **L8** | 8.31 | **Hatchet Queue Integration** | Architectural Evaluation Completed | **Decided: Retain Temporal for L8; Hatchet Deferred to Phase 6 for L5** |

---

## 2. Detailed Breakdown of Deferred Items

### DEF-01: L2 Memory Access Control Bridge (Feature 2.38)
- **Scope:** Fine-grained relationship-based access control (ReBAC) and attribute-based access control (ABAC) over persistent memory records, episodic rollups, and fact graph entities.
- **Upstream Blocker:** Layer 12 IAM system (Permify / OpenFGA schema and authorization service).
- **Current State:** L2 currently enforces tenant isolation, project ID filtering, and per-user namespaces (`user_id`, `tenant_id`, `project_id`) at the database and adapter level.
- **Unlocking Criteria:** Once L12 provides the centralized ReBAC client (`iam.client.check_permission(actor, action, resource)`), L2 will wire the `MemoryEngine` pre-read and pre-write access hooks.

### DEF-02: L3 Permission-Filtered Retrieval (Feature 3.36)
- **Scope:** Scoping knowledge base and vector similarity search results to documents and chunks the requesting user has explicit `VIEW` permissions for.
- **Upstream Blocker:** Layer 12 IAM system (Permify / OpenFGA).
- **Current State:** L3 provides collection-level and namespace-level partitioning.
- **Unlocking Criteria:** L12 authorization engine deployment allowing token-injected pre-filtering on Qdrant/Meilisearch vector queries.

### DEF-03: L8 Second-Opinion Trigger (Feature 8.15)
- **Scope:** Triggering second-opinion arbitration or consensus reruns when initial task reasoning confidence is marginal or task risk is elevated.
- **Upstream Blocker:** Layer 11 Accuracy Scoring & Evaluation Service.
- **Current State:** L4 Tiered Synthesis has second-opinion fallback based on local model confidence thresholds (< 0.5), and L7 Recommender has local rule arbitration. Full orchestration-level automatic second-opinion re-runs require L11 real-time output accuracy scoring.
- **Unlocking Criteria:** Deployment of Layer 11 live accuracy scorer providing real-time quality confidence metrics back to the Layer 8 Cognitive Policy Engine.

### DEF-04: L8 Hatchet Orchestration Evaluation
- **Scope:** Evaluating Hatchet distributed task queue against Temporal for durable execution.
- **Formal Decision:** Documented in `docs/evaluations/hatchet_vs_temporal.md`. Temporal is retained as the standard durable orchestrator for Layer 8 workflows. Hatchet is deferred to Phase 6 as an optional lightweight queue backend for Layer 5 sandbox workers.

---

## 3. Maintenance and Review Schedule
- **Review Cadence:** Evaluated upon kickoff of Wave B (Layers 11–13).
- **Owner:** Architecture & Cognitive Systems Core.
