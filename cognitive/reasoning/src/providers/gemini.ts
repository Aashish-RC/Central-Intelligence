import type { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';
import type {
  ProviderAdapter,
  ProviderConfig,
  StreamTransformState,
  UpstreamRequest,
} from '../types/provider.js';

export class GeminiProviderAdapter implements ProviderAdapter {
  public id = 'gemini';
  public name = 'Google Gemini REST API';

  public transformRequest(req: ChatCompletionRequest, config: ProviderConfig): UpstreamRequest {
    const baseUrl =
      config.baseUrl.replace(/\/$/, '') || 'https://generativelanguage.googleapis.com';
    const cleanModel = req.model.replace(/^gemini\//, '').replace(/^google\//, '');
    const isStream = req.stream === true;
    const action = isStream ? 'streamGenerateContent?alt=sse' : 'generateContent';

    const url = `${baseUrl}/v1beta/models/${cleanModel}:${action}`;

    const headers: Record<string, string> = {
      'content-type': 'application/json',
      ...config.headers,
    };

    if (config.apiKey) {
      headers['x-goog-api-key'] = config.apiKey;
    }

    // Separate system messages from chat contents
    let systemInstruction: { parts: { text: string }[] } | undefined = undefined;
    const contents: Array<{ role: 'user' | 'model'; parts: { text: string }[] }> = [];

    for (const msg of req.messages) {
      if (msg.role === 'system') {
        systemInstruction = {
          parts: [{ text: msg.content || '' }],
        };
      } else {
        const role = msg.role === 'assistant' ? 'model' : 'user';
        contents.push({
          role,
          parts: [{ text: msg.content || '' }],
        });
      }
    }

    const payload: Record<string, unknown> = {
      contents,
    };

    if (systemInstruction) {
      payload.systemInstruction = systemInstruction;
    }

    const generationConfig: Record<string, unknown> = {};
    if (req.temperature !== undefined) generationConfig.temperature = req.temperature;
    if (req.top_p !== undefined) generationConfig.topP = req.top_p;
    if (req.max_tokens !== undefined) generationConfig.maxOutputTokens = req.max_tokens;

    if (Object.keys(generationConfig).length > 0) {
      payload.generationConfig = generationConfig;
    }

    return {
      url,
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    };
  }

  public transformResponse(
    responseBody: unknown,
    _status: number,
    _config: ProviderConfig,
  ): ChatCompletionResponse {
    const raw = responseBody as any;
    const candidate = raw?.candidates?.[0];
    const text = candidate?.content?.parts?.map((p: any) => p.text).join('') || '';
    const finishReason = candidate?.finishReason?.toLowerCase() || 'stop';

    const usage = raw?.usageMetadata;
    const promptTokens = usage?.promptTokenCount || 0;
    const completionTokens = usage?.candidatesTokenCount || 0;

    return {
      id: `chatcmpl-${Date.now()}`,
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: raw?.modelVersion || 'gemini',
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: text,
          },
          finish_reason: finishReason === 'stop' ? 'stop' : finishReason,
        },
      ],
      usage: {
        prompt_tokens: promptTokens,
        completion_tokens: completionTokens,
        total_tokens: promptTokens + completionTokens,
      },
    };
  }

  public transformStreamChunk(rawChunk: string, state: StreamTransformState): string | null {
    const trimmed = rawChunk.trim();
    if (!trimmed || !trimmed.startsWith('data:')) {
      return null;
    }

    const jsonStr = trimmed.slice(5).trim();
    if (jsonStr === '[DONE]') {
      return 'data: [DONE]\n\n';
    }

    try {
      const parsed = JSON.parse(jsonStr);
      const text = parsed?.candidates?.[0]?.content?.parts?.map((p: any) => p.text).join('') || '';
      const finishReason = parsed?.candidates?.[0]?.finishReason?.toLowerCase() || null;

      const chunk = {
        id: state.id,
        object: 'chat.completion.chunk',
        created: state.created,
        model: state.model,
        choices: [
          {
            index: 0,
            delta: {
              content: text,
            },
            finish_reason: finishReason === 'stop' ? 'stop' : finishReason,
          },
        ],
      };

      return `data: ${JSON.stringify(chunk)}\n\n`;
    } catch {
      return null;
    }
  }
}
