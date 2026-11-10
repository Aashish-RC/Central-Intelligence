# Layer 13: Entitlements & Billing (Control Plane) — COMPLETE

The Entitlements & Billing layer governs usage limits, consumption-based metering, subscription tiers, customer quotas, universal payment processing, BYOK/BYOI policies, and dispute resolution workflows.

---

## Architecture & Subsystems

1. **Token Metering (`control/billing/metering/`) (Features 13.09, 13.10)**
   - Integrates with OpenMeter via CloudEvents 1.0 schema.
   - Real-time token consumption tracking (prompt, completion, cache).
   - Real-time cost attribution by user, tenant, and application.

2. **Billing Engine (`control/billing/engine/`) (Features 13.01–13.05, 13.14–13.16)**
   - Quarantined usage-based billing engine (Lago API integration, strict REST boundary).
   - Plan definitions, feature entitlements, quotas, and subscription lifecycles.
   - Wallets, on-demand credit top-ups, and regional tax calculations.

3. **Hyperswitch Payment Router (`control/billing/payments/`) (Feature 13.13)**
   - Universal payment orchestration powered by Juspay Hyperswitch (Apache-2.0).
   - Routes payments across Stripe, PayPal, and global card processors.
   - Automatic invoice settlement linking Lago invoice IDs to captured payment intents.

4. **BYOK Credit Bypass (`control/billing/byok/`) (Features 13.06, 13.10)**
   - Automatically detects user-supplied credentials and bypasses platform billing.
   - Meters usage in OpenMeter with `byok=True, billable=False` while maintaining rate limit and quota visibility.
   - Wires into L4 `cognitive/reasoning/providers/byokAdapter.ts`.

5. **BYO Infrastructure Compute Metering (`control/billing/byoi/`) (Feature 13.08)**
   - Meters compute workloads across heterogeneous targets: local devices, peer devices (LAN mesh), and cloud compute.
   - Computes real-time workload distributions (e.g. 50% local, 30% peer device, 20% cloud).

6. **Spend Caps & Real-Time Alerts (`control/billing/spend/`) (Feature 13.11)**
   - Real-time spend tracking against monthly budgets.
   - 80% threshold: dispatches email notification alerts to customer/admin.
   - 100% threshold: automatically pauses autonomous agent execution to prevent cost overruns.
   - Wires into L5 `FinancialAuthorityGuard` and L8 `BudgetTracker`.

7. **Automated Refund Pipeline (`control/billing/refunds/`) (Feature 13.12)**
   - Detects upstream model provider errors (500, 502, 503, 504, 529, timeouts).
   - Automatically restores consumed tokens to customer wallet/quota.
   - Automatically executes Hyperswitch monetary refunds if micro-payments were captured.

8. **Free-Tier Quota Gaming Detector (`control/billing/abuse/`) (Feature 13.18)**
   - Detects rapid account churn and free-tier abuse by correlating IP clusters, device fingerprints, and canonical email aliases.
   - Bridges to Layer 10 Abuse Detectors (`quota_gaming_detector.py` and `multi_account_detector.py`).

9. **Billing Audit Trails & Disputes (`control/billing/audit/`) (Feature 13.17)**
   - Cryptographic audit trail for every billing transaction anchored into Layer 10 Unified Merkle Ledger.
   - Customer dispute lifecycle: open dispute, evidence review, and resolution execution (refund vs uphold).

---

## Testing & Verification

```bash
# Run all Layer 13 billing tests
python -m pytest control/billing/ -q -m 'not live'

# Run payment router tests (13.13)
python -m pytest control/billing/payments/tests/ -q

# Run BYOK bypass tests (13.06, 13.10)
python -m pytest control/billing/byok/tests/ -q

# Run BYOI infrastructure metering tests (13.08)
python -m pytest control/billing/byoi/tests/ -q

# Run spend caps & alert tests (13.11)
python -m pytest control/billing/spend/tests/ -q

# Run automated refund pipeline tests (13.12)
python -m pytest control/billing/refunds/tests/ -q

# Run quota gaming abuse tests (13.18)
python -m pytest control/billing/abuse/tests/ -q

# Run billing audit and dispute tests (13.17)
python -m pytest control/billing/audit/tests/ -q
```
