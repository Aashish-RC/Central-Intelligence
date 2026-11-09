/**
 * Claim Decomposition Engine - Sub-module B of L4 Adaptive Multi-Model Synthesis Engine
 * Feature IDs: 4.08, 11.14
 *
 * Splits reasoning output into atomic propositions and verifies each claim
 * against reference knowledge (e.g. L3 Knowledge RRF search / facts store).
 */

export interface AtomicClaim {
  id: string;
  claim: string;
  verified: boolean;
  confidence: number;
  evidence?: string[];
  rationale?: string;
}

export interface ClaimDecompositionResult {
  originalText: string;
  claims: AtomicClaim[];
  supportedRatio: number;      // 0.0 - 1.0 (verified claims / total claims)
  isReliable: boolean;         // true if supportedRatio >= threshold
  unverifiedClaims: AtomicClaim[];
  metadata?: Record<string, any>;
}

export interface KnowledgeSource {
  search(query: string): Promise<string[]>;
}

export interface ClaimDecomposerConfig {
  reliabilityThreshold?: number; // default 0.8
  decomposeFn?: (text: string) => Promise<string[]>;
  verifierFn?: (claim: string, knowledge: string[]) => Promise<{ verified: boolean; confidence: number; evidence?: string[] }>;
}

export class ClaimDecomposer {
  private reliabilityThreshold: number;
  private decomposeFn?: (text: string) => Promise<string[]>;
  private verifierFn?: (claim: string, knowledge: string[]) => Promise<{ verified: boolean; confidence: number; evidence?: string[] }>;

  constructor(config?: ClaimDecomposerConfig) {
    this.reliabilityThreshold = config?.reliabilityThreshold ?? 0.8;
    this.decomposeFn = config?.decomposeFn;
    this.verifierFn = config?.verifierFn;
  }

  /**
   * Splits a block of text into atomic verifiable factual propositions.
   */
  async decompose(text: string): Promise<string[]> {
    if (!text || text.trim().length === 0) {
      return [];
    }

    if (this.decomposeFn) {
      return await this.decomposeFn(text);
    }

    return this.heuristicDecompose(text);
  }

  /**
   * Decomposes output text and verifies each atomic claim against supplied knowledge.
   */
  async decomposeAndVerify(
    text: string,
    knowledgeContext: string[] = [],
  ): Promise<ClaimDecompositionResult> {
    const rawClaims = await this.decompose(text);
    
    if (rawClaims.length === 0) {
      return {
        originalText: text,
        claims: [],
        supportedRatio: 1.0,
        isReliable: true,
        unverifiedClaims: [],
      };
    }

    const atomicClaims: AtomicClaim[] = [];

    for (let i = 0; i < rawClaims.length; i++) {
      const claimText = rawClaims[i];
      let verification: { verified: boolean; confidence: number; evidence?: string[] };

      if (this.verifierFn) {
        verification = await this.verifierFn(claimText, knowledgeContext);
      } else {
        verification = this.heuristicVerify(claimText, knowledgeContext);
      }

      atomicClaims.push({
        id: `claim-${i + 1}`,
        claim: claimText,
        verified: verification.verified,
        confidence: verification.confidence,
        evidence: verification.evidence,
        rationale: verification.verified ? 'Supported by knowledge source' : 'Uncorroborated by knowledge source',
      });
    }

    const verifiedCount = atomicClaims.filter((c) => c.verified).length;
    const supportedRatio = Number((verifiedCount / atomicClaims.length).toFixed(3));
    const isReliable = supportedRatio >= this.reliabilityThreshold;
    const unverifiedClaims = atomicClaims.filter((c) => !c.verified);

    return {
      originalText: text,
      claims: atomicClaims,
      supportedRatio,
      isReliable,
      unverifiedClaims,
    };
  }

  /**
   * Rule-based atomic sentence and clause decomposition.
   */
  private heuristicDecompose(text: string): string[] {
    // 1. Split text into sentences
    const sentences = text
      .split(/(?<=[.!?])\s+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 5);

    const atomicPropositions: string[] = [];

    for (const sentence of sentences) {
      // Split on coordinate conjunctions and semicolons while maintaining self-contained context
      const parts = sentence
        .split(/;\s*|\s+(?:and also|as well as|additionally|furthermore)\s+/i)
        .map((p) => p.trim())
        .filter((p) => p.length > 5);

      for (const part of parts) {
        // Strip trailing punctuation
        const cleaned = part.replace(/[.!?]+$/, '').trim();
        if (cleaned.length > 0) {
          atomicPropositions.push(cleaned);
        }
      }
    }

    return atomicPropositions.length > 0 ? atomicPropositions : [text.trim()];
  }

  /**
   * Heuristic claim verifier against knowledge snippets.
   */
  private heuristicVerify(
    claim: string,
    knowledgeContext: string[],
  ): { verified: boolean; confidence: number; evidence?: string[] } {
    if (knowledgeContext.length === 0) {
      // No knowledge base supplied -> cannot formally corroborate
      return { verified: false, confidence: 0.3 };
    }

    const claimKeywords = claim
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, '')
      .split(/\s+/)
      .filter((w) => w.length > 3 && !['this', 'that', 'with', 'from', 'have', 'were', 'which'].includes(w));

    if (claimKeywords.length === 0) {
      return { verified: true, confidence: 0.7 };
    }

    const matchingEvidence: string[] = [];
    let bestMatchRatio = 0;

    for (const doc of knowledgeContext) {
      const docLower = doc.toLowerCase();
      const matched = claimKeywords.filter((kw) => docLower.includes(kw));
      const ratio = matched.length / claimKeywords.length;

      if (ratio > bestMatchRatio) {
        bestMatchRatio = ratio;
      }
      if (ratio >= 0.5) {
        matchingEvidence.push(doc);
      }
    }

    const verified = bestMatchRatio >= 0.5;
    return {
      verified,
      confidence: Number(bestMatchRatio.toFixed(2)),
      evidence: matchingEvidence.length > 0 ? matchingEvidence : undefined,
    };
  }
}
