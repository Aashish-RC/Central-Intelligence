/**
 * Process Reward Verifier (PRM) - Sub-module A of L4 Adaptive Multi-Model Synthesis Engine
 * Feature IDs: 4.08, 11.14
 *
 * Grades intermediate reasoning steps and prunes invalid logic BEFORE subsequent steps execute.
 * Evaluates step confidence:
 *  - score >= 0.8: High confidence, proceed with current branch
 *  - 0.5 <= score < 0.8: Passable / acceptable logic step
 *  - score < 0.5: Low confidence, prune branch and trigger alternative exploration
 */

export interface ReasoningStep {
  id: string;
  index: number;
  text: string;
  score: number;
  status: 'valid' | 'pruned' | 'tentative';
  rationale?: string;
}

export interface PRMVerifyRequest {
  task: string;
  step: string;
  stepIndex?: number;
  priorSteps?: string[];
}

export interface PRMVerifyResult {
  score: number;
  valid: boolean;
  action: 'continue' | 'prune' | 'retry';
  rationale: string;
}

export interface PRMVerifierConfig {
  minPassScore?: number;       // default 0.5
  highConfidenceScore?: number; // default 0.8
  scoringFn?: (task: string, step: string, priorSteps: string[]) => Promise<{ score: number; rationale?: string }>;
}

export class ProcessRewardVerifier {
  private minPassScore: number;
  private highConfidenceScore: number;
  private scoringFn?: (task: string, step: string, priorSteps: string[]) => Promise<{ score: number; rationale?: string }>;

  constructor(config?: PRMVerifierConfig) {
    this.minPassScore = config?.minPassScore ?? 0.5;
    this.highConfidenceScore = config?.highConfidenceScore ?? 0.8;
    this.scoringFn = config?.scoringFn;
  }

  /**
   * Scores an individual reasoning step in context of task and prior steps.
   */
  async verifyStep(req: PRMVerifyRequest): Promise<PRMVerifyResult> {
    const prior = req.priorSteps ?? [];
    
    let score: number;
    let rationale = '';

    if (this.scoringFn) {
      const res = await this.scoringFn(req.task, req.step, prior);
      score = Math.max(0, Math.min(1, res.score));
      rationale = res.rationale ?? `PRM model score: ${score.toFixed(2)}`;
    } else {
      // Deterministic heuristic PRM scorer when no custom LLM scoring callback is supplied
      score = this.evaluateHeuristicScore(req.task, req.step, prior);
      rationale = score < this.minPassScore
        ? 'Contradictory or logically flawed intermediate step'
        : score >= this.highConfidenceScore
          ? 'Strong logical progression towards solution'
          : 'Acceptable intermediate step';
    }

    if (score < this.minPassScore) {
      return {
        score,
        valid: false,
        action: 'prune',
        rationale: rationale || 'Step score below threshold (0.5); branch pruned.',
      };
    }

    if (score >= this.highConfidenceScore) {
      return {
        score,
        valid: true,
        action: 'continue',
        rationale: rationale || 'High confidence step (>= 0.8); continue branch.',
      };
    }

    return {
      score,
      valid: true,
      action: 'continue',
      rationale: rationale || 'Step acceptable (>= 0.5); continue branch.',
    };
  }

  /**
   * Evaluates a full chain of reasoning steps, pruning invalid steps.
   */
  async verifyReasoningTrace(
    task: string,
    steps: string[],
  ): Promise<{
    steps: ReasoningStep[];
    isValidTrace: boolean;
    finalScore: number;
    prunedSteps: ReasoningStep[];
  }> {
    const evaluatedSteps: ReasoningStep[] = [];
    const prunedSteps: ReasoningStep[] = [];
    const prior: string[] = [];

    for (let i = 0; i < steps.length; i++) {
      const stepText = steps[i];
      const verification = await this.verifyStep({
        task,
        step: stepText,
        stepIndex: i,
        priorSteps: prior,
      });

      const stepRecord: ReasoningStep = {
        id: `step-${i + 1}`,
        index: i,
        text: stepText,
        score: verification.score,
        status: verification.valid ? 'valid' : 'pruned',
        rationale: verification.rationale,
      };

      if (!verification.valid) {
        prunedSteps.push(stepRecord);
        evaluatedSteps.push(stepRecord);
        // Once a critical flaw is encountered, the trace is invalidated
        break;
      }

      evaluatedSteps.push(stepRecord);
      prior.push(stepText);
    }

    const validSteps = evaluatedSteps.filter((s) => s.status === 'valid');
    const isValidTrace = prunedSteps.length === 0 && validSteps.length === steps.length;
    const finalScore = validSteps.length > 0
      ? validSteps.reduce((acc, s) => acc + s.score, 0) / validSteps.length
      : 0;

    return {
      steps: evaluatedSteps,
      isValidTrace,
      finalScore: Number(finalScore.toFixed(3)),
      prunedSteps,
    };
  }

  /**
   * Fallback rule-based heuristic step evaluator.
   */
  private evaluateHeuristicScore(task: string, step: string, prior: string[]): number {
    const lowerStep = step.toLowerCase();
    
    // Explicit fallacy / hallucination markers
    const invalidPatterns = [
      /\b(impossible|contradiction|division by zero|undefined value|false premise|hallucinated|syntax error)\b/i,
      /\b(2\s*\+\s*2\s*=\s*5|1\s*=\s*0|true\s*==\s*false)\b/i,
      /\b(therefore i cannot complete this task|gives up|infinite loop)\b/i,
    ];

    for (const pat of invalidPatterns) {
      if (pat.test(lowerStep)) {
        return 0.2;
      }
    }

    // Circular repetition penalty
    for (const p of prior) {
      if (p.trim().toLowerCase() === lowerStep.trim()) {
        return 0.35; // Circular repetition
      }
    }

    // Coherent reasoning indicators
    const strongIndicators = [
      /\b(because|therefore|hence|consequently|first|next|finally|let|given that|substituting)\b/i,
      /\b(verified|validated|calculates to|results in|matches condition)\b/i,
    ];

    let score = 0.75;
    for (const ind of strongIndicators) {
      if (ind.test(lowerStep)) {
        score += 0.1;
        break;
      }
    }

    return Math.min(score, 0.95);
  }
}
