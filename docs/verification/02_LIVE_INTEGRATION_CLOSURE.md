# 02 — Live Integration Closure

**Reviewed:** 2026-11-17
**Revalidated revision:** `af5f7f163af10a9c29b2778e15a2311a4c9afc02`
**Status:** **OPEN — 0 of 11 scenarios has genuine live-service pass evidence**

## Result

The 11 historical scenarios were selected and their explicit preflight was run with live target/credential variables blanked in that process. On the current revision the result was **10 expected prerequisite failures, 1 pass of a mocked Kamal command-sequence test, 8 deselected unrelated tests, and 0 skips**. None of the 11 was executed against a real target service. Separately, two live Qdrant Compose E2E tests passed against an already-running local service; neither is one of these 11 scenarios.

The test module no longer calls `pytest.skip()` for missing live prerequisites. When explicitly selected, cases now fail with the missing variable rather than appearing as successful or silently skipped. The module remains marked `live` and is excluded by the repository's normal offline pytest configuration; run the live gate explicitly.

## Scenario evidence

| # | Test | Evidence/status |
|---:|---|---|
| 1 | `test_openfga_persists_across_python_restart` | **Not run live.** `OPENFGA_LIVE_URL` was absent. The Compose definition now configures PostgreSQL persistence and migrations, but neither was run. |
| 2 | `test_infisical_persists_across_python_restart` | **Not run live.** `INFISICAL_LIVE_URL`, `INFISICAL_CLIENT_ID`, and `INFISICAL_CLIENT_SECRET` were absent. No secret write/read/revocation was attempted. |
| 3 | `test_lago_persists_across_python_restart` | **Not run live.** `LAGO_LIVE_URL` and `LAGO_API_KEY` were absent. No customer/subscription operation was attempted. |
| 4 | `test_openmeter_persists_across_python_restart` | **Not run live.** `OPENMETER_LIVE_URL` was absent. The unit test accepts the API's HTTP 204 event-ingestion response; the mocked adapter test passed, but no Kafka event was ingested or queried from a service. |
| 5 | `test_signoz_persists_across_python_restart` | **Not run live.** `SIGNOZ_LIVE_URL` was absent. Its assertion now polls for the emitted operation name in the returned trace payload; no trace was exported or retrieved. |
| 6 | `test_temporal_workflow_survives_worker_restart` | **Not run live.** `TEMPORAL_LIVE_URL` was absent. No worker interruption/replay was attempted. |
| 7 | `test_supabase_relational_and_vector_persist` | **Not run.** `POSTGRES_LIVE_URL` is present in the local environment, but the test creates tables and embeddings. The target was not confirmed to be a disposable authorized test database, so no mutation was made. Compose storage was changed from `tmpfs` to the declared named volume. |
| 8 | `test_sandbox_executes_real_python` | **Not run.** `SANDBOX_LIVE=1` was not enabled. The adapter may call a paid external execution provider, which was not invoked. |
| 9 | `test_kamal_deployment_command_sequence_is_simulated` | **Passed only as a simulation** in the preflight run. `subprocess.run`, executable discovery, and HTTP are mocked. It is not evidence that the Kamal CLI or a server works; no deployment was performed, as required. |
| 10 | `test_bytebase_migration_executes_real_ddl` | **Not run live.** `BYTEBASE_LIVE_URL` and `BYTEBASE_API_TOKEN` were absent. No authenticated migration or DDL was attempted. |
| 11 | `test_librechat_routes_to_reasoning_gateway` | **Not run live.** `LIBRECHAT_LIVE_URL`, `REASONING_GATEWAY_URL`, and `REASONING_GATEWAY_API_KEY` were unavailable. Compose now mounts the custom endpoint config and sets host-to-container networking, but neither LibreChat nor the gateway was started. The existing adapter-level test does not prove a UI-originated request. |

### Genuine live vs. fail-closed vs. mocked

- **Genuine live successes among these 11:** 0.
- **Fail-closed preflight outcomes:** 10 cases failed before making a service request because prerequisites were deliberately blank. These are configuration blockers, not service failures and not live passes.
- **Mocked/simulated:** the Kamal command-order test; the OpenMeter adapter regression test; the earlier 31-test adapter suite. None counts as a live-service success.
- **Expected fail-closed regression:** `test_live_query_fails_closed_when_openmeter_down` passed against the local unused port `127.0.0.1:59998`; this verifies adapter behavior only.
- **Skipped:** 0 in the selected preflight run. Other offline pytest commands continue to exclude tests marked `live` by configuration; the explicit live gate is required.

