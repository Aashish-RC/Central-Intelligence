import crypto from 'node:crypto';
import type { CooldownTracker } from '../resilience/cooldown.js';

export interface SessionBinding {
  sessionId: string;
  targetEndpoint: string;
  createdAt: number;
  lastActiveAt: number;
  expiresAt: number;
}

export interface SessionAffinityOptions {
  ttlSeconds?: number;
}

export class SessionAffinityManager {
  private static instance: SessionAffinityManager;
  private sessions: Map<string, SessionBinding> = new Map();
  private ttlSeconds: number;

  constructor(options: SessionAffinityOptions = {}) {
    this.ttlSeconds = options.ttlSeconds ?? 1800; // 30 minutes
  }

  public static getInstance(): SessionAffinityManager {
    if (!SessionAffinityManager.instance) {
      SessionAffinityManager.instance = new SessionAffinityManager();
    }
    return SessionAffinityManager.instance;
  }

  /**
   * Resolves the target endpoint for a given session.
   * If the session has an active binding and the target is healthy, returns it.
   * Otherwise, chooses a healthy candidate deterministically using consistent hashing,
   * binds the session to it, and returns it.
   */
  public resolveTarget(
    sessionId: string,
    candidates: string[],
    cooldownTracker?: CooldownTracker,
  ): string | undefined {
    if (candidates.length === 0) return undefined;

    const now = Date.now();
    const existing = this.sessions.get(sessionId);

    // If active binding exists and target is in candidates
    if (existing && existing.expiresAt > now && candidates.includes(existing.targetEndpoint)) {
      // Check if target is healthy/available
      const isHealthy = !cooldownTracker || cooldownTracker.isAvailable(existing.targetEndpoint);
      if (isHealthy) {
        existing.lastActiveAt = now;
        existing.expiresAt = now + this.ttlSeconds * 1000;
        return existing.targetEndpoint;
      }
    }

    // Filter healthy candidates
    const healthyCandidates = candidates.filter(
      (c) => !cooldownTracker || cooldownTracker.isAvailable(c),
    );
    const pool = healthyCandidates.length > 0 ? healthyCandidates : candidates;

    // Deterministic consistent hash assignment
    const hash = crypto.createHash('sha256').update(sessionId).digest('hex');
    const index = Number.parseInt(hash.slice(0, 8), 16) % pool.length;
    const selected = pool[index];

    this.sessions.set(sessionId, {
      sessionId,
      targetEndpoint: selected,
      createdAt: now,
      lastActiveAt: now,
      expiresAt: now + this.ttlSeconds * 1000,
    });

    return selected;
  }

  public getBinding(sessionId: string): SessionBinding | undefined {
    const binding = this.sessions.get(sessionId);
    if (!binding) return undefined;
    if (Date.now() > binding.expiresAt) {
      this.sessions.delete(sessionId);
      return undefined;
    }
    return binding;
  }

  public clear(): void {
    this.sessions.clear();
  }
}
