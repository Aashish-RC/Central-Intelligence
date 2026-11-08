import { beforeEach, describe, expect, it } from 'vitest';
import { CooldownTracker } from '../src/resilience/cooldown.js';
import { SessionAffinityManager } from '../src/routing/session-affinity.js';

describe('Feature 32: Sticky Session Affinity Engine', () => {
  let manager: SessionAffinityManager;
  let cooldown: CooldownTracker;

  beforeEach(() => {
    manager = SessionAffinityManager.getInstance();
    manager.clear();
    cooldown = new CooldownTracker();
  });

  it('consistently pins the same session ID to the same endpoint', () => {
    const candidates = ['endpoint-a', 'endpoint-b', 'endpoint-c'];
    const session1 = 'session-chat-user-42';

    const target1 = manager.resolveTarget(session1, candidates, cooldown);
    const target2 = manager.resolveTarget(session1, candidates, cooldown);
    const target3 = manager.resolveTarget(session1, candidates, cooldown);

    expect(target1).toBeDefined();
    expect(target2).toBe(target1);
    expect(target3).toBe(target1);
  });

  it('re-routes to a healthy candidate when pinned endpoint enters cooldown', () => {
    const candidates = ['endpoint-a', 'endpoint-b'];
    const session1 = 'session-failover-test';

    const initialTarget = manager.resolveTarget(session1, candidates, cooldown);
    expect(initialTarget).toBeDefined();

    // Mark the pinned target as unhealthy (in cooldown)
    cooldown.recordFailure(initialTarget!, 60);
    expect(cooldown.isAvailable(initialTarget!)).toBe(false);

    // Subsequent resolution should fail over to the other candidate
    const failoverTarget = manager.resolveTarget(session1, candidates, cooldown);
    expect(failoverTarget).toBeDefined();
    expect(failoverTarget).not.toBe(initialTarget);
    expect(candidates.includes(failoverTarget!)).toBe(true);
  });

  it('renews session TTL on repeated active access', () => {
    const candidates = ['endpoint-1'];
    const session = 'session-ttl-test';

    manager.resolveTarget(session, candidates);
    const bindingBefore = manager.getBinding(session);
    expect(bindingBefore).toBeDefined();

    const initialExpiry = bindingBefore!.expiresAt;
    // Access again
    manager.resolveTarget(session, candidates);
    const bindingAfter = manager.getBinding(session);
    expect(bindingAfter!.expiresAt).toBeGreaterThanOrEqual(initialExpiry);
  });
});
