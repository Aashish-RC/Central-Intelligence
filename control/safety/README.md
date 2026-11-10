# Layer 10: Safety, Trust & Privacy (Control Plane) — COMPLETE

The Safety layer enforces prompt safety, anti-jailbreak defenses, PII filtering, audit immutability, data residency, abuse prevention, minor protections, and regulatory compliance governance.

---

## Architecture & Subsystems

1. **🚩 4-Tier PII & Telemetry Scrubber (`control/safety/pii/`) (Feature 10.30)**
   - **Tier 1 (Telemetry):** Technical non-PII metrics (tokens, latency, model, cost) with pseudonymized user ID. Retained 90–365 days -> L14 SigNoz.
   - **Tier 2 (Diagnostic):** Redacted chat snippets with sensitive entities scrubbed. Retained 14–30 days for triage.
   - **Tier 3 (Action Audit):** Tamper-proof, cryptographically encrypted records of agent actions and tool calls. Retained 1 year (365 days) -> Unified Merkle Ledger.
   - **Tier 4 (ZDR):** Zero-Data Retention volatile RAM-only buffer with atomic purge on delivery and 30s auto-expiry.
   - **Right-to-Erasure:** Universal `purge_all(user_id)` propagating deletion across all four tiers simultaneously.

2. **NeMo Guardrails Integration (`control/safety/guardrails/nemo/`) (Feature 10.02)**
   - Wraps NVIDIA NeMo Guardrails (`LLMRails`) with programmable Colang flows (`actions.co`, `general.co`, `config.yml`).
   - Input rails detect obfuscated, encoding-based jailbreaks (Base64, Hex, ROT13, Leetspeak, URL encoding, Binary) that standard regex filters miss.
   - Output rails enforce factuality, hallucination prevention, and internal system prompt / delimiter leak detection.

3. **c15t Consent Management & Privacy Mode (`control/safety/consent/`) (Features 10.29, 10.35)**
   - Granular explicit opt-in for telemetry, diagnostic recording, and model training.
   - Per-user Privacy Mode overriding all retention and forcing Tier 4 Zero-Data Retention (zero data in logs).
   - Cryptographic GDPR Article 7 compliance receipt export.

4. **Emergency Agent Kill Switch (`control/safety/action_safety/`) (Feature 10.24)**
   - Instantaneous, sub-second (< 1s) execution halting across tenant, user, or individual agent scopes.
   - Freezes running state snapshots and immediately aborts active tool invocations and registered async callbacks.

5. **Indirect Prompt Injection Detector (`control/safety/guardrails/core/indirect_injection.py`) (Feature 10.04)**
   - Scans 3rd-party untrusted retrieved content (web search results, crawled pages, RAG documents) for embedded instruction overrides.
   - Flags and neutralizes hidden CSS styles (`display:none`, `font-size:0px`), HTML comment directives, and delimiter breakout escapes.

6. **Over-Reliance Guard (`control/safety/wellbeing/`) (Feature 10.55)**
   - Tracks consecutive decision-deferral patterns ("what should I do?", "you decide").
   - Triggers wellbeing advisories upon reaching threshold (default 10) prompting autonomous user judgment; resets on agency assertion.

7. **Universal Memory Erasure Propagator (`control/safety/privacy/`) (Feature 10.31)**
   - Propagates GDPR Article 17 Right-to-Erasure across L2 Cognitive Memory, L3 Knowledge, Qdrant vector points, Meilisearch indexes, Redis cache, L10 PII Scrubber tiers, and L14 logs.
   - Appends an immutable compliance meta-record (with pseudonymized user hash) into the Unified Merkle Ledger.

8. **Data Residency and Geo-Fencing Enforcer (`control/safety/privacy/`) (Feature 10.32)**
   - Geo-fences data boundaries (EU, US, APAC, GLOBAL).
   - Guarantees EU user prompts and completions route only to EU-region model endpoints and EU storage sinks, preventing cross-border transfers.

9. **Legal Hold & Lawful Authority Request Handler (`control/safety/legal/`) (Features 10.46, 10.47)**
   - Places active preservation holds suspending data erasure during litigation or compliance audits.
   - Ingests government subpoenas, court orders, and warrants with immutable cryptographic hash-chained audit trails.

10. **Multi-Account & Abuse Detectors (`control/safety/abuse/`) (Features 10.48, 10.49, 10.50)**
    - Sybil and multi-account creation detection using IP clustering, email canonicalization, and device fingerprints.
    - Quota gaming detector: identifies churning, rapid registration-to-exhaustion, and parallel multi-tenant quota circumvention.
    - Automated misuse detector: detects programmatic bot patterns, request frequency spikes (>1000 req/min), automated headless browser headers, and mechanical timing variance.

