import crypto from 'node:crypto';
import type { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';
import type {
  ProviderAdapter,
  ProviderConfig,
  StreamTransformState,
  UpstreamRequest,
} from '../types/provider.js';

export interface BedrockConfig extends ProviderConfig {
  region?: string;
  accessKeyId?: string;
  secretAccessKey?: string;
  sessionToken?: string;
}

export class BedrockProviderAdapter implements ProviderAdapter {
  public id = 'bedrock';
  public name = 'AWS Bedrock Runtime Adapter';

  /**
   * Generates AWS SigV4 signed headers for a request.
   */
  public static signAwsSigV4(params: {
    method: string;
    url: URL;
    headers: Record<string, string>;
    body: string;
    accessKeyId: string;
    secretAccessKey: string;
    sessionToken?: string;
    region: string;
    service?: string;
    now?: Date;
  }): Record<string, string> {
    const {
      method,
      url,
      headers: inputHeaders,
      body,
      accessKeyId,
      secretAccessKey,
      sessionToken,
      region,
      service = 'bedrock',
      now = new Date(),
    } = params;

    const amzDate = now.toISOString().replace(/[:-]|\.\d{3}/g, '');
    const dateStamp = amzDate.substring(0, 8);

    const payloadHash = crypto.createHash('sha256').update(body, 'utf8').digest('hex');

    const headers: Record<string, string> = {
      ...inputHeaders,
      host: url.host,
      'x-amz-date': amzDate,
      'x-amz-content-sha256': payloadHash,
    };

    if (sessionToken) {
      headers['x-amz-security-token'] = sessionToken;
    }

    // Sort headers for canonical request
    const sortedHeaderKeys = Object.keys(headers)
      .map((k) => k.toLowerCase())
      .sort();
    const canonicalHeaders = sortedHeaderKeys.map((k) => `${k}:${headers[k].trim()}\n`).join('');
    const signedHeaders = sortedHeaderKeys.join(';');

    const canonicalRequest = [
      method.toUpperCase(),
      url.pathname,
      url.search ? url.search.substring(1) : '',
      canonicalHeaders,
      signedHeaders,
      payloadHash,
    ].join('\n');

    const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;
    const canonicalRequestHash = crypto
      .createHash('sha256')
      .update(canonicalRequest, 'utf8')
      .digest('hex');
    const stringToSign = ['AWS4-HMAC-SHA256', amzDate, credentialScope, canonicalRequestHash].join(
      '\n',
    );

    // Key derivation
    const kDate = crypto.createHmac('sha256', `AWS4${secretAccessKey}`).update(dateStamp).digest();
    const kRegion = crypto.createHmac('sha256', kDate).update(region).digest();
    const kService = crypto.createHmac('sha256', kRegion).update(service).digest();
    const kSigning = crypto.createHmac('sha256', kService).update('aws4_request').digest();

    const signature = crypto
      .createHmac('sha256', kSigning)
      .update(stringToSign, 'utf8')
      .digest('hex');

    headers['Authorization'] =
      `AWS4-HMAC-SHA256 Credential=${accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

    return headers;
  }

  public transformRequest(req: ChatCompletionRequest, config: BedrockConfig): UpstreamRequest {
    const region = config.region || process.env.AWS_REGION || 'us-east-1';
    const modelId = encodeURIComponent(req.model);
    const endpoint = config.baseUrl || `https://bedrock-runtime.${region}.amazonaws.com`;
    const action = req.stream ? 'converse-stream' : 'converse';
    const urlString = `${endpoint.replace(/\/+$/, '')}/model/${modelId}/${action}`;
    const url = new URL(urlString);

    // Bedrock Converse API payload structure
    const systemPrompts: Array<{ text: string }> = [];
    const messages: Array<{ role: 'user' | 'assistant'; content: Array<{ text: string }> }> = [];

    for (const msg of req.messages) {
      const contentText = msg.content || '';
      if (msg.role === 'system') {
        systemPrompts.push({ text: contentText });
      } else {
        messages.push({
          role: msg.role === 'assistant' ? 'assistant' : 'user',
          content: [{ text: contentText }],
        });
      }
    }

    const bedrockPayload: Record<string, unknown> = {
      messages,
      inferenceConfig: {
        ...(req.max_tokens ? { maxTokens: req.max_tokens } : {}),
        ...(req.temperature !== undefined ? { temperature: req.temperature } : {}),
        ...(req.top_p !== undefined ? { topP: req.top_p } : {}),
      },
    };

    if (systemPrompts.length > 0) {
      bedrockPayload.system = systemPrompts;
    }

    const body = JSON.stringify(bedrockPayload);
    const baseHeaders: Record<string, string> = {
      'content-type': 'application/json',
      accept: 'application/json',
    };

    const accessKeyId = config.accessKeyId || process.env.AWS_ACCESS_KEY_ID || 'dummy-access-key';
    const secretAccessKey =
      config.secretAccessKey || process.env.AWS_SECRET_ACCESS_KEY || 'dummy-secret-key';
    const sessionToken = config.sessionToken || process.env.AWS_SESSION_TOKEN;

    const signedHeaders = BedrockProviderAdapter.signAwsSigV4({
      method: 'POST',
      url,
      headers: baseHeaders,
      body,
      accessKeyId,
      secretAccessKey,
      sessionToken,
      region,
    });

    return {
      url: urlString,
      method: 'POST',
      headers: signedHeaders,
      body,
    };
  }

  public transformResponse(
    responseBody: unknown,
    status: number,
    _config: BedrockConfig,
  ): ChatCompletionResponse {
    const resp = responseBody as any;
    const text = resp?.output?.message?.content?.[0]?.text || '';
    const inputTokens = resp?.usage?.inputTokens || 0;
    const outputTokens = resp?.usage?.outputTokens || 0;

    return {
      id: `bedrock-${crypto.randomUUID()}`,
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: _config.id,
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: text,
          },
          finish_reason: resp?.stopReason === 'end_turn' ? 'stop' : resp?.stopReason || 'stop',
        },
      ],
      usage: {
        prompt_tokens: inputTokens,
        completion_tokens: outputTokens,
        total_tokens: inputTokens + outputTokens,
      },
    };
  }

  public transformStreamChunk(rawChunk: string, state: StreamTransformState): string | null {
    // Bedrock stream frames
    try {
      if (!rawChunk || !rawChunk.trim()) return null;
      let line = rawChunk.trim();
      if (line.startsWith('data:')) {
        line = line.substring(5).trim();
      }
      if (line === '[DONE]') return null;

      const parsed = JSON.parse(line);
      const text = parsed?.contentBlockDelta?.delta?.text || '';
      if (!text) return null;

      const chunkObj = {
        id: state.id,
        object: 'chat.completion.chunk',
        created: state.created,
        model: state.model,
        choices: [
          {
            index: 0,
            delta: { content: text },
            finish_reason: null,
          },
        ],
      };

      return `data: ${JSON.stringify(chunkObj)}\n\n`;
    } catch {
      return null;
    }
  }
}
