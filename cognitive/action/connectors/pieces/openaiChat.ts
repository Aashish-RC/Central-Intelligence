/**
 * OpenAI Chat Completion Connector.
 *
 * Adapted from ActivePieces community/openai piece pattern (MIT License).
 * No code copied — pure native TypeScript implementation.
 * License: MIT (ActivePieces community piece pattern)
 */

import type { ConnectorPiece, ConnectorContext } from '../connectorContract.js';

export const openaiChatPiece: ConnectorPiece = {
  pieceId: 'openai',
  displayName: 'OpenAI',
  description: 'Interact with OpenAI models for chat completion and more.',
  logoEmoji: '🤖',
  authType: 'secret_text',
  authFields: [
    {
      key: 'api_key',
      displayName: 'OpenAI API Key',
      required: true,
      type: 'password',
    },
  ],
  category: 'AI & ML',
  licenseNote: 'Adapted from ActivePieces community/openai (MIT). No upstream code copied.',
  actions: [
    {
      actionId: 'chat_completion',
      displayName: 'Chat Completion',
      description: 'Send a prompt to an OpenAI chat model and receive a completion.',
      props: [
        {
          key: 'model',
          displayName: 'Model',
          description: 'OpenAI model to use.',
          type: 'dropdown',
          required: true,
          defaultValue: 'gpt-4o-mini',
          options: [
            { label: 'GPT-4o', value: 'gpt-4o' },
            { label: 'GPT-4o Mini', value: 'gpt-4o-mini' },
            { label: 'GPT-3.5 Turbo', value: 'gpt-3.5-turbo' },
            { label: 'GPT-4 Turbo', value: 'gpt-4-turbo' },
          ],
        },
        {
          key: 'system_prompt',
          displayName: 'System Prompt',
          description: 'Optional system instruction for the model.',
          type: 'long_text',
          required: false,
          defaultValue: 'You are a helpful assistant.',
        },
        {
          key: 'user_message',
          displayName: 'User Message',
          description: 'The user message to send to the model.',
          type: 'long_text',
          required: true,
        },
        {
          key: 'temperature',
          displayName: 'Temperature',
          description: 'Sampling temperature (0.0 – 2.0). Default: 0.7.',
          type: 'number',
          required: false,
          defaultValue: 0.7,
        },
        {
          key: 'max_tokens',
          displayName: 'Max Tokens',
          description: 'Maximum tokens in the completion. Default: 1024.',
          type: 'number',
          required: false,
          defaultValue: 1024,
        },
      ],
      async run(ctx: ConnectorContext): Promise<unknown> {
        const apiKey = ctx.auth?.api_key;
        if (!apiKey) throw new Error('OpenAI API key is required.');

        const messages: Array<{ role: string; content: string }> = [];

        const systemPrompt = ctx.propsValue.system_prompt as string | undefined;
        if (systemPrompt) {
          messages.push({ role: 'system', content: systemPrompt });
        }

        messages.push({ role: 'user', content: String(ctx.propsValue.user_message) });

        const requestBody = {
          model: ctx.propsValue.model || 'gpt-4o-mini',
          messages,
          temperature: Number(ctx.propsValue.temperature ?? 0.7),
          max_tokens: Number(ctx.propsValue.max_tokens ?? 1024),
        };

        const res = await fetch('https://api.openai.com/v1/chat/completions', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${apiKey}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestBody),
        });

        if (!res.ok) {
          const err = await res.text();
          throw new Error(`OpenAI API error (${res.status}): ${err}`);
        }

        const data = (await res.json()) as {
          id: string;
          choices: Array<{ message: { content: string }; finish_reason: string }>;
          usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
        };

        return {
          id: data.id,
          content: data.choices[0]?.message.content ?? '',
          finishReason: data.choices[0]?.finish_reason,
          usage: data.usage,
        };
      },
    },
  ],
};
