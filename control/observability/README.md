# Layer 14: Observability (Control Plane)

The Observability layer provides comprehensive telemetry, distributed tracing, latency percentiles, status reporting, and product analytics across the Central-Intelligence monorepo.

## Architecture & Subsystems

1. **SigNoz OpenTelemetry Engine (`control/observability/signoz/`)**
   - Full OpenTelemetry standard conformance.
   - Cross-layer distributed traces (spanning Perception, Memory, Knowledge, Reasoning, Action, and Control).
   - Real-time latency distribution percentiles ($P_{50}, P_{90}, P_{95}, P_{99}$).
   - Error rate calculation and request replay debugging.

2. **4-Tier Structured Log Router (`control/observability/logging/`)**
   - Integrates with Layer 10 Crown Jewel (`FourTierPIIScrubber`).
   - Routes telemetry metrics to SigNoz (Tier 1), diagnostic traces to ephemeral stores (Tier 2), compliance actions to Merkle ledgers (Tier 3), and Zero-Data Retention (ZDR) to volatile RAM (Tier 4).

3. **Uptime & Health Monitoring (`control/observability/uptime/`)**
   - Automated heartbeat monitoring and public status pages.

4. **Product Analytics (`control/observability/posthog/`)**
   - Feature adoption, funnels, and differential privacy guarantees.

## Testing

```bash
python -m pytest control/observability/signoz/tests/ -v
```
