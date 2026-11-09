/**
 * Layer 5 Action: ACI.dev Unified Tool Federation Adapter
 *
 * Provides cross-provider tool federation enabling autonomous agents to discover
 * and execute tools seamlessly across MCP servers, Nango OAuth integrations,
 * and native connectors.
 *
 * Repo: https://github.com/aipotheosis-labs/aci
 * License: Apache-2.0
 */

import type { ConnectorPiece, ConnectorContext } from './connectorContract.js';
import { discoverMCPTools, executeMCPTool } from './mcpBridge.js';
import { nangoAdapter } from './nango_adapter.js';

export interface FederatedToolDefinition {
  id: string; // e.g. "federated:mcp:read_file" or "federated:nango:github_list_repos"
  name: string;
  provider: 'mcp' | 'nango' | 'connector' | 'external';
  providerName: string;
  description: string;
  category?: string;
  inputSchema: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
  };
  consequential?: boolean;
}

export interface ACIProviderConfig {
  name: string;
  type: 'mcp' | 'nango' | 'connector' | 'external';
  endpoint?: string;
  apiKey?: string;
  enabled?: boolean;
}

export class ACIToolFederationEngine {
  private customProviders: Map<string, ACIProviderConfig> = new Map();
  private customTools: Map<string, FederatedToolDefinition & { handler: (args: any) => Promise<any> }> = new Map();

  constructor() {
    this.registerDefaultCustomTools();
  }

  private registerDefaultCustomTools(): void {
    // Built-in starter tools for ACI federation
    this.registerCustomTool({
      id: 'federated:system:calculate',
      name: 'calculate',
      provider: 'external',
      providerName: 'aci-math',
      description: 'Perform arithmetic and statistical calculations.',
      category: 'Math',
      inputSchema: {
        type: 'object',
        properties: {
          expression: { type: 'string', description: 'Mathematical expression to evaluate' },
        },
        required: ['expression'],
      },
      handler: async (args: { expression: string }) => {
        // Safe evaluation
        const sanitized = args.expression.replace(/[^0-9+\-*/().]/g, '');
        // eslint-disable-next-line no-eval
        const result = Function(`"use strict"; return (${sanitized})`)();
        return { expression: args.expression, result };
      },
    });
  }

  public registerCustomTool(
    tool: FederatedToolDefinition & { handler: (args: any) => Promise<any> },
  ): void {
    this.customTools.set(tool.id, tool);
  }

  public registerProvider(provider: ACIProviderConfig): void {
    this.customProviders.set(provider.name, provider);
  }

