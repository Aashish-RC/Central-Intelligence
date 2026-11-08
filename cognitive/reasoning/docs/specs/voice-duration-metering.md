Authored by a session that read the source. Implementation must be done by a fresh session that sees only this file.

# Voice-Duration Metering & Preflight Session Leases — Clean-Room Behavior Specification

### 1. Scope and Objective
The voice duration metering subsystem tracks real-time bidirectional audio streaming duration in voice sessions, coordinates preflight duration leases, and enforces maximum allowable conversational turn and session limits.

---

### 2. Inputs and Trigger Events
1. **Lease Allocation Request**:
   - Client or session orchestrator requests a preflight lease specifying account/session identifier, requested duration limit (in seconds or milliseconds), and maximum permissible silence timeout.
2. **Audio Streaming Events**:
   - Turn initialization timestamp marking client voice input start.
   - Speech detection boundary events (user speech started, user speech finished).
   - Audio output generation timestamps marking synthetic speech playback start and end.
   - Heartbeat or lease renewal requests during long-running continuous turns.
3. **Lease Release Request**:
   - Turn completion or session closure signal containing actual consumed audio duration.

---

### 3. Outputs and Actions
1. **Lease Grant**:
   - Generates an opaque lease identifier, the approved maximum duration window, and a deadline timestamp after which the lease expires if not extended.
2. **Turn Metering Record**:
   - Computes cumulative speech duration across user input and assistant audio output, returning total billed seconds and remaining balance.
3. **Session Interruption / Termination**:
   - When cumulative turn duration reaches or exceeds the granted lease without renewal, the subsystem emits a quota exceeded termination signal to stop stream egress.

---

### 4. State Kept
- Ephemeral lease registry storing active records:
  - Lease identifier.
  - Associated session identifier and account identifier.
  - Maximum approved duration and grant timestamp.
  - Active status (granted, running, completed, or expired).
  - Cumulative audio millisecond counters per turn.
- Completed leases are removed or transitioned to an archived status for usage accounting.

---

### 5. Edge Cases
- **Abrupt Socket Disconnection**: If a client disconnects without sending an explicit turn-end event, the lease must terminate gracefully at the expiration deadline and calculate duration based on the last recorded frame.
- **Simultaneous Audio (Barge-In)**: When user speech overlaps with assistant speech playback, duration must meter both channels without double-counting clock time if policy mandates wall-clock metering, or accumulate both channels if channel-time metering is active.
- **Zero-Length Streams**: Connection opened and closed with no audio data transmitted must meter 0 seconds and immediately release any held reserve.
- **Stale Renewals**: Renewal attempts for an expired or terminated lease must be rejected.

---

### 6. Expiry Rules
- Leases automatically expire if no audio packets or heartbeat pings are received within a short sliding window (e.g., 30 seconds).
- Unused preflight allocations are returned to the account's available quota immediately upon lease release or expiry.

---

### 7. Error Behavior
- If an account has exhausted its voice budget, lease allocation fails with a capacity/quota rejection before any streaming connection is established.
- Audio chunks received against an invalid, expired, or non-existent lease trigger a session termination signal.
- System clock jumps or backwards adjustments must be handled monotonically to prevent negative durations.
