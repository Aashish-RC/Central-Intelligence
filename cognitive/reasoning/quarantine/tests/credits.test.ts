import { describe, it, expect, vi } from 'vitest';
import { CreditManager } from '../credits.js';

describe('Feature 46: Prepaid Credit Gating & Automated Invoicing Webhooks', () => {
  it('manages account balances, additions, and gating', () => {
    const manager = new CreditManager();
    manager.addCredits('cust_1', 10.0);

    expect(manager.checkSufficientCredits('cust_1', 5.0)).toBe(true);
    expect(manager.checkSufficientCredits('cust_1', 15.0)).toBe(false);
  });

  it('deducts cost and fires webhook events on low and depleted balance', () => {
    const manager = new CreditManager();
    const eventSpy = vi.fn();
    manager.onBillingEvent(eventSpy);

    manager.addCredits('cust_2', 6.0); // low threshold is 5.0

    // Deduct $2 -> balance becomes $4 (triggering balance.low)
    const res1 = manager.deductCost('cust_2', 2.0);
    expect(res1.success).toBe(true);
    expect(res1.newBalance).toBe(4.0);

    expect(eventSpy).toHaveBeenCalledWith(
      expect.objectContaining({ event: 'balance.low', accountId: 'cust_2' })
    );

    // Deduct $5 -> balance becomes -$1 (triggering balance.depleted)
    const res2 = manager.deductCost('cust_2', 5.0);
    expect(res2.success).toBe(false);
    expect(eventSpy).toHaveBeenCalledWith(
      expect.objectContaining({ event: 'balance.depleted', accountId: 'cust_2' })
    );
  });
});
