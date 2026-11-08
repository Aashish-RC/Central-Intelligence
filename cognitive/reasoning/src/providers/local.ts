import type { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';
import type {
  ProviderAdapter,
  ProviderConfig,
  StreamTransformState,
  UpstreamRequest,
} from '../types/provider.js';

/**
 * Adapter for OpenAI-compatible local runtimes (llama.cpp server, LocalAI, vLLM, Ollama OpenAI-compat endpoint).
 */
export class OpenAICompatibleLocalAdapter implements ProviderAdapter {
  constructor(
    public id = 'localai',
    public name = 'OpenAI Compatible Local Runtime',
  ) {}

  public transformRequest(req: ChatCompletionRequest, config: ProviderConfig): UpstreamRequest {
    const cleanBaseUrl = config.baseUrl.replace(/\/+$/, '');
    // If baseUrl ends in /v1, use /v1/chat/completions; otherwise append /v1/chat/completions or /chat/completions
    const url = cleanBaseUrl.endsWith('/v1')
      ? `${cleanBaseUrl}/chat/completions`
      : `${cleanBaseUrl}/v1/chat/completions`;

    const headers: Record<string, string> = {
      'content-type': 'application/json',
      ...(config.apiKey ? { authorization: `Bearer ${config.apiKey}` } : {}),
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
