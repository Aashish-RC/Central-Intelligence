/**
 * Layer 4 Reasoning: Hermes Agent Adapter
 *
 * Wraps NousResearch Hermes Agent as an autonomous cognitive reasoning loop
 * on top of the Central Intelligence Model Gateway.
 * The Gateway handles model routing, rate limiting, token caching, and budgets;
 * Hermes executes the multi-turn tool-calling reasoning loop with persistent memory.
 *
 * Repo: https://github.com/NousResearch/hermes-agent
 * License: MIT
 */

import type {
  ChatCompletionMessage,
  ChatCompletionRequest,
  ChatCompletionResponse,
} from '../types/chat.js';

export interface HermesTool {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
  handler: (args: Record<string, any>) => Promise<any> | any;
}

export interface HermesAgentOptions {
  name?: string;
  model?: string;
  systemPrompt?: string;
  maxTurns?: number;
  tools?: HermesTool[];
  temperature?: number;
}

export interface HermesRunResult {
  finalResponse: string;
  turns: number;
  toolCallsExecuted: number;
  messages: ChatCompletionMessage[];
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export class HermesAgentAdapter {
  public id = 'hermes';
  public name: string;
  public model: string;
  public systemPrompt: string;
  public maxTurns: number;
  public temperature: number;

  private tools: Map<string, HermesTool> = new Map();
  private memory: ChatCompletionMessage[] = [];

  constructor(options: HermesAgentOptions = {}) {
    this.name = options.name || 'HermesAgent';
    this.model = options.model || 'nous-hermes-2-pro';
    this.systemPrompt =
      options.systemPrompt ||
      'You are Hermes, a state-of-the-art cognitive reasoning agent. Solve problems systematically using available tools.';
    this.maxTurns = options.maxTurns || 8;
    this.temperature = options.temperature ?? 0.2;

    if (options.tools) {
      for (const tool of options.tools) {
        this.registerTool(tool);
      }
    }
  }

  public registerTool(tool: HermesTool): void {
    this.tools.set(tool.name, tool);
  }

  public getTools(): HermesTool[] {
    return Array.from(this.tools.values());
  }

  public getMemory(): ChatCompletionMessage[] {
    return [...this.memory];
  }

  public clearMemory(): void {
    this.memory = [];
  }

  public setMemory(messages: ChatCompletionMessage[]): void {
    this.memory = [...messages];
  }

  /**
   * Formats registered tools for OpenAI / Hermes standard function calling schema.
   */
  public toToolSpecs(): Array<{
    type: 'function';
    function: {
      name: string;
      description: string;
      parameters: Record<string, unknown>;
    };
  }> {
    return Array.from(this.tools.values()).map((t) => ({
      type: 'function',
      function: {
        name: t.name,
        description: t.description,
        parameters: t.parameters,
      },
    }));
  }

  /**
   * Executes a multi-turn reasoning and tool-calling loop using the provided Gateway dispatcher.
   */
  public async run(
    userPrompt: string,
    gatewayDispatcher: (req: ChatCompletionRequest) => Promise<ChatCompletionResponse>,
    overrideOptions?: { maxTurns?: number },
  ): Promise<HermesRunResult> {
    const maxTurns = overrideOptions?.maxTurns || this.maxTurns;
    let turnCount = 0;
    let totalToolCalls = 0;
    let totalPromptTokens = 0;
    let totalCompletionTokens = 0;

    // Ensure system prompt is present in memory
    if (this.memory.length === 0 && this.systemPrompt) {
      this.memory.push({
        role: 'system',
        content: this.systemPrompt,
      });
    }

    // Append new user turn to memory
    this.memory.push({
      role: 'user',
      content: userPrompt,
    });

    const toolsSpec = this.toToolSpecs();

    while (turnCount < maxTurns) {
      turnCount++;

      const request: ChatCompletionRequest = {
        model: this.model,
        messages: this.memory,
        temperature: this.temperature,
        tools: toolsSpec.length > 0 ? (toolsSpec as any) : undefined,
        tool_choice: toolsSpec.length > 0 ? 'auto' : undefined,
      };

      const response = await gatewayDispatcher(request);

      if (response.usage) {
        totalPromptTokens += response.usage.prompt_tokens || 0;
        totalCompletionTokens += response.usage.completion_tokens || 0;
      }

      const choice = response.choices?.[0];
      if (!choice || !choice.message) {
        throw new Error('Hermes Agent received empty or malformed completion from Gateway.');
      }

      const assistantMessage = choice.message;
      this.memory.push(assistantMessage);

      // Check if tool calls were requested
      const toolCalls = assistantMessage.tool_calls;
      if (toolCalls && toolCalls.length > 0) {
        totalToolCalls += toolCalls.length;

        for (const tc of toolCalls) {
          const tool = this.tools.get(tc.function.name);
          let toolResultContent: string;

          if (!tool) {
            toolResultContent = JSON.stringify({
              error: `Tool '${tc.function.name}' not registered on Hermes Agent.`,
            });
          } else {
            try {
              const args =
                typeof tc.function.arguments === 'string'
                  ? JSON.parse(tc.function.arguments)
                  : tc.function.arguments || {};
              const result = await tool.handler(args);
              toolResultContent =
                typeof result === 'string' ? result : JSON.stringify(result);
            } catch (err: any) {
              toolResultContent = JSON.stringify({
                error: err.message || 'Tool execution encountered an exception',
              });
            }
          }

          // Append tool response to memory
          this.memory.push({
            role: 'tool',
            tool_call_id: tc.id,
            content: toolResultContent,
          });
        }

        // Loop back for model to synthesize reasoning with tool results
        continue;
      }

      // No tool calls requested: final reasoning output produced
      return {
        finalResponse: assistantMessage.content || '',
        turns: turnCount,
        toolCallsExecuted: totalToolCalls,
        messages: this.getMemory(),
        usage: {
          prompt_tokens: totalPromptTokens,
          completion_tokens: totalCompletionTokens,
          total_tokens: totalPromptTokens + totalCompletionTokens,
        },
      };
    }

    throw new Error(`Hermes reasoning loop reached maximum turns limit (${maxTurns}).`);
  }
}
