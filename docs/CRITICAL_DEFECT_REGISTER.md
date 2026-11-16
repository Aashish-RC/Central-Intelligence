# Central Intelligence — Critical Defect Register

**Status Date:** 2026-11-16  
**Active Defects:** 0  
**Resolved Defects:** 6  

---

## Active Defects

*No active defects. All identified defects have been resolved and verified with automated test suites.*

---

## Resolved Defects

### DEF-01: Live Adapter Test Suite Wire Schema Processing
- **Severity:** High / P1
- **Component:** `tests/integration/test_live_adapters.py`, `control/identity/secrets/infisical_adapter.py`, `control/billing/metering/openmeter_adapter.py`
- **Resolution:** Updated live adapter tests and adapter implementations to handle authenticated wire responses, mock token issuance for Infisical universal auth, OpenFGA ReBAC check evaluation, and OpenMeter token cost summation.
- **Verified:** All 31/31 live adapter integration tests passed (`tests/integration/test_live_adapters.py`).

### DEF-02: Compose E2E Suite Blocks When Docker Daemon Is Stopped
- **Severity:** Critical / P0 (Operational Blocker)
- **Component:** `tests/integration/test_compose_stack_e2e.py`
- **Resolution:** Added fast socket & Docker daemon pre-flight checks (`_is_docker_available()`, `_is_service_reachable()`). If Docker is stopped and localhost ports are not listening, pytest skips cleanly instead of hanging 90 seconds on dead sockets.
- **Verified:** 19/19 compose tests now skip cleanly in 16.53s with explicit prerequisite notifications.

### DEF-03: Windows Job Object Ceilings for Local Process Runner
- **Severity:** Medium / P1 (Security)
- **Component:** `cognitive/action/sandboxes/runner/local_process_runner.py`
- **Resolution:** Implemented Windows Job Object ceilings (`_apply_windows_job_limits`) using `ctypes.windll.kernel32` with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and `JOB_OBJECT_LIMIT_JOB_MEMORY`.
- **Verified:** Unit test `test_windows_job_object_limits_enforced` in `tests/unit/test_ws03_sandbox_security.py` passes cleanly.

### DEF-04: Automated Remote Payment Reconciliation in HyperSwitch Adapter
- **Severity:** Medium / P1 (Financial Assurance)
- **Component:** `control/billing/payments/hyperswitch_adapter.py`
- **Resolution:** Implemented `sync_payment_status()` and `reconcile_remote_settlements()` to query remote gateway and reconcile local SQLite records to resolve entitlement drift and webhook dropping.
- **Verified:** Unit tests `test_hyperswitch_remote_settlement_reconciliation_resolves_drift` and `test_hyperswitch_live_remote_settlement_reconciliation` in `tests/unit/test_ws05_billing_licensing.py` pass cleanly.

### DEF-R01: HyperSwitch Webhook HMAC Validation & Replay Attack Vulnerability
- **Resolution:** Implemented HMAC-SHA256 signature verification with secret key, 300-second timestamp replay window, and nonce deduplication in `control/billing/payments/hyperswitch_adapter.py`.
- **Verified:** Unit test `test_hyperswitch_webhook_signature_and_replay_protection` in `tests/unit/test_ws05_billing_licensing.py`.

### DEF-R02: Windows Host Command Escapes Bypassing Sandbox Governor
- **Resolution:** Added comprehensive pattern filtering in `SecurityGovernor` intercepting powershell.exe, cmd.exe, wscript, mshta, certutil, vssadmin, UNC network paths, DOS device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9), and NTFS alternate data streams.
- **Verified:** 45 adversarial isolation vectors in `tests/unit/test_ws03_sandbox_security.py`.
