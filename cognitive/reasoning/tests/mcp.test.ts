import { beforeEach, describe, expect, it } from 'vitest';
import { MCPGateway } from '../src/mcp/gateway.js';
import type { ChatCompletionRequest, ChatCompletionResponse } from '../src/types/chat.js';

describe('Feature 17: Model Context Protocol (MCP) Gateway & Agent Loop', () => {
  let mcp: MCPGateway;

  beforeEach(() => {
    mcp = MCPGateway.getInstance();
    mcp.clear();
  });

  it('registers tools and exports OpenAI-compatible function schemas', () => {
    mcp.registerTool({
      name: 'get_weather',
      description: 'Get current temperature and conditions for a city.',
      inputSchema: {
        type: 'object',
        properties: {
          city: { type: 'string' },
          unit: { type: 'string', enum: ['celsius', 'fahrenheit'] },
        },
        required: ['city'],
      },
      handler: async (args) => {
        return { city: args.city, temp: 22, condition: 'Sunny' };
      },
    });

    const openAITools = mcp.toOpenAITools();
    expect(openAITools.length).toBe(1);
    expect(openAITools[0].type).toBe('function');
    expect(openAITools[0].function.name).toBe('get_weather');
    expect(openAITools[0].function.description).toBe(
      'Get current temperature and conditions for a city.',
    );
    expect(openAITools[0].function.parameters.required).toContain('city');
  });

  it('executes tool call directly with JSON string arguments', async () => {
    mcp.registerTool({
      name: 'calculate_sum',
      description: 'Add two numbers',
      inputSchema: {
        type: 'object',
        properties: { a: { type: 'number' }, b: { type: 'number' } },
        required: ['a', 'b'],
      },
      handler: (args) => {
        return { result: Number(args.a) + Number(args.b) };
      },
    });

    const execution = await mcp.executeToolCall({
      id: 'call_abc123',
      function: {
        name: 'calculate_sum',
        arguments: JSON.stringify({ a: 15, b: 27 }),
      },
    });

    expect(execution.tool_call_id).toBe('call_abc123');
    expect(JSON.parse(execution.content)).toEqual({ result: 42 });
  });

  it('orchestrates autonomous multi-turn agent tool loop', async () => {
    // Register tool
    mcp.registerTool({
      name: 'lookup_user_status',
      description: 'Lookup user status by ID',
      inputSchema: {
        type: 'object',
        properties: { userId: { type: 'string' } },
        required: ['userId'],
      },
      handler: (args) => ({ status: 'ACTIVE', tier: 'PRO', userId: args.userId }),
    });

    // Mock dispatcher that simulates a 2-step LLM conversation:
    // Turn 1: Model requests tool call
    // Turn 2: Model receives tool result and outputs final answer
    let callCount = 0;
    const mockDispatcher = async (req: ChatCompletionRequest): Promise<ChatCompletionResponse> => {
      callCount += 1;
      if (callCount === 1) {
        return {
          id: 'chatcmpl-mock-1',
          object: 'chat.completion',
          created: 1729270000,
          model: 'gpt-4o',
          choices: [
            {
              index: 0,
              message: {
                role: 'assistant',
                content: null as any,
                tool_calls: [
                  {
                    id: 'call_user_99',
                    type: 'function',
                    function: {
                      name: 'lookup_user_status',
                      arguments: JSON.stringify({ userId: 'u_12345' }),
                    },
                  },
                ],
              },
              finish_reason: 'tool_calls',
            },
          ],
          usage: { prompt_tokens: 20, completion_tokens: 15, total_tokens: 35 },
        };
      } else {
        // Turn 2
        return {
          id: 'chatcmpl-mock-2',
          object: 'chat.completion',
          created: 1729270001,
          model: 'gpt-4o',
          choices: [
            {
              index: 0,
              message: {
                role: 'assistant',
                content: 'User u_12345 is an ACTIVE customer on the PRO tier.',
              },
              finish_reason: 'stop',
            },
          ],
          usage: { prompt_tokens: 50, completion_tokens: 12, total_tokens: 62 },
        };
      }
    };

    const initialRequest: ChatCompletionRequest = {
      model: 'gpt-4o',
      messages: [{ role: 'user', content: 'What is the status of user u_12345?' }],
    };

    const finalResponse = await mcp.runAgentLoop(initialRequest, mockDispatcher);

    expect(callCount).toBe(2);
    expect(finalResponse.choices[0].finish_reason).toBe('stop');
    expect(finalResponse.choices[0].message.content).toBe(
      'User u_12345 is an ACTIVE customer on the PRO tier.',
    );
  });
});
