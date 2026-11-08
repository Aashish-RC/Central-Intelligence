import type { ChatCompletionRequest, ChatCompletionResponse } from './chat.js';

export interface ProviderConfig {
  id: string;
  name: string;
  baseUrl: string;
  apiKey?: string;
  headers?: Record<string, string>;
  timeoutMs?: number;
}

export interface UpstreamRequest {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  headers: Record<string, string>;
  body?: string;
}

export interface ProviderAdapter {
  id: string;
  name: string;
  transformRequest(req: ChatCompletionRequest, config: ProviderConfig): UpstreamRequest;
  transformResponse(
    responseBody: unknown,
    status: number,
    config: ProviderConfig,
  ): ChatCompletionResponse;
  transformStreamChunk(rawChunk: string, state: StreamTransformState): string | null;
}

export interface StreamTransformState {
  model: string;
  id: string;
  created: number;
  buffer: string;
  customState?: Record<string, unknown>;
}
