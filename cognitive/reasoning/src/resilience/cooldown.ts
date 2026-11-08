import type { EndpointHealth } from '../types/resilience.js';

export class CooldownTracker {
  private healthMap: Map<string, EndpointHealth> = new Map();
  private readonly baseCooldownSec = 5;
  private readonly maxCooldownSec = 120;

  public getOrCreate(endpointId: string): EndpointHealth {
    let health = this.healthMap.get(endpointId);
    if (!health) {
      health = {
        endpointId,
        consecutiveFailures: 0,
        isInCooldown: false,
        cooldownUntil: 0,
        lastSuccess: 0,
        lastFailure: 0,
        inFlightRequests: 0,
        movingAverageLatencyMs: 0,
      };
      this.healthMap.set(endpointId, health);
    }
    return health;
  }

  public getHealth(endpointId: string): EndpointHealth {
    return this.getOrCreate(endpointId);
  }

  public getInFlight(endpointId: string): number {
    return this.getOrCreate(endpointId).inFlightRequests;
  }

  public isAvailable(endpointId: string): boolean {
    const health = this.getOrCreate(endpointId);
    if (!health.isInCooldown) return true;
    if (Date.now() >= health.cooldownUntil) {
      // Cooldown expired; allow a canary probe request
      health.isInCooldown = false;
      return true;
    }
    return false;
  }

  public recordSuccess(endpointId: string, latencyMs: number): void {
    const health = this.getOrCreate(endpointId);
    health.consecutiveFailures = 0;
    health.isInCooldown = false;
    health.cooldownUntil = 0;
    health.lastSuccess = Date.now();
    // Exponential moving average for latency (alpha = 0.2)
    if (health.movingAverageLatencyMs === 0) {
      health.movingAverageLatencyMs = latencyMs;
    } else {
      health.movingAverageLatencyMs = Math.round(
        0.2 * latencyMs + 0.8 * health.movingAverageLatencyMs,
      );
    }
  }

  public recordFailure(endpointId: string, explicitCooldownSec?: number): void {
    const health = this.getOrCreate(endpointId);
    health.consecutiveFailures += 1;
    health.lastFailure = Date.now();
    health.isInCooldown = true;

    const cooldownDuration =
      explicitCooldownSec && explicitCooldownSec > 0
        ? explicitCooldownSec
        : Math.min(
            this.baseCooldownSec * Math.pow(2, health.consecutiveFailures - 1),
            this.maxCooldownSec,
          );

    health.cooldownUntil = Date.now() + cooldownDuration * 1000;
  }

  public incrementInFlight(endpointId: string): void {
    const health = this.getOrCreate(endpointId);
    health.inFlightRequests += 1;
  }

  public decrementInFlight(endpointId: string): void {
    const health = this.getOrCreate(endpointId);
    health.inFlightRequests = Math.max(0, health.inFlightRequests - 1);
  }
}
