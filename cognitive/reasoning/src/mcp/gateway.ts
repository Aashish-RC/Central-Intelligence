// Belongs to Layer 1 tool registry. Temporarily hosted in the gateway. To be moved out.

import type { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';

export interface MCPToolDefinition {
  name: string;
  description: string;
  inputSchema: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
  handler: (args: Record<string, unknown>) => Promise<unknown> | unknown;
}
export type McpToolDefinition = MCPToolDefinition;

export interface OpenAIToolFormat {
  type: 'function';
  function: {
    name: string;
    description: string;
    parameters: {
      type: 'object';
      properties: Record<string, unknown>;
      required?: string[];
    };
  };
}

export class MCPGateway {
  private static instance: MCPGateway;
  private tools: Map<string, MCPToolDefinition> = new Map();

  public static getInstance(): MCPGateway {
    if (!MCPGateway.instance) {
      MCPGateway.instance = new MCPGateway();
    }
    return MCPGateway.instance;
  }

  public registerTool(tool: MCPToolDefinition): void {
    this.tools.set(tool.name, tool);
  }

  public getTool(name: string): MCPToolDefinition | undefined {
    return this.tools.get(name);
  }

  public listTools(): MCPToolDefinition[] {
    return Array.from(this.tools.values());
  }

  /**
   * Exports registered MCP tools in OpenAI chat tool format.
   */
  public toOpenAITools(): OpenAIToolFormat[] {
    return Array.from(this.tools.values()).map((tool) => ({
      type: 'function',
      function: {
        name: tool.name,
        description: tool.description,
        parameters: tool.inputSchema,
      },
    }));
  }

  /**
   * Injects registered MCP tools into a ChatCompletionRequest if tools are not already set.
   */
  public injectTools(request: ChatCompletionRequest): ChatCompletionRequest {
    if (this.tools.size === 0) return request;
    const mcpTools = this.toOpenAITools();

    return {
      ...request,
      tools: [...(request.tools || []), ...mcpTools] as any,
      tool_choice: request.tool_choice || 'auto',
    };
  }

  /**
   * Executes a single tool call against registered MCP tools.
   */
  public async executeToolCall(toolCall: {
    id: string;
    type?: string;
    function: { name: string; arguments: string | Record<string, unknown> };
  }): Promise<{ tool_call_id: string; content: string; isError?: boolean }> {
    const tool = this.tools.get(toolCall.function.name);
    if (!tool) {
      return {
        tool_call_id: toolCall.id,
        content: JSON.stringify({
          error: `Tool '${toolCall.function.name}' not found on MCP gateway.`,
        }),
        isError: true,
      };
    }

    try {
      const args =
        typeof toolCall.function.arguments === 'string'
          ? JSON.parse(toolCall.function.arguments)
          : toolCall.function.arguments;

      const result = await tool.handler(args);
      return {
        tool_call_id: toolCall.id,
        content: typeof result === 'string' ? result : JSON.stringify(result),
      };
    } catch (err: any) {
      return {
        tool_call_id: toolCall.id,
        content: JSON.stringify({ error: err.message || 'Execution failed' }),
        isError: true,
      };
    }
  }

  /**
   * Runs an autonomous agent execution loop:
   * - Injects MCP tools
   * - Calls modelDispatcher
   * - If model returns tool_calls, executes them and loops back
   * - Terminates on final stop or maxTurns limit
   */
  public async runAgentLoop(
    initialRequest: ChatCompletionRequest,
    modelDispatcher: (req: ChatCompletionRequest) => Promise<ChatCompletionResponse>,
    maxTurns = 5,
  ): Promise<ChatCompletionResponse> {
    let currentRequest = this.injectTools(initialRequest);
    let turns = 0;

    while (turns < maxTurns) {
      turns += 1;
      const response = await modelDispatcher(currentRequest);
      const firstChoice = response.choices[0];

      if (
        !firstChoice ||
        firstChoice.finish_reason !== 'tool_calls' ||
        !firstChoice.message?.tool_calls?.length
      ) {
        return response;
      }

      // Execute all tool calls in parallel
      const toolCalls = firstChoice.message.tool_calls;
      const toolResults = await Promise.all(toolCalls.map((tc) => this.executeToolCall(tc)));

      // Append assistant message with tool calls and tool responses to request
      const updatedMessages = [
        ...currentRequest.messages,
        {
          role: 'assistant' as const,
          content: firstChoice.message.content || '',
          tool_calls: toolCalls,
        },
        ...toolResults.map((tr) => ({
          role: 'tool' as const,
          tool_call_id: tr.tool_call_id,
          content: tr.content,
        })),
      ];

      currentRequest = {
        ...currentRequest,
        messages: updatedMessages,
      };
    }

    throw new Error(`MCP Agent loop exceeded maximum turns (${maxTurns}).`);
  }

  public clear(): void {
    this.tools.clear();
  }
}
