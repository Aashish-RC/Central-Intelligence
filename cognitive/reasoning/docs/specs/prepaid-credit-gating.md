Authored by a session that read the source. Implementation must be done by a fresh session that sees only this file.

# Prepaid Credit Gating & Automated Webhooks — Clean-Room Behavior Specification

### 1. Scope and Objective
The prepaid credit subsystem manages tenant account balances, enforces pre-request credit sufficiency checks, debits usage charges upon request completion, and dispatches automated webhook notifications for low-balance warnings and zero-balance exhaustion.

---

### 2. Inputs and Trigger Events
1. **Balance Provisioning (Top-Up)**:
   - Account identifier, credit addition amount, currency code (e.g., USD), and optional unique transaction reference for idempotency.
2. **Preflight Gating Check**:
   - Account identifier and anticipated minimum cost required to initiate a model inference request.
3. **Usage Settlement (Debit)**:
   - Account identifier, actual cost consumed (computed from input/output tokens, image counts, or audio seconds), model identifier, and request timestamp.
4. **Policy Configuration**:
   - Low-balance alert threshold, webhook destination URL, and retry policy parameters.

---

### 3. Outputs and Actions
1. **Preflight Decision**:
   - If available balance is greater than or equal to the required threshold, return permission to proceed.
   - If available balance is lower than required, reject the request with HTTP status code 402 (Payment Required) and a JSON error indicating insufficient balance.
2. **Balance Mutation**:
   - Updates the account ledger with the debit amount and returns current balance and transaction confirmation.
3. **Notification Webhooks**:
   - Dispatches an asynchronous HTTP webhook payload when the balance falls below the warning threshold.
   - Dispatches an asynchronous HTTP webhook payload when the balance reaches zero or becomes negative.

---

### 4. State Kept
- Account balance registry mapping account identifier to:
  - Current numerical balance.
  - Currency standard.
  - Configured low-balance threshold.
  - Cumulative credited amount and cumulative debited amount.
  - Timestamp of last mutation.

---

### 5. Edge Cases
- **Concurrent Inflight Requests**: Multiple requests executing simultaneously from the same account must not cause race conditions. Atomic balance updates or reserve locks must prevent balance underflows beyond permissible overdraft policies.
- **Micro-Cent Precision**: Currency calculations must maintain at least 6 decimal places of precision to avoid floating-point drift on fractional token costs.
- **Negative Balance Grace Handling**: If a long generation exceeds the initial estimate and dips the account balance below zero, the current response completes successfully, but the resulting negative balance strictly gates subsequent requests.
- **Idempotent Top-Ups**: Repeated delivery of identical transaction references must not apply duplicate credits.
- **Webhook Delivery Failures**: Remote endpoint downtime must trigger bounded exponential retries and must never block synchronous gateway inference pipelines.

---

### 6. Expiry Rules
- Accounts marked inactive for a designated dormancy period may have balance records archived.
- Promotional credit grants may specify an expiration date; when debited, credits nearing expiration should be consumed prior to non-expiring cash balances.

---

### 7. Error Behavior
- Requests for non-existent accounts fail closed with an unauthorized or account-not-found error.
- Invalid debit amounts (negative or non-finite numbers) are rejected with validation errors.
- Network errors during external webhook delivery are logged as telemetry alerts without interfering with gateway inference responses.
