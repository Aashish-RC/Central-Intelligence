export interface TokenizeRequest {
  model?: string;
  prompt?: string;
  messages?: Array<{ role: string; content: string }>;
}

export interface TokenizeResponse {
  count: number;
  model: string;
  character_count: number;
}

export class TokenCounter {
  /**
   * Fast, accurate token approximation based on model architecture BPE averages.
   * OpenAI / Claude averages ~4 characters per token for English text.
   * Chat messages include per-message packaging overhead (~4 tokens for role/envelope).
   */
  public static countTokens(text: string, model = 'gpt-4o'): number {
    if (!text || text.length === 0) return 0;

    // Word and character heuristic calibrated against cl100k / o200k
    const words = text.trim().split(/\s+/).length;
    const chars = text.length;

    // Fast approximation: 1 token ~= 4 chars, with adjustments for symbols and numbers
    const specialChars = (text.match(/[^a-zA-Z0-9\s]/g) || []).length;
    const estimated = Math.ceil(chars / 4.0 + specialChars * 0.25);

    return Math.max(1, Math.round((estimated + words * 0.75) / 1.75));
  }

  public static countMessageTokens(
    messages: Array<{ role: string; content: string }>,
    model = 'gpt-4o',
  ): { totalTokens: number; messageDetails: Array<{ role: string; tokens: number }> } {
    let total = 3; // Priming tokens

    const details = messages.map((msg) => {
      const msgTokens = 4 + TokenCounter.countTokens(msg.content || '', model);
      total += msgTokens;
      return {
        role: msg.role,
        tokens: msgTokens,
      };
    });

    return { totalTokens: total, messageDetails: details };
  }
}
