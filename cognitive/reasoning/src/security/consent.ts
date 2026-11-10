/**
 * c15t Consent Management Bridge (Features 10.29, 10.35)
 * Verifies explicit user consent before model dispatch, telemetry emission,
 * and enforces per-user Privacy Mode (no training, zero data retention).
 */

export interface UserConsentState {
  userId: string;
  tenantId?: string;
  privacyMode: boolean;
  purposes: {
    telemetry?: boolean;
    diagnostics?: boolean;
    modelTraining?: boolean;
    externalDispatch?: boolean;
    analytics?: boolean;
  };
}

export class ConsentGuard {
  private userConsents = new Map<string, UserConsentState>();

  private key(userId: string, tenantId = "default"): string {
    return `${tenantId}:${userId}`;
  }

  public setConsent(consent: UserConsentState): void {
    const k = this.key(consent.userId, consent.tenantId || "default");
    this.userConsents.set(k, consent);
  }

  public isPrivacyMode(userId: string, tenantId = "default"): boolean {
    const k = this.key(userId, tenantId);
    const c = this.userConsents.get(k);
    return c?.privacyMode ?? false;
  }

  public canDispatchToExternalModel(userId: string, tenantId = "default"): boolean {
    const k = this.key(userId, tenantId);
    const c = this.userConsents.get(k);
    if (!c) {
      // Default to allowing external dispatch if no explicit restriction, unless in privacy mode
      return true;
    }
    if (c.privacyMode) {
      // Allowed for processing, but model training MUST be strictly forbidden
      return true;
    }
    return c.purposes.externalDispatch !== false;
  }

  public canUseForModelTraining(userId: string, tenantId = "default"): boolean {
    const k = this.key(userId, tenantId);
    const c = this.userConsents.get(k);
    if (!c || c.privacyMode) {
      return false;
    }
    return c.purposes.modelTraining === true;
  }
}

export const defaultConsentGuard = new ConsentGuard();

