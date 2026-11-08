import { describe, it, expect, beforeEach } from 'vitest';
import { TokenVault } from '../src/security/vault.js';
import { PIIMaskingEngine } from '../src/security/pii.js';

describe('Feature 19: Clean-Room Reversible PII Masking & Detokenization Vault', () => {
  let vault: TokenVault;
  let engine: PIIMaskingEngine;

  beforeEach(() => {
    vault = TokenVault.getInstance();
    vault.clear();
    engine = new PIIMaskingEngine();
  });

  it('detects multiple PII entities accurately', () => {
    const text = 'Reach out to test.user@example.com, call 415-555-2671, SSN 123-45-6789, or IP 192.168.1.1.';
    const matches = engine.detect(text);
    expect(matches.length).toBe(4);
    expect(matches.map(m => m.type)).toEqual(['EMAIL', 'PHONE', 'SSN', 'IP_ADDRESS']);
  });

  it('reversibly tokenizes and detokenizes unary text', () => {
    const original = 'Please transfer funds to card 4111 2222 3333 4444 and email support@stripe.com';
    const masked = engine.maskText(original);

    expect(masked).not.toContain('4111 2222 3333 4444');
    expect(masked).not.toContain('support@stripe.com');
    expect(masked).toMatch(/\[TOKEN_CREDIT_CARD_[a-f0-9]{10}\]/);
    expect(masked).toMatch(/\[TOKEN_EMAIL_[a-f0-9]{10}\]/);

    const unmasked = engine.unmaskText(masked);
    expect(unmasked).toBe(original);
  });

  it('masks ChatCompletionRequest messages and unmasks ChatCompletionResponse choices', () => {
    const req = {
      model: 'gpt-4o',
      messages: [
        { role: 'user' as const, content: 'My email is alice@company.org.' }
      ]
    };

    const maskedReq = engine.maskRequest(req);
    expect(maskedReq.messages[0].content).not.toContain('alice@company.org');
    expect(maskedReq.messages[0].content).toContain('[TOKEN_EMAIL_');

    const fakeToken = maskedReq.messages[0].content.match(/\[TOKEN_EMAIL_[a-f0-9]+\]/)![0];

    const resp = {
      id: 'chatcmpl-test',
      object: 'chat.completion' as const,
      created: 1729270000,
      model: 'gpt-4o',
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant' as const,
            content: `I have recorded your email address as ${fakeToken}.`
          },
          finish_reason: 'stop'
        }
      ],
      usage: {
        prompt_tokens: 10,
        completion_tokens: 12,
        total_tokens: 22
      }
    };

    const unmaskedResp = engine.unmaskResponse(resp);
    expect(unmaskedResp.choices[0].message.content).toBe('I have recorded your email address as alice@company.org.');
  });

  it('handles stream detokenization across split chunk boundaries without data loss', () => {
    const originalEmail = 'john.doe@enterprise.com';
    const token = vault.store(originalEmail, 'EMAIL');

    // Simulate token split across two streaming chunks:
    const half = Math.floor(token.length / 2);
    const chunk1 = `Hello user, your email [${token.slice(1, half)}`;
    const chunk2 = `${token.slice(half)} has been verified.`;

    const streamDetokenizer = engine.createStreamDetokenizer();

    const output1 = streamDetokenizer(chunk1);
    // Chunk 1 has an unclosed token prefix, so the prefix should be buffered
    expect(output1).toBe('Hello user, your email ');

    const output2 = streamDetokenizer(chunk2);
    // Chunk 2 completes the token and immediately detokenizes
    expect(output2).toBe(`${originalEmail} has been verified.`);
  });
});
