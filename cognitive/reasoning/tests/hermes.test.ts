import { describe, expect, it } from 'vitest';
import { HermesAgentAdapter, type HermesTool } from '../src/agents/hermesAdapter.js';
import type {
  ChatCompletionRequest,
  ChatCompletionResponse,
} from '../src/types/chat.js';

describe('HermesAgentAdapter', () => {
  it('correctly registers tools and exports standard tool schemas', () => {
    const agent = new HermesAgentAdapter();
    const weatherTool: HermesTool = {
      name: 'get_weather',
      description: 'Fetch current weather for a city',
      parameters: {
        type: 'object',
        properties: {
          location: { type: 'string', description: 'City name' },
        },
        required: ['location'],
      },
      handler: async ({ location }) => ({ location, temp: 22, condition: 'Clear' }),
    };

    agent.registerTool(weatherTool);
    expect(agent.getTools()).toHaveLength(1);

    const specs = agent.toToolSpecs();
    expect(specs).toHaveLength(1);
    expect(specs[0].function.name).toBe('get_weather');
    expect(specs[0].function.parameters.required).toEqual(['location']);
  });

  it('performs multi-turn reasoning and autonomous tool calling', async () => {
    let toolExecutionCount = 0;
    const weatherTool: HermesTool = {
      name: 'get_weather',
      description: 'Fetch current weather for a city',
      parameters: {
        type: 'object',
        properties: {
          location: { type: 'string' },
        },
      },
      handler: async ({ location }) => {
        toolExecutionCount++;
        return { location, temperature: 18, condition: 'Sunny' };
      },
    };

    const agent = new HermesAgentAdapter({
      tools: [weatherTool],
      maxTurns: 5,
    });

    // Mock Gateway dispatcher simulating LLM decision:
    // Turn 1: Model decides to call get_weather tool
    // Turn 2: Model synthesizes reasoning with tool response
    const mockGatewayDispatcher = async (
      req: ChatCompletionRequest,
    ): Promise<ChatCompletionResponse> => {
      const lastMessage = req.messages[req.messages.length - 1];

      if (lastMessage.role === 'user') {
        return {
          id: 'chatcmpl-turn-1',
          object: 'chat.completion',
          created: Date.now(),
          model: req.model,
          choices: [
            {
              index: 0,
              finish_reason: 'tool_calls',
              message: {
                role: 'assistant',
                content: 'Checking current weather in Tokyo...',
                tool_calls: [
                  {
                    id: 'call_123',
                    type: 'function',
                    function: {
                      name: 'get_weather',
                      arguments: JSON.stringify({ location: 'Tokyo' }),
                    },
                  },
                ],
              },
            },
          ],
          usage: { prompt_tokens: 45, completion_tokens: 15, total_tokens: 60 },
        };
      }

      if (lastMessage.role === 'tool') {
        const toolData = JSON.parse(lastMessage.content || '{}');
        return {
          id: 'chatcmpl-turn-2',
          object: 'chat.completion',
          created: Date.now(),
          model: req.model,
          choices: [
            {
              index: 0,
              finish_reason: 'stop',
              message: {
                role: 'assistant',
                content: `The weather in ${toolData.location} is currently ${toolData.condition} with a temperature of ${toolData.temperature}°C.`,
              },
            },
          ],
          usage: { prompt_tokens: 70, completion_tokens: 25, total_tokens: 95 },
        };
      }

      throw new Error(`Unexpected message role: ${lastMessage.role}`);
    };

    const result = await agent.run(
      'What is the weather in Tokyo right now?',
      mockGatewayDispatcher,
    );

    expect(toolExecutionCount).toBe(1);
    expect(result.turns).toBe(2);
    expect(result.toolCallsExecuted).toBe(1);
    expect(result.finalResponse).toContain('Tokyo');
    expect(result.finalResponse).toContain('Sunny');
    expect(result.finalResponse).toContain('18°C');
    expect(result.usage?.total_tokens).toBe(155);
  });

  it('persists conversation memory across multiple user turns', async () => {
    const agent = new HermesAgentAdapter();

    const mockDispatcher = async (
      req: ChatCompletionRequest,
    ): Promise<ChatCompletionResponse> => {
      const userMessages = req.messages.filter((m) => m.role === 'user');
      const responseContent =
        userMessages.length === 1
          ? 'Hello! Nice to meet you.'
          : `I recall your previous message: "${userMessages[0].content}". You now said: "${userMessages[1].content}".`;

      return {
        id: `chatcmpl-${userMessages.length}`,
        object: 'chat.completion',
        created: Date.now(),
        model: req.model,
        choices: [
          {
            index: 0,
            finish_reason: 'stop',
            message: {
              role: 'assistant',
              content: responseContent,
            },
          },
        ],
      };
    };

    // First interaction
    const round1 = await agent.run('My favorite language is TypeScript.', mockDispatcher);
    expect(round1.finalResponse).toBe('Hello! Nice to meet you.');

    // Second interaction - verifying conversation history is preserved
    const round2 = await agent.run('What is my favorite language?', mockDispatcher);
    expect(round2.finalResponse).toContain('My favorite language is TypeScript.');

    const memory = agent.getMemory();
    expect(memory.length).toBeGreaterThanOrEqual(4); // system, user1, assistant1, user2, assistant2
  });

  it('handles tool execution failures gracefully and feeds error back to model', async () => {
    const faultyTool: HermesTool = {
      name: 'broken_calculator',
      description: 'A tool that fails',
      parameters: { type: 'object', properties: {} },
      handler: () => {
        throw new Error('Database connection timed out');
      },
    };

    const agent = new HermesAgentAdapter({ tools: [faultyTool] });

    const mockDispatcher = async (
      req: ChatCompletionRequest,
    ): Promise<ChatCompletionResponse> => {
      const last = req.messages[req.messages.length - 1];

      if (last.role === 'user') {
        return {
          id: 'chatcmpl-1',
          object: 'chat.completion',
          created: Date.now(),
          model: req.model,
          choices: [
            {
              index: 0,
              finish_reason: 'tool_calls',
              message: {
                role: 'assistant',
                content: 'Calling broken tool...',
                tool_calls: [
                  {
                    id: 'call_err',
                    type: 'function',
                    function: { name: 'broken_calculator', arguments: '{}' },
                  },
                ],
              },
            },
          ],
        };
      }

      if (last.role === 'tool') {
        return {
          id: 'chatcmpl-2',
          object: 'chat.completion',
          created: Date.now(),
          model: req.model,
          choices: [
            {
              index: 0,
              finish_reason: 'stop',
              message: {
                role: 'assistant',
                content: 'The tool failed with an error, but I recovered.',
              },
            },
          ],
        };
      }

      throw new Error('Unexpected');
    };

    const result = await agent.run('Calculate something', mockDispatcher);
    expect(result.finalResponse).toContain('The tool failed with an error, but I recovered.');
  });
});
