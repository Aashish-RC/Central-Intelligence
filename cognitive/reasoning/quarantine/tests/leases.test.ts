import { describe, it, expect } from 'vitest';
import { RealtimeVoiceMeter } from '../leases.js';

describe('Feature 45: Realtime Voice Turn Duration Metering & Preflight Session Leases', () => {
  it('grants a preflight duration lease for realtime voice sessions', () => {
    const meter = new RealtimeVoiceMeter(0.06);
    const lease = meter.grantLease('sess_123', 'client_abc', 30);

    expect(lease.leaseId).toMatch(/^lease_/);
    expect(lease.grantedDurationSeconds).toBe(30);
    expect(lease.consumedDurationSeconds).toBe(0);
    expect(lease.status).toBe('active');
  });

  it('meters audio turn chunks and tracks remaining lease duration', () => {
    const meter = new RealtimeVoiceMeter(0.06);
    const lease = meter.grantLease('sess_456', 'client_xyz', 10);

    // Record 4 seconds of audio (4000ms)
    const update1 = meter.recordAudioChunk(lease.leaseId, 4000);
    expect(update1.allowed).toBe(true);
    expect(update1.remainingSeconds).toBeCloseTo(6, 1);
    expect(update1.totalCost).toBeGreaterThan(0);

    // Record 7 more seconds (exceeding 10s granted)
    const update2 = meter.recordAudioChunk(lease.leaseId, 7000);
    expect(update2.allowed).toBe(false);
    expect(meter.getLease(lease.leaseId)?.status).toBe('exhausted');
  });

  it('allows explicit session release', () => {
    const meter = new RealtimeVoiceMeter();
    const lease = meter.grantLease('sess_789', 'client_1', 60);
    meter.releaseLease(lease.leaseId);
    expect(meter.getLease(lease.leaseId)?.status).toBe('released');
  });
});
