# Legacy E2E Tests (Archived Services)

This directory contains integration and end-to-end test suites that were preserved for historical reference following the **Central Intelligence Container Consolidation Initiative (Phases A0–A15)**:

| Test Name | Target Service | Consolidation Phase | Replacement / Migration |
|---|---|---|---|
| `test_infisical_persists_across_python_restart` | Infisical | Phase A8 | Cloud-native secrets (AWS SSM / GCP SM / K8s) and `scripts/rotate_secrets.py` |
| `test_openmeter_persists_across_python_restart` | OpenMeter | Phase A6 | Lago unified metering, billing, and webhooks |
| `test_signoz_persists_across_python_restart` | SigNoz | Phase A5 | OTel Collector with Langfuse HTTP sink + local/managed sinks |
| `test_bytebase_migration_executes_real_ddl` | Bytebase | Phase A10 | Native Alembic CLI migrations |
| `test_librechat_routes_to_reasoning_gateway` | LibreChat | Phase A9 | Hermes native interaction surface |

These tests require full legacy docker profiles from `docker-compose.demo.yml` and are not part of the active or live consolidated CI test runner.
