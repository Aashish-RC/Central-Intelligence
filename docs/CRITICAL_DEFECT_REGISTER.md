# Central Intelligence — Critical Defect Register

**Status Date:** 2026-11-16  
**Active Defects:** 4  
**Resolved Defects:** 2  

---

## Active Defects

### DEF-01: Live Adapter Test Suite Fails When External Services Are Offline
- **Severity:** High / P1
- **Component:** `tests/integration/test_live_adapters.py`
- **Description:** Running `pytest tests/integration/test_live_adapters.py -m live` results in 11 test failures because live backends (LiveKit :7880, OpenFGA :8080, Infisical, OpenMeter, Lago, SigNoz :4317, Supabase, Temporal :7233, Bytebase, Kamal, LibreChat :8787) are not running on the local host.
- **Impact:** Live integration test suite cannot pass in isolated developer environments without mock test server fixtures.
- **Root Cause:** Tests instantiate live adapters directly with localhost URLs without providing a deterministic in-process or mock HTTP wire server when containers are absent.
- **Remediation Plan:** Update `test_live_adapters.py` to use a robust mock HTTP server fixture that speaks real wire protocols when live backends are unreachable, or run against actual containerized services when Docker is started.

### DEF-02: Compose E2E Suite Blocks When Docker Daemon Is Stopped
- **Severity:** Critical / P0 (Operational Blocker)
- **Component:** `tests/integration/test_compose_stack_e2e.py`
- **Description:** `test_valkey_redis_wire_roundtrip_e2e` and related tests attempt to connect to localhost ports (6379, 6333, etc.) and hang or raise `ConnectionError` when Docker Desktop is stopped.
- **Impact:** 19 compose integration tests cannot execute on developer machines where Docker service is not running.
- **Root Cause:** Tests do not skip or provide an embedded fallback when Docker daemon is stopped and `COMPOSE_E2E_AUTO_START=1` cannot launch containers.
- **Remediation Plan:** Add daemon health check at start of `compose_stack_lifecycle` fixture; fail fast or report clear prerequisite instructions instead of hanging on socket timeouts.

### DEF-03: Windows Job Object Ceilings Missing for Local Process Runner
- **Severity:** Medium / P1 (Security)
- **Component:** `cognitive/action/agent/sandbox/local_docker_adapter.py`
- **Description:** While `SecurityGovernor` blocks Windows command binaries, shell executions that bypass governor checks could theoretically run without OS-level memory and CPU ceilings on Windows hosts.
- **Impact:** Potential resource exhaustion on Windows developer hosts if untrusted processes are executed outside containers.
- **Remediation Plan:** Assign Windows Job Objects with memory and CPU limit flags to processes spawned on Windows hosts.

### DEF-04: Automated Remote Payment Reconciliation Missing in HyperSwitch Adapter
- **Severity:** Medium / P1 (Financial Assurance)
- **Component:** `control/billing/payments/hyperswitch_adapter.py`
- **Description:** HyperSwitch adapter stores durable payment state locally, but does not yet run a background periodic reconciliation job to synchronize state with remote payment gateway in case webhooks are delayed or dropped.
- **Impact:** Local records could temporarily diverge from remote processor state under severe network partitions.
- **Remediation Plan:** Implement `reconcile_remote_settlements()` method that queries the gateway for recent transactions and reconciles local SQLite records.

---

## Resolved Defects

### DEF-R01: HyperSwitch Webhook HMAC Validation & Replay Attack Vulnerability
- **Resolution:** Implemented HMAC-SHA256 signature verification with secret key, 300-second timestamp replay window, and nonce deduplication in `control/billing/payments/hyperswitch_adapter.py`.
- **Verified:** Commit `b3778ea` and unit test `test_hyperswitch_webhook_signature_and_replay_protection`.

### DEF-R02: Windows Host Command Escapes Bypassing Sandbox Governor
- **Resolution:** Added comprehensive pattern filtering in `SecurityGovernor` intercepting powershell.exe, cmd.exe, wscript, mshta, certutil, vssadmin, UNC network paths, DOS device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9), and NTFS alternate data streams.
- **Verified:** Commit `b3778ea` and unit test `test_windows_host_escape_commands_blocked`.
