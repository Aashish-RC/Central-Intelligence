import { beforeEach, describe, expect, it } from 'vitest';
import { PIIMaskingEngine } from '../src/security/pii.js';
import { TokenVault } from '../src/security/vault.js';
import type { ChatCompletionRequest, ChatCompletionResponse } from '../src/types/chat.js';

describe('Reversible PII Masking Engine (Clean-Room Spec)', () => {
  let mockTime = 1000000;
  const mockClock = () => mockTime;
  let vault: TokenVault;
  let engine: PIIMaskingEngine;

  beforeEach(() => {
    mockTime = 1000000;
    vault = new TokenVault(3600, { clock: mockClock } as any);
    engine = new PIIMaskingEngine({ vault } as any);
  });

  describe('Detection & PII Categories', () => {
    it('detects valid email addresses', () => {
      const text = 'Reach out to support@example.com or user.name+tag@sub.domain.co.uk for help.';
      const matches = engine.detect(text);

      const emailMatches = matches.filter((m) => m.type === 'EMAIL');
      expect(emailMatches.length).toBe(2);
      expect(emailMatches[0].value).toBe('support@example.com');
      expect(emailMatches[1].value).toBe('user.name+tag@sub.domain.co.uk');
    });

    it('detects various phone number formats', () => {
      const text = 'Call +1-800-555-0199 or (555) 123-4567 or 555-987-6543 today.';
      const matches = engine.detect(text);

      const phoneMatches = matches.filter((m) => m.type === 'PHONE');
      expect(phoneMatches.length).toBeGreaterThanOrEqual(2);
      expect(phoneMatches.some((m) => m.value.includes('555-0199'))).toBe(true);
      expect(phoneMatches.some((m) => m.value.includes('123-4567'))).toBe(true);
    });

    it('detects valid US Social Security Numbers (SSN)', () => {
      const text = 'Tax ID is 123-45-6789.';
      const matches = engine.detect(text);

      const ssnMatches = matches.filter((m) => m.type === 'SSN');
      expect(ssnMatches.length).toBe(1);
      expect(ssnMatches[0].value).toBe('123-45-6789');
    });

    it('edge case: rejects invalid SSN area codes (000, 666, 900-999)', () => {
      const text = 'Invalid SSNs: 000-12-3456, 666-12-3456, 900-12-3456, 999-12-3456.';
      const matches = engine.detect(text);
      const ssnMatches = matches.filter((m) => m.type === 'SSN');
      expect(ssnMatches.length).toBe(0);
    });

    it('edge case: detects valid Credit Cards with Luhn checksum validation', () => {
      // Valid Visa (passes Luhn)
      const validVisa = '4532 0150 0000 0007';
      // Invalid Visa (same prefix, fails Luhn)
      const invalidVisa = '4532 0150 0000 0008';

      const text = `Valid: ${validVisa}, Invalid: ${invalidVisa}`;
      const matches = engine.detect(text);

      const ccMatches = matches.filter((m) => m.type === 'CREDIT_CARD');
      expect(ccMatches.length).toBe(1);
      expect(ccMatches[0].value).toBe(validVisa);
    });

    it('detects IPv4 and IPv6 addresses', () => {
      const text = 'Servers at 192.168.1.1 and 2001:0db8:85a3:0000:0000:8a2e:0370:7334.';
      const matches = engine.detect(text);

      const ipMatches = matches.filter((m) => m.type === 'IP_ADDRESS');
      expect(ipMatches.length).toBe(2);
      expect(ipMatches.some((m) => m.value === '192.168.1.1')).toBe(true);
      expect(ipMatches.some((m) => m.value.includes('2001:0db8'))).toBe(true);
    });
  });

  describe('Edge Cases: Contiguity & Overlap', () => {
    it('edge case: punctuation contiguity ensures trailing periods and commas are not captured inside entities', () => {
      const text = 'My contact is alice@corp.com, or bob@corp.com. What is yours?';
      const matches = engine.detect(text);

      expect(matches[0].value).toBe('alice@corp.com');
      expect(matches[1].value).toBe('bob@corp.com');

      const masked = engine.maskText(text);
      expect(masked).not.toContain('alice@corp.com');
      expect(masked).toMatch(/, or /);
      expect(masked).toMatch(/\. What is yours\?/);
    });

    it('edge case: nested or adjacent entities are substituted cleanly without corrupting surrounding text', () => {
      const text = 'Send invoice to test@domain.com;192.168.1.10;123-45-6789';
      const masked = engine.maskText(text);

      expect(masked).not.toContain('test@domain.com');
      expect(masked).not.toContain('192.168.1.10');
      expect(masked).not.toContain('123-45-6789');
      expect(masked.split(';').length).toBe(3);

      const restored = engine.unmaskText(masked);
      expect(restored).toBe(text);
    });

    it('longest match takes precedence when entity spans overlap', () => {
      // Longest match takes precedence
      const text = 'Contact: user@domain.com';
      const matches = engine.detect(text);
      expect(matches.length).toBe(1);
      expect(matches[0].type).toBe('EMAIL');
    });
  });

  describe('Request & Response Masking / Unmasking', () => {
    it('maskRequest masks all message content in ChatCompletionRequest', () => {
      const request: ChatCompletionRequest = {
        model: 'gpt-4o',
        messages: [
          { role: 'system', content: 'You are helpful' },
          { role: 'user', content: 'My email is user@test.com and phone is 555-123-4567' },
        ],
      };

      const masked = engine.maskRequest(request);
      expect(masked.messages[1].content).not.toContain('user@test.com');
      expect(masked.messages[1].content).not.toContain('555-123-4567');
      expect(masked.messages[1].content).toMatch(/\[(?:TOKEN|PII)_EMAIL_/);
      expect(masked.messages[1].content).toMatch(/\[(?:TOKEN|PII)_PHONE_/);
    });

    it('unmaskResponse restores surrogate tokens in ChatCompletionResponse choices', () => {
      const emailToken = vault.store('ceo@company.com', 'EMAIL');
      const response: ChatCompletionResponse = {
        id: 'cmpl-res-1',
        object: 'chat.completion',
        created: 1000,
        model: 'gpt-4o',
        choices: [
          {
            index: 0,
            message: { role: 'assistant', content: `Confirmation sent to ${emailToken}.` },
            finish_reason: 'stop',
          },
        ],
      };

      const unmasked = engine.unmaskResponse(response);
      expect(unmasked.choices[0].message.content).toBe('Confirmation sent to ceo@company.com.');
    });

    it('edge case: unrecognized or hallucinated tokens in model output are passed through unmodified', () => {
      const unrecognizedText = 'Hello [PII_EMAIL_hallucinated_999] world';
      const restored = engine.unmaskText(unrecognizedText);
      expect(restored).toBe(unrecognizedText);
    });

    it('edge case: expired tokens fail safe and remain as surrogate tokens without throwing', () => {
      const token = vault.store('old@secret.com', 'EMAIL', 10);
      const text = `Data: ${token}`;

      // Advance clock past expiration
      mockTime += 15 * 1000;

      const restored = engine.unmaskText(text);
      expect(restored).toBe(`Data: ${token}`);
    });
  });

  describe('Streaming Incremental Restoration (createStreamDetokenizer)', () => {
    it('edge case: restores surrogate token split across chunk boundaries (2 fragments)', () => {
      const original = 'director@domain.org';
      const token = vault.store(original, 'EMAIL'); // e.g. [PII_EMAIL_xyz]
      const half = Math.floor(token.length / 2);
      const chunk1 = `Notice sent to ${token.slice(0, half)}`;
      const chunk2 = `${token.slice(half)} safely.`;

      const detokenize = engine.createStreamDetokenizer();
      const out1 = detokenize(chunk1);
      const out2 = detokenize(chunk2);

      const combined = out1 + out2;
      expect(combined).toBe(`Notice sent to ${original} safely.`);
    });

    it('edge case: restores surrogate token split across 3 byte fragments', () => {
      const original = '4532 0150 0000 0004';
      const token = vault.store(original, 'CREDIT_CARD');

      const p1 = Math.floor(token.length / 3);
      const p2 = Math.floor((token.length * 2) / 3);

      const chunk1 = token.slice(0, p1);
      const chunk2 = token.slice(p1, p2);
      const chunk3 = `${token.slice(p2)} end`;

      const detokenize = engine.createStreamDetokenizer();
      const out1 = detokenize(chunk1);
      const out2 = detokenize(chunk2);
      const out3 = detokenize(chunk3);

      expect(out1 + out2 + out3).toBe(`${original} end`);
    });

    it('emits regular text immediately without artificial buffering when no surrogate prefix is present', () => {
      const detokenize = engine.createStreamDetokenizer();

      const chunk1 = 'The quick brown fox ';
      const chunk2 = 'jumps over the lazy dog.';

      expect(detokenize(chunk1)).toBe(chunk1);
      expect(detokenize(chunk2)).toBe(chunk2);
    });

    it('emits standard bracketed text if it turns out not to be a surrogate token', () => {
      const detokenize = engine.createStreamDetokenizer();

      const chunk1 = 'Refer to [Chapter 1';
      const chunk2 = '] for details.';

      const out1 = detokenize(chunk1);
      const out2 = detokenize(chunk2);

      expect(out1 + out2).toBe('Refer to [Chapter 1] for details.');
    });
  });
});