### Revalidation commands and host evidence (2026-11-17)

The preflight used the repository's existing `.venv` and set each variable below to an empty value in the test process only; no `.env` file was changed:

```powershell
$names = 'OPENFGA_LIVE_URL','INFISICAL_LIVE_URL','INFISICAL_CLIENT_ID','INFISICAL_CLIENT_SECRET',
  'LAGO_LIVE_URL','LAGO_API_KEY','OPENMETER_LIVE_URL','OPENMETER_API_TOKEN','SIGNOZ_LIVE_URL',
  'TEMPORAL_LIVE_URL','POSTGRES_LIVE_URL','SANDBOX_LIVE','BYTEBASE_LIVE_URL','BYTEBASE_API_TOKEN',
  'LIBRECHAT_LIVE_URL','REASONING_GATEWAY_URL','REASONING_GATEWAY_API_KEY'
foreach ($name in $names) { Set-Item -Path "Env:$name" -Value '' }
.\.venv\Scripts\python.exe -m pytest -o addopts= tests\integration\test_compose_stack_e2e.py `
  -k 'openfga_persists or infisical_persists or lago_persists or openmeter_persists or signoz_persists or temporal_workflow_survives_worker_restart or supabase_relational_and_vector_persist or sandbox_executes_real_python or bytebase_migration_executes_real_ddl or librechat_routes_to_reasoning_gateway or kamal_deployment_command_sequence_is_simulated' `
  --tb=no -q
# 10 failed (missing prerequisites), 1 passed (mocked Kamal), 8 deselected
```

The Python 3.11.14 and 3.13.11 offline suites each passed (**1,195 passed, 1 skipped, 125 deselected**). TypeScript workspace, connector, orchestration, and surface suites passed. These are regression checks, not live evidence for any of the 11 scenarios.

## Exact verification commands

The selected scenario preflight was run after setting the following process environment variables to empty strings: `OPENFGA_LIVE_URL`, `INFISICAL_LIVE_URL`, `INFISICAL_CLIENT_ID`, `INFISICAL_CLIENT_SECRET`, `LAGO_LIVE_URL`, `LAGO_API_KEY`, `OPENMETER_LIVE_URL`, `SIGNOZ_LIVE_URL`, `TEMPORAL_LIVE_URL`, `POSTGRES_LIVE_URL`, `SANDBOX_LIVE`, `BYTEBASE_LIVE_URL`, `BYTEBASE_API_TOKEN`, `LIBRECHAT_LIVE_URL`, `REASONING_GATEWAY_URL`, and `REASONING_GATEWAY_API_KEY`. No `.env` file was modified.

```powershell
.\.venv\Scripts\python.exe -m pytest -o addopts= tests\integration\test_compose_stack_e2e.py `
  -k 'openfga_persists or infisical_persists or lago_persists or openmeter_persists or signoz_persists or temporal_workflow_survives_worker_restart or supabase_relational_and_vector_persist or sandbox_executes_real_python or bytebase_migration_executes_real_ddl or librechat_routes_to_reasoning_gateway or kamal_deployment_command_sequence_is_simulated' `
  --tb=no -q
```

Additional relevant evidence:

```powershell
.\.venv\Scripts\python.exe -m pytest -o addopts= control\billing\metering\tests\test_openmeter.py -q
# 5 passed

.\.venv\Scripts\python.exe -m pytest -o addopts= control\billing\metering\tests\test_openmeter_live.py::test_live_query_fails_closed_when_openmeter_down -q
# 1 passed; local fail-closed check, not a live service

.\.venv\Scripts\python.exe -m pytest -o addopts= tests\integration\test_compose_stack_e2e.py --collect-only -q
# 19 collected
```

## Remaining requirements to close

1. Provide authorized disposable-service endpoints/credentials for Infisical, Lago, and Bytebase, plus reasoning-gateway configuration. Do not provide production credentials.
2. Confirm `POSTGRES_LIVE_URL` points to an authorized disposable test database before running its DDL/write test.
3. Use a host with enough memory and registry access to build/pull and start small service batches. Then verify readiness, migrations, authenticated operations, actual persisted data after restart, and trace retrieval.
4. Run sandbox coverage only against a local/free authorized runner, and keep Kamal deployment unexecuted unless deployment authorization is separately granted.
5. Add a real LibreChat login/chat request that traverses its configured custom endpoint to the reasoning gateway; a healthy UI and a direct adapter call are not equivalent.

**Release gate:** Batch 1 live integration closure is incomplete. Do not mark tasks 10.2 or 11.2 complete and do not recommend Batch 2 until the above live evidence is captured.
