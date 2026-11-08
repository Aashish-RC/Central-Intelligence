import type { ChatCompletionRequest } from '../types/chat.js';
import type { MultiUnitUsage } from '../types/telemetry.js';

export interface ExtractedUsage extends MultiUnitUsage {
  cacheWriteTokens?: number;
  estimated?: boolean;
}

export class TokenUsageAccounting {
  /**
   * Estimates token count for a text string using a standard ~4 chars/token heuristic
   */
  public static estimateTokens(text: string): number {
    if (!text || text.length === 0) return 0;
    // Standard rule: ~4 chars per token, minimum 1 token for non-empty text
    return Math.max(1, Math.ceil(text.trim().length / 4));
  }

  /**
   * Estimates prompt tokens from a ChatCompletionRequest
   */
  public static estimatePromptTokens(req: ChatCompletionRequest): number {
    let totalChars = 0;
    for (const msg of req.messages) {
      totalChars += (msg.role || '').length + 4; // overhead per message
      totalChars += (msg.content || '').length;
      if (msg.name) totalChars += msg.name.length;
    }
    return Math.max(1, Math.ceil(totalChars / 4));
  }

  /**
   * Extracts and unifies usage from provider responses (OpenAI, Anthropic, Gemini, Ollama)
   * Falls back to token estimation if usage is missing from upstream response.
   */
  public static extractUsage(
    rawResponse: any,
    provider: string,
    req?: ChatCompletionRequest,
    completionText?: string,
  ): ExtractedUsage {
    // 1. OpenAI format
    if (rawResponse?.usage) {
      const u = rawResponse.usage;
      const promptTokens = u.prompt_tokens ?? 0;
      const completionTokens = u.completion_tokens ?? 0;
      const cachedPromptTokens = u.prompt_tokens_details?.cached_tokens ?? 0;
      const reasoningTokens = u.completion_tokens_details?.reasoning_tokens ?? 0;
      const totalTokens = u.total_tokens ?? promptTokens + completionTokens;

      return {
        promptTokens,
        completionTokens,
        reasoningTokens,
        cachedPromptTokens,
        totalTokens,
        estimated: false,
      };
    }

    // 2. Anthropic format
    if (rawResponse?.usage?.input_tokens !== undefined || rawResponse?.input_tokens !== undefined) {
      const u = rawResponse.usage || rawResponse;
      const promptTokens = u.input_tokens ?? 0;
      const completionTokens = u.output_tokens ?? 0;
      const cachedPromptTokens = u.cache_read_input_tokens ?? 0;
      const cacheWriteTokens = u.cache_creation_input_tokens ?? 0;
      const totalTokens = promptTokens + completionTokens;

      return {
        promptTokens,
        completionTokens,
        reasoningTokens: 0,
        cachedPromptTokens,
        cacheWriteTokens,
        totalTokens,
        estimated: false,
      };
    }

    // 3. Gemini format
    if (rawResponse?.usageMetadata) {
      const u = rawResponse.usageMetadata;
      const promptTokens = u.promptTokenCount ?? 0;
      const completionTokens = u.candidatesTokenCount ?? 0;
      const cachedPromptTokens = u.cachedContentTokenCount ?? 0;
      const totalTokens = u.totalTokenCount ?? promptTokens + completionTokens;

      return {
        promptTokens,
        completionTokens,
        reasoningTokens: 0,
        cachedPromptTokens,
        totalTokens,
        estimated: false,
      };
    }

    // 4. Ollama format
    if (rawResponse?.prompt_eval_count !== undefined || rawResponse?.eval_count !== undefined) {
      const promptTokens = rawResponse.prompt_eval_count ?? 0;
      const completionTokens = rawResponse.eval_count ?? 0;

      return {
        promptTokens,
        completionTokens,
        reasoningTokens: 0,
        cachedPromptTokens: 0,
        totalTokens: promptTokens + completionTokens,
        estimated: false,
      };
    }

    // Fallback: Usage omitted by provider, compute estimation
    const promptEst = req ? this.estimatePromptTokens(req) : 0;
    const completionEst = completionText ? this.estimateTokens(completionText) : 0;

    return {
      promptTokens: promptEst,
      completionTokens: completionEst,
      reasoningTokens: 0,
      cachedPromptTokens: 0,
      totalTokens: promptEst + completionEst,
      estimated: true,
    };
  }
}
