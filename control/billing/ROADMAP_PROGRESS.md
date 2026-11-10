# Layer 13: Entitlements & Billing — Feature Roadmap Progress & Checkpoint Log

> **Subsystem Core:** Python (FastAPI, OpenMeter, Lago Quarantine Adapter, Hyperswitch)  
> **Status Standard:** Verified against functional test suites.  
> **Test Suite:** `control/billing/metering/tests/`, `control/billing/engine/tests/`

---

## 1. Feature Status Table

| Feature ID | Feature Name | Status | License Treatment | Reviewed by Human | Verification Evidence |
|:---|:---|:---:|:---|:---:|:---|
| **13.01** | Plan Definitions & Tier Specifications | **pending** | Adapted (AGPL-3.0 Quarantined - Lago) | no | Task 13.2 |
| **13.02** | Feature Entitlements per Plan | **pending** | Adapted (AGPL-3.0 Quarantined - Lago) | no | Task 13.2 |
| **13.03** | Licensing & Seat Allocation | **pending** | Adapted (AGPL-3.0 Quarantined - Lago) | no | Task 13.2 |
| **13.04** | Usage Quotas (Tokens, RPM, Concurrency) | **pending** | Adapted (AGPL-3.0 Quarantined - Lago) | no | Task 13.2 |
| **13.05** | Real-Time Entitlement Gate at Request Time | **pending** | Adapted (AGPL-3.0 Quarantined - Lago) | no | Task 13.2 |
| **13.06** | BYOK Credit Bypass | **pending** | Own implementation | no | Task 13.4 |
| **13.08** | BYO Infrastructure Compute Metering | **pending** | Own implementation | no | Task 13.5 |
| **13.09** | Real-Time Token Consumption Metering | **built** | Adapted (Apache-2.0 - OpenMeter) | no | `metering/tests/test_openmeter.py` |
| **13.10** | Multi-Tenant & Multi-App Cost Attribution | **built** | Adapted (Apache-2.0 - OpenMeter) | no | `metering/tests/test_openmeter.py` |
| **13.11** | Real-Time Spend Caps & Alerts (80%/100%) | **pending** | Own implementation | no | Task 13.6 |
| **13.12** | Automated Provider-Error Refund Pipeline | **pending** | Own implementation | no | Task 13.7 |
| **13.13** | Invoicing & Payment Processing | **pending** | Adapted (Apache-2.0 - Hyperswitch) | no | Task 13.3 |
| **13.14** | Subscription Lifecycle (Upgrade, Downgrade, Cancel) | **pending** | Adapted (AGPL-3.0 Quarantined - Lago) | no | Task 13.2 |
| **13.15** | Credits, Wallets & On-Demand Top-Ups | **pending** | Adapted (AGPL-3.0 Quarantined - Lago) | no | Task 13.2 |
| **13.16** | Tax Calculation & Regional Pricing | **pending** | Adapted (AGPL-3.0 Quarantined - Lago) | no | Task 13.2 |
| **13.17** | Tamper-Proof Billing Audit & Dispute Workflow | **pending** | Own implementation | no | Task 13.9 |
| **13.18** | Free-Tier Quota Abuse Detector | **pending** | Own implementation | no | Task 13.8 |
