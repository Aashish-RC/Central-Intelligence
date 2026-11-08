import type { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';
import type {
  ProviderAdapter,
  ProviderConfig,
  StreamTransformState,
  UpstreamRequest,
} from '../types/provider.js';

export class OllamaAdapter implements ProviderAdapter {
  public id = 'ollama';
  public name = 'Ollama';

  public transformRequest(req: ChatCompletionRequest, config: ProviderConfig): UpstreamRequest {
    // Ollama supports native /v1/chat/completions or /api/chat
    const url = `${config.baseUrl.replace(/\/+$/, '')}/v1/chat/completions`;
    const headers: Record<string, string> = {
      'content-type': 'application/json',
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
    return rawChunk;
  }
}
