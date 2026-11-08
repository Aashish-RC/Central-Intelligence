import crypto from 'node:crypto';
import type { AuditHook, AuditRecord } from '../types/ra1.js';

export interface PromotionalCredit {
  id: string;
  amount: number;
  expiresAt: string; // ISO date string
}

export interface AccountLedger {
  accountId: string;
  balance: number;
  currency: string;
  lowBalanceThreshold: number;
  cumulativeCredited: number;
  cumulativeDebited: number;
  lastMutationTimestamp: number;
  promotionalCredits: PromotionalCredit[];
}

export type WebhookDispatcher = (url: string, payload: any, signature: string) => Promise<void>;

export interface CreditManagerConfig {
  defaultLowBalanceThreshold?: number;
  webhookUrl?: string;
  webhookSecret?: string;
  maxWebhookRetries?: number;
  webhookDispatcher?: WebhookDispatcher;
}

export interface TopUpRequest {
  accountId: string;
  amount: number;
  currency?: string;
  transactionRef?: string;
}

export interface TopUpResult {
  success: boolean;
  currentBalance: number;
  isDuplicate?: boolean;
  transactionRef?: string;
}

export interface PromotionalCreditGrant {
  accountId: string;
  amount: number;
  expiresAt: string;
}

export interface PreflightDecision {
  allowed: boolean;
  statusCode: number;
  currentBalance?: number;
  bypassed?: boolean;
  error?: {
    message: string;
    type: string;
    code: number;
  };
}

export interface SettleUsageRequest {
  accountId: string;
  actualCost: number;
  model: string;
  timestamp?: string;
  metadata?: Record<string, unknown>;
}

export interface SettleUsageResult {
  success: boolean;
  previousBalance: number;
  currentBalance: number;
  debitedAmount: number;
  transactionId: string;
}

/**
 * Prepaid Credit Gating & Automated Webhooks Subsystem.
 * Manages tenant balances, enforces preflight sufficiency checks, debits usage,
 * and dispatches signed webhooks for low or exhausted balances.
 */
export class PrepaidCreditManager {
  private accounts: Map<string, AccountLedger> = new Map();
  private processedTransactions: Set<string> = new Set();
  private defaultLowBalanceThreshold: number;
  private webhookUrl?: string;
  private webhookSecret?: string;
  private maxWebhookRetries: number;
  private webhookDispatcher: WebhookDispatcher;

