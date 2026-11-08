import type { AuditHook, AuditRecord } from '../types/ra1.js';

export type MeteringPolicy = 'wall-clock' | 'channel-time';

export interface VoiceLeaseConfig {
  meteringPolicy?: MeteringPolicy;
  defaultSilenceTimeoutSeconds?: number;
}

export type LeaseStatus = 'granted' | 'running' | 'completed' | 'expired' | 'terminated';

export interface VoiceLeaseRecord {
  leaseId: string;
  accountId: string;
  sessionId: string;
  approvedDurationSeconds: number;
  grantTimestamp: number;
  deadlineTimestamp: number;
  silenceTimeoutSeconds: number;
  lastActivityTimestamp: number;
  status: LeaseStatus;
  // Interval tracking
  userIntervals: Array<{ start: number; end?: number }>;
  assistantIntervals: Array<{ start: number; end?: number }>;
  lastRecordedTimestamp: number;
}

export interface LeaseAllocationRequest {
  accountId: string;
  sessionId: string;
  requestedDurationSeconds: number;
  silenceTimeoutSeconds?: number;
}

export interface LeaseGrantResult {
  granted: boolean;
  leaseId?: string;
  approvedDurationSeconds?: number;
  deadlineTimestamp?: number;
  statusCode?: number;
  error?: string;
}

export interface VoiceEvent {
  leaseId: string;
  type:
    | 'user_speech_start'
    | 'user_speech_end'
    | 'assistant_speech_start'
    | 'assistant_speech_end'
    | 'heartbeat';
  timestamp?: number;
}

export interface AudioChunkRecord {
  leaseId: string;
  channel: 'user' | 'assistant';
  chunkTimestamp?: number;
}

export interface RecordEventResult {
  success: boolean;
  shouldTerminate?: boolean;
  terminationReason?: string;
  totalBilledSeconds?: number;
  remainingApprovedSeconds?: number;
  error?: string;
}

export interface LeaseRenewalRequest {
  leaseId: string;
  additionalDurationSeconds: number;
}

export interface LeaseRenewalResult {
  success: boolean;
  newApprovedDurationSeconds?: number;
  newDeadlineTimestamp?: number;
  error?: string;
}

export interface LeaseReleaseResult {
  leaseId: string;
  consumedSeconds: number;
  refundedSeconds: number;
  status: LeaseStatus;
}

export interface TurnMetrics {
  totalBilledSeconds: number;
  remainingApprovedSeconds: number;
  userSpeechSeconds: number;
  assistantSpeechSeconds: number;
}

/**
 * Voice Duration Metering & Preflight Session Leases Subsystem.
 * Tracks real-time bidirectional audio streaming duration and manages preflight duration leases.
 */
export class VoiceLeaseManager {
  private meteringPolicy: MeteringPolicy;
  private defaultSilenceTimeoutSeconds: number;
  private leases: Map<string, VoiceLeaseRecord> = new Map();
  // Account available quota registry (in seconds)
  private accountQuotas: Map<string, number> = new Map();

  constructor(config: VoiceLeaseConfig = {}) {
    this.meteringPolicy = config.meteringPolicy || 'wall-clock';
    this.defaultSilenceTimeoutSeconds = config.defaultSilenceTimeoutSeconds || 30;
  }

  public isEnabled(): boolean {
    return process.env.FEATURE_VOICE_LEASES === 'true';
  }

  public setAccountQuota(accountId: string, seconds: number): void {
    this.accountQuotas.set(accountId, Math.max(0, seconds));
  }

  public getAccountAvailableQuota(accountId: string): number {
    return this.accountQuotas.get(accountId) ?? 0;
  }

  public getLease(leaseId: string): VoiceLeaseRecord | undefined {
    return this.leases.get(leaseId);
  }

