import { describe, it, expect } from "vitest";
import { DebateOrchestrator } from "../src/debate/orchestrator";
import { DebateProposition } from "../src/debate/models";

describe("DebateOrchestrator (4.05)", () => {
  const proposition: DebateProposition = {
    id: "prop_async_io",
    statement: "All database I/O in the cognitive worker pipeline should be fully asynchronous.",
    context: { system: "Aevum CI Pipeline", targetLatencyMs: 15 },
  };

  it("orchestrates a default multi-turn debate and reaches a verdict", async () => {
    const orchestrator = new DebateOrchestrator({ maxRounds: 2 });
    const verdict = await orchestrator.conductDebate(proposition);

    expect(verdict.propositionId).toBe(proposition.id);
    expect(verdict.roundsCompleted).toBeGreaterThan(0);
    expect(["proponent", "opponent", "compromise", "inconclusive"]).toContain(verdict.winner);
    expect(verdict.confidence).toBeGreaterThan(0.5);
    expect(verdict.keyArguments.length).toBeGreaterThan(0);
    expect(verdict.rationale).toBeDefined();
  });

  it("supports custom agent debaters and declares opponent winner when rebuttal is stronger", async () => {
    const customDebater = async (
      agentId: string,
      role: "proponent" | "opponent" | "judge",
      _prop: DebateProposition,
      _round: number
    ) => {
      if (role === "proponent") {
        return {
          argument: "We believe async I/O is universally better without qualification.",
          confidence: 0.35,
        };
      } else if (role === "opponent") {
        return {
          argument: "Synchronous embedded SQLite memory access has 10x lower overhead for small fact queries.",
          confidence: 0.92,
        };
      } else {
        return {
          argument: "Reviewing opposing arguments against low-latency SQLite benchmark.",
          confidence: 0.9,
        };
      }
    };

    const orchestrator = new DebateOrchestrator({ maxRounds: 2 }, customDebater);
    const verdict = await orchestrator.conductDebate(proposition);

    expect(verdict.winner).toBe("opponent");
    expect(verdict.confidence).toBe(0.92);
    expect(verdict.rationale).toContain("Opponent decisively refuted");
  });

  it("detects early convergence when confidence delta exceeds threshold", async () => {
    const customDebater = async (
      _agentId: string,
      role: "proponent" | "opponent" | "judge"
    ) => {
      if (role === "proponent") {
        return { argument: "Irrefutable proof of theorem.", confidence: 0.98 };
      } else if (role === "opponent") {
        return { argument: "Conceding point.", confidence: 0.1 };
      } else {
        return { argument: "Judge observes concession.", confidence: 0.95 };
      }
    };

    const orchestrator = new DebateOrchestrator(
      { maxRounds: 5, convergenceThreshold: 0.8 },
      customDebater
    );
    const verdict = await orchestrator.conductDebate(proposition);

    expect(verdict.roundsCompleted).toBe(1);
    expect(verdict.consensusReached).toBe(true);
    expect(verdict.winner).toBe("proponent");
  });

  it("produces a compromise verdict when debaters have balanced confidence", async () => {
    const customDebater = async (
      _agentId: string,
      role: "proponent" | "opponent" | "judge"
    ) => {
      if (role === "proponent") {
        return { argument: "Async handles high concurrency well.", confidence: 0.75 };
      } else if (role === "opponent") {
        return { argument: "Sync is simpler and less error-prone for unit tasks.", confidence: 0.72 };
      } else {
        return { argument: "Evaluating hybrid trade-off.", confidence: 0.8 };
      }
    };

    const orchestrator = new DebateOrchestrator({ maxRounds: 2 }, customDebater);
    const verdict = await orchestrator.conductDebate(proposition);

    expect(verdict.winner).toBe("compromise");
    expect(verdict.rationale).toContain("compromise approach is recommended");
  });
});
