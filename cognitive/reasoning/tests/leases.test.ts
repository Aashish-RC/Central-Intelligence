import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { VoiceLeaseConfig, VoiceLeaseManager } from '../src/realtime/leases.js';
import type { AuditRecord } from '../src/types/ra1.js';

describe('Voice-Duration Metering & Preflight Session Leases', () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    delete process.env.FEATURE_VOICE_LEASES;
  });

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it('Rule V16: Feature flag OFF by default rejects or disables lease management', () => {
    const manager = new VoiceLeaseManager();
    const result = manager.allocateLease({
      accountId: 'acc-1',
      sessionId: 'sess-1',
      requestedDurationSeconds: 60,
    });
    expect(result.granted).toBe(false);
    expect(result.error).toContain('disabled');
  });

  describe('When FEATURE_VOICE_LEASES is enabled', () => {
    beforeEach(() => {
      process.env.FEATURE_VOICE_LEASES = 'true';
    });

    it('Rule V1 & V2: Lease allocation request generates opaque lease ID, approved duration window and deadline', () => {
      const manager = new VoiceLeaseManager();
      manager.setAccountQuota('acc-1', 300); // 300 seconds available

      const grant = manager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-1',
        requestedDurationSeconds: 60,
        silenceTimeoutSeconds: 30,
      });

      expect(grant.granted).toBe(true);
      expect(grant.leaseId).toBeDefined();
      expect(grant.leaseId?.startsWith('lease-')).toBe(true);
      expect(grant.approvedDurationSeconds).toBe(60);
      expect(grant.deadlineTimestamp).toBeGreaterThan(Date.now());
      expect(manager.getLease(grant.leaseId!)?.status).toBe('running');
    });

    it('Rule V3 & V4: Tracks audio streaming events and computes cumulative billed seconds and remaining balance', () => {
      const manager = new VoiceLeaseManager();
      manager.setAccountQuota('acc-1', 120);

      const grant = manager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-1',
        requestedDurationSeconds: 60,
      });
      const leaseId = grant.leaseId!;

      // User speaks for 5 seconds (5000ms)
      manager.recordEvent({
        leaseId,
        type: 'user_speech_start',
        timestamp: 1000,
      });
      manager.recordEvent({
        leaseId,
        type: 'user_speech_end',
        timestamp: 6000,
      });

      // Assistant responds for 10 seconds (10000ms)
      manager.recordEvent({
        leaseId,
        type: 'assistant_speech_start',
        timestamp: 6500,
      });
      manager.recordEvent({
        leaseId,
        type: 'assistant_speech_end',
        timestamp: 16500,
      });

      const metrics = manager.getTurnMetrics(leaseId);
      expect(metrics.totalBilledSeconds).toBe(15); // 5s user + 10s assistant
      expect(metrics.remainingApprovedSeconds).toBe(45); // 60s approved - 15s billed
    });

    it('Rule V5: Emits session interruption / termination when turn duration reaches or exceeds granted lease', () => {
      const manager = new VoiceLeaseManager();
      manager.setAccountQuota('acc-1', 100);

      const grant = manager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-1',
        requestedDurationSeconds: 10, // only 10s lease
      });
      const leaseId = grant.leaseId!;

      // User speaks for 12 seconds
      manager.recordEvent({ leaseId, type: 'user_speech_start', timestamp: 0 });
      const recordResult = manager.recordEvent({
        leaseId,
        type: 'user_speech_end',
        timestamp: 12000,
      });

      expect(recordResult.shouldTerminate).toBe(true);
      expect(recordResult.terminationReason).toBe('quota_exceeded');
      expect(manager.getLease(leaseId)?.status).toBe('terminated');
    });

    it('Rule V6: Heartbeat or lease renewal extends deadline and duration during long-running turns', () => {
      const manager = new VoiceLeaseManager();
      manager.setAccountQuota('acc-1', 200);

      const grant = manager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-1',
        requestedDurationSeconds: 30,
      });
      const leaseId = grant.leaseId!;
      const originalDeadline = grant.deadlineTimestamp;

      // Renew with additional 30 seconds
      const renewal = manager.renewLease({
        leaseId,
        additionalDurationSeconds: 30,
      });

      expect(renewal.success).toBe(true);
      expect(renewal.newApprovedDurationSeconds).toBe(60);
      expect(renewal.newDeadlineTimestamp).toBeGreaterThanOrEqual(originalDeadline!);
    });

    it('Rule V7: Lease release immediately returns unused preflight allocation to account quota', () => {
      const manager = new VoiceLeaseManager();
      manager.setAccountQuota('acc-1', 100);

      const grant = manager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-1',
        requestedDurationSeconds: 40,
      });
      const leaseId = grant.leaseId!;

      // Preflight holds 40 seconds; available is 60s
      expect(manager.getAccountAvailableQuota('acc-1')).toBe(60);

      // Only consumed 10 seconds of speech
      manager.recordEvent({ leaseId, type: 'user_speech_start', timestamp: 0 });
      manager.recordEvent({ leaseId, type: 'user_speech_end', timestamp: 10000 });

      const releaseResult = manager.releaseLease(leaseId);
      expect(releaseResult.consumedSeconds).toBe(10);
      expect(releaseResult.refundedSeconds).toBe(30);

      // Account available quota is now 90 (100 - 10 consumed)
      expect(manager.getAccountAvailableQuota('acc-1')).toBe(90);
      expect(manager.getLease(leaseId)?.status).toBe('completed');
    });

    it('Rule V8: Abrupt socket disconnection calculates duration based on last recorded frame', () => {
      const manager = new VoiceLeaseManager();
      manager.setAccountQuota('acc-1', 100);

      const grant = manager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-1',
        requestedDurationSeconds: 50,
      });
      const leaseId = grant.leaseId!;

      manager.recordEvent({ leaseId, type: 'user_speech_start', timestamp: 0 });
      manager.recordAudioChunk({ leaseId, channel: 'user', chunkTimestamp: 7500 });
      // Socket abruptly disconnects without explicit speech_end
      const disconnectResult = manager.handleSocketDisconnect(leaseId);

      expect(disconnectResult.calculatedDurationSeconds).toBe(7.5);
      expect(manager.getAccountAvailableQuota('acc-1')).toBe(92.5);
      expect(manager.getLease(leaseId)?.status).toBe('completed');
    });

    it('Rule V9: Simultaneous Audio (Barge-In) handles wall-clock and channel-time metering policies', () => {
      // Wall-clock policy: overlapping speech intervals should not be double-counted
      const wallClockManager = new VoiceLeaseManager({ meteringPolicy: 'wall-clock' });
      wallClockManager.setAccountQuota('acc-1', 100);
      const grant1 = wallClockManager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-1',
        requestedDurationSeconds: 60,
      });
      const l1 = grant1.leaseId!;

      // Assistant starts at t=0 and speaks until t=10000 (10s)
      wallClockManager.recordEvent({ leaseId: l1, type: 'assistant_speech_start', timestamp: 0 });
      // User barges in at t=5000 and speaks until t=12000 (7s)
      wallClockManager.recordEvent({ leaseId: l1, type: 'user_speech_start', timestamp: 5000 });
      wallClockManager.recordEvent({ leaseId: l1, type: 'assistant_speech_end', timestamp: 10000 });
      wallClockManager.recordEvent({ leaseId: l1, type: 'user_speech_end', timestamp: 12000 });

      // Total union interval: [0, 12000] -> exactly 12 seconds
      expect(wallClockManager.getTurnMetrics(l1).totalBilledSeconds).toBe(12);

      // Channel-time policy: accumulates both channels
      const channelTimeManager = new VoiceLeaseManager({ meteringPolicy: 'channel-time' });
      channelTimeManager.setAccountQuota('acc-2', 100);
      const grant2 = channelTimeManager.allocateLease({
        accountId: 'acc-2',
        sessionId: 'sess-2',
        requestedDurationSeconds: 60,
      });
      const l2 = grant2.leaseId!;

      channelTimeManager.recordEvent({ leaseId: l2, type: 'assistant_speech_start', timestamp: 0 });
      channelTimeManager.recordEvent({ leaseId: l2, type: 'user_speech_start', timestamp: 5000 });
      channelTimeManager.recordEvent({
        leaseId: l2,
        type: 'assistant_speech_end',
        timestamp: 10000,
      });
      channelTimeManager.recordEvent({ leaseId: l2, type: 'user_speech_end', timestamp: 12000 });

      // Total channel time: 10s assistant + 7s user = 17 seconds
      expect(channelTimeManager.getTurnMetrics(l2).totalBilledSeconds).toBe(17);
    });

    it('Rule V10: Zero-length streams meter 0 seconds and immediately release held reserve', () => {
      const manager = new VoiceLeaseManager();
      manager.setAccountQuota('acc-1', 50);

      const grant = manager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-1',
        requestedDurationSeconds: 30,
      });
      expect(manager.getAccountAvailableQuota('acc-1')).toBe(20);

      // Connection closes without any audio events
      const release = manager.releaseLease(grant.leaseId!);
      expect(release.consumedSeconds).toBe(0);
      expect(release.refundedSeconds).toBe(30);
      expect(manager.getAccountAvailableQuota('acc-1')).toBe(50);
    });

    it('Rule V11: Stale renewals for expired or terminated leases are rejected', () => {
      const manager = new VoiceLeaseManager();
      manager.setAccountQuota('acc-1', 100);

      const grant = manager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-1',
        requestedDurationSeconds: 20,
      });
      const leaseId = grant.leaseId!;
      manager.releaseLease(leaseId); // terminates/completes

      const staleRenewal = manager.renewLease({
        leaseId,
        additionalDurationSeconds: 10,
      });
      expect(staleRenewal.success).toBe(false);
      expect(staleRenewal.error).toContain('not running');
    });

    it('Rule V12: Auto-expires if no audio packets or heartbeat received within silence timeout window', () => {
      const manager = new VoiceLeaseManager();
      manager.setAccountQuota('acc-1', 100);

      const grant = manager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-1',
        requestedDurationSeconds: 60,
        silenceTimeoutSeconds: 5, // 5 seconds silence timeout
      });
      const leaseId = grant.leaseId!;

      // Check after 6 seconds of silence
      const expired = manager.checkInactivityExpiry(leaseId, Date.now() + 6000);
      expect(expired).toBe(true);
      expect(manager.getLease(leaseId)?.status).toBe('expired');
      // Quota is returned to account
      expect(manager.getAccountAvailableQuota('acc-1')).toBe(100);
    });

    it('Rule V13: Quota exhaustion rejects lease allocation before streaming connection established', () => {
      const manager = new VoiceLeaseManager();
      manager.setAccountQuota('acc-1', 10); // only 10s left

      const grant = manager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-1',
        requestedDurationSeconds: 30, // requests 30s
      });

      expect(grant.granted).toBe(false);
      expect(grant.statusCode).toBe(429);
      expect(grant.error).toContain('budget');
    });

    it('Rule V14: Audio chunks against invalid, expired or non-existent lease trigger session termination', () => {
      const manager = new VoiceLeaseManager();
      const res = manager.recordAudioChunk({
        leaseId: 'non-existent-lease',
        channel: 'user',
        chunkTimestamp: Date.now(),
      });

      expect(res.shouldTerminate).toBe(true);
      expect(res.terminationReason).toBe('invalid_lease');
    });

    it('Rule V15: System clock jumps or backwards adjustments are handled monotonically', () => {
      const manager = new VoiceLeaseManager();
      manager.setAccountQuota('acc-1', 100);

      const grant = manager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-1',
        requestedDurationSeconds: 60,
      });
      const leaseId = grant.leaseId!;

      // First event at t=10000
      manager.recordEvent({ leaseId, type: 'user_speech_start', timestamp: 10000 });
      // Clock jumps backwards to t=8000
      manager.recordEvent({ leaseId, type: 'user_speech_end', timestamp: 8000 });

      // Monotonic guard ensures duration is never negative
      const metrics = manager.getTurnMetrics(leaseId);
      expect(metrics.totalBilledSeconds).toBe(0);
    });

    it('Rule V17: Emits usage records compatible with H4 audit hook without billing logic leaks', async () => {
      const manager = new VoiceLeaseManager();
      manager.setAccountQuota('acc-1', 100);

      const grant = manager.allocateLease({
        accountId: 'acc-1',
        sessionId: 'sess-voice-99',
        requestedDurationSeconds: 30,
      });
      const leaseId = grant.leaseId!;

      manager.recordEvent({ leaseId, type: 'assistant_speech_start', timestamp: 0 });
      manager.recordEvent({ leaseId, type: 'assistant_speech_end', timestamp: 8000 });

      const auditRecords: AuditRecord[] = [];
      const dummyAuditHook = async (rec: AuditRecord) => {
        auditRecords.push(rec);
      };

      await manager.emitH4AuditRecord(leaseId, {
        auditHook: dummyAuditHook,
        model: 'openai/gpt-4o-realtime-preview',
        provider: 'openai',
      });

      expect(auditRecords.length).toBe(1);
      const record = auditRecords[0];
      expect(record.model).toBe('openai/gpt-4o-realtime-preview');
      expect(record.provider).toBe('openai');
      expect(record.outcome).toBe('success');
      expect(record.metadata?.voiceDurationSeconds).toBe(8);
      expect(record.metadata?.leaseId).toBe(leaseId);
      expect(record.tokens.totalTokens).toBe(8); // standardized duration units
    });
  });
});
