import { describe, expect, it } from 'vitest';
import {
  ACIToolFederationEngine,
  aciFederation,
  aciPiece,
} from '../aci_adapter.js';
import {
  getConnectorPiece,
  getConnectorAction,
  CONNECTOR_REGISTRY,
} from '../connectorRegistry.js';

describe('ACI.dev Tool Federation Adapter (Layer 5)', () => {
  it('registers aci piece in connector registry', () => {
    const piece = getConnectorPiece('aci');
    expect(piece).toBeDefined();
    expect(piece?.pieceId).toBe('aci');
    expect(piece?.category).toBe('Federation & Orchestration');
    expect(CONNECTOR_REGISTRY).toContain(aciPiece);
  });

  it('discovers tools across all registered providers (MCP, Nango, Connectors) (Acceptance Criteria 1)', async () => {
    const tools = await aciFederation.listFederatedTools();

    expect(tools.length).toBeGreaterThan(5);

    const providers = new Set(tools.map((t) => t.provider));
    expect(providers.has('mcp')).toBe(true);
    expect(providers.has('nango')).toBe(true);
    expect(providers.has('connector')).toBe(true);
    expect(providers.has('external')).toBe(true);

    // Verify key tools exist
    const toolIds = tools.map((t) => t.id);
    expect(toolIds).toContain('federated:mcp:filesystem:read_file');
    expect(toolIds).toContain('federated:nango:github_list_repos');
    expect(toolIds).toContain('federated:connector:openclaw:open_file');
    expect(toolIds).toContain('federated:system:calculate');
  });

  it('filters tools by provider and query', async () => {
    const mcpOnly = await aciFederation.listFederatedTools({ provider: 'mcp' });
    expect(mcpOnly.every((t) => t.provider === 'mcp')).toBe(true);

    const githubSearch = await aciFederation.listFederatedTools({ query: 'github' });
    expect(githubSearch.length).toBeGreaterThan(0);
    expect(githubSearch.some((t) => t.name.includes('github'))).toBe(true);
  });

  it('executes an MCP federated tool', async () => {
    const result = (await aciFederation.executeTool(
      'federated:mcp:filesystem:read_file',
      { path: 'src/index.ts' },
    )) as any;

    expect(result).toBeDefined();
    expect(result.path).toBe('src/index.ts');
    expect(result.content).toContain('MCP file stream online');
  });

  it('executes a Nango federated tool (Acceptance Criteria 2)', async () => {
    const repos = (await aciFederation.executeTool(
      'federated:nango:github_list_repos',
      {},
      { propsValue: {}, auth: { connection_id: 'gh-conn-test' } },
    )) as any[];

    expect(Array.isArray(repos)).toBe(true);
    expect(repos.length).toBeGreaterThan(0);
    expect(repos.some((r) => r.name === 'Central-Intelligence')).toBe(true);
  });

  it('executes a native Connector federated tool', async () => {
    const sysResult = (await aciFederation.executeTool(
      'federated:connector:openclaw:system_info',
      {},
    )) as any;

    expect(sysResult).toBeDefined();
    expect(sysResult.platform).toBe(process.platform);
  });

  it('executes a custom ACI federated tool', async () => {
    const mathResult = (await aciFederation.executeTool(
      'federated:system:calculate',
      { expression: '21 * 2' },
    )) as any;

    expect(mathResult.result).toBe(42);
  });

  it('executes tool discovery and dispatch via ACI ConnectorPiece actions', async () => {
    const listAction = getConnectorAction('aci', 'list_tools');
    expect(listAction).toBeDefined();

    const discovered = (await listAction?.run({
      propsValue: { provider: 'nango' },
    })) as any[];

    expect(Array.isArray(discovered)).toBe(true);
    expect(discovered.every((t) => t.provider === 'nango')).toBe(true);

    const execAction = getConnectorAction('aci', 'execute_tool');
    expect(execAction).toBeDefined();

    const executed = (await execAction?.run({
      propsValue: {
        tool_id: 'federated:system:calculate',
        args: { expression: '100 + 50' },
      },
    })) as any;

    expect(executed.result).toBe(150);
  });
});