  constructor(config: CreditManagerConfig = {}) {
    this.defaultLowBalanceThreshold = config.defaultLowBalanceThreshold ?? 5.0;
    this.webhookUrl = config.webhookUrl;
    this.webhookSecret = config.webhookSecret;
    this.maxWebhookRetries = config.maxWebhookRetries ?? 3;

    this.webhookDispatcher =
      config.webhookDispatcher ||
      (async (url, payload, signature) => {
        await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'x-signature': signature,
            'x-gateway-signature': signature,
          },
          body: JSON.stringify(payload),
        });
      });
  }

  public isEnabled(): boolean {
    return process.env.FEATURE_PREPAID_CREDITS === 'true';
  }

  public getAccount(accountId: string): AccountLedger | undefined {
    return this.accounts.get(accountId);
  }

  public topUp(req: TopUpRequest): TopUpResult {
    // Check idempotency
    if (req.transactionRef && this.processedTransactions.has(req.transactionRef)) {
      const existing = this.accounts.get(req.accountId);
      return {
        success: true,
        currentBalance: existing ? existing.balance : 0,
        isDuplicate: true,
        transactionRef: req.transactionRef,
      };
    }

    if (req.amount < 0 || !isFinite(req.amount)) {
      throw new Error(`Invalid top-up amount: ${req.amount}`);
    }

    let acc = this.accounts.get(req.accountId);
    if (!acc) {
      acc = {
        accountId: req.accountId,
        balance: 0,
        currency: req.currency || 'USD',
        lowBalanceThreshold: this.defaultLowBalanceThreshold,
        cumulativeCredited: 0,
        cumulativeDebited: 0,
        lastMutationTimestamp: Date.now(),
        promotionalCredits: [],
      };
      this.accounts.set(req.accountId, acc);
    }

    const precisionAmount = this.roundMicroCents(req.amount);
    acc.balance = this.roundMicroCents(acc.balance + precisionAmount);
    acc.cumulativeCredited = this.roundMicroCents(acc.cumulativeCredited + precisionAmount);
    acc.lastMutationTimestamp = Date.now();

    if (req.transactionRef) {
      this.processedTransactions.add(req.transactionRef);
    }

    return {
      success: true,
      currentBalance: acc.balance,
      transactionRef: req.transactionRef,
    };
  }

  public grantPromotionalCredit(grant: PromotionalCreditGrant): void {
    let acc = this.accounts.get(grant.accountId);
    if (!acc) {
      acc = {
        accountId: grant.accountId,
        balance: 0,
        currency: 'USD',
        lowBalanceThreshold: this.defaultLowBalanceThreshold,
        cumulativeCredited: 0,
        cumulativeDebited: 0,
        lastMutationTimestamp: Date.now(),
        promotionalCredits: [],
      };
      this.accounts.set(grant.accountId, acc);
    }

    const amount = this.roundMicroCents(grant.amount);
    acc.promotionalCredits.push({
      id: `promo-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
      amount,
      expiresAt: grant.expiresAt,
    });

    acc.balance = this.roundMicroCents(acc.balance + amount);
    acc.cumulativeCredited = this.roundMicroCents(acc.cumulativeCredited + amount);
    acc.lastMutationTimestamp = Date.now();
  }

  public async checkPreflight(
    accountId: string,
    anticipatedMinCost: number,
  ): Promise<PreflightDecision> {
    // Feature flag OFF by default: bypasses gating
    if (!this.isEnabled()) {
      return { allowed: true, statusCode: 200, bypassed: true };
    }

    const acc = this.accounts.get(accountId);
    if (!acc) {
      return {
        allowed: false,
        statusCode: 402,
        error: {
          message: `Account not found: '${accountId}' has no active prepaid account`,
          type: 'account_not_found',
          code: 402,
        },
      };
    }

    if (acc.balance < anticipatedMinCost) {
      return {
        allowed: false,
        statusCode: 402,
        currentBalance: acc.balance,
        error: {
          message: `Insufficient prepaid balance: available ${acc.balance} ${acc.currency}, required ${anticipatedMinCost}`,
          type: 'payment_required',
          code: 402,
        },
      };
    }

    return {
      allowed: true,
      statusCode: 200,
      currentBalance: acc.balance,
    };
  }

  public settleUsage(req: SettleUsageRequest): SettleUsageResult {
    if (req.actualCost < 0 || !isFinite(req.actualCost)) {
      throw new Error(`Invalid debit amount: ${req.actualCost}`);
    }

    const acc = this.accounts.get(req.accountId);
    if (!acc) {
      throw new Error(`Account '${req.accountId}' not found for settlement`);
    }

    const debitAmount = this.roundMicroCents(req.actualCost);
    const prevBalance = acc.balance;

    // Deduct from promotional credits first (sorted by expiration date)
    let remainingToDebit = debitAmount;
    if (acc.promotionalCredits && acc.promotionalCredits.length > 0) {
      const activePromos = acc.promotionalCredits
        .filter((p) => new Date(p.expiresAt).getTime() > Date.now() && p.amount > 0)
        .sort((a, b) => new Date(a.expiresAt).getTime() - new Date(b.expiresAt).getTime());

      for (const promo of activePromos) {
        if (remainingToDebit <= 0) break;
        const deduct = Math.min(promo.amount, remainingToDebit);
        promo.amount = this.roundMicroCents(promo.amount - deduct);
        remainingToDebit = this.roundMicroCents(remainingToDebit - deduct);
      }
    }

    // Update overall balance
    acc.balance = this.roundMicroCents(acc.balance - debitAmount);
    acc.cumulativeDebited = this.roundMicroCents(acc.cumulativeDebited + debitAmount);
    acc.lastMutationTimestamp = Date.now();

    const currentBalance = acc.balance;
    const txId = `tx-debit-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;

    // Check for webhook triggers asynchronously (non-blocking)
    this.checkWebhookTriggers(acc, prevBalance, currentBalance);

    return {
      success: true,
      previousBalance: prevBalance,
      currentBalance,
      debitedAmount: debitAmount,
      transactionId: txId,
    };
  }

  /**
   * Creates an H4 Audit Hook consumer.
   * Billing settlement listens to H4 audit records without leaking into engine core.
   */
  public createH4AuditHook(nextHook?: AuditHook): AuditHook {
    return async (record: AuditRecord) => {
      if (this.isEnabled() && record.outcome === 'success') {
        const accountId = (record.metadata?.tenantId as string) || record.actor;
        const cost = record.cost?.totalCost;

        if (accountId && cost !== undefined && cost > 0 && this.accounts.has(accountId)) {
          try {
            this.settleUsage({
              accountId,
              actualCost: cost,
              model: record.model,
              timestamp: record.timestamp,
              metadata: record.metadata,
            });
          } catch (err) {
            console.error(
              `[PrepaidCreditManager] Audit hook settlement failed for account '${accountId}':`,
              err,
            );
          }
        }
      }

      if (nextHook) {
        await nextHook(record);
      }
    };
  }

  private checkWebhookTriggers(
    acc: AccountLedger,
    prevBalance: number,
    currentBalance: number,
  ): void {
    if (!this.webhookUrl) return;

    // Zero or negative balance trigger
    if (prevBalance > 0 && currentBalance <= 0) {
      this.dispatchWebhookAsync({
        eventType: 'balance.exhausted',
        accountId: acc.accountId,
        currentBalance,
        currency: acc.currency,
        timestamp: new Date().toISOString(),
      });
      return;
    }

    // Low balance trigger: crossed threshold from above
    if (
      prevBalance >= acc.lowBalanceThreshold &&
      currentBalance < acc.lowBalanceThreshold &&
      currentBalance > 0
    ) {
      this.dispatchWebhookAsync({
        eventType: 'balance.low',
        accountId: acc.accountId,
        currentBalance,
        threshold: acc.lowBalanceThreshold,
        currency: acc.currency,
        timestamp: new Date().toISOString(),
      });
    }
  }

  private pendingWebhooks: Promise<void>[] = [];

  public async flushWebhooks(): Promise<void> {
    await Promise.allSettled(this.pendingWebhooks);
    this.pendingWebhooks = [];
  }

  private dispatchWebhookAsync(payload: any): void {
    // Non-blocking fire-and-forget with bounded retries
    const promise = (async () => {
      const payloadString = JSON.stringify(payload);
      const signature = this.webhookSecret
        ? crypto.createHmac('sha256', this.webhookSecret).update(payloadString).digest('hex')
        : '';

      let attempt = 0;
      let delay = 10;

      while (attempt <= this.maxWebhookRetries) {
        try {
          await this.webhookDispatcher(this.webhookUrl!, payload, signature);
          return;
        } catch (err) {
          attempt++;
          if (attempt > this.maxWebhookRetries) {
            console.error(
              `[PrepaidCreditManager] Webhook delivery failed after ${attempt} attempts:`,
              err,
            );
            return;
          }
          await new Promise((r) => setTimeout(r, delay));
          delay *= 2;
        }
      }
    })();

    this.pendingWebhooks.push(promise);
  }

  /**
   * Avoids floating-point drift by rounding to 6 decimal places.
   */
  private roundMicroCents(value: number): number {
    return Math.round(value * 1e6) / 1e6;
  }
}
