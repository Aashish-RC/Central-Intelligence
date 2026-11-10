# Layer 10: Safety, Trust & Privacy (Control Plane)

The Safety layer enforces prompt safety, anti-jailbreak defenses, PII filtering, audit immutability, data residency, and compliance governance.

## Architecture & Subsystems

1. **🚩 4-Tier PII & Telemetry Scrubber (`control/safety/pii/`)**
   - **Tier 1 (Telemetry):** Technical non-PII metrics (tokens, latency, model, cost) with pseudonymized/hashed user ID. Retained 90–365 days -> L14 SigNoz.
   - **Tier 2 (Diagnostic):** Redacted chat snippets with sensitive entities scrubbed. Retained 14–30 days for triage.
   - **Tier 3 (Action Audit):** Tamper-proof, cryptographically encrypted records of agent actions and tool calls. Retained 1 year (365 days) -> Unified Merkle Ledger.
   - **Tier 4 (ZDR):** Zero-Data Retention volatile RAM-only buffer with atomic purge on delivery and 30s auto-expiry.
   - **Right-to-Erasure:** Universal `purge_all(user_id)` propagating deletion across all four tiers simultaneously.

2. **Guardrails Engine (`control/safety/guardrails/`)**
   - Input jailbreak / injection filtering.
   - Output hallucination & toxicity detection.
   - Tool execution authorization & output checks.
   - NeMo Guardrails colang adapters.

3. **Unified Audit Ledger (`control/safety/audit/`)**
   - Cryptographic append-only Merkle hash chain for tamper-evident recording of actions and dispatches across all modules.

4. **Rules & Governance Engine (`control/safety/rules/` & `control/safety/governance/`)**
   - Per-tenant, per-profession policy evaluation.
   - Privacy-law modes (GDPR, India DPDP, CCPA).
   - Regulatory standards (SOC 2, ISO 27001, EU AI Act).

## Testing

```bash
python -m pytest control/safety/guardrails/tests/ -v
python -m pytest control/safety/pii/tests/ -v
```
