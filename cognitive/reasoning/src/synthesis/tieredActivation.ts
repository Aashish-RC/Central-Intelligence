/**
 * Tiered Activation Gate & Facade - Sub-module D of L4 Adaptive Multi-Model Synthesis Engine
 * Feature IDs: 4.08, 11.14
 *
 * Fast path for simple tasks; full multi-model PRM + MoA synthesis for high-stakes/complex tasks.
 * Tiers:
 *  - Tier 0 (Simple): Single model, zero synthesis overhead (e.g. "what's 2+2")
 *  - Tier 1 (Moderate): Single model + Claim Decomposition fact-checking
 *  - Tier 2 (Complex): Process Reward Verifier (PRM) step scoring + Claim Decomposition
 *  - Tier 3 (High-Stakes): Full MoA Fusion (3+ models) + PRM validation + Claim Decomposition
 *  - Second Opinion Dynamic Escalation: Escalates to Tier 3 if initial confidence < 0.5
 */

import { ProcessRewardVerifier, type ReasoningStep } from './prmVerifier.js';
import { ClaimDecomposer, type ClaimDecompositionResult } from './claimDecomposer.js';
import { MoAFusionAggregator, type CandidateResponse, type MoAFusionResult } from './moaFusion.js';

export type SynthesisTier = 0 | 1 | 2 | 3;

export interface SynthesisExecutionRequest {
  task: string;
  tier?: SynthesisTier;
  context?: string[];
  candidateModels?: string[];
  steps?: string[];
  initialAccuracyScore?: number; // L11 score or initial provider confidence
  singleModelRunner?: (task: string, model?: string) => Promise<string>;
  multiModelRunner?: (task: string, models: string[]) => Promise<CandidateResponse[]>;
}

export interface SynthesisExecutionResponse {
  finalText: string;
  activatedTier: SynthesisTier;
  escalatedToSecondOpinion: boolean;
  prmEvaluation?: {
    steps: ReasoningStep[];
    finalScore: number;
    isValidTrace: boolean;
  };
  claimVerification?: ClaimDecompositionResult;
  moaFusion?: MoAFusionResult;
  latencyMs: number;
  metadata?: Record<string, any>;
}

export interface TieredActivationConfig {
  prmVerifier?: ProcessRewardVerifier;
  claimDecomposer?: ClaimDecomposer;
  moaAggregator?: MoAFusionAggregator;
}

export class TieredActivationGate {
  private prmVerifier: ProcessRewardVerifier;
  private claimDecomposer: ClaimDecomposer;
  private moaAggregator: MoAFusionAggregator;

  constructor(config?: TieredActivationConfig) {
    this.prmVerifier = config?.prmVerifier ?? new ProcessRewardVerifier();
    this.claimDecomposer = config?.claimDecomposer ?? new ClaimDecomposer();
    this.moaAggregator = config?.moaAggregator ?? new MoAFusionAggregator({
      claimDecomposer: this.claimDecomposer,
    });
  }

  /**
   * Automatically determines appropriate synthesis tier from task complexity.
   */
  public determineTier(task: string, initialAccuracyScore?: number): SynthesisTier {
    // If accuracy / confidence is already flagged as failing, escalate immediately
    if (initialAccuracyScore !== undefined && initialAccuracyScore < 0.5) {
      return 3;
    }

    const lower = task.toLowerCase();

    // Tier 3: High-Stakes / Architecture / Distributed Systems
    if (
      /\b(distributed system|architecture|mission critical|high stakes|security audit|consensus protocol|byzantine|multisig)\b/i.test(lower) ||
      task.length > 500
    ) {
      return 3;
    }

    // Tier 2: Complex / Multi-step logic / Proofs
    if (
      /\b(step by step|reason through|proof|calculate|algorithm|derivation|verify intermediate|solve for)\b/i.test(lower)
    ) {
      return 2;
    }

    // Tier 0: Simple lookups, greetings, basic arithmetic
    if (
      /^(hi|hello|hey|ping|status)\b/i.test(lower) ||
      /\b(2\s*\+\s*2|what is the capital of|current time|weather in)\b/i.test(lower) ||
      task.trim().length < 30
    ) {
      return 0;
    }

    // Tier 1: Moderate explanations, summaries, translations
    return 1;
  }

