# Central Intelligence Platform Audit — 05. Security & Governance

**Baseline:** Commit `138b95b` on branch `main`  
**CI Baseline:** GitHub Actions Run `43480953326`  
**Scope:** Authentication, Zanzibar ReBAC authorization, secret vaulting, cryptographic Merkle audit ledger, prompt injection defense, PII scrubbing, fail-closed guards, tool sandboxing, supply-chain hygiene, and AGPL quarantine.

---

## 1. Authentication & Tenant Boundaries

### Keycloak OIDC Authentication (`control/identity/keycloak_adapter.py`)
- **Implemented Logic:**
  - Password strength validation: `validate_password_strength()` enforces minimum 8 characters, uppercase, lowercase, numbers, and special symbols (`#L114-L122`).
  - Hashing: Uses SHA-256 with 16-byte random salt (`secrets.token_hex(16)`) and constant-time comparison (`hmac.compare_digest()`, `#L158`).
  - Passkeys (WebAuthn/FIDO2) and TOTP MFA verification methods are declared.
- **Vulnerabilities & Security Gaps:**
  - **In-Memory Credential Persistence:** User records, password hashes, and active sessions are stored in `self._users: Dict[str, KeycloakUserRecord] = {}` in Python memory. They are not persisted to Keycloak's PostgreSQL backend. A process restart wipes all credentials.
  - **Single Secret Token Signing:** JWTs are signed with a temporary in-memory key `secrets.token_hex(32)` (`#L103`) rather than asymmetric RS256/ES256 public-private keys issued by Keycloak's JWKS endpoint.

---

## 2. Authorization & Zanzibar ReBAC Access Control

### OpenFGA ReBAC Adapter (`control/identity/openfga_adapter.py`)
- **Relationship Model:**
  - Evaluates canonical Google Zanzibar tuples: `(user, relation, object)`.
  - Supports document hierarchies: `owner -> editor -> viewer`.
  - Supports delegation grants with expiration timestamps (`is_valid()`, `#L50-L52`).
- **Critical Security Defect:**
  - **Bypassed Authorization Daemon:** `OpenFGAAdapter` stores all tuples in an ephemeral set: `self._tuples: Set[Tuple[str, str, str]] = set()` (`#L70`).
  - Zero HTTP or gRPC calls are made to the live OpenFGA daemon (`http://openfga:8081`).
  - If the Python process dies, all access control policies are destroyed, reverting to an empty permission set.

---

## 3. Secret Vault & Key Lifecycle

### Infisical Adapter (`control/identity/secrets/infisical_adapter.py`)
- **Vault Features:**
  - Supports scoped secrets by tenant and application (`_scope_key()`, `#L88`).
  - Zero-downtime key rotation with grace period (`rotate_secret()`, `#L171-L200`).
  - Audit logging of all secret reads, stores, and rotations (`_record_audit()`).
- **Critical Vulnerabilities:**
  - **Plaintext Secrets in RAM:** Secrets are stored unencrypted in `self._vault: Dict[Tuple[str, Optional[str], str], ScopedSecret] = {}` in heap memory.
  - **No Hardware Security or KMS:** Ignores the configured Infisical KMS container (`:8083`).
  - Core credentials and user BYOK keys vanish on server restart.

---

## 4. Cryptographic Audit Logging & Merkle Ledger

### Unified Audit Ledger (`control/safety/audit/ledger.py`)
- **Architecture:** Append-only SQLite ledger with cryptographic hash chaining.
- **Hash Computation:**
  ```python
  payload = (
      f"{prev_hash}|{entry.id}|{entry.tenant_id}|{entry.project_id}|"
      f"{entry.user_id or ''}|{entry.role}|{entry.module}|{entry.action}|"
      f"{entry.resource}|{entry.status}|{entry.severity.value}|"
      f"{details_json}|{entry.client_ip or ''}|{entry.timestamp.isoformat()}"
  )
  entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
  ```
