import { z } from "zod";

export type DebateRole = "proponent" | "opponent" | "judge" | "participant";

export interface AgentTurn {
  agentId: string;
  role: DebateRole;
  roundNumber: number;
  argument: string;
  citations?: string[];
  counterArguments?: string[];
  confidence: number;
  timestamp: number;
}

export interface DebateRound {
  roundNumber: number;
  turns: AgentTurn[];
  roundSummary?: string;
}

export interface DebateProposition {
  id: string;
  statement: string;
  context?: Record<string, unknown>;
}

export type DebateWinner = "proponent" | "opponent" | "compromise" | "inconclusive";

export interface DebateVerdict {
  propositionId: string;
  winner: DebateWinner;
  confidence: number;
  rationale: string;
  roundsCompleted: number;
  keyArguments: string[];
  consensusReached: boolean;
}

export interface DebateConfig {
  maxRounds: number;
  convergenceThreshold: number;
  requireJudge: boolean;
  timeoutMs?: number;
}

export const AgentTurnSchema = z.object({
  agentId: z.string(),
  role: z.enum(["proponent", "opponent", "judge", "participant"]),
  roundNumber: z.number(),
  argument: z.string(),
  citations: z.array(z.string()).optional(),
  counterArguments: z.array(z.string()).optional(),
  confidence: z.number().min(0).max(1),
  timestamp: z.number(),
});

export const DebateVerdictSchema = z.object({
  propositionId: z.string(),
  winner: z.enum(["proponent", "opponent", "compromise", "inconclusive"]),
  confidence: z.number().min(0).max(1),
  rationale: z.string(),
  roundsCompleted: z.number(),
  keyArguments: z.array(z.string()),
  consensusReached: z.boolean(),
});
