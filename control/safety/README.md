# Layer 10: Safety, Trust & Privacy (Control Plane)

The Safety layer enforces prompt safety, anti-jailbreak defenses, PII filtering, audit immutability, data residency, and compliance governance.

## Architecture & Subsystems

1. **🚩 4-Tier PII & Telemetry Scrubber (`control/safety/pii/`)**
   - **Tier 1 (Telemetry):** Technical non-PII metrics (tokens, latency, model, cost) with pseudonymized/hashed user ID. Retained 90–365 days -> L14 SigNoz.
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
   - Guarantees EU user prompts and completions route only to EU-region model endpoints and EU storage sinks, preventing cross-border transfers to US SigNoz or US model endpoints.

9. **Legal Hold & Lawful Authority Request Handler (`control/safety/legal/`) (Features 10.46, 10.47)**
   - Places active preservation holds suspending data erasure during litigation or compliance audits.
   - Ingests government subpoenas, court orders, and warrants with immutable cryptographic hash-chained audit trails.

10. **Unified Audit Ledger (`control/safety/audit/`)**
    - Cryptographic append-only Merkle hash chain for tamper-evident recording of cross-module actions and dispatches.

## Testing

```bash
# Run all Layer 10 tests
python -m pytest control/safety/ -q -m 'not live'

# Run Guardrails tests
python -m pytest control/safety/guardrails/tests/ -q -m 'not live'

# Run PII Scrubber tests
python -m pytest control/safety/pii/tests/ -q

# Run Consent tests
python -m pytest control/safety/consent/tests/ -q

# Run Kill Switch tests
python -m pytest control/safety/action_safety/tests/ -q

# Run Privacy & Residency tests
python -m pytest control/safety/privacy/tests/ -q

# Run Wellbeing tests
python -m pytest control/safety/wellbeing/tests/ -q

# Run Legal Hold tests
python -m pytest control/safety/legal/tests/ -q
```
