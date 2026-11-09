# Central-Intelligence: Deferred Engineering Items & Dependency Matrix

This document tracks items intentionally deferred per the Central-Intelligence monorepo work plan, their upstream layer blockers, and the conditions required to unlock them.

---

## 1. Summary Status Table

| Item ID | Layer | Feature | Title / Description | Upstream Dependency | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DEF-01** | **L2** | 2.38 | **Memory Access Control Bridge** | **L12 (IAM / Permify / OpenFGA)** | **UNBLOCKED** (Wired to L12 OpenFGA) |
| **DEF-02** | **L3** | 3.36 | **Permission-Filtered Retrieval** | **L12 (IAM / Permify / OpenFGA)** | **UNBLOCKED** (Wired to L12 OpenFGA) |
| **DEF-03** | **L8** | 8.15 | **Second-Opinion Trigger** | **L11 (Evaluation / Accuracy Score)** | **UNBLOCKED** (Wired to L11 Accuracy Score) |
| **DEF-04** | **L8** | 8.31 | **Hatchet Queue Integration** | Architectural Evaluation Completed | **Decided: Retain Temporal for L8; Hatchet Deferred to Phase 6 for L5** |

---

## 2. Detailed Breakdown of Deferred Items

### DEF-01: L2 Memory Access Control Bridge (Feature 2.38)
- **Scope:** Fine-grained relationship-based access control (ReBAC) and attribute-based access control (ABAC) over persistent memory records, episodic rollups, and fact graph entities.
- **Upstream Blocker:** Layer 12 IAM system (Permify / OpenFGA schema and authorization service).
- **Status:** **UNBLOCKED** — Integrated with `control.identity.openfga_adapter.OpenFGAAdapter` via `cognitive/memory/access_control/openfga_bridge.py`. Pre-write (`remember`) and pre-read (`recall`) hooks enforced.
- **Verification:** Verified via `cognitive/memory/tests/test_access_control.py`.

### DEF-02: L3 Permission-Filtered Retrieval (Feature 3.36)
- **Scope:** Scoping knowledge base and vector similarity search results to documents and chunks the requesting user has explicit `VIEW` permissions for.
- **Upstream Blocker:** Layer 12 IAM system (Permify / OpenFGA).
- **Status:** **UNBLOCKED** — Integrated with `control.identity.openfga_adapter.OpenFGAAdapter` via `cognitive/knowledge/access_control/openfga_bridge.py`. Enforces `can_view` document ReBAC filtering in `LocalHybridSearchEngine`, `ReciprocalRankFusion`, and `MeilisearchClient`.
- **Verification:** Verified via `cognitive/knowledge/search/tests/test_permission_filter.py`.

### DEF-03: L8 Second-Opinion Trigger (Feature 8.15)
- **Scope:** Triggering second-opinion arbitration or consensus reruns when initial task reasoning confidence is marginal or task risk is elevated.
- **Upstream Blocker:** Layer 11 Accuracy Scoring & Evaluation Service.
- **Status:** **UNBLOCKED** — Integrated with Layer 11 Accuracy Score Evaluator ($S_{composite} = w_1 S_{feedback} + w_2 S_{web} + w_3 S_{consensus}$). Cognitive routing policy engine `maybeTriggerSecondOpinion` triggers automatic model escalation (e.g. to `claude-3-7-sonnet` or `o3-mini`) when composite accuracy is below 0.50.
- **Verification:** Verified via `control/orchestration/tests/secondOpinion.test.ts`.

### DEF-04: L8 Hatchet Orchestration Evaluation
- **Scope:** Evaluating Hatchet distributed task queue against Temporal for durable execution.
- **Formal Decision:** Documented in `docs/evaluations/hatchet_vs_temporal.md`. Temporal is retained as the standard durable orchestrator for Layer 8 workflows. Hatchet is deferred to Phase 6 as an optional lightweight queue backend for Layer 5 sandbox workers.

---

## 3. Maintenance and Review Schedule
- **Review Cadence:** Evaluated upon kickoff of Wave B (Layers 11–13).
- **Owner:** Architecture & Cognitive Systems Core.

