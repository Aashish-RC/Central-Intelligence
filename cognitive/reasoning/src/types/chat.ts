import { z } from 'zod';

export const ToolCallSchema = z.object({
  id: z.string(),
  type: z.literal('function'),
  function: z.object({
    name: z.string(),
    arguments: z.string(),
  }),
});

export const ToolDefinitionSchema = z.object({
  type: z.literal('function'),
  function: z.object({
    name: z.string(),
    description: z.string().optional(),
    parameters: z.record(z.unknown()),
  }),
});

export const ChatMessageSchema = z.object({
  role: z.enum(['system', 'user', 'assistant', 'tool']),
  content: z.string().nullable(),
  name: z.string().optional(),
  tool_call_id: z.string().optional(),
  tool_calls: z.array(ToolCallSchema).optional(),
});

export const ChatCompletionRequestSchema = z.object({
  model: z.string().min(1, 'Model name is required'),
  messages: z.array(ChatMessageSchema).min(1, 'At least one message is required'),
  temperature: z.number().min(0).max(2).optional(),
  top_p: z.number().min(0).max(1).optional(),
  n: z.number().int().min(1).optional(),
  stream: z.boolean().optional(),
  stop: z.union([z.string(), z.array(z.string())]).optional(),
  max_tokens: z.number().int().positive().optional(),
  max_completion_tokens: z.number().int().positive().optional(),
  presence_penalty: z.number().min(-2).max(2).optional(),
  frequency_penalty: z.number().min(-2).max(2).optional(),
  user: z.string().optional(),
  tools: z.array(ToolDefinitionSchema).optional(),
  tool_choice: z
    .union([
      z.enum(['none', 'auto', 'required']),
      z.object({
        type: z.literal('function'),
        function: z.object({ name: z.string() }),
      }),
    ])
    .optional(),
  seed: z.number().int().optional(),
  response_format: z
    .object({
      type: z.enum(['text', 'json_object']),
    })
    .optional(),
});

export type ChatMessage = z.infer<typeof ChatMessageSchema>;
export type ChatCompletionMessage = ChatMessage;
export type ToolCall = z.infer<typeof ToolCallSchema>;
export type ToolDefinition = z.infer<typeof ToolDefinitionSchema>;
export type ChatCompletionRequest = z.infer<typeof ChatCompletionRequestSchema>;

export interface ChatCompletionChoice {
  index: number;
  message: ChatMessage;
  finish_reason: 'stop' | 'length' | 'tool_calls' | 'content_filter' | null;
}

export interface ChatCompletionUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  prompt_tokens_details?: {
    cached_tokens?: number;
  };
  completion_tokens_details?: {
    reasoning_tokens?: number;
  };
}

export interface ChatCompletionResponse {
  id: string;
  object: 'chat.completion';
  created: number;
  model: string;
  choices: ChatCompletionChoice[];
  usage?: ChatCompletionUsage;
  system_fingerprint?: string;
}

export interface ChatCompletionChunkDelta {
  role?: 'assistant';
  content?: string | null;
  reasoning_content?: string | null;
  tool_calls?: Array<{
    index: number;
    id?: string;
    type?: 'function';
    function?: {
      name?: string;
      arguments?: string;
    };
  }>;
}

export interface ChatCompletionChunkChoice {
  index: number;
  delta: ChatCompletionChunkDelta;
  finish_reason: 'stop' | 'length' | 'tool_calls' | 'content_filter' | null;
}

export interface ChatCompletionChunk {
  id: string;
  object: 'chat.completion.chunk';
  created: number;
  model: string;
  choices: ChatCompletionChunkChoice[];
  usage?: ChatCompletionUsage;
}
