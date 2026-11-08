Authored by a session that read the source or the old code. Implementation must be done by a fresh session that sees only this file.

Purpose: return a stored response for an identical request, never for a different one.
Default: disabled. Enabled per gateway config; per-request bypass with header "Cache-Control: no-cache".
Key: SHA-256 (hex) of canonical JSON (object keys sorted recursively, arrays kept in order, undefined omitted) of EVERY field that can change the output: model, messages, temperature, top_p, max tokens, stop, seed, n, presence/frequency penalties, logit_bias, tools, tool_choice, response_format, plus any provider-specific pass-through fields. Plus a scope: tenant id and actor id. Two requests differing in any of those never share a key. Different tenants never share a key.
Store only: non-streaming, successful (HTTP 200) responses. Never errors, never streams, never responses flagged by guardrails.
Entry: response body, status, created time, TTL (config, default 5 minutes).
Limits: max entries (config); when full, evict the least recently used.
Hit: return the stored body, header "x-cache: HIT", and emit an audit record with outcome "success" and cached=true (cost 0, tokens from the stored response marked as served-from-cache). Miss: header "x-cache: MISS".
Expiry: expired entries are never returned and are purged lazily on access.
Time comes from an injectable clock for tests.
Edge cases to test: the strings "Aa" and "BB" as message content give different keys; changing stop, seed, tool_choice or response_format changes the key; cross-tenant isolation; TTL expiry; LRU eviction; bypass header; streaming request never cached.
