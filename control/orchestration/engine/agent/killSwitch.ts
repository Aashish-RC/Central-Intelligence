/**
 * Emergency Agent Kill Switch for Orchestration Loop (Feature 10.24)
 * Provides sub-second halting of ReAct and multi-step agent loops.
 */

export interface KillSwitchStatus {
  halted: boolean;
  tenantId?: string;
  userId?: string;
  reason?: string;
  triggeredAt?: number;
}

export class AgentKillSwitchTS {
  private globalHalted = false;
  private tenantHalts = new Map<string, string>();
  private userHalts = new Map<string, string>();

  public triggerGlobal(reason = "Emergency global halt"): void {
    this.globalHalted = true;
  }

  public triggerTenant(tenantId: string, reason = "Emergency tenant halt"): void {
    this.tenantHalts.set(tenantId, reason);
  }

  public triggerUser(userId: string, reason = "Emergency user halt"): void {
    this.userHalts.set(userId, reason);
  }

  public isHalted(userId?: string, tenantId?: string): boolean {
    if (this.globalHalted) return true;
    if (tenantId && this.tenantHalts.has(tenantId)) return true;
    if (userId && this.userHalts.has(userId)) return true;
    return false;
  }

  public getHaltReason(userId?: string, tenantId?: string): string {
    if (this.globalHalted) return "Global kill switch active";
    if (tenantId && this.tenantHalts.has(tenantId)) return this.tenantHalts.get(tenantId)!;
    if (userId && this.userHalts.has(userId)) return this.userHalts.get(userId)!;
    return "";
  }

  public reset(): void {
    this.globalHalted = false;
    this.tenantHalts.clear;
    this.userHalts.clear();
  }
}

export const defaultKillSwitchTS = new AgentKillSwitchTS();