- **Merkle Tree Root:** `get_merkle_root()` constructs a full binary Merkle tree over all sequential entries.
- **Tamper Detection:** `verify_integrity()` traverses the entire ledger from seq 1. Any modification of past rows breaks `entry_hash` or `prev_hash` validation (`#L265-L290`).
- **Verdict: VERIFIED PRODUCTION-GRADE CROWN JEWEL.**

---

## 5. Prompt Injection Defense & Untrusted Content Handling

### Dual-Boundary Assembler (`control/context/trust/boundary_assembler.py`)
- **Segregation Model:**
  - Encloses low-trust data (user input, retrieved chunks, tool outputs, memory facts) within `<untrusted_content>` tags.
  - Neutralizes XML delimiter breakouts:
    ```python
    safe_content = self.content.replace("</untrusted_content>", "&lt;/untrusted_content&gt;")
    ```
  - Scans for injection signatures (e.g., `"ignore previous instructions"`, `"system override"`, `"you are now in developer mode"`).
- **Residual Risks:**
  - Regex detection can be bypassed by non-English evasion or Unicode homoglyphs. Must be paired with a model-based guardrail (NeMo).

---

## 6. PII Scrubbing & Data Privacy

### Four-Tier PII Scrubber (`control/safety/pii/tier_scrubber.py`)
- **Tier 1 (Telemetry):** Aggressive masking for public sinks (IPs, emails, names, phones, SSNs, credit cards, access keys).
- **Tier 2 (Diagnostics):** Preserves debugging structure, redacts personal secrets.
- **Tier 3 (Audit):** Retains cryptographic hashes, masks plaintext identifiers.
- **Tier 4 (ZDR - Zero Data Retention):** Ephemeral execution buffer; wiped immediately after turn completion.
- **Verdict: VERIFIED ROBUST.**

---

## 7. The Crown Jewel Production Guard Defect

### Production Guard (`control/safety/production_guard.py`)
The platform's primary defense against running insecure mock drivers in production contains a fatal flaw:

```python
# control/safety/production_guard.py, lines 30-32:
def is_production() -> bool:
    """Return True if ``ENVIRONMENT`` is set to ``production``."""
    return os.getenv("ENVIRONMENT", "").strip().lower() == "production"
```

1. **Naming Discrepancy:** `docs/DEPLOYMENT.md#L33` and `docs/SECURITY_REVIEW.md#L51` explicitly instruct operators to set `ENV=production`. Because `is_production()` checks `ENVIRONMENT` and not `ENV`, the guard evaluates to `False` in deployments following the official guide.
2. **Missing Invocations (Dead Imports):** Over 57% of adapters (19 of 33 files) import `fail_closed_in_production` but never call it. For example, `cognitive/perception/vision/paddleocr_adapter.py#L20` imports the function, but line 153 silently falls back to a synthetic string badge in live mode without raising an error.

---

## 8. Tool Execution Sandboxing & Blast Radius

### E2B MicroVM Sandbox (`cognitive/action/agent/sandbox/e2b_adapter.py`)
- In production with `e2b` installed, executes commands inside microVMs.
- In development/test mode, returns static dictionary without executing commands (`#L65-L71`).
- Blast radius simulator (`cognitive/action/safety/blast_radius.py`) predicts destructiveness, checking for commands like `rm -rf`, `drop table`, and `delete`.

---

## 9. Supply-Chain & Third-Party Licensing Review

### License Quarantine Enforcement (`scripts/check_licenses.py`)
- **Zero Live Secrets:** Scans pass cleanly; no hardcoded API keys exist in git history.
- **Docker Compose Pinning:** All 29 images use explicit semantic tags (no `:latest`).
- **AGPL-3.0 Quarantine:** Lago (`getlago/api:v1.16.0`) is isolated on `agpl_quarantine_net`. Codebase AST scan confirms zero `import lago` statements exist.
- **Non-OSI Service Isolation:** Memgraph (BSL-1.1), FalkorDB (SSPL-v1), Nango (Elastic-2.0), Phoenix (Elastic-2.0), and Dragonfly (BSL-1.1) are quarantined behind Docker Compose profiles (`profiles: ["self-hosted-non-osi"]`). Default stack is 100% OSI-approved.
