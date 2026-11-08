import { describe, expect, it } from 'vitest';
import { BedrockProviderAdapter } from '../src/providers/bedrock.js';
import { ProviderRegistry } from '../src/providers/registry.ts';

describe('Feature 16: AWS Bedrock Provider Adapter & SigV4 Signing', () => {
  it('registers in ProviderRegistry', () => {
    expect(ProviderRegistry.has('bedrock')).toBe(true);
    const adapter = ProviderRegistry.get('bedrock');
    expect(adapter).toBeDefined();
    expect(adapter?.id).toBe('bedrock');
  });

  it('generates compliant AWS SigV4 signed headers', () => {
    const adapter = new BedrockProviderAdapter();
    const req = {
      model: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      messages: [
        { role: 'system' as const, content: 'You are an AI assistant.' },
        { role: 'user' as const, content: 'Summarize quantum mechanics in one sentence.' },
      ],
      temperature: 0.5,
      max_tokens: 200,
    };

    const upstream = adapter.transformRequest(req, {
      id: 'bedrock',
      name: 'AWS Bedrock',
      baseUrl: 'https://bedrock-runtime.us-east-1.amazonaws.com',
      region: 'us-east-1',
      accessKeyId: 'AKIAIOSFODNN7EXAMPLE',
      secretAccessKey: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
    });

    expect(upstream.method).toBe('POST');
    expect(upstream.url).toContain('/model/anthropic.claude-3-5-sonnet-20241022-v2%3A0/converse');
    expect(upstream.headers['host']).toBe('bedrock-runtime.us-east-1.amazonaws.com');
    expect(upstream.headers['x-amz-date']).toBeDefined();
    expect(upstream.headers['x-amz-content-sha256']).toBeDefined();
    expect(upstream.headers['Authorization']).toMatch(
      /^AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE\/\d{8}\/us-east-1\/bedrock\/aws4_request/,
    );

    const parsedBody = JSON.parse(upstream.body!);
    expect(parsedBody.messages[0].role).toBe('user');
    expect(parsedBody.messages[0].content[0].text).toBe(
      'Summarize quantum mechanics in one sentence.',
    );
    expect(parsedBody.system[0].text).toBe('You are an AI assistant.');
    expect(parsedBody.inferenceConfig.temperature).toBe(0.5);
    expect(parsedBody.inferenceConfig.maxTokens).toBe(200);
  });

  it('transforms Converse response into standard OpenAI format', () => {
    const adapter = new BedrockProviderAdapter();
    const mockBedrockResponse = {
      output: {
        message: {
          role: 'assistant',
          content: [{ text: 'Quantum mechanics governs physical properties at atomic scales.' }],
        },
      },
      usage: {
        inputTokens: 18,
        outputTokens: 11,
        totalTokens: 29,
      },
      stopReason: 'end_turn',
    };

    const result = adapter.transformResponse(mockBedrockResponse, 200, {
      id: 'bedrock',
      name: 'AWS Bedrock',
      baseUrl: 'https://bedrock-runtime.us-east-1.amazonaws.com',
    });

    expect(result.object).toBe('chat.completion');
    expect(result.choices[0].message.content).toBe(
      'Quantum mechanics governs physical properties at atomic scales.',
    );
    expect(result.choices[0].finish_reason).toBe('stop');
    expect(result.usage.prompt_tokens).toBe(18);
    expect(result.usage.completion_tokens).toBe(11);
    expect(result.usage.total_tokens).toBe(29);
  });

  it('transforms Bedrock stream chunks to OpenAI SSE chunks', () => {
    const adapter = new BedrockProviderAdapter();
    const state = {
      model: 'anthropic.claude-3-5-sonnet-20241022-v2:0',
      id: 'chatcmpl-test-123',
      created: 1729270000,
      buffer: '',
    };

    const rawChunk = JSON.stringify({
      contentBlockDelta: {
        delta: { text: 'Hello' },
      },
    });

    const sseChunk = adapter.transformStreamChunk(rawChunk, state);
    expect(sseChunk).toBeDefined();
    expect(sseChunk).toContain('data: ');
    const parsed = JSON.parse(sseChunk!.replace('data: ', '').trim());
    expect(parsed.choices[0].delta.content).toBe('Hello');
  });
});
