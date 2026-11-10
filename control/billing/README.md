# Layer 13: Entitlements & Billing (Control Plane)

The Entitlements & Billing layer governs usage limits, consumption-based metering, subscription tiers, customer quotas, and payment processing.

## Architecture & Subsystems

1. **Token Metering (`control/billing/metering/`)**
   - Integrates with OpenMeter via CloudEvents 1.0 schema.
   - Real-time token consumption tracking (prompt, completion, cache).
   - Real-time cost attribution by user, tenant, and application.

2. **Billing Engine (`control/billing/engine/`)**
   - Quarantined usage-based billing engine (Lago API integration, strict REST quarantine).
   - Plan definitions, feature entitlements, quotas, and subscription lifecycles.

3. **Payments Router (`control/billing/payments/`)**
   - Universal payment orchestration powered by Hyperswitch.

4. **BYOK & BYOI Policy (`control/billing/byok/`, `control/billing/byoi/`)**
   - Credit bypass when user supplies their own API keys or infrastructure.

## Testing

```bash
python -m pytest control/billing/metering/tests/ -v
```