  public allocateLease(req: LeaseAllocationRequest): LeaseGrantResult {
    if (!this.isEnabled()) {
      return {
        granted: false,
        statusCode: 503,
        error: 'Voice duration metering feature is disabled (FEATURE_VOICE_LEASES is off)',
      };
    }

    const available = this.getAccountAvailableQuota(req.accountId);
    if (available < req.requestedDurationSeconds) {
      return {
        granted: false,
        statusCode: 429,
        error: `Insufficient voice budget: available ${available}s, requested ${req.requestedDurationSeconds}s`,
      };
    }

    // Deduct preflight reservation from available quota
    this.accountQuotas.set(req.accountId, available - req.requestedDurationSeconds);

    const now = Date.now();
    const silenceTimeout = req.silenceTimeoutSeconds || this.defaultSilenceTimeoutSeconds;
    const leaseId = `lease-${now}-${Math.random().toString(36).substring(2, 9)}`;
    const deadlineTimestamp = now + req.requestedDurationSeconds * 1000 + silenceTimeout * 1000;

    const leaseRecord: VoiceLeaseRecord = {
      leaseId,
      accountId: req.accountId,
      sessionId: req.sessionId,
      approvedDurationSeconds: req.requestedDurationSeconds,
      grantTimestamp: now,
      deadlineTimestamp,
      silenceTimeoutSeconds: silenceTimeout,
      lastActivityTimestamp: now,
      status: 'running',
      userIntervals: [],
      assistantIntervals: [],
      lastRecordedTimestamp: 0,
    };

    this.leases.set(leaseId, leaseRecord);

    return {
      granted: true,
      leaseId,
      approvedDurationSeconds: req.requestedDurationSeconds,
      deadlineTimestamp,
      statusCode: 200,
    };
  }

  public recordEvent(event: VoiceEvent): RecordEventResult {
    const lease = this.leases.get(event.leaseId);
    if (!lease || lease.status !== 'running') {
      return {
        success: false,
        shouldTerminate: true,
        terminationReason: 'invalid_lease',
        error: 'Lease is invalid, expired, or completed',
      };
    }

    const rawTimestamp = event.timestamp !== undefined ? event.timestamp : Date.now();
    // System clock jumps: handle monotonically
    const timestamp = Math.max(rawTimestamp, lease.lastRecordedTimestamp);
    lease.lastRecordedTimestamp = timestamp;
    lease.lastActivityTimestamp = Date.now();

    if (event.type === 'heartbeat') {
      return { success: true };
    }

    if (event.type === 'user_speech_start') {
      lease.userIntervals.push({ start: timestamp });
    } else if (event.type === 'user_speech_end') {
      const active = lease.userIntervals.find((i) => i.end === undefined);
      if (active) {
        active.end = Math.max(active.start, timestamp);
      } else {
        lease.userIntervals.push({ start: timestamp, end: timestamp });
      }
    } else if (event.type === 'assistant_speech_start') {
      lease.assistantIntervals.push({ start: timestamp });
    } else if (event.type === 'assistant_speech_end') {
      const active = lease.assistantIntervals.find((i) => i.end === undefined);
      if (active) {
        active.end = Math.max(active.start, timestamp);
      } else {
        lease.assistantIntervals.push({ start: timestamp, end: timestamp });
      }
    }

    const metrics = this.computeMetrics(lease);
    if (metrics.totalBilledSeconds >= lease.approvedDurationSeconds) {
      lease.status = 'terminated';
      return {
        success: true,
        shouldTerminate: true,
        terminationReason: 'quota_exceeded',
        totalBilledSeconds: metrics.totalBilledSeconds,
        remainingApprovedSeconds: 0,
      };
    }

    return {
      success: true,
      shouldTerminate: false,
      totalBilledSeconds: metrics.totalBilledSeconds,
      remainingApprovedSeconds: metrics.remainingApprovedSeconds,
    };
  }