11. **Account Lifecycle Grace Period & Auto-Erasure (`control/safety/lifecycle/`) (Features 10.51, 10.52)**
    - Soft-deletion lifecycle with 30-day retention grace period. Allows account recovery within 30 days without data loss.
    - Automated expiration runner: upon lapse of 30 days, triggers Universal Memory Erasure Propagator (Feature 10.31) for permanent deletion.
    - Respects active legal holds, preventing deletion if user is under preservation order.

12. **Content Rights Enforcer & Source Attribution (`control/safety/rights/`) (Features 10.56, 10.57)**
    - Verbatim reproduction prevention: detects copyrighted text passages via sliding n-gram matching and redacts them in outbound generation.
    - Source attribution enforcer: verifies citations on model outputs derived from external sources and automatically formats/appends attribution footers.

13. **Third-Party Personal Data Minimizer (`control/safety/privacy/`) (Features 10.58, 10.59)**
    - Protects non-user personal data (names, emails, phone numbers, SSNs, credit cards in uploaded documents).
    - Multi-stage pipeline minimization: cleanses non-user data before L1 input gateway, L2 memory storage, L3 RAG/Meilisearch indexing, and L4 model dispatch.

14. **Safeguards for Minors & Child-Safety Mode (`control/safety/wellbeing/`) (Feature 10.44)**
    - Age-gating verified via L12 Identity (Keycloak).
    - Child-safety mode: blocks adult, mature, gambling, and age-restricted substance content.
    - Disables high-risk agent capabilities for minors (payments, financial transfers, raw browser automation, shell execution).

15. **Custom AI Governance Module (`control/safety/governance/`) (Features 10.25, 10.26, 10.27, 10.28)**
    - Clean Apache-2.0 custom governance framework replacing AGPL VerifyWise.
    - Profession-specific rule sets: Legal, Medical, Financial, Engineering disclaimers and checks.
    - Statutory compliance modes: GDPR, India DPDP Act 2023, CCPA/CPRA.
    - Security standards: SOC 2 Type II, ISO 27001 continuous audit policies.
    - AI regulations: EU AI Act High-Risk (Articles 6, 9-15 mandatory human-in-the-loop oversight and strict immutable logging), EU AI Act transparency, ISO 42001, NIST AI RMF.

16. **Cryptographic Audit Log Tamper-Proofer (`control/safety/audit/`) (Feature 10.36)**
    - Chained cryptographic hashing where each entry embeds the SHA-256 hash of the predecessor.
    - Merkle tree root computation for batch sealing.
    - Tamper detection engine: pinpointing the exact entry index and mutation type (payload alteration vs broken previous hash link).

17. **Continuous Automated Red-Team Runner (`control/safety/guardrails/tests/`) (Feature 10.39)**
    - Scheduled weekly adversarial attack campaigns across prompt injections, multi-turn jailbreaks, tool outputs, and homoglyphs.
    - Wires with L11 Scenario Simulation Runner (`control/evaluation/simulation/scenario_runner.py`) to feed multi-turn adversarial dialogs and generate weekly vulnerability reports of attack vectors that breached defenses.

---

## Verification & Test Suites

```bash
# Run all Layer 10 safety tests
python -m pytest control/safety/ -q -m 'not live'

# Run abuse detector tests (10.48, 10.49, 10.50)
python -m pytest control/safety/abuse/tests/ -q

# Run account lifecycle grace period tests (10.51, 10.52)
python -m pytest control/safety/lifecycle/tests/ -q

# Run content rights & attribution tests (10.56, 10.57)
python -m pytest control/safety/rights/tests/ -q

# Run third-party data minimizer tests (10.58, 10.59)
python -m pytest control/safety/privacy/tests/test_third_party.py -q

# Run minor safeguards tests (10.44)
python -m pytest control/safety/wellbeing/tests/test_minor_safeguards.py -q

# Run AI governance module tests (10.25, 10.26, 10.27, 10.28)
python -m pytest control/safety/governance/tests/ -q

# Run audit log tamper-proofing tests (10.36)
python -m pytest control/safety/audit/tests/test_tamper_proof.py -q

# Run red-team continuous runner tests (10.39)
python -m pytest control/safety/guardrails/tests/test_redteam_extension.py -q
```
