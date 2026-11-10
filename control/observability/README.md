# Layer 14: Observability (Control Plane)

The Observability layer provides comprehensive telemetry, distributed tracing, latency percentiles, status reporting, metric anomaly detection, and privacy-preserving product analytics across the Central-Intelligence monorepo.

## Architecture & Subsystems

1. **SigNoz OpenTelemetry Engine (`control/observability/signoz/`)**
   - Full OpenTelemetry standard conformance.
   - Cross-layer distributed traces (spanning Perception, Memory, Knowledge, Reasoning, Action, and Control).
   - Real-time latency distribution percentiles ($P_{50}, P_{90}, P_{95}, P_{99}$).
   - Error rate calculation and request replay debugging.

2. **4-Tier Structured Log Router & Retention Engine (`control/observability/log_routing/`, `control/observability/log_management/`)**
   - Integrates with Layer 10 Crown Jewel (`FourTierPIIScrubber`).
   - Routes telemetry metrics to SigNoz (Tier 1), diagnostic traces to ephemeral stores (Tier 2), compliance actions to Merkle ledgers (Tier 3), and Zero-Data Retention (ZDR) to volatile RAM (Tier 4).
   - `RetentionScheduler` enforces tenant/user TTLs and respects c15t consent privacy mode (zero retention for privacy mode).

3. **Metric Anomaly Detector (`control/observability/alerts/`)**
   - Statistical anomaly detector (>3σ z-score spikes) against rolling baseline windows.
   - Dispatches alerts to webhooks, Slack channels, and email sinks.

4. **Observability Dashboards (`control/observability/dashboards/`)**
   - **Real-Time System Dashboard (`14.15`)**: Cluster-wide latency, throughput, error rates, and active spans (admin-restricted).
   - **Per-Tenant Dashboard (`14.16`)**: Enforces strict tenant isolation; tenants only see their own metrics.
   - **Per-App Dashboard (`14.17`)**: Breakdown by application / agent service with PostHog feature invocation analytics.
   - **Executive Dashboard (`14.18`)**: High-level KPIs, total cost, aggregate usage trends, and model spend breakdown.

5. **Operator Usage Analytics (`control/observability/admin_console/`)**
   - Cross-tenant usage inspection and heavy user identification.
   - Wires directly into Layer 12 IAM `OperatorConsole` for supervisory interventions.

6. **Privacy-Preserving Funnels (`control/observability/privacy/`)**
   - Mathematical differential privacy layer over product analytics using the Laplace mechanism calibrated to epsilon ($\epsilon$).
   - Protects individual user privacy while preserving macro conversion trends.

7. **Uptime & Health Monitoring (`control/observability/uptime/`)**
   - Automated heartbeat monitoring and public status pages via Uptime Kuma adapter.

8. **Product Analytics (`control/observability/posthog/`)**
   - Feature adoption, funnels, and session replay streams via PostHog adapter.

## Testing

```bash
python -m pytest control/observability/ -q -m 'not live'
```
