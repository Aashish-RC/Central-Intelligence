/**
 * Feature 46: Prepaid Credit Gating & Automated Invoicing Webhook Hooks
 * Manages customer wallet balances, auto-cutoffs on depletion, and billing event webhooks.
 */

export interface CreditAccount {
  accountId: string;
  balanceUsd: number;
  currency: string;
  isPrepaid: boolean;
  lowBalanceThresholdUsd: number;
  autoTopUpEnabled: boolean;
  autoTopUpAmountUsd: number;
}

export interface BillingWebhookEvent {
  id: string;
  event: 'balance.deducted' | 'balance.low' | 'balance.depleted' | 'invoice.created' | 'topup.success';
  accountId: string;
  data: Record<string, any>;
  timestamp: number;
}

export type WebhookHandler = (event: BillingWebhookEvent) => Promise<void> | void;

export class CreditManager {
  private accounts: Map<string, CreditAccount> = new Map();
  private webhookHandlers: WebhookHandler[] = [];

  registerAccount(account: CreditAccount): void {
    this.accounts.set(account.accountId, { ...account });
  }

  getAccount(accountId: string): CreditAccount | undefined {
    return this.accounts.get(accountId);
  }

  onBillingEvent(handler: WebhookHandler): void {
    this.webhookHandlers.push(handler);
  }

  addCredits(accountId: string, amountUsd: number): CreditAccount {
    let account = this.accounts.get(accountId);
    if (!account) {
      account = {
        accountId,
        balanceUsd: amountUsd,
        currency: 'USD',
        isPrepaid: true,
        lowBalanceThresholdUsd: 5.0,
        autoTopUpEnabled: false,
        autoTopUpAmountUsd: 50.0,
      };
      this.accounts.set(accountId, account);
    } else {
      account.balanceUsd += amountUsd;
    }

    this.emitEvent({
      id: `evt_topup_${Date.now()}`,
      event: 'topup.success',
      accountId,
      data: { addedAmount: amountUsd, newBalance: account.balanceUsd },
      timestamp: Date.now(),
    });

    return account;
  }

  checkSufficientCredits(accountId: string, estimatedCostUsd: number = 0.01): boolean {
    const account = this.accounts.get(accountId);
    if (!account) return true; // Unmetered / default pass
    if (!account.isPrepaid) return true; // Post-paid enterprise account
    return account.balanceUsd >= estimatedCostUsd;
  }

  deductCost(accountId: string, costUsd: number): { success: boolean; newBalance: number } {
    const account = this.accounts.get(accountId);
    if (!account) {
      return { success: true, newBalance: 0 };
    }

    account.balanceUsd -= costUsd;

    this.emitEvent({
      id: `evt_deduct_${Date.now()}`,
      event: 'balance.deducted',
      accountId,
      data: { costUsd, newBalance: account.balanceUsd },
      timestamp: Date.now(),
    });

    if (account.balanceUsd <= 0) {
      this.emitEvent({
        id: `evt_depleted_${Date.now()}`,
        event: 'balance.depleted',
        accountId,
        data: { currentBalance: account.balanceUsd },
        timestamp: Date.now(),
      });
      return { success: false, newBalance: account.balanceUsd };
    }

    if (account.balanceUsd <= account.lowBalanceThresholdUsd) {
      this.emitEvent({
        id: `evt_low_${Date.now()}`,
        event: 'balance.low',
        accountId,
        data: { currentBalance: account.balanceUsd, threshold: account.lowBalanceThresholdUsd },
        timestamp: Date.now(),
      });
    }

    return { success: true, newBalance: account.balanceUsd };
  }

  private emitEvent(event: BillingWebhookEvent): void {
    for (const handler of this.webhookHandlers) {
      try {
        handler(event);
      } catch {
        // Suppress webhook handler exceptions to protect core billing pipeline
      }
    }
  }
}
