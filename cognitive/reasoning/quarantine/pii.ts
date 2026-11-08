import { TokenVault } from './vault.js';
import { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';

export type PIIEntityType = 'EMAIL' | 'PHONE' | 'SSN' | 'CREDIT_CARD' | 'IP_ADDRESS';

export interface PIIEntityMatch {
  type: PIIEntityType;
  value: string;
  start: number;
  end: number;
}

export interface PIIEngineOptions {
  enabledTypes?: PIIEntityType[];
  vaultTtlSeconds?: number;
}

const DEFAULT_PATTERNS: Record<PIIEntityType, RegExp> = {
  EMAIL: /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g,
  PHONE: /(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/g,
  SSN: /\b\d{3}-\d{2}-\d{4}\b/g,
  CREDIT_CARD: /\b(?:\d{4}[-\s]?){3}\d{4}\b/g,
  IP_ADDRESS: /\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b/g,
};

export class PIIMaskingEngine {
  private vault: TokenVault;
  private enabledTypes: Set<PIIEntityType>;

  constructor(options: PIIEngineOptions = {}) {
    this.vault = TokenVault.getInstance();
    this.enabledTypes = new Set(
      options.enabledTypes ?? ['EMAIL', 'PHONE', 'SSN', 'CREDIT_CARD', 'IP_ADDRESS']
    );
  }

  /**
   * Scans text and extracts non-overlapping entity matches (longest match wins).
   */
  public detect(text: string): PIIEntityMatch[] {
    const rawMatches: PIIEntityMatch[] = [];

    for (const type of this.enabledTypes) {
      const regex = new RegExp(DEFAULT_PATTERNS[type].source, 'g');
      let match: RegExpExecArray | null;

      while ((match = regex.exec(text)) !== null) {
        rawMatches.push({
          type,
          value: match[0],
          start: match.index,
          end: match.index + match[0].length
        });
      }
    }

    // Sort by start position; resolve overlaps by keeping the longest match
    rawMatches.sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));

    const resolved: PIIEntityMatch[] = [];
    let lastEnd = -1;

    for (const m of rawMatches) {
      if (m.start >= lastEnd) {
        resolved.push(m);
        lastEnd = m.end;
      }
    }

    return resolved;
  }

  /**
   * Replaces sensitive entities with opaque surrogate tokens stored in the vault.
   */
  public maskText(text: string): string {
    const matches = this.detect(text);
    if (matches.length === 0) return text;

    let result = '';
    let cursor = 0;

    for (const match of matches) {
      result += text.slice(cursor, match.start);
      const token = this.vault.store(match.value, match.type);
      result += token;
      cursor = match.end;
    }

    result += text.slice(cursor);
    return result;
  }

  /**
   * Masks sensitive PII across all messages in a ChatCompletionRequest.
   */
  public maskRequest(request: ChatCompletionRequest): ChatCompletionRequest {
    const maskedMessages = request.messages.map(msg => ({
      ...msg,
      content: msg.content ? this.maskText(msg.content) : msg.content
    }));

    return {
      ...request,
      messages: maskedMessages
    };
  }

  /**
   * Detokenizes all token placeholders back to their original values in text.
   */
  public unmaskText(text: string): string {
    return text.replace(/\[TOKEN_[A-Z_]+_[a-f0-9]+\]/g, (token) => {
      const record = this.vault.get(token);
      return record ? record.originalValue : token;
    });
  }

  /**
   * Unmasks sensitive PII in a ChatCompletionResponse.
   */
  public unmaskResponse(response: ChatCompletionResponse): ChatCompletionResponse {
    const choices = response.choices.map(c => ({
      ...c,
      message: {
        ...c.message,
        content: c.message.content ? this.unmaskText(c.message.content) : c.message.content
      }
    }));

    return {
      ...response,
      choices
    };
  }

  /**
   * Creates a streaming detokenizer for SSE streams that maintains a residual buffer
   * across chunk boundaries.
   */
  public createStreamDetokenizer(): (chunk: string) => string {
    let residualBuffer = '';

    return (chunk: string): string => {
      const combined = residualBuffer + chunk;
      residualBuffer = '';

      // Check if there is an unclosed token prefix at the tail of combined
      // e.g. "[TOKEN_EMA" or "["
      const openBracketIdx = combined.lastIndexOf('[');
      if (openBracketIdx !== -1) {
        const potentialFragment = combined.slice(openBracketIdx);
        // If it starts with [ and has no closing ], it could be a token fragment
        if (!potentialFragment.includes(']') && /\[(?:T(?:O(?:K(?:E(?:N(?:_[A-Z0-9_]*)?)?)?)?)?)?$/.test(potentialFragment)) {
          residualBuffer = potentialFragment;
          const readyPart = combined.slice(0, openBracketIdx);
          return this.unmaskText(readyPart);
        }
      }

      return this.unmaskText(combined);
    };
  }
}
