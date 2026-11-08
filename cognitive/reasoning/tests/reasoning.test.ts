import { describe, expect, it } from 'vitest';
import { ReasoningIsolationEngine } from '../src/security/reasoning.js';
import type { ChatCompletionResponse } from '../src/types/chat.js';

describe('Feature 42: Reasoning Extraction & Encrypted Isolation Engine', () => {
  const sampleRawResponse: ChatCompletionResponse = {
    id: 'chatcmpl-reasoning-1',
    object: 'chat.completion',
    created: 1729270000,
    model: 'deepseek-r1',
    choices: [
      {
        index: 0,
        message: {
          role: 'assistant',
          content: '<think>Let me calculate 2+2. It equals 4.</think>The answer is 4.',
        },
        finish_reason: 'stop',
      },
    ],
    usage: { prompt_tokens: 10, completion_tokens: 15, total_tokens: 25 },
  };

  it('extracts reasoning content into separate field and cleans main content', () => {
    const engine = new ReasoningIsolationEngine({ mode: 'extract' });
    const processed = engine.processResponse(sampleRawResponse);

    expect(processed.choices[0].message.content).toBe('The answer is 4.');
    expect((processed.choices[0].message as any).reasoning_content).toBe(
      'Let me calculate 2+2. It equals 4.',
    );
  });

  it('redacts reasoning content completely in redact mode', () => {
    const engine = new ReasoningIsolationEngine({ mode: 'redact' });
    const processed = engine.processResponse(sampleRawResponse);

    expect(processed.choices[0].message.content).toBe('The answer is 4.');
    expect((processed.choices[0].message as any).reasoning_content).toBeUndefined();
  });

  it('encrypts reasoning content with AES-256-GCM and decrypts accurately', () => {
    const secretKey = 'my-super-secret-vault-encryption-key';
    const engine = new ReasoningIsolationEngine({
      mode: 'encrypt',
      encryptionKey: secretKey,
    });

    const processed = engine.processResponse(sampleRawResponse);
    const encryptedReasoning = (processed.choices[0].message as any).reasoning_content;

    expect(encryptedReasoning).toBeDefined();
    expect(encryptedReasoning).not.toContain('Let me calculate');
    expect((processed.choices[0].message as any).reasoning_encrypted).toBe(true);

    // Verify round-trip decryption
    const decrypted = engine.decryptReasoning(encryptedReasoning);
    expect(decrypted).toBe('Let me calculate 2+2. It equals 4.');
  });
});
