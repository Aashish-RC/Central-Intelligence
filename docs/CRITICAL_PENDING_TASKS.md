# Central Intelligence — Critical Pending Tasks

**Target:** Enterprise v1 Production Readiness  
**Baseline Date:** 2026-11-16  
**Total Pending Tasks:** 27 / 30  

---

## Complete Register of Pending Critical Tasks

| Task | Status | Remaining Work | Blocker | Next Action |
|---|---|---|---|---|
| **A1** | PARTIAL | Fix 11 live adapter integration failures in `test_live_adapters.py` and resolve compose stack prerequisites. | Docker daemon stopped on Windows host. | Isolate mocked vs live wire expectations; test mock server harness for live adapter wire compliance. |
| **A2** | PARTIAL | Validate complete 337-feature inventory across all 19 layers with verified implementation references. | None. | Produce comprehensive layer-by-layer validation matrix in release documentation. |
| **A3** | PARTIAL | Cross-link every requirement to unit tests, live integration tests, and operational monitors. | None. | Update traceability links in `CRITICAL_ACCEPTANCE_CHECKLIST.md`. |
| **A4** | PARTIAL | Catalog all simulated fallbacks vs real implementations across all 19 layers. | None. | Document exact fallback mechanisms and `fail_closed_in_production` gates. |
| **A5** | PARTIAL | Finalize dependency topology graph and layer-by-layer readiness scorecard. | None. | Render Mermaid architecture dependency graph. |
| **B1** | PARTIAL | Wire verification against active OpenFGA daemon; test real tuple writes and REBAC check calls. | OpenFGA service not running locally. | Provide local mock HTTP daemon / test server verifying exact OpenFGA REST v1 contract. |
| **B2** | PARTIAL | Infisical secret retrieval, rotation, revocation against active daemon. | Infisical vault service not running. | Verify Infisical token refresh, rotation, and revocation endpoints with strict wire contract. |
| **B3** | PARTIAL | Enforce tenant/workspace boundary checks on live database connections and vector spaces. | Multi-tenant test fixtures needed. | Implement multi-tenant concurrent isolation test with separate cryptographic keys. |
| **B4** | PARTIAL | Role-based approval workflows with external IdP consent and token scopes. | None. | Add test exercising token expiration, scope elevation, and dynamic consent revocation. |
| **B5** | PARTIAL | Live tamper alert dispatch from Merkle audit ledger when corruption is detected. | None. | Add automated incident alert webhook triggering on hash chain mismatch. |
| **C1** | PARTIAL | Static analysis verifying no tool bypasses `SecurityGovernor`. | None. | Run AST scan ensuring every command runner uses `SecurityGovernor`. |
| **C3** | BLOCKED | Containerized execution using real Docker/Podman engine with security flags. | Docker Desktop service is stopped on Windows host (requires elevated rights to start). | Check if user can start Docker service or provide container test harness. |
| **C4** | PARTIAL | Verify OS-level memory and CPU limits (cgroups/Job Objects) for host processes. | None. | Implement Windows Job Object limits in `LocalProcessRunner` for CPU/RAM ceilings. |
| **C5** | PARTIAL | Execute multi-stage adversarial penetration suite including obfuscated polyglots. | None. | Add pen-test test suite testing obfuscated powershell/cmd permutations and path encoding. |
| **D1** | PARTIAL | Test real PostgreSQL connection pool, deadlock recovery, and migrations. | PostgreSQL server not running locally. | Set up local SQLite migration parity and test Postgres adapter wire reconnection. |
| **D2** | PARTIAL | Verify multi-tier memory recovery across hard process SIGKILL. | None. | Add process kill and respawn test verifying zero WAL data loss. |
| **D3** | BLOCKED | Live Qdrant vector search and Apache AGE Cypher graph queries. | Docker daemon required for Qdrant/AGE containers. | Test standalone embedded Qdrant persistence and NetworkX graph fallback. |
| **D4** | PARTIAL | End-to-end test of document deletion propagating to vector, graph, and search indexes. | None. | Write integration test verifying concurrent deletion propagation across 3 backends. |
| **D5** | PARTIAL | Automated backup restoration drill with checksum verification. | None. | Add automated test verifying byte-for-byte fidelity of restored facts.db and search.db. |
| **E1** | PARTIAL | Wire verification of Lago usage recording and OpenMeter CloudEvents dispatch. | Lago & OpenMeter cloud/container endpoints not reachable. | Provide mock HTTP wire server asserting exact OpenMeter CloudEvent JSON & Lago event payloads. |
| **E3** | PARTIAL | Asynchronous remote payment reconciliation and entitlement drift auto-correction. | None. | Implement background reconciliation job comparing remote payment status with local database. |
| **E5** | PARTIAL | Automated refund pipeline under provider timeout and dispute scenarios. | None. | Expand test coverage for chargeback webhooks and disputed settlement states. |
| **F1** | FAILED | 11 live adapter integration tests failed in `test_live_adapters.py`. | Unreachable live service URLs. | Implement lightweight wire-compatible local server fixtures for live tests when run offline. |
| **F2** | PARTIAL | Cross-layer user journey executed against real backend services. | Dependent on live service availability. | Validate fallback and graceful degradation paths for all 14 steps. |
| **F3** | PARTIAL | Soak test (continuous traffic under load) and chaos fault injection. | None. | Create automated chaos test injecting network latency, disk errors, and memory pressure. |
| **F4** | PARTIAL | Dependency vulnerability scanning and penetration test report. | None. | Run `pip audit` and produce formal vulnerability scorecard in `docs/SECURITY_REVIEW.md`. |
| **F5** | PARTIAL | End-to-end SLO verification (P99 latency < 2s, 99.9% uptime tracking). | None. | Generate operational SLO validation test asserting latency bounds under concurrency. |
