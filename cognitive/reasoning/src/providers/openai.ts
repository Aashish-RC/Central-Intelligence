import type { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';
import type {
  ProviderAdapter,
  ProviderConfig,
  StreamTransformState,
  UpstreamRequest,
} from '../types/provider.js';

export class OpenAIAdapter implements ProviderAdapter {
  public id = 'openai';
  public name = 'OpenAI';

  public transformRequest(req: ChatCompletionRequest, config: ProviderConfig): UpstreamRequest {
    const url = `${config.baseUrl.replace(/\/+$/, '')}/chat/completions`;
    const headers: Record<string, string> = {
      'content-type': 'application/json',
      authorization: `Bearer ${config.apiKey || ''}`,
      ...(config.headers || {}),
    };

    return {
      url,
      method: 'POST',
      headers,
      body: JSON.stringify(req),
    };
  }

  public transformResponse(
    responseBody: unknown,
    _status: number,
    _config: ProviderConfig,
  ): ChatCompletionResponse {
    return responseBody as ChatCompletionResponse;
  }

  public transformStreamChunk(rawChunk: string, _state: StreamTransformState): string | null {
    // OpenAI SSE format is standard; pass through valid SSE lines
    return rawChunk;
  }
}
