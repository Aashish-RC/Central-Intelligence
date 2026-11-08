Authored by a session that read the source. Implementation must be done by a fresh session that sees only this file.

# GeoIP & Abuse IP Blocking — Clean-Room Behavior Specification

### 1. Scope and Objective
The GeoIP and abuse IP filtering subsystem inspects incoming HTTP requests at the gateway perimeter to enforce geographical residency constraints and block malicious or abusive client IP addresses before requests reach internal routing, inference, or security pipelines.

---

### 2. Inputs and Evaluation Criteria
1. **Client IP Identification**:
   - The engine receives the client network address (IPv4 or IPv6) either directly from the network socket or from trusted edge reverse-proxy forwarding headers.
2. **Geographical Data**:
   - Optional ISO 3166-1 alpha-2 two-letter country code associated with the client address (e.g. from an edge header or an IP geolocation dataset).
3. **Filtering Policy Configuration**:
   - An allowed list or denied list of two-letter ISO country codes.
   - An explicit list of blocked individual IP addresses (IPv4 and IPv6).
   - An explicit list of blocked subnet CIDR network prefixes (e.g., IPv4 /24 subnets or IPv6 /64 subnets).

---

### 3. Outputs and Actions
1. **Admit**:
   - If the client IP is not in any blocked address or CIDR list, and the country code is not blocked (or is in the allowlist if an allowlist is active), the request is admitted to proceed down the gateway middleware pipeline.
2. **Deny**:
   - If the client matches any blocked criteria, the request is immediately rejected with HTTP status code 403 (Forbidden) and a standard JSON error response explaining that access from the client network or location is restricted.

---

### 4. State Kept
- Static or dynamically updated in-memory lookup structures:
  - Exact set of blacklisted individual IP strings.
  - Parsed list of CIDR subnets representing network addresses and bitmask lengths.
  - Normalized uppercase set of country codes for allow/deny lists.
- No mutable per-request state or persistent transaction logs are required within the filter itself.

---

### 5. Edge Cases
- **Loopback and Private Networks**: Localhost and standard private network ranges (RFC 1918, RFC 4193) should be permitted unless specifically restricted in configuration.
- **IPv4-Mapped IPv6 Addresses**: Addresses formatted in IPv4-mapped IPv6 syntax must be normalized to their standard IPv4 representation before evaluation against IPv4 rules.
- **CIDR Boundary Matching**: Correct bitwise evaluation of first and last addresses within a CIDR block.
- **Country Code Case-Insensitivity**: Case variations in incoming country headers must be normalized.
- **Missing Country Header**: If geographical blocking is configured but the country cannot be determined, policy must define whether to allow or deny (default: admit IP, block only on explicit match).

---

### 6. Expiry and Invalidation Rules
- Statically loaded configuration persists until server configuration reload.
- If temporary dynamic IP bans are supported, entries expire after a specified time-to-live duration and are removed from the active blocklist upon lookup or via background purge.

---

### 7. Error Behavior
- Malformed IP strings fail closed in strict mode (treated as unauthorized) or are ignored if the header is unverifiable.
- Under all block conditions, the subsystem returns a clean HTTP 403 response without leaking gateway architecture, operating system, or backend provider information.