  public recordAudioChunk(record: AudioChunkRecord): RecordEventResult {
    const lease = this.leases.get(record.leaseId);
    if (!lease || lease.status !== 'running') {
      return {
        success: false,
        shouldTerminate: true,
        terminationReason: 'invalid_lease',
        error: 'Lease is not active',
      };
    }

    const timestamp = record.chunkTimestamp !== undefined ? record.chunkTimestamp : Date.now();
    lease.lastRecordedTimestamp = Math.max(timestamp, lease.lastRecordedTimestamp);
    lease.lastActivityTimestamp = Date.now();

    const targetIntervals =
      record.channel === 'user' ? lease.userIntervals : lease.assistantIntervals;
    const active = targetIntervals.find((i) => i.end === undefined);
    if (active) {
      active.end = Math.max(active.start, timestamp);
    } else {
      // Chunk without explicit start
      targetIntervals.push({ start: timestamp, end: timestamp });
    }

    const metrics = this.computeMetrics(lease);
    if (metrics.totalBilledSeconds >= lease.approvedDurationSeconds) {
      lease.status = 'terminated';
      return {
        success: true,
        shouldTerminate: true,
        terminationReason: 'quota_exceeded',
        totalBilledSeconds: metrics.totalBilledSeconds,
        remainingApprovedSeconds: 0,
      };
    }

    return {
      success: true,
      shouldTerminate: false,
      totalBilledSeconds: metrics.totalBilledSeconds,
      remainingApprovedSeconds: metrics.remainingApprovedSeconds,
    };
  }

  public renewLease(req: LeaseRenewalRequest): LeaseRenewalResult {
    const lease = this.leases.get(req.leaseId);
    if (!lease || lease.status !== 'running') {
      return {
        success: false,
        error: 'Cannot renew: lease not found or not running',
      };
    }

    const available = this.getAccountAvailableQuota(lease.accountId);
    if (available < req.additionalDurationSeconds) {
      return {
        success: false,
        error: `Insufficient quota to renew: requested ${req.additionalDurationSeconds}s, available ${available}s`,
      };
    }

    // Deduct additional duration from account
    this.accountQuotas.set(lease.accountId, available - req.additionalDurationSeconds);

    lease.approvedDurationSeconds += req.additionalDurationSeconds;
    lease.deadlineTimestamp += req.additionalDurationSeconds * 1000;
    lease.lastActivityTimestamp = Date.now();

    return {
      success: true,
      newApprovedDurationSeconds: lease.approvedDurationSeconds,
      newDeadlineTimestamp: lease.deadlineTimestamp,
    };
  }

  public releaseLease(leaseId: string): LeaseReleaseResult {
    const lease = this.leases.get(leaseId);
    if (!lease) {
      return { leaseId, consumedSeconds: 0, refundedSeconds: 0, status: 'completed' };
    }

    // Close any unclosed intervals with lastRecordedTimestamp
    this.closeOpenIntervals(lease);

    const metrics = this.computeMetrics(lease);
    const consumedSeconds = Math.min(metrics.totalBilledSeconds, lease.approvedDurationSeconds);
    const refundedSeconds = Math.max(0, lease.approvedDurationSeconds - consumedSeconds);

    // Return unused quota to account
    const currentQuota = this.getAccountAvailableQuota(lease.accountId);
    this.accountQuotas.set(lease.accountId, currentQuota + refundedSeconds);

    lease.status = 'completed';

    return {
      leaseId,
      consumedSeconds,
      refundedSeconds,
      status: 'completed',
    };
  }

  public handleSocketDisconnect(leaseId: string): { calculatedDurationSeconds: number } {
    const lease = this.leases.get(leaseId);
    if (!lease) {
      return { calculatedDurationSeconds: 0 };
    }

    // Close intervals with last recorded timestamp
    this.closeOpenIntervals(lease);

    const release = this.releaseLease(leaseId);
    return { calculatedDurationSeconds: release.consumedSeconds };
  }

  public checkInactivityExpiry(leaseId: string, currentTimestamp = Date.now()): boolean {
    const lease = this.leases.get(leaseId);
    if (!lease || lease.status !== 'running') return false;

    const silenceMs = lease.silenceTimeoutSeconds * 1000;
    if (currentTimestamp - lease.lastActivityTimestamp > silenceMs) {
      lease.status = 'expired';
      this.closeOpenIntervals(lease);
      const metrics = this.computeMetrics(lease);
      const consumed = Math.min(metrics.totalBilledSeconds, lease.approvedDurationSeconds);
      const refund = Math.max(0, lease.approvedDurationSeconds - consumed);

      const quota = this.getAccountAvailableQuota(lease.accountId);
      this.accountQuotas.set(lease.accountId, quota + refund);
      return true;
    }
    return false;
  }

