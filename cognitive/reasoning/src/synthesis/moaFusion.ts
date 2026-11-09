/**
 * Mixture of Agents (MoA) Fusion Aggregator - Sub-module C of L4 Adaptive Multi-Model Synthesis Engine
 * Feature IDs: 4.08, 11.14
 *
 * Runs N candidate models in parallel and synthesizes their complementary insights
 * into a single superior, cross-verified response with Claim Decomposition verification.
 */

import { ClaimDecomposer, type ClaimDecompositionResult } from './claimDecomposer.js';

export interface CandidateResponse {
  model: string;
  content: string;
  confidence?: number;
  latencyMs?: number;
  tokensUsed?: number;
}

export interface MoAFusionResult {
  synthesizedText: string;
  candidates: CandidateResponse[];
  consensusScore: number;       // 0.0 - 1.0 cross-candidate agreement
  claimVerification?: ClaimDecompositionResult;
  modelCount: number;
  dominantModel?: string;
  metadata?: Record<string, any>;
}

export interface MoAFusionConfig {
  aggregatorFn?: (prompt: string, candidates: CandidateResponse[]) => Promise<string>;
  claimDecomposer?: ClaimDecomposer;
  minCandidates?: number;       // default 2 (typically 3)
}

export class MoAFusionAggregator {
  private aggregatorFn?: (prompt: string, candidates: CandidateResponse[]) => Promise<string>;
  private claimDecomposer: ClaimDecomposer;
  private minCandidates: number;

  constructor(config?: MoAFusionConfig) {
    this.aggregatorFn = config?.aggregatorFn;
    this.claimDecomposer = config?.claimDecomposer ?? new ClaimDecomposer();
    this.minCandidates = config?.minCandidates ?? 2;
  }

  /**
   * Fuses candidate responses from multiple models into a synthesized output.
   */
  async fuse(
    prompt: string,
    candidates: CandidateResponse[],
    knowledgeContext: string[] = [],
  ): Promise<MoAFusionResult> {
    if (!candidates || candidates.length === 0) {
      throw new Error('MoA fusion requires at least one candidate response.');
    }

    if (candidates.length === 1) {
      // Single candidate fast return
      const verification = await this.claimDecomposer.decomposeAndVerify(
        candidates[0].content,
        knowledgeContext,
      );
      return {
        synthesizedText: candidates[0].content,
        candidates,
        consensusScore: 1.0,
        claimVerification: verification,
        modelCount: 1,
        dominantModel: candidates[0].model,
      };
    }

    // 1. Synthesize responses across candidate models
    let synthesizedText = '';
    if (this.aggregatorFn) {
      synthesizedText = await this.aggregatorFn(prompt, candidates);
    } else {
      synthesizedText = this.heuristicAggregate(prompt, candidates);
    }

    // 2. Measure cross-candidate consensus score
    const consensusScore = this.calculateConsensus(candidates);

    // 3. Verify synthesized output via Claim Decomposition (Sub-module B)
    const claimVerification = await this.claimDecomposer.decomposeAndVerify(
      synthesizedText,
      knowledgeContext,
    );

    // 4. Identify most influential/dominant model candidate
    const dominantModel = this.identifyDominantModel(synthesizedText, candidates);

    return {
      synthesizedText,
      candidates,
      consensusScore,
      claimVerification,
      modelCount: candidates.length,
      dominantModel,
    };
  }

  /**
   * Heuristic synthesis when no external aggregator LLM call is configured.
   * Merges unique insights and extracts shared factual consensus.
   */
  private heuristicAggregate(prompt: string, candidates: CandidateResponse[]): string {
    // Extract unique non-redundant key sentences across candidates
    const seenSentences = new Set<string>();
    const keySentences: string[] = [];

    // Sort candidates by confidence if available
    const sorted = [...candidates].sort((a, b) => (b.confidence ?? 0.8) - (a.confidence ?? 0.8));

    for (const cand of sorted) {
      const sentences = cand.content
        .split(/(?<=[.!?])\s+/)
        .map((s) => s.trim())
        .filter((s) => s.length > 5);

      for (const sentence of sentences) {
        const normalized = sentence.toLowerCase().replace(/[^a-z0-9]/g, '');
        if (!seenSentences.has(normalized)) {
          seenSentences.add(normalized);
          keySentences.push(sentence);
        }
      }
    }

    return keySentences.join(' ');
  }

  /**
   * Calculates similarity / agreement score between candidates.
   */
  private calculateConsensus(candidates: CandidateResponse[]): number {
    if (candidates.length <= 1) return 1.0;

    const wordSets = candidates.map((c) => {
      return new Set(
        c.content
          .toLowerCase()
          .replace(/[^a-z0-9\s]/g, '')
          .split(/\s+/)
          .filter((w) => w.length > 3),
      );
    });

    let totalJaccard = 0;
    let pairs = 0;

    for (let i = 0; i < wordSets.length; i++) {
      for (let j = i + 1; j < wordSets.length; j++) {
        const intersection = new Set([...wordSets[i]].filter((x) => wordSets[j].has(x)));
        const union = new Set([...wordSets[i], ...wordSets[j]]);
        const jaccard = union.size === 0 ? 1 : intersection.size / union.size;
        totalJaccard += jaccard;
        pairs++;
      }
    }

    const avg = pairs > 0 ? totalJaccard / pairs : 1.0;
    // Base agreement between multiple LLMs responding to same prompt
    const baseConsensus = 0.45;
    return Number(Math.min(1.0, baseConsensus + (1 - baseConsensus) * avg).toFixed(3));
  }

  /**
   * Finds candidate model whose text shares the highest overlap with the synthesis.
   */
  private identifyDominantModel(synthesis: string, candidates: CandidateResponse[]): string {
    const synthWords = new Set(
      synthesis
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, '')
        .split(/\s+/)
        .filter((w) => w.length > 3),
    );

    let bestModel = candidates[0].model;
    let maxOverlap = -1;

    for (const cand of candidates) {
      const words = cand.content
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, '')
        .split(/\s+/)
        .filter((w) => w.length > 3);
      
      const overlap = words.filter((w) => synthWords.has(w)).length;
      if (overlap > maxOverlap) {
        maxOverlap = overlap;
        bestModel = cand.model;
      }
    }

    return bestModel;
  }
}
