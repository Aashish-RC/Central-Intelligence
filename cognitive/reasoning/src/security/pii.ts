import type { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';
import { TokenVault } from './vault.js';

export type MaskCategory = 'EMAIL' | 'PHONE' | 'SSN' | 'CREDIT_CARD' | 'IP_ADDRESS';
export type PIIEntityType = MaskCategory;

export interface MaskEntityMatch {
  type: MaskCategory;
  value: string;
  start: number;
  end: number;
}
export type PIIEntityMatch = MaskEntityMatch;

export interface MaskEngineOptions {
  enabledTypes?: MaskCategory[];
  vaultTtlSeconds?: number;
  vault?: TokenVault;
}
export type PIIEngineOptions = MaskEngineOptions;

export class PIIMaskingEngine {
  private enabledTypes: Set<MaskCategory>;
  private vaultTtlSeconds: number;
  private vault: TokenVault;

  constructor(options: MaskEngineOptions = {}) {
    this.enabledTypes = new Set<MaskCategory>(
      options.enabledTypes ?? ['EMAIL', 'PHONE', 'SSN', 'CREDIT_CARD', 'IP_ADDRESS'],
    );
    this.vaultTtlSeconds = options.vaultTtlSeconds ?? 3600;
    this.vault = options.vault ?? TokenVault.getInstance();
  }

  /**
   * Scans text for sensitive data entities across all enabled categories.
   * Resolves non-overlapping spans deterministically (longest match takes precedence).
   */
  public detect(text: string): MaskEntityMatch[] {
    const rawMatches: MaskEntityMatch[] = [];

    // 1. Email Detection
    if (this.enabledTypes.has('EMAIL')) {
      const emailRegex = /\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b/g;
      let match: RegExpExecArray | null;
      while ((match = emailRegex.exec(text)) !== null) {
        const cleaned = this.trimTrailingPunctuation(match[0], match.index);
        rawMatches.push({
          type: 'EMAIL',
          value: cleaned.value,
          start: cleaned.start,
          end: cleaned.end,
        });
      }
    }

    // 2. SSN Detection (US Social Security Numbers)
    if (this.enabledTypes.has('SSN')) {
      // Format: AAA-GG-SSSS where AAA is not 000, 666, or 900-999; GG is not 00; SSSS is not 0000
      const ssnRegex = /\b(?!000|666|9\d{2})(\d{3})-(?!00)(\d{2})-(?!0000)(\d{4})\b/g;
      let match: RegExpExecArray | null;
      while ((match = ssnRegex.exec(text)) !== null) {
        rawMatches.push({
          type: 'SSN',
          value: match[0],
          start: match.index,
          end: match.index + match[0].length,
        });
      }
    }

    // 3. Credit Card Detection with Luhn validation
    if (this.enabledTypes.has('CREDIT_CARD')) {
      // 13 to 19 digits with optional spaces or dashes
      const ccRegex = /\b(?:\d[ -]?){13,19}\b/g;
      let match: RegExpExecArray | null;
      while ((match = ccRegex.exec(text)) !== null) {
        const raw = match[0];
        const cleaned = this.trimTrailingPunctuation(raw, match.index);
        const digits = cleaned.value.replace(/\D/g, '');

        if (digits.length >= 13 && digits.length <= 19 && this.passesLuhnChecksum(digits)) {
          rawMatches.push({
            type: 'CREDIT_CARD',
            value: cleaned.value,
            start: cleaned.start,
            end: cleaned.end,
          });
        }
      }
    }

    // 4. Phone Number Detection
    if (this.enabledTypes.has('PHONE')) {
      // Matches standard international and domestic formats
      const phoneRegex = /(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g;
      let match: RegExpExecArray | null;
      while ((match = phoneRegex.exec(text)) !== null) {
        const cleaned = this.trimTrailingPunctuation(match[0], match.index);
        const digitCount = cleaned.value.replace(/\D/g, '').length;
        if (digitCount >= 7 && digitCount <= 15) {
          rawMatches.push({
            type: 'PHONE',
            value: cleaned.value,
            start: cleaned.start,
            end: cleaned.end,
          });
        }
      }
    }

    // 5. IP Address Detection (IPv4 & IPv6)
    if (this.enabledTypes.has('IP_ADDRESS')) {
      // IPv4
      const ipv4Regex =
        /\b(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}\b/g;
      let match: RegExpExecArray | null;
      while ((match = ipv4Regex.exec(text)) !== null) {
        rawMatches.push({
          type: 'IP_ADDRESS',
          value: match[0],
          start: match.index,
          end: match.index + match[0].length,
        });
      }

      // IPv6
      const ipv6Regex =
        /\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|\b(?:[0-9a-fA-F]{1,4}:){1,7}:[0-9a-fA-F]{1,4}\b/g;
      while ((match = ipv6Regex.exec(text)) !== null) {
        rawMatches.push({
          type: 'IP_ADDRESS',
          value: match[0],
          start: match.index,
          end: match.index + match[0].length,
        });
      }
    }

    // Resolve non-overlapping spans: longest match takes precedence
    rawMatches.sort((a, b) => {
      const lenA = a.end - a.start;
      const lenB = b.end - b.start;
      if (lenB !== lenA) return lenB - lenA; // longer first
      return a.start - b.start;
    });

    const nonOverlapping: MaskEntityMatch[] = [];
    for (const match of rawMatches) {
      const overlaps = nonOverlapping.some(
        (existing) => Math.max(match.start, existing.start) < Math.min(match.end, existing.end),
      );
      if (!overlaps) {
        nonOverlapping.push(match);
      }
    }

    nonOverlapping.sort((a, b) => a.start - b.start);
    return nonOverlapping;
  }

  public maskText(text: string): string {
    const matches = this.detect(text);
    if (matches.length === 0) return text;

    let result = '';
    let lastIndex = 0;

    for (const match of matches) {
      result += text.slice(lastIndex, match.start);
      const token = this.vault.store(match.value, match.type, this.vaultTtlSeconds);
      result += token;
      lastIndex = match.end;
    }

    result += text.slice(lastIndex);
    return result;
  }

  public maskRequest(request: ChatCompletionRequest): ChatCompletionRequest {
    const cloned: ChatCompletionRequest = JSON.parse(JSON.stringify(request));
    if (Array.isArray(cloned.messages)) {
      for (const msg of cloned.messages) {
        if (typeof msg.content === 'string') {
          msg.content = this.maskText(msg.content);
        }
      }
    }
    return cloned;
  }

  public unmaskText(text: string): string {
    const tokenRegex = /\[(?:TOKEN|PII)_[A-Z_]+_[a-zA-Z0-9_-]+\]/g;
    return text.replace(tokenRegex, (token) => {
      const record = this.vault.get(token);
      if (record && record.originalValue) {
        return record.originalValue;
      }
      // Fails safe: leaves token as-is if expired or unrecognized
      return token;
    });
  }

  public unmaskResponse(response: ChatCompletionResponse): ChatCompletionResponse {
    const cloned: ChatCompletionResponse = JSON.parse(JSON.stringify(response));
    if (Array.isArray(cloned.choices)) {
      for (const choice of cloned.choices) {
        if (choice.message && typeof choice.message.content === 'string') {
          choice.message.content = this.unmaskText(choice.message.content);
        }
      }
    }
    return cloned;
  }

  /**
   * Creates a stateful stream detokenizer function that maintains a residual buffer
   * across chunk boundaries to reconstruct surrogate tokens split in transit.
   */
  public createStreamDetokenizer(): (chunk: string) => string {
    let residualBuffer = '';

    return (chunk: string): string => {
      const combined = residualBuffer + chunk;
      residualBuffer = '';

      if (!combined) return '';

      // Find possible surrogate token prefix at the tail of combined
      // Surrogate format: [TOKEN_<CATEGORY>_<HEX>] or [PII_<CATEGORY>_<HEX>]
      const surrogatePrefixRegex =
        /\[(?:(?:T(?:O(?:K(?:E(?:N)?)?)?)?|P(?:I(?:I)?)?)(?:_[A-Z_]*(?:_[a-zA-Z0-9_-]*)?)?)?$/;
      const prefixMatch = combined.match(surrogatePrefixRegex);

      let processable = combined;
      if (prefixMatch && prefixMatch.index !== undefined) {
        // If the tail looks like a potential incomplete surrogate token prefix (max length 40)
        const tailLength = combined.length - prefixMatch.index;
        if (tailLength < 45) {
          residualBuffer = combined.slice(prefixMatch.index);
          processable = combined.slice(0, prefixMatch.index);
        }
      }

      return this.unmaskText(processable);
    };
  }

  private trimTrailingPunctuation(
    str: string,
    startIndex: number,
  ): { value: string; start: number; end: number } {
    let trimmed = str;
    let endOffset = 0;
    while (trimmed.length > 0 && /[.,;:!?'")\]>]$/.test(trimmed)) {
      trimmed = trimmed.slice(0, -1);
      endOffset++;
    }
    return {
      value: trimmed,
      start: startIndex,
      end: startIndex + str.length - endOffset,
    };
  }

  private passesLuhnChecksum(digits: string): boolean {
    let sum = 0;
    let shouldDouble = false;

    for (let i = digits.length - 1; i >= 0; i--) {
      let digit = Number.parseInt(digits.charAt(i), 10);
      if (shouldDouble) {
        digit *= 2;
        if (digit > 9) digit -= 9;
      }
      sum += digit;
      shouldDouble = !shouldDouble;
    }

    return sum % 10 === 0;
  }
}
