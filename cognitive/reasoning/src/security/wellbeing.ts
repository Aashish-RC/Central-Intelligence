/**
 * Over-Reliance Guard Companion (Feature 10.55)
 * Tracks repeated decision-deferrals and injects wellbeing guidance.
 */

export class OverRelianceGuardTS {
  private userCounts = new Map<string, number>();
  private readonly threshold: number;

  constructor(threshold = 10) {
    this.threshold = threshold;
  }

  public isDeferral(prompt: string): boolean {
    const p = prompt.toLowerCase();
    return (
      p.includes("what should i do") ||
      p.includes("you decide") ||
      p.includes("decide for me") ||
      p.includes("tell me what to do") ||
      p.includes("which one should i choose") ||
      p.includes("you choose") ||
      p.includes("should i quit") ||
      p.includes("should i break up")
    );
  }

  public isAgencyAssertion(prompt: string): boolean {
    const p = prompt.toLowerCase();
    return (
      p.includes("i have decided") ||
      p.includes("i decided") ||
      p.includes("my choice is") ||
      p.includes("i will pick") ||
      p.includes("i disagree")
    );
  }

  public recordTurn(userId: string, prompt: string): { warn: boolean; count: number; warning?: string } {
    if (this.isAgencyAssertion(prompt)) {
      this.userCounts.set(userId, 0);
      return { warn: false, count: 0 };
    }

    if (this.isDeferral(prompt)) {
      const current = (this.userCounts.get(userId) || 0) + 1;
      this.userCounts.set(userId, current);
      if (current >= this.threshold) {
        return {
          warn: true,
          count: current,
          warning: "Wellbeing Notice: You have asked the AI to decide for you multiple times in a row. Remember that AI is an assistant, and you should exercise your own autonomous judgment for important personal decisions."
        };
      }
      return { warn: false, count: current };
    }

    return { warn: false, count: this.userCounts.get(userId) || 0 };
  }
}

export const defaultOverRelianceGuardTS = new OverRelianceGuardTS();
