/**
 * Feature 45: Realtime Voice Turn Duration Metering & Preflight Session Leases
 * Meters live bidirectional audio stream duration and grants preflight turn leases.
 */

export interface VoiceLease {
  leaseId: string;
  sessionId: string;
  clientId: string;
  grantedDurationSeconds: number;
  consumedDurationSeconds: number;
  ratePerMinuteUsd: number;
  totalCostUsd: number;
  status: 'active' | 'exhausted' | 'released';
  createdAt: number;
  expiresAt: number;
}

export class RealtimeVoiceMeter {
  private leases: Map<string, VoiceLease> = new Map();
  private defaultAudioRatePerMin: number;

  constructor(defaultAudioRatePerMin: number = 0.06) {
    this.defaultAudioRatePerMin = defaultAudioRatePerMin;
  }

  grantLease(sessionId: string, clientId: string, durationSeconds: number = 60): VoiceLease {
    const leaseId = `lease_${Math.random().toString(36).substring(2, 10)}`;
    const now = Date.now();
    const lease: VoiceLease = {
      leaseId,
      sessionId,
      clientId,
      grantedDurationSeconds: durationSeconds,
      consumedDurationSeconds: 0,
      ratePerMinuteUsd: this.defaultAudioRatePerMin,
      totalCostUsd: 0,
      status: 'active',
      createdAt: now,
      expiresAt: now + durationSeconds * 1000,
    };
    this.leases.set(leaseId, lease);
    return lease;
  }

  recordAudioChunk(leaseId: string, durationMs: number): { allowed: boolean; remainingSeconds: number; totalCost: number } {
    const lease = this.leases.get(leaseId);
    if (!lease || lease.status !== 'active') {
      return { allowed: false, remainingSeconds: 0, totalCost: lease?.totalCostUsd || 0 };
    }

    const chunkSeconds = durationMs / 1000;
    lease.consumedDurationSeconds += chunkSeconds;
    lease.totalCostUsd = (lease.consumedDurationSeconds / 60) * lease.ratePerMinuteUsd;

    const remaining = lease.grantedDurationSeconds - lease.consumedDurationSeconds;
    if (remaining <= 0) {
      lease.status = 'exhausted';
      return { allowed: false, remainingSeconds: 0, totalCost: lease.totalCostUsd };
    }

    return { allowed: true, remainingSeconds: remaining, totalCost: lease.totalCostUsd };
  }

  releaseLease(leaseId: string): VoiceLease | null {
    const lease = this.leases.get(leaseId);
    if (!lease) return null;
    lease.status = 'released';
    return lease;
  }

  getLease(leaseId: string): VoiceLease | undefined {
    return this.leases.get(leaseId);
  }
}
