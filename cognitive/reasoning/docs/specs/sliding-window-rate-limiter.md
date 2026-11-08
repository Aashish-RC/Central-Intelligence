Authored by a session that read the source or the old code. Implementation must be done by a fresh session that sees only this file.

Purpose: limit requests per key (actor, tenant, or model; chosen by config) to N per window of W milliseconds, using a true sliding window (not fixed buckets).
Check-and-record is one atomic step: if allowed, the request is recorded in the same call.
Result: allowed (bool), remaining, limit, resetAfterMs, retryAfterMs (when denied).
Denied requests are not recorded, so they do not extend the window.
Caller maps denial to HTTP 429 with the standard error envelope and a Retry-After header in whole seconds (rounded up).
Config: default limit and window; per-key-class overrides; limit 0 means block all; missing config means unlimited.
Memory: entries older than the window are purged on access; total tracked keys capped (config); when capped, idle keys are evicted first.
Time comes from an injectable clock.
Edge cases to test: exactly N allowed then N+1 denied; request allowed again right after the oldest one leaves the window; denied requests do not consume quota; two keys are independent; concurrent calls in the same tick do not exceed N; clock jump backwards does not grant extra quota.
