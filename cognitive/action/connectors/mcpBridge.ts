/**
 * MCP Bridge — Live wiring for Model Context Protocol (MCP) servers.
 *
 * Connects Rivet-derived MCP concepts (mcpDiscovery, mcpGetPrompt, mcpToolCall)
 * into the live chat/agent pipeline so MCP servers can be discovered and invoked
 * mid-conversation alongside ActivePieces connectors without conflict.
 */

export interface MCPToolParameter {
  type: string;
  description?: string;
  required?: boolean;
}

export interface MCPTool {
  name: string;
  description: string;
  serverName: string;
  serverUrl?: string;
  inputSchema: {
    type: 'object';
    properties: Record<string, MCPToolParameter>;
    required?: string[];
  };
  consequential?: boolean;
  consequentialReason?: string;
}

export interface MCPPrompt {
  name: string;
  description?: string;
  arguments?: Array<{ name: string; description?: string; required?: boolean }>;
  template: string;
}

export interface MCPServerConfig {
  name: string;
  url?: string;
  transport?: 'http' | 'stdio' | 'in_memory';
  tools?: MCPTool[];
  prompts?: MCPPrompt[];
  customHandler?: (toolName: string, args: Record<string, unknown>) => Promise<unknown>;
}

// In-memory registry of connected MCP servers
const registeredServers: Map<string, MCPServerConfig> = new Map();

// Built-in starter MCP tools for instant out-of-the-box discovery & testing
const DEFAULT_MCP_SERVERS: MCPServerConfig[] = [
  {
    name: 'filesystem',
    url: 'http://localhost:8080/mcp/filesystem',
    transport: 'in_memory',
    tools: [
      {
        name: 'read_file',
        description: 'Read contents of a local file path.',
        serverName: 'filesystem',
        consequential: false,
        inputSchema: {
          type: 'object',
          properties: {
            path: { type: 'string', description: 'Relative or absolute file path', required: true },
          },
          required: ['path'],
        },
      },
      {
        name: 'delete_file',
        description: 'Delete a file permanently from disk.',
        serverName: 'filesystem',
        consequential: true,
        consequentialReason: 'Deletes a file permanently from disk.',
        inputSchema: {
          type: 'object',
          properties: {
            path: { type: 'string', description: 'File path to delete', required: true },
          },
          required: ['path'],
        },
      },
    ],
    prompts: [
      {
        name: 'code_review',
        description: 'Template for performing a security and architecture review on a code file.',
        template: 'Please review the following code for security vulnerabilities, race conditions, and performance bottlenecks:\n\n{code}',
      },
    ],
    customHandler: async (toolName, args) => {
      if (toolName === 'read_file') {
        const path = String(args.path || '');
        return {
          path,
          content: `// Contents of ${path}\nexport const ready = true;\nconsole.log("MCP file stream online");`,
          sizeBytes: 84,
        };
      }
      if (toolName === 'delete_file') {
        const path = String(args.path || '');
        return {
          success: true,
          deletedPath: path,
          status: 'deleted',
          timestamp: new Date().toISOString(),
        };
      }
      throw new Error(`Unknown filesystem MCP tool: ${toolName}`);
    },
  },
  {
    name: 'github',
    url: 'http://localhost:8080/mcp/github',
    transport: 'in_memory',
    tools: [
      {
        name: 'get_issue',
        description: 'Fetch details, comments, and status for a GitHub issue.',
        serverName: 'github',
        consequential: false,
        inputSchema: {
          type: 'object',
          properties: {
            repo: { type: 'string', description: 'GitHub repository (owner/repo)', required: true },
            issueNumber: { type: 'number', description: 'Issue or PR number', required: true },
          },
          required: ['repo', 'issueNumber'],
        },
      },
      {
        name: 'create_issue',
        description: 'Create a new issue on a public or private GitHub repository.',
        serverName: 'github',
        consequential: true,
        consequentialReason: 'Creates a public issue on an external GitHub repository.',
        inputSchema: {
          type: 'object',
          properties: {
            repo: { type: 'string', description: 'GitHub repository (owner/repo)', required: true },
            title: { type: 'string', description: 'Issue title', required: true },
            body: { type: 'string', description: 'Markdown issue body', required: false },
          },
          required: ['repo', 'title'],
        },
      },
    ],
    customHandler: async (toolName, args) => {
      if (toolName === 'get_issue') {
        return {
          repo: args.repo,
          issueNumber: args.issueNumber,
          title: 'Implement ReAct agent orchestrator loop',
          state: 'open',
          labels: ['feature', 'agentic', 'phase4'],
          author: 'aashish',
          body: 'We need a robust Think-Act-Observe loop with human approval cards.',
        };
      }
      if (toolName === 'create_issue') {
        return {
          success: true,
          issueNumber: 42,
          htmlUrl: `https://github.com/${args.repo}/issues/42`,
          title: args.title,
          state: 'open',
          createdAt: new Date().toISOString(),
        };
      }
      throw new Error(`Unknown github MCP tool: ${toolName}`);
    },
  },
];

