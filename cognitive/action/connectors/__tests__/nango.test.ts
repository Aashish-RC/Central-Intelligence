import { describe, expect, it } from 'vitest';
import {
  NangoAdapter,
  nangoAdapter,
  nangoPiece,
} from '../nango_adapter.js';
import {
  getConnectorPiece,
  getConnectorAction,
  CONNECTOR_REGISTRY,
} from '../connectorRegistry.js';

describe('Nango Federated OAuth Connector (Layer 5)', () => {
  it('registers nango piece in connector registry', () => {
    const piece = getConnectorPiece('nango');
    expect(piece).toBeDefined();
    expect(piece?.pieceId).toBe('nango');
    expect(piece?.category).toBe('Federated Integrations');
    expect(CONNECTOR_REGISTRY).toContain(nangoPiece);
  });

  it('exposes all required actions for federated integrations', () => {
    const actionIds = nangoPiece.actions.map((a) => a.actionId);
    expect(actionIds).toContain('github_list_repos');
    expect(actionIds).toContain('slack_send_message');
    expect(actionIds).toContain('google_drive_list_files');
    expect(actionIds).toContain('proxy_request');
  });

  it('retrieves OAuth connection credentials', async () => {
    const conn = await nangoAdapter.getConnection('github', 'user-gh-1');
    expect(conn).toBeDefined();
    expect(conn?.providerConfigKey).toBe('github');
    expect(conn?.credentials.access_token).toBeDefined();
  });

  it('authenticates to GitHub via Nango and lists repositories (Acceptance Criteria)', async () => {
    // Direct adapter method
    const repos = await nangoAdapter.listGithubRepos('github-conn-42');
    expect(Array.isArray(repos)).toBe(true);
    expect(repos.length).toBeGreaterThan(0);
    expect(repos[0]).toHaveProperty('full_name');
    expect(repos[0].name).toBe('Central-Intelligence');

    // Via ConnectorAction runner
    const action = getConnectorAction('nango', 'github_list_repos');
    expect(action).toBeDefined();
    const actionResult = (await action?.run({
      auth: { connection_id: 'github-conn-42' },
      propsValue: {},
    })) as any[];

    expect(Array.isArray(actionResult)).toBe(true);
    expect(actionResult.some((r) => r.name === 'Central-Intelligence')).toBe(true);
  });

  it('posts message via Slack OAuth integration', async () => {
    const slackAction = getConnectorAction('nango', 'slack_send_message');
    expect(slackAction).toBeDefined();

    const res = (await slackAction?.run({
      auth: { connection_id: 'slack-conn-01' },
      propsValue: {
        channel: '#engineering',
        text: 'Automated notification via Nango OAuth',
      },
    })) as any;

    expect(res.ok).toBe(true);
    expect(res.channel).toBe('#engineering');
  });

  it('lists files from Google Workspace via Nango Google Drive integration', async () => {
    const driveAction = getConnectorAction('nango', 'google_drive_list_files');
    expect(driveAction).toBeDefined();

    const files = (await driveAction?.run({
      auth: { connection_id: 'google-conn-01' },
      propsValue: {},
    })) as any[];

    expect(Array.isArray(files)).toBe(true);
    expect(files.length).toBeGreaterThan(0);
    expect(files[0]).toHaveProperty('name');
  });

  it('executes generic raw proxy request to any Nango-supported API', async () => {
    const proxyAction = getConnectorAction('nango', 'proxy_request');
    expect(proxyAction).toBeDefined();

    const res = (await proxyAction?.run({
      auth: { connection_id: 'linear-conn-01' },
      propsValue: {
        provider: 'linear',
        endpoint: '/graphql',
        method: 'POST',
      },
    })) as any;

    expect(res.status).toBe(200);
    expect(res.provider).toBe('linear');
  });
});
