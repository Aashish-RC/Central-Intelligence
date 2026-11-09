/**
 * Collaboration Controls for Multi-Agent Reasoning
 *
 * Implements governance and stability controls for agent-to-agent interactions:
 * - A2A message schema validation and prompt injection filtering (Feature 4.23)
 * - Conversation history token budget pruning (Feature 4.24)
 * - Circular dialogue and ping-pong loop detection (Feature 4.25)
 * - Multi-agent consensus voting engine (Feature 4.26)
 *
 * Features: 4.23 - 4.26
 */

export interface A2AMessage {
  id: string;
  senderId: string;
  recipientId: string;
  action: string;
  payload: Record<string, unknown>;
  timestamp?: number;
}

export interface DialogueTurn {
  speaker: string;
  content: string;
  timestamp?: number;
}

export interface ConsensusCandidate {
  candidateId: string;
  agentId: string;
  solution: string;
  confidence: number;
  votes?: number;
}

export class CollaborationControls {
  private readonly loopSimilarityThreshold: number;

  constructor(config?: { loopSimilarityThreshold?: number }) {
    this.loopSimilarityThreshold = config?.loopSimilarityThreshold ?? 0.8;
  }

  /**
   * Feature 4.23: Validates an inter-agent message against expected structure and injection patterns.
   */
  validateA2AMessage(
    message: A2AMessage,
    requiredFields: string[] = []
  ): { valid: boolean; error?: string } {
    if (!message.senderId || !message.recipientId || !message.action) {
      return { valid: false, error: 'A2A message missing required header fields (senderId, recipientId, action)' };
    }

    if (!message.payload || typeof message.payload !== 'object') {
      return { valid: false, error: 'A2A payload must be a non-null object' };
    }

    for (const field of requiredFields) {
      if (!(field in message.payload)) {
        return { valid: false, error: `Missing required payload field: '${field}'` };
      }
    }

    // Check payload values for adversarial injection tags
    const payloadStr = JSON.stringify(message.payload);
    const injectionPatterns = [
      /<\s*system\s*>/i,
      /ignore\s+(?:all\s+)?previous\s+instructions/i,
      /\[\s*system\s*instruction\s*\]/i,
    ];

    for (const pat of injectionPatterns) {
      if (pat.test(payloadStr)) {
        return { valid: false, error: `A2A message payload contains blocked adversarial pattern '${pat.source}'` };
      }
    }

    return { valid: true };
  }

  /**
   * Feature 4.25: Circular Dialogue & Ping-Pong Loop Detection.
   * Identifies repetitive polite loops or oscillating states between collaborating agents.
   */
  detectPingPongLoop(
    history: DialogueTurn[],
    windowSize: number = 4
  ): { isLooping: boolean; confidence: number; reason?: string } {
    if (history.length < windowSize) {
      return { isLooping: false, confidence: 0.0 };
    }

    const recent = history.slice(-windowSize);

    // Check alternating speakers (e.g. A -> B -> A -> B)
    const speakers = recent.map((t) => t.speaker);
    const alternating = speakers[0] === speakers[2] && speakers[1] === speakers[3] && speakers[0] !== speakers[1];

    if (!alternating) {
      return { isLooping: false, confidence: 0.0 };
    }

    // Ping-pong keyword indicators
    const pingPongPhrases = [
      'thank you', 'thanks', "you're welcome", 'happy to help',
      'anything else', 'looks good', 'sounds good', 'acknowledged',
      'no problem', 'agree', 'let me know',
    ];

    let matchCount = 0;
    for (const turn of recent) {
      const lower = turn.content.toLowerCase();
      if (pingPongPhrases.some((phrase) => lower.includes(phrase))) {
        matchCount++;
      }
    }

    // High repetitive overlap
    const content0 = recent[0].content.trim().toLowerCase();
    const content2 = recent[2].content.trim().toLowerCase();
    const exactRepeat = content0 === content2 && content0.length > 0;

    if (exactRepeat || matchCount >= 3) {
      return {
        isLooping: true,
        confidence: exactRepeat ? 0.95 : 0.85,
        reason: exactRepeat
          ? `Exact repeated turn detected between alternating speakers: "${content0.substring(0, 40)}..."`
          : `Ping-pong pleasantry loop detected (${matchCount}/${windowSize} turns matched repetitive polite patterns)`,
      };
    }

    return { isLooping: false, confidence: 0.2 };
  }

  /**
   * Feature 4.24: Prunes conversation turns to fit within token limit while preserving critical anchors.
   */
  pruneConversationHistory(turns: DialogueTurn[], maxEstimatedTokens: number): DialogueTurn[] {
    const estimateTokens = (text: string) => Math.ceil(text.split(/\s+/).length * 1.3);

    let totalTokens = turns.reduce((acc, t) => acc + estimateTokens(t.content), 0);
    if (totalTokens <= maxEstimatedTokens) {
      return [...turns];
    }

    // Retain first turn (anchor context/goal) and latest turns, pruning middle
    if (turns.length <= 2) {
      return [...turns];
    }

    const firstTurn = turns[0];
    const workingTurns = turns.slice(1);

    while (workingTurns.length > 1 && totalTokens > maxEstimatedTokens) {
      const removed = workingTurns.shift();
      if (removed) {
        totalTokens -= estimateTokens(removed.content);
      }
    }

    return [firstTurn, ...workingTurns];
  }

  /**
   * Feature 4.26: Computes consensus solution among parallel candidate solutions from multiple agents.
   */
  computeConsensus(candidates: ConsensusCandidate[]): {
    winner: ConsensusCandidate;
    consensusScore: number;
    agreementRatio: number;
  } {
    if (candidates.length === 0) {
      throw new Error('Cannot compute consensus with zero candidates');
    }

    if (candidates.length === 1) {
      return { winner: candidates[0], consensusScore: candidates[0].confidence, agreementRatio: 1.0 };
    }

    // Group candidates by normalized solution
    const groups: Map<string, { candidates: ConsensusCandidate[]; totalScore: number }> = new Map();

    for (const c of candidates) {
      const norm = c.solution.trim().toLowerCase().replace(/\s+/g, ' ');
      const existing = groups.get(norm);
      if (existing) {
        existing.candidates.push(c);
        existing.totalScore += c.confidence + (c.votes || 1);
      } else {
        groups.set(norm, { candidates: [c], totalScore: c.confidence + (c.votes || 1) });
      }
    }

    // Select group with highest cumulative score
    let bestGroup: { candidates: ConsensusCandidate[]; totalScore: number } | null = null;
    for (const group of groups.values()) {
      if (!bestGroup || group.totalScore > bestGroup.totalScore) {
        bestGroup = group;
      }
    }

    const winner = bestGroup!.candidates.sort((a, b) => b.confidence - a.confidence)[0];
    const agreementRatio = bestGroup!.candidates.length / candidates.length;
    const avgConfidence =
      bestGroup!.candidates.reduce((sum, c) => sum + c.confidence, 0) / bestGroup!.candidates.length;

    return {
      winner,
      consensusScore: Math.round(avgConfidence * 100) / 100,
      agreementRatio: Math.round(agreementRatio * 100) / 100,
    };
  }
}