// Initialize default servers
for (const server of DEFAULT_MCP_SERVERS) {
  registeredServers.set(server.name, server);
}

/**
 * Register or update an MCP server in the bridge.
 */
export function registerMCPServer(server: MCPServerConfig): void {
  registeredServers.set(server.name, server);
}

/**
 * Discovers available tools from configured MCP servers.
 * Emulates Rivet's mcpDiscovery node in the live agent pipeline.
 */
export async function discoverMCPTools(serverNameFilter?: string): Promise<MCPTool[]> {
  const tools: MCPTool[] = [];
  for (const [name, server] of registeredServers.entries()) {
    if (serverNameFilter && serverNameFilter !== name) continue;
    if (server.tools) {
      tools.push(...server.tools);
    }
  }
  return tools;
}

/**
 * Retrieves an MCP prompt template.
 * Emulates Rivet's mcpGetPrompt node.
 */
export async function getMCPPrompt(
  name: string,
  args?: Record<string, unknown>,
  serverName?: string
): Promise<{ prompt: string }> {
  for (const [, server] of registeredServers.entries()) {
    if (serverName && server.name !== serverName) continue;
    const found = server.prompts?.find((p) => p.name === name);
    if (found) {
      let promptText = found.template;
      if (args) {
        for (const [k, v] of Object.entries(args)) {
          promptText = promptText.replaceAll(`{${k}}`, String(v));
        }
      }
      return { prompt: promptText };
    }
  }
  throw new Error(`MCP prompt not found: "${name}"`);
}

/**
 * Executes a tool on a connected MCP server.
 * Emulates Rivet's mcpToolCall node.
 */
export async function executeMCPTool(
  serverName: string,
  toolName: string,
  args: Record<string, unknown>
): Promise<unknown> {
  const server = registeredServers.get(serverName);
  if (!server) {
    throw new Error(`MCP server not found: "${serverName}"`);
  }

  const tool = server.tools?.find((t) => t.name === toolName);
  if (!tool) {
    throw new Error(`MCP tool "${toolName}" not found on server "${serverName}"`);
  }

  // If server has custom execution handler (in-memory or protocol bridge)
  if (server.customHandler) {
    return server.customHandler(toolName, args);
  }

  // HTTP transport execution fallback
  if (server.url) {
    try {
      const resp = await fetch(`${server.url}/tools/${toolName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args),
      });
      return await resp.json();
    } catch (err) {
      throw new Error(`Failed to call MCP tool "${toolName}" at ${server.url}: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  return { status: 'ok', server: serverName, tool: toolName, executedWith: args };
}

/**
 * Format MCP tools into the uniform ReAct Agent Tool interface.
 * Uses the namespace format "mcp:{server}:{tool}" to avoid conflicts with connector pieces.
 */
export function mcpToolToAgentToolId(serverName: string, toolName: string): string {
  return `mcp:${serverName}:${toolName}`;
}

export function parseMCPToolId(agentToolId: string): { serverName: string; toolName: string } | null {
  const parts = agentToolId.split(':');
  if (parts.length === 3 && parts[0] === 'mcp') {
    return { serverName: parts[1], toolName: parts[2] };
  }
  return null;
}