  /**
   * Discover and list all tools available across all registered providers:
   * 1. Built-in and dynamically connected MCP servers
   * 2. Nango OAuth pre-built SaaS actions
   * 3. Native ActivePieces-style connectors
   * 4. Custom/External ACI tools
   */
  public async listFederatedTools(filter?: {
    provider?: string;
    category?: string;
    query?: string;
  }): Promise<FederatedToolDefinition[]> {
    const tools: FederatedToolDefinition[] = [];

    // 1. Ingest MCP tools from mcpBridge
    try {
      const mcpTools = await discoverMCPTools();
      for (const t of mcpTools) {
        tools.push({
          id: `federated:mcp:${t.serverName}:${t.name}`,
          name: t.name,
          provider: 'mcp',
          providerName: `mcp-${t.serverName}`,
          description: t.description,
          category: 'MCP',
          inputSchema: t.inputSchema as any,
          consequential: t.consequential,
        });
      }
    } catch {
      // MCP discovery fallback
    }

    // 2. Ingest Nango actions
    tools.push(
      {
        id: 'federated:nango:github_list_repos',
        name: 'github_list_repos',
        provider: 'nango',
        providerName: 'nango-github',
        description: 'Fetch repositories for authenticated GitHub account.',
        category: 'Development',
        inputSchema: { type: 'object', properties: {} },
        consequential: false,
      },
      {
        id: 'federated:nango:slack_send_message',
        name: 'slack_send_message',
        provider: 'nango',
        providerName: 'nango-slack',
        description: 'Post message into Slack channel via Nango federated OAuth.',
        category: 'Communication',
        inputSchema: {
          type: 'object',
          properties: {
            channel: { type: 'string', description: 'Slack channel ID or name' },
            text: { type: 'string', description: 'Message content' },
          },
          required: ['channel', 'text'],
        },
        consequential: true,
      },
      {
        id: 'federated:nango:google_drive_list_files',
        name: 'google_drive_list_files',
        provider: 'nango',
        providerName: 'nango-google-drive',
        description: 'List user documents from Google Workspace via Nango.',
        category: 'Productivity',
        inputSchema: { type: 'object', properties: {} },
        consequential: false,
      },
    );

    // 3. Ingest native Connector actions
    const { CONNECTOR_REGISTRY } = await import('./connectorRegistry.js');
    for (const piece of CONNECTOR_REGISTRY) {
      if (!piece || piece.pieceId === 'aci' || piece.pieceId === 'nango') continue;
      for (const action of piece.actions || []) {
        tools.push({
          id: `federated:connector:${piece.pieceId}:${action.actionId}`,
          name: `${piece.pieceId}_${action.actionId}`,
          provider: 'connector',
          providerName: piece.displayName,
          description: action.description,
          category: piece.category,
          inputSchema: {
            type: 'object',
            properties: action.props.reduce((acc, p) => {
              acc[p.key] = { type: p.type, description: p.description };
              return acc;
            }, {} as Record<string, unknown>),
            required: action.props.filter((p) => p.required).map((p) => p.key),
          },
          consequential: action.consequential,
        });
      }
    }

    // 4. Ingest custom ACI registered tools
    for (const tool of this.customTools.values()) {
      tools.push({
        id: tool.id,
        name: tool.name,
        provider: tool.provider,
        providerName: tool.providerName,
        description: tool.description,
        category: tool.category,
        inputSchema: tool.inputSchema,
        consequential: tool.consequential,
      });
    }

    // Apply filtering
    return tools.filter((t) => {
      if (filter?.provider && t.provider !== filter.provider) return false;
      if (filter?.category && t.category?.toLowerCase() !== filter.category.toLowerCase()) return false;
      if (filter?.query) {
        const q = filter.query.toLowerCase();
        return t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q);
      }
      return true;
    });
  }

  /**
   * Dispatches and executes any federated tool across MCP, Nango, connectors, or external ACI tools.
   */
  public async executeTool(
    toolId: string,
    args: Record<string, unknown> = {},
    context?: ConnectorContext,
  ): Promise<unknown> {
    const parts = toolId.split(':');
    if (parts[0] !== 'federated') {
      throw new Error(`Invalid federated tool ID: '${toolId}'. Must start with 'federated:'`);
    }

    const providerType = parts[1];

    // 1. Custom tool execution
    if (this.customTools.has(toolId)) {
      const custom = this.customTools.get(toolId)!;
      return custom.handler(args);
    }

    // 2. MCP Tool Execution
    if (providerType === 'mcp') {
      const serverName = parts[2];
      const toolName = parts[3];
      return executeMCPTool(serverName, toolName, args);
    }

    // 3. Nango Federated Execution
    if (providerType === 'nango') {
      const actionName = parts[2];
      const connId = (context?.auth?.connection_id as string) || 'default-user';
      if (actionName === 'github_list_repos') {
        return nangoAdapter.listGithubRepos(connId);
      }
      if (actionName === 'slack_send_message') {
        return nangoAdapter.postSlackMessage(
          connId,
          (args.channel as string) || '#general',
          (args.text as string) || '',
        );
      }
      if (actionName === 'google_drive_list_files') {
        return nangoAdapter.listGoogleDriveFiles(connId);
      }
      return nangoAdapter.proxy({
        providerConfigKey: (args.provider as string) || 'github',
        connectionId: connId,
        endpoint: (args.endpoint as string) || '/user',
      });
    }

    // 4. Native Connector Execution
    if (providerType === 'connector') {
      const pieceId = parts[2];
      const actionId = parts[3];
      const { getConnectorAction } = await import('./connectorRegistry.js');
      const action = getConnectorAction(pieceId, actionId);
      if (!action) {
        throw new Error(`Connector action '${pieceId}:${actionId}' not found.`);
      }
      return action.run({
        auth: context?.auth || {},
        propsValue: args,
      });
    }

    throw new Error(`Unrecognized federated tool provider: '${providerType}' for tool '${toolId}'`);
  }
}

export const aciFederation = new ACIToolFederationEngine();

/**
 * ConnectorPiece representation of ACI tool federation.
 */
export const aciPiece: ConnectorPiece = {
  pieceId: 'aci',
  displayName: 'ACI.dev Tool Federation',
  description: 'Federated tool discovery and dispatch across MCP, Nango, and active connector pieces.',
  logoEmoji: '🌐',
  authType: 'none',
  category: 'Federation & Orchestration',
  licenseNote: 'Powered by ACI.dev (Apache-2.0). Native central-intelligence integration.',
  actions: [
    {
      actionId: 'list_tools',
      displayName: 'Discover Federated Tools',
      description: 'List all available tools across MCP, Nango, and Connectors.',
      consequential: false,
      props: [
        {
          key: 'provider',
          displayName: 'Provider Filter',
          type: 'dropdown',
          required: false,
          options: [
            { label: 'All Providers', value: '' },
            { label: 'MCP', value: 'mcp' },
            { label: 'Nango', value: 'nango' },
            { label: 'Native Connectors', value: 'connector' },
          ],
        },
        {
          key: 'query',
          displayName: 'Search Query',
          type: 'short_text',
          required: false,
        },
      ],
      async run(ctx: ConnectorContext): Promise<unknown> {
        return aciFederation.listFederatedTools({
          provider: ctx.propsValue.provider as string,
          query: ctx.propsValue.query as string,
        });
      },
    },
    {
      actionId: 'execute_tool',
      displayName: 'Execute Federated Tool',
      description: 'Invoke a discovered tool using its federated identifier.',
      consequential: true,
      consequentialReason: 'Executes federated actions across connected systems.',
      props: [
        {
          key: 'tool_id',
          displayName: 'Federated Tool ID',
          type: 'short_text',
          required: true,
        },
        {
          key: 'args',
          displayName: 'Tool Arguments',
          type: 'object',
          required: false,
        },
      ],
      async run(ctx: ConnectorContext): Promise<unknown> {
        const toolId = ctx.propsValue.tool_id as string;
        const args = (ctx.propsValue.args as Record<string, unknown>) || {};
        return aciFederation.executeTool(toolId, args, ctx);
      },
    },
  ],
};