  /**
   * Executes adaptive synthesis according to the determined or specified tier.
   */
  async run(req: SynthesisExecutionRequest): Promise<SynthesisExecutionResponse> {
    const startTime = Date.now();
    let escalated = false;

    // Check second opinion condition upfront
    if (req.initialAccuracyScore !== undefined && req.initialAccuracyScore < 0.5) {
      escalated = true;
    }

    let tier = escalated
      ? 3
      : req.tier !== undefined
        ? req.tier
        : this.determineTier(req.task, req.initialAccuracyScore);

    // Fast-path: Tier 0 (Simple tasks skip synthesis completely)
    if (tier === 0) {
      const runner = req.singleModelRunner ?? (async (t) => this.mockSingleModel(t, req.context));
      const text = await runner(req.task);

      // Check second opinion condition
      if (req.initialAccuracyScore !== undefined && req.initialAccuracyScore < 0.5) {
        tier = 3;
        escalated = true;
      } else {
        return {
          finalText: text,
          activatedTier: 0,
          escalatedToSecondOpinion: false,
          latencyMs: Date.now() - startTime,
        };
      }
    }

    // Tier 1: Moderate tasks (Single model + Claim Decomposition)
    if (tier === 1) {
      const runner = req.singleModelRunner ?? (async (t) => this.mockSingleModel(t, req.context));
      const text = await runner(req.task);
      const claimResult = await this.claimDecomposer.decomposeAndVerify(text, req.context ?? []);

      // If factual reliability fails and not explicitly pinned to tier 1, trigger full Tier 3 synthesis as second opinion
      if (!claimResult.isReliable && req.tier === undefined) {
        tier = 3;
        escalated = true;
      } else {
        return {
          finalText: text,
          activatedTier: 1,
          escalatedToSecondOpinion: false,
          claimVerification: claimResult,
          latencyMs: Date.now() - startTime,
        };
      }
    }

    // Tier 2: Complex tasks (PRM step verification + Claim Decomposition)
    if (tier === 2) {
      const runner = req.singleModelRunner ?? (async (t) => this.mockSingleModel(t, req.context));
      const text = await runner(req.task);

      // Verify intermediate steps
      const stepsToVerify = req.steps ?? text.split(/(?<=[.!?])\s+/).filter((s) => s.trim().length > 5);
      const prmEval = await this.prmVerifier.verifyReasoningTrace(req.task, stepsToVerify);

      // Verify factual claims
      const claimResult = await this.claimDecomposer.decomposeAndVerify(text, req.context ?? []);

      // If PRM trace is invalid or final score < 0.5 and not pinned to tier 2, escalate to Tier 3
      if ((!prmEval.isValidTrace || prmEval.finalScore < 0.5) && req.tier === undefined) {
        tier = 3;
        escalated = true;
      } else {
        return {
          finalText: text,
          activatedTier: 2,
          escalatedToSecondOpinion: false,
          prmEvaluation: prmEval,
          claimVerification: claimResult,
          latencyMs: Date.now() - startTime,
        };
      }
    }

    // Tier 3: High-Stakes tasks (Full MoA Fusion + PRM validation + Claim Decomposition)
    const models = req.candidateModels ?? ['claude-3-5-sonnet', 'gpt-4o', 'gemini-1.5-pro'];
    const multiRunner = req.multiModelRunner ?? (async (t, m) => this.mockMultiModel(t, m));
    const candidates = await multiRunner(req.task, models);

    const moaResult = await this.moaAggregator.fuse(req.task, candidates, req.context ?? []);

    // Also run PRM verification on the synthesized text steps
    const synthSteps = moaResult.synthesizedText.split(/(?<=[.!?])\s+/).filter((s) => s.trim().length > 5);
    const prmEval = await this.prmVerifier.verifyReasoningTrace(req.task, synthSteps);

    return {
      finalText: moaResult.synthesizedText,
      activatedTier: 3,
      escalatedToSecondOpinion: escalated,
      moaFusion: moaResult,
      prmEvaluation: prmEval,
      claimVerification: moaResult.claimVerification,
      latencyMs: Date.now() - startTime,
    };
  }

  private mockSingleModel(task: string, context?: string[]): string {
    if (/2\s*\+\s*2/.test(task)) {
      return '4';
    }
    if (context && context.length > 0) {
      return context.join(' ');
    }
    return `Output for task: ${task}`;
  }

  private mockMultiModel(task: string, models: string[]): CandidateResponse[] {
    return models.map((m, idx) => ({
      model: m,
      content: `Candidate ${idx + 1} from ${m} addressing ${task}. Comprehensive architectural considerations include modular fault isolation and horizontal scaling.`,
      confidence: 0.85 + (idx * 0.05),
      latencyMs: 120 + (idx * 20),
    }));
  }
}
