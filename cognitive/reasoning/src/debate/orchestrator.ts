import {
  AgentTurn,
  DebateConfig,
  DebateProposition,
  DebateRound,
  DebateVerdict,
} from "./models.js";

export type AgentDebaterFn = (
  agentId: string,
  role: "proponent" | "opponent" | "judge",
  proposition: DebateProposition,
  round: number,
  history: AgentTurn[]
) => Promise<{
  argument: string;
  confidence: number;
  counterArguments?: string[];
  citations?: string[];
}>;

export class DebateOrchestrator {
  private config: DebateConfig;
  private debaterFn?: AgentDebaterFn;

  constructor(config?: Partial<DebateConfig>, debaterFn?: AgentDebaterFn) {
    this.config = {
      maxRounds: config?.maxRounds ?? 3,
      convergenceThreshold: config?.convergenceThreshold ?? 0.8,
      requireJudge: config?.requireJudge ?? true,
      timeoutMs: config?.timeoutMs ?? 30000,
    };
    this.debaterFn = debaterFn;
  }

  /**
   * Run a multi-agent debate session on a given proposition.
   */
  public async conductDebate(
    proposition: DebateProposition,
    proponentId = "agent_proponent",
    opponentId = "agent_opponent",
    judgeId = "agent_judge"
  ): Promise<DebateVerdict> {
    const rounds: DebateRound[] = [];
    const allTurns: AgentTurn[] = [];

    let consensusReached = false;
    let finalVerdict: DebateVerdict | null = null;

    for (let r = 1; r <= this.config.maxRounds; r++) {
      const currentTurns: AgentTurn[] = [];

      // Proponent's turn
      const propResponse = await this.getAgentTurn(
        proponentId,
        "proponent",
        proposition,
        r,
        allTurns
      );
      const propTurn: AgentTurn = {
        agentId: proponentId,
        role: "proponent",
        roundNumber: r,
        argument: propResponse.argument,
        confidence: propResponse.confidence,
        counterArguments: propResponse.counterArguments,
        citations: propResponse.citations,
        timestamp: Date.now(),
      };
      currentTurns.push(propTurn);
      allTurns.push(propTurn);

      // Opponent's turn
      const oppResponse = await this.getAgentTurn(
        opponentId,
        "opponent",
        proposition,
        r,
        allTurns
      );
      const oppTurn: AgentTurn = {
        agentId: opponentId,
        role: "opponent",
        roundNumber: r,
        argument: oppResponse.argument,
        confidence: oppResponse.confidence,
        counterArguments: oppResponse.counterArguments,
        citations: oppResponse.citations,
        timestamp: Date.now(),
      };
      currentTurns.push(oppTurn);
      allTurns.push(oppTurn);

      // Judge evaluation turn if enabled
      if (this.config.requireJudge) {
        const judgeResponse = await this.getAgentTurn(
          judgeId,
          "judge",
          proposition,
          r,
          allTurns
        );
        const judgeTurn: AgentTurn = {
          agentId: judgeId,
          role: "judge",
          roundNumber: r,
          argument: judgeResponse.argument,
          confidence: judgeResponse.confidence,
          timestamp: Date.now(),
        };
        currentTurns.push(judgeTurn);
        allTurns.push(judgeTurn);
      }

      rounds.push({
        roundNumber: r,
        turns: currentTurns,
      });

      // Check convergence if confidence difference is decisive or threshold met
      const propConf = propTurn.confidence;
      const oppConf = oppTurn.confidence;
      const diff = Math.abs(propConf - oppConf);

      if (diff >= this.config.convergenceThreshold) {
        consensusReached = true;
        break;
      }
    }

    // Synthesize final verdict
    return this.synthesizeVerdict(proposition, rounds, allTurns, consensusReached);
  }

  private async getAgentTurn(
    agentId: string,
    role: "proponent" | "opponent" | "judge",
    proposition: DebateProposition,
    round: number,
    history: AgentTurn[]
  ) {
    if (this.debaterFn) {
      return await this.debaterFn(agentId, role, proposition, round, history);
    }

    // Default heuristic mock debater
    if (role === "proponent") {
      return {
        argument: `Affirming '${proposition.statement}': robust architectural alignment and empirical precedent validate the premise.`,
        confidence: Math.min(0.95, 0.7 + round * 0.08),
        counterArguments: ["Previous edge cases are addressed via isolated sandboxing."],
        citations: ["RFC-819", "System Architecture §4.2"],
      };
    } else if (role === "opponent") {
      return {
        argument: `Rebutting '${proposition.statement}': potential state race conditions and operational blast radius remain unmitigated.`,
        confidence: Math.max(0.4, 0.65 - round * 0.05),
        counterArguments: ["Failure containment overhead may surpass predicted throughput gains."],
        citations: ["Reliability Engineering standard 14.1"],
      };
    } else {
      return {
        argument: `Judicial assessment for round ${round}: weighing evidence between proponent and opponent.`,
        confidence: 0.85,
      };
    }
  }

  private synthesizeVerdict(
    proposition: DebateProposition,
    rounds: DebateRound[],
    allTurns: AgentTurn[],
    consensusReached: boolean
  ): DebateVerdict {
    const propTurns = allTurns.filter((t) => t.role === "proponent");
    const oppTurns = allTurns.filter((t) => t.role === "opponent");

    const avgPropConf =
      propTurns.reduce((acc, t) => acc + t.confidence, 0) / (propTurns.length || 1);
    const avgOppConf =
      oppTurns.reduce((acc, t) => acc + t.confidence, 0) / (oppTurns.length || 1);

    let winner: "proponent" | "opponent" | "compromise" | "inconclusive" = "inconclusive";
    let rationale = "";

    const delta = avgPropConf - avgOppConf;
    if (delta > 0.2) {
      winner = "proponent";
      rationale = `Proponent presented consistently stronger empirical arguments (avg confidence ${avgPropConf.toFixed(2)} vs ${avgOppConf.toFixed(2)}).`;
    } else if (delta < -0.2) {
      winner = "opponent";
      rationale = `Opponent decisively refuted the proposition with higher evidence certainty (avg confidence ${avgOppConf.toFixed(2)} vs ${avgPropConf.toFixed(2)}).`;
    } else if (Math.abs(delta) <= 0.2 && rounds.length > 1) {
      winner = "compromise";
      rationale = `Arguments demonstrated balanced validity; a synthesized compromise approach is recommended.`;
    } else {
      winner = "inconclusive";
      rationale = `Insufficient convergence across ${rounds.length} debate rounds.`;
    }

    const keyArguments: string[] = [
      ...propTurns.slice(-1).map((t) => `Proponent: ${t.argument}`),
      ...oppTurns.slice(-1).map((t) => `Opponent: ${t.argument}`),
    ];

    const overallConfidence = Number((Math.max(avgPropConf, avgOppConf)).toFixed(2));

    return {
      propositionId: proposition.id,
      winner,
      confidence: overallConfidence,
      rationale,
      roundsCompleted: rounds.length,
      keyArguments,
      consensusReached,
    };
  }
}
