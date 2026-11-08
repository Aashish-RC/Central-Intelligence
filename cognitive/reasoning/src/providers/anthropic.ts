import type { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';
import type {
  ProviderAdapter,
  ProviderConfig,
  StreamTransformState,
  UpstreamRequest,
} from '../types/provider.js';

interface AnthropicMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface AnthropicResponse {
  id: string;
  type: string;
  role: string;
  content: Array<{ type: string; text?: string }>;
  model: string;
  stop_reason: string | null;
  usage: {
    input_tokens: number;
    output_tokens: number;
    cache_read_input_tokens?: number;
    cache_creation_input_tokens?: number;
  };
}

export class AnthropicAdapter implements ProviderAdapter {
  public id = 'anthropic';
  public name = 'Anthropic';

  public transformRequest(req: ChatCompletionRequest, config: ProviderConfig): UpstreamRequest {
    const url = `${config.baseUrl.replace(/\/+$/, '')}/v1/messages`;
    const headers: Record<string, string> = {
      'content-type': 'application/json',
      'x-api-key': config.apiKey || '',
      'anthropic-version': '2023-06-01',
      ...(config.headers || {}),
    };

    // Extract system prompt
    let systemPrompt: string | undefined;
    const anthropicMessages: AnthropicMessage[] = [];

    for (const msg of req.messages) {
      if (msg.role === 'system') {
        systemPrompt = (systemPrompt ? `${systemPrompt}\n\n` : '') + (msg.content || '');
      } else if (msg.role === 'user' || msg.role === 'assistant') {
        anthropicMessages.push({
          role: msg.role,
          content: msg.content || '',
        });
      }
    }

    const payload: Record<string, unknown> = {
      model: req.model,
      messages: anthropicMessages,
      max_tokens: req.max_tokens || req.max_completion_tokens || 4096,
      stream: req.stream || false,
    };

    if (systemPrompt) {
      payload.system = systemPrompt;
    }
    if (req.temperature !== undefined) {
      payload.temperature = req.temperature;
    }
    if (req.top_p !== undefined) {
      payload.top_p = req.top_p;
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
    const ant = responseBody as AnthropicResponse;
    const fullText = (ant.content || [])
      .filter((c) => c.type === 'text')
      .map((c) => c.text || '')
      .join('');

    return {
      id: ant.id || `chatcmpl-${Date.now()}`,
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: ant.model || 'claude',
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: fullText,
          },
          finish_reason:
            ant.stop_reason === 'end_turn' ? 'stop' : (ant.stop_reason as any) || 'stop',
        },
      ],
      usage: {
        prompt_tokens: ant.usage?.input_tokens || 0,
        completion_tokens: ant.usage?.output_tokens || 0,
        total_tokens: (ant.usage?.input_tokens || 0) + (ant.usage?.output_tokens || 0),
        prompt_tokens_details: {
          cached_tokens: ant.usage?.cache_read_input_tokens || 0,
        },
      },
    };
  }

  public transformStreamChunk(rawChunk: string, state: StreamTransformState): string | null {
    // Look for content_block_delta in Anthropic SSE stream
    if (!rawChunk.startsWith('data:')) return null;
    const jsonStr = rawChunk.replace(/^data:\s*/, '').trim();
    if (!jsonStr || jsonStr === '[DONE]') return null;

    try {
      const parsed = JSON.parse(jsonStr);
      if (parsed.type === 'content_block_delta' && parsed.delta?.text) {
        const deltaText = parsed.delta.text;
        const normalizedChunk = {
          id: state.id,
          object: 'chat.completion.chunk',
          created: state.created,
          model: state.model,
          choices: [
            {
              index: 0,
              delta: {
                content: deltaText,
              },
              finish_reason: null,
            },
          ],
        };
        return `data: ${JSON.stringify(normalizedChunk)}\n\n`;
      }

      if (parsed.type === 'message_stop') {
        const finalChunk = {
          id: state.id,
          object: 'chat.completion.chunk',
          created: state.created,
          model: state.model,
          choices: [
            {
              index: 0,
              delta: {},
              finish_reason: 'stop',
            },
          ],
        };
        return `data: ${JSON.stringify(finalChunk)}\n\ndata: [DONE]\n\n`;
      }
    } catch {
      // Ignore non-JSON lines (e.g. ping/heartbeat)
    }

    return null;
  }
}
