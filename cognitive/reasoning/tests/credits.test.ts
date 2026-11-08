import crypto from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CreditManagerConfig, PrepaidCreditManager } from '../src/telemetry/credits.js';
import type { AuditRecord } from '../src/types/ra1.js';

describe('Prepaid Credit Gating & Automated Webhooks', () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    delete process.env.FEATURE_PREPAID_CREDITS;
  });

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it('Rule C15: Feature flag OFF by default bypasses gating (admits all preflight checks)', async () => {
    const manager = new PrepaidCreditManager();
    // Account does not even exist, but flag is off -> admits
    const decision = await manager.checkPreflight('non-existent-acc', 5.0);
    expect(decision.allowed).toBe(true);
    expect(decision.bypassed).toBe(true);
  });

  describe('When FEATURE_PREPAID_CREDITS is enabled', () => {
    beforeEach(() => {
      process.env.FEATURE_PREPAID_CREDITS = 'true';
    });

    it('Rule C1: Balance provisioning (top-up) adds funds and records ledger state', () => {
      const manager = new PrepaidCreditManager();
      const res = manager.topUp({
        accountId: 'acc-cust-1',
        amount: 50.0,
        currency: 'USD',
        transactionRef: 'tx-1001',
      });

      expect(res.success).toBe(true);
      expect(res.currentBalance).toBe(50.0);

      const acc = manager.getAccount('acc-cust-1');
      expect(acc?.balance).toBe(50.0);
      expect(acc?.currency).toBe('USD');
      expect(acc?.cumulativeCredited).toBe(50.0);
      expect(acc?.cumulativeDebited).toBe(0.0);
    });

    it('Rule C2 & C3: Preflight gating check admits when sufficient, rejects with 402 when insufficient', async () => {
      const manager = new PrepaidCreditManager();
      manager.topUp({ accountId: 'acc-cust-1', amount: 5.0, currency: 'USD' });

      // Sufficient: anticipated cost 2.0 <= 5.0
      const okDecision = await manager.checkPreflight('acc-cust-1', 2.0);
      expect(okDecision.allowed).toBe(true);
      expect(okDecision.statusCode).toBe(200);

      // Insufficient: anticipated cost 10.0 > 5.0
      const rejectDecision = await manager.checkPreflight('acc-cust-1', 10.0);
      expect(rejectDecision.allowed).toBe(false);
      expect(rejectDecision.statusCode).toBe(402);
      expect(rejectDecision.error?.type).toBe('payment_required');
      expect(rejectDecision.error?.message).toContain('Insufficient prepaid balance');
    });

    it('Rule C4: Usage settlement (debit) updates balance ledger and returns current balance and confirmation', () => {
      const manager = new PrepaidCreditManager();
      manager.topUp({ accountId: 'acc-cust-1', amount: 20.0, currency: 'USD' });

      const debitRes = manager.settleUsage({
        accountId: 'acc-cust-1',
        actualCost: 3.5,
        model: 'gpt-4o',
        timestamp: new Date().toISOString(),
      });

      expect(debitRes.success).toBe(true);
      expect(debitRes.previousBalance).toBe(20.0);
      expect(debitRes.currentBalance).toBe(16.5);
      expect(debitRes.debitedAmount).toBe(3.5);

      const acc = manager.getAccount('acc-cust-1');
      expect(acc?.balance).toBe(16.5);
      expect(acc?.cumulativeDebited).toBe(3.5);
    });

    it('Rule C5: Low-balance warning webhook dispatched when balance dips below threshold', async () => {
      let dispatchedPayload: any = null;
      let dispatchedSignature: string | null = null;

      const manager = new PrepaidCreditManager({
        defaultLowBalanceThreshold: 5.0,
        webhookUrl: 'https://billing.internal/webhook',
        webhookSecret: 'secret-key-123',
        webhookDispatcher: async (url, payload, signature) => {
          dispatchedPayload = payload;
          dispatchedSignature = signature;
        },
      });

      manager.topUp({ accountId: 'acc-alert-1', amount: 10.0, currency: 'USD' });

      // Debit 6.0 -> balance becomes 4.0 (< 5.0 threshold)
      manager.settleUsage({
        accountId: 'acc-alert-1',
        actualCost: 6.0,
        model: 'gpt-4o',
      });
      await manager.flushWebhooks();

      expect(dispatchedPayload).not.toBeNull();
      expect(dispatchedPayload.eventType).toBe('balance.low');
      expect(dispatchedPayload.accountId).toBe('acc-alert-1');
      expect(dispatchedPayload.currentBalance).toBe(4.0);
      expect(dispatchedPayload.threshold).toBe(5.0);

      // Verify HMAC signature
      const expectedSig = crypto
        .createHmac('sha256', 'secret-key-123')
        .update(JSON.stringify(dispatchedPayload))
        .digest('hex');
      expect(dispatchedSignature).toBe(expectedSig);
    });

    it('Rule C6 & C7: Zero-balance / exhaustion webhook dispatched and signed with HMAC', async () => {
      let dispatchedPayload: any = null;
      let dispatchedSignature: string | null = null;

      const manager = new PrepaidCreditManager({
        defaultLowBalanceThreshold: 2.0,
        webhookUrl: 'https://billing.internal/webhook',
        webhookSecret: 'hmac-secret-abc',
        webhookDispatcher: async (url, payload, signature) => {
          dispatchedPayload = payload;
          dispatchedSignature = signature;
        },
      });

      manager.topUp({ accountId: 'acc-zero-1', amount: 5.0, currency: 'USD' });

      // Debit 5.0 -> balance becomes 0
      manager.settleUsage({
        accountId: 'acc-zero-1',
        actualCost: 5.0,
        model: 'claude-3-5-sonnet',
      });
      await manager.flushWebhooks();

      expect(dispatchedPayload).not.toBeNull();
      expect(dispatchedPayload.eventType).toBe('balance.exhausted');
      expect(dispatchedPayload.accountId).toBe('acc-zero-1');
      expect(dispatchedPayload.currentBalance).toBe(0);

      const expectedSig = crypto
        .createHmac('sha256', 'hmac-secret-abc')
        .update(JSON.stringify(dispatchedPayload))
        .digest('hex');
      expect(dispatchedSignature).toBe(expectedSig);
    });

    it('Rule C8: Micro-cent precision maintained to at least 6 decimal places without floating drift', () => {
      const manager = new PrepaidCreditManager();
      manager.topUp({ accountId: 'acc-micro', amount: 1.0, currency: 'USD' });

      // Settle 10 small token debits of $0.000123 each
      for (let i = 0; i < 10; i++) {
        manager.settleUsage({
          accountId: 'acc-micro',
          actualCost: 0.000123,
          model: 'gpt-4o-mini',
        });
      }

      const acc = manager.getAccount('acc-micro')!;
      // 1.0 - (10 * 0.000123) = 1.0 - 0.001230 = 0.998770
      expect(acc.balance).toBe(0.99877);
      expect(acc.cumulativeDebited).toBe(0.00123);
    });

    it('Rule C9: Negative balance grace handling allows completion of current request, but gates next', async () => {
      const manager = new PrepaidCreditManager();
      manager.topUp({ accountId: 'acc-grace', amount: 2.0, currency: 'USD' });

      // Anticipated cost was 1.5 -> admitted
      const preflight = await manager.checkPreflight('acc-grace', 1.5);
      expect(preflight.allowed).toBe(true);

      // But generation ended up costing 3.5 -> balance becomes -1.5
      const settleRes = manager.settleUsage({
        accountId: 'acc-grace',
        actualCost: 3.5,
        model: 'gpt-4o',
      });
      expect(settleRes.success).toBe(true);
      expect(settleRes.currentBalance).toBe(-1.5);

      // Next preflight request is strictly gated
      const nextPreflight = await manager.checkPreflight('acc-grace', 0.1);
      expect(nextPreflight.allowed).toBe(false);
      expect(nextPreflight.statusCode).toBe(402);
    });

    it('Rule C10: Idempotent top-ups prevent duplicate credits on duplicate transaction reference', () => {
      const manager = new PrepaidCreditManager();
      const topUp1 = manager.topUp({
        accountId: 'acc-idem',
        amount: 100.0,
        currency: 'USD',
        transactionRef: 'tx-uniq-999',
      });
      expect(topUp1.success).toBe(true);
      expect(topUp1.currentBalance).toBe(100.0);

      // Repeat with same transaction reference
      const topUp2 = manager.topUp({
        accountId: 'acc-idem',
        amount: 100.0,
        currency: 'USD',
        transactionRef: 'tx-uniq-999',
      });
      expect(topUp2.success).toBe(true);
      expect(topUp2.isDuplicate).toBe(true);
      expect(topUp2.currentBalance).toBe(100.0); // did not add another 100
      expect(manager.getAccount('acc-idem')?.balance).toBe(100.0);
    });

    it('Rule C11: Asynchronous non-blocking webhooks with bounded retries do not block caller', async () => {
      let callCount = 0;
      const manager = new PrepaidCreditManager({
        defaultLowBalanceThreshold: 5.0,
        webhookUrl: 'https://failing-endpoint.test/webhook',
        webhookDispatcher: async () => {
          callCount++;
          throw new Error('Endpoint down');
        },
        maxWebhookRetries: 2,
      });

      manager.topUp({ accountId: 'acc-retry', amount: 6.0, currency: 'USD' });

      // Calling settleUsage should return synchronously without throwing
      const startTime = Date.now();
      const res = manager.settleUsage({
        accountId: 'acc-retry',
        actualCost: 3.0, // dips below 5.0 -> triggers webhook
        model: 'gpt-4o',
      });
      const duration = Date.now() - startTime;

      expect(res.success).toBe(true);
      expect(duration).toBeLessThan(100); // synchronous return
    });

    it('Rule C12: Promotional credits nearing expiration are consumed before non-expiring cash balances', () => {
      const manager = new PrepaidCreditManager();
      // Provision permanent cash balance of $50
      manager.topUp({ accountId: 'acc-promo', amount: 50.0, currency: 'USD' });

      // Grant promotional credit of $10 expiring tomorrow
      const tomorrow = new Date(Date.now() + 86400000).toISOString();
      manager.grantPromotionalCredit({
        accountId: 'acc-promo',
        amount: 10.0,
        expiresAt: tomorrow,
      });

      expect(manager.getAccount('acc-promo')?.balance).toBe(60.0);

      // Debit $5 -> should be deducted from expiring promo credits first
      manager.settleUsage({ accountId: 'acc-promo', actualCost: 5.0, model: 'gpt-4o' });
      expect(manager.getAccount('acc-promo')?.balance).toBe(55.0);
      expect(manager.getAccount('acc-promo')?.promotionalCredits[0].amount).toBe(5.0);

      // Debit another $7 -> consumes remaining $5 promo + $2 cash
      manager.settleUsage({ accountId: 'acc-promo', actualCost: 7.0, model: 'gpt-4o' });
      expect(manager.getAccount('acc-promo')?.balance).toBe(48.0);
      expect(manager.getAccount('acc-promo')?.promotionalCredits[0].amount).toBe(0.0);
    });

    it('Rule C13: Non-existent account fails closed', async () => {
      const manager = new PrepaidCreditManager();
      const res = await manager.checkPreflight('unknown-account-id', 1.0);
      expect(res.allowed).toBe(false);
      expect(res.statusCode).toBe(402);
      expect(res.error?.message).toContain('Account not found');
    });

    it('Rule C14: Invalid debit amounts (negative or non-finite numbers) are rejected', () => {
      const manager = new PrepaidCreditManager();
      manager.topUp({ accountId: 'acc-val', amount: 20.0, currency: 'USD' });

      expect(() => {
        manager.settleUsage({ accountId: 'acc-val', actualCost: -5.0, model: 'gpt-4o' });
      }).toThrow('Invalid debit amount');

      expect(() => {
        manager.settleUsage({ accountId: 'acc-val', actualCost: Number.NaN, model: 'gpt-4o' });
      }).toThrow('Invalid debit amount');
    });

    it('Rule C16: Consumes usage events via H4 audit hook without billing logic leaking elsewhere', async () => {
      const manager = new PrepaidCreditManager();
      manager.topUp({ accountId: 'tenant-42', amount: 10.0, currency: 'USD' });

      // Create an audit record hook handler
      const creditAuditHook = manager.createH4AuditHook();

      const mockRecord: AuditRecord = {
        requestId: 'req-1',
        traceId: 'tr-1',
        timestamp: new Date().toISOString(),
        actor: 'user-bob',
        model: 'gpt-4o',
        provider: 'openai',
        targetId: 'tgt-1',
        tokens: {
          promptTokens: 100,
          completionTokens: 50,
          reasoningTokens: 0,
          cachedPromptTokens: 0,
          totalTokens: 150,
        },
        cost: {
          currency: 'USD',
          promptCost: 0.0005,
          completionCost: 0.00075,
          reasoningCost: 0,
          cacheDiscount: 0,
          totalCost: 0.00125,
        },
        latencyMs: 120,
        outcome: 'success',
        statusCode: 200,
        metadata: { tenantId: 'tenant-42' },
      };

      await creditAuditHook(mockRecord);

      const acc = manager.getAccount('tenant-42')!;
      expect(acc.cumulativeDebited).toBe(0.00125);
      expect(acc.balance).toBe(9.99875);
    });
  });
});