  public getTurnMetrics(leaseId: string): TurnMetrics {
    const lease = this.leases.get(leaseId);
    if (!lease) {
      return {
        totalBilledSeconds: 0,
        remainingApprovedSeconds: 0,
        userSpeechSeconds: 0,
        assistantSpeechSeconds: 0,
      };
    }
    return this.computeMetrics(lease);
  }

  /**
   * Emits usage record to H4 Audit Hook.
   * Billing/metering events are decoupled and only emitted via H4.
   */
  public async emitH4AuditRecord(
    leaseId: string,
    options: {
      auditHook: AuditHook;
      model: string;
      provider: string;
    },
  ): Promise<void> {
    const lease = this.leases.get(leaseId);
    if (!lease) return;

    const metrics = this.computeMetrics(lease);
    const durationSeconds = metrics.totalBilledSeconds;

    const record: AuditRecord = {
      requestId: `req-voice-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
      traceId: `trace-${lease.sessionId}`,
      timestamp: new Date().toISOString(),
      actor: lease.accountId,
      model: options.model,
      provider: options.provider,
      targetId: 'voice-session',
      tokens: {
        promptTokens: 0,
        completionTokens: 0,
        reasoningTokens: 0,
        cachedPromptTokens: 0,
        totalTokens: durationSeconds,
        estimated: false,
      },
      cost: {
        currency: 'USD',
        promptCost: 0,
        completionCost: 0,
        reasoningCost: 0,
        cacheDiscount: 0,
        totalCost: 0,
      },
      latencyMs: durationSeconds * 1000,
      outcome: 'success',
      statusCode: 200,
      metadata: {
        leaseId,
        sessionId: lease.sessionId,
        voiceDurationSeconds: durationSeconds,
        userSpeechSeconds: metrics.userSpeechSeconds,
        assistantSpeechSeconds: metrics.assistantSpeechSeconds,
      },
    };

    await options.auditHook(record);
  }

  private closeOpenIntervals(lease: VoiceLeaseRecord): void {
    const last = lease.lastRecordedTimestamp;
    for (const i of lease.userIntervals) {
      if (i.end === undefined) i.end = Math.max(i.start, last);
    }
    for (const i of lease.assistantIntervals) {
      if (i.end === undefined) i.end = Math.max(i.start, last);
    }
  }

  private computeMetrics(lease: VoiceLeaseRecord): TurnMetrics {
    const userIntervals = lease.userIntervals.map((i) => ({
      start: i.start,
      end: i.end !== undefined ? i.end : Math.max(i.start, lease.lastRecordedTimestamp),
    }));

    const assistantIntervals = lease.assistantIntervals.map((i) => ({
      start: i.start,
      end: i.end !== undefined ? i.end : Math.max(i.start, lease.lastRecordedTimestamp),
    }));

    const userMs = userIntervals.reduce((acc, i) => acc + Math.max(0, i.end - i.start), 0);
    const assistantMs = assistantIntervals.reduce(
      (acc, i) => acc + Math.max(0, i.end - i.start),
      0,
    );

    let totalBilledMs = 0;

    if (this.meteringPolicy === 'channel-time') {
      totalBilledMs = userMs + assistantMs;
    } else {
      // Wall-clock policy: merge overlapping intervals across both channels
      const allIntervals = [...userIntervals, ...assistantIntervals].sort(
        (a, b) => a.start - b.start,
      );
      if (allIntervals.length > 0) {
        let currentStart = allIntervals[0].start;
        let currentEnd = allIntervals[0].end;

        for (let i = 1; i < allIntervals.length; i++) {
          const interval = allIntervals[i];
          if (interval.start <= currentEnd) {
            currentEnd = Math.max(currentEnd, interval.end);
          } else {
            totalBilledMs += Math.max(0, currentEnd - currentStart);
            currentStart = interval.start;
            currentEnd = interval.end;
          }
        }
        totalBilledMs += Math.max(0, currentEnd - currentStart);
      }
    }

    const totalBilledSeconds = totalBilledMs / 1000;
    const remainingApprovedSeconds = Math.max(
      0,
      lease.approvedDurationSeconds - totalBilledSeconds,
    );

    return {
      totalBilledSeconds,
      remainingApprovedSeconds,
      userSpeechSeconds: userMs / 1000,
      assistantSpeechSeconds: assistantMs / 1000,
    };
  }
}
