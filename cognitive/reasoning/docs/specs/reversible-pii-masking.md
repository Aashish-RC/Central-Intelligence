Authored by a session that read the source. Implementation must be done by a fresh session that sees only this file.

# Reversible PII Masking — Clean-Room Behavior Specification

### 1. Scope and Objective
The reversible privacy and sensitive data masking subsystem intercepts completion requests, identifies sensitive personal data (including email addresses, telephone numbers, and government identification numbers), substitutes each sensitive entity with an opaque surrogate token placeholder prior to sending payloads upstream, and transparently restores the original values within downstream model responses—both for complete single responses and incrementally across streaming chunk fragments.

---

### 2. Inputs and Transformation
1. **Inbound Request Content**:
   - The engine evaluates text message contents in incoming requests.
2. **Entity Detection**:
   - Matches substrings against defined sensitive patterns (e.g. Email addresses, Phone numbers, Social Security Numbers, Credit Card numbers, IP addresses, Physical street addresses).
   - Non-overlapping entity spans are resolved deterministically (longest match takes precedence).
3. **Vault Storage & Surrogate Generation**:
   - For each detected sensitive entity, the vault generates an opaque surrogate token (e.g., bracketed alphanumeric label).
   - Token placeholder format: `[TOKEN_<TYPE>_<HEX>]` (e.g., `[TOKEN_EMAIL_1a2b3c4d5e6f]`).
   - The token format must not collide with standard markdown syntax or natural language words.
   - The association between surrogate token and original value, entity category, creation time, and expiration time is stored in an ephemeral, memory-bounded registry.
4. **Upstream Substitution**:
   - Sensitive text within the payload is replaced with its surrogate token before reaching upstream model providers.

---

### 3. Downstream Restoration
1. **Complete Response Restoration**:
   - For non-streaming responses, occurrences of active surrogate tokens in assistant message text are replaced with original values.
2. **Streaming Incremental Restoration**:
   - Across server-sent streaming chunks, surrogate tokens may be split across chunk boundaries.
   - The streaming processor maintains a residual buffer:
     - When a chunk ends with a partial surrogate token prefix, the fragment is held until the terminating token boundary is reached or confirmed not to be a surrogate.
     - As soon as a complete surrogate token is recognized, it is immediately converted back to its original value.
     - Regular text without surrogate prefixes is emitted without delay to minimize latency.

---

### 4. State Kept
- Ephemeral in-memory lookup vault:
  - Mapping from surrogate token to original entity and metadata.
  - Reverse mapping to avoid creating redundant surrogates for identical values within the same session.
- Bounded capacity with least-recently-used eviction policy.

---

### 5. Edge Cases
- **Boundary Splitting Across Multiple Chunks**: A surrogate token split into two or three small byte fragments in stream transport.
- **Tokens in Unprompted Model Output**: If the model hallucinated or repeated an unrecognized token structure, it is passed through unmodified.
- **Nested or Adjacent Entities**: Handling contiguous entities separated by punctuation or spaces without corrupting surrounding text.
- **Punctuation Contiguity**: Ensuring trailing punctuation (commas, periods) is not erroneously captured inside entity values.

---

### 6. Expiry Rules
- Surrogate token mappings expire after an explicit time-to-live (e.g., 3600 seconds).
- Expired tokens are purged periodically or during lookup. Unrecognized or expired tokens encountered during response restoration remain unchanged.

---

### 7. Error Behavior
- Under memory pressure, oldest mappings are safely evicted.
- Restoration of an expired token fails safe (leaves the token in place rather than crashing or throwing unhandled errors).
- Plaintext values and token mappings are never logged to public logs or exported in unencrypted audit events.
