/**
 * Layer 5 Action: Nango Federated OAuth Connector Adapter
 *
 * Provides a unified meta-connector gateway across 500+ pre-built OAuth integrations
 * (GitHub, Slack, Google Workspace, HubSpot, Salesforce, Linear, etc.)
 * acting as a federated layer above hand-written connectors.
 *
 * Repo: https://github.com/NangoHQ/nango
 * License: Elastic-2.0
 */

import { Nango } from '@nangohq/node';
import type { ConnectorPiece, ConnectorContext } from './connectorContract.js';

export interface NangoAdapterConfig {
  secretKey?: string;
  host?: string;
  mockMode?: boolean;
}

export interface NangoProxyRequestParams {
  providerConfigKey: string;
  connectionId: string;
  endpoint: string;
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  headers?: Record<string, string>;
  data?: any;
  params?: Record<string, string>;
}

export interface NangoConnectionRecord {
  connectionId: string;
  providerConfigKey: string;
  credentials: {
    type: 'OAuth2' | 'Basic' | 'ApiKey';
    access_token?: string;
    refresh_token?: string;
    expires_at?: string;
    raw?: Record<string, any>;
  };
}

export class NangoAdapter {
  public id = 'nango';
  public name = 'Nango Federated Gateway';
  private client?: Nango;
  private mockMode: boolean;
  private mockConnections: Map<string, NangoConnectionRecord> = new Map();

  constructor(config: NangoAdapterConfig = {}) {
    const secretKey = config.secretKey || process.env.NANGO_SECRET_KEY || 'mock-secret-key';
    const host = config.host || process.env.NANGO_HOST || 'http://localhost:3003';
    this.mockMode = config.mockMode ?? (process.env.NODE_ENV === 'test' || !process.env.NANGO_SECRET_KEY);

    try {
      this.client = new Nango({ secretKey, host });
    } catch {
      this.mockMode = true;
    }
  }

  public isMockMode(): boolean {
    return this.mockMode;
  }

  /**
   * Set or seed mock connection credentials for testing / offline environments.
   */
  public setMockConnection(record: NangoConnectionRecord): void {
    const key = `${record.providerConfigKey}:${record.connectionId}`;
    this.mockConnections.set(key, record);
  }

  /**
   * Fetch authenticated connection details.
   */
  public async getConnection(
    providerConfigKey: string,
    connectionId: string,
  ): Promise<NangoConnectionRecord | null> {
    if (this.mockMode) {
      const key = `${providerConfigKey}:${connectionId}`;
      return (
        this.mockConnections.get(key) || {
          connectionId,
          providerConfigKey,
          credentials: {
            type: 'OAuth2',
            access_token: `mock-token-${providerConfigKey}-${connectionId}`,
            expires_at: new Date(Date.now() + 3600 * 1000).toISOString(),
          },
        }
      );
    }

    if (!this.client) throw new Error('Nango client not initialized');
    const conn = await this.client.getConnection(providerConfigKey, connectionId);
    return conn as unknown as NangoConnectionRecord;
  }

  /**
   * Proxy an authenticated API request to upstream SaaS service using stored OAuth tokens.
   */
  public async proxy(params: NangoProxyRequestParams): Promise<any> {
    if (this.mockMode) {
      return this.handleMockProxy(params);
    }

    if (!this.client) throw new Error('Nango client not initialized');
    return this.client.proxy({
      providerConfigKey: params.providerConfigKey,
      connectionId: params.connectionId,
      endpoint: params.endpoint,
      method: params.method || 'GET',
      headers: params.headers,
      data: params.data,
      params: params.params,
    });
  }

  /**
   * GitHub: Authenticate and list repositories.
   */
  public async listGithubRepos(connectionId: string): Promise<Array<{ id: number; name: string; full_name: string }>> {
    const res = await this.proxy({
      providerConfigKey: 'github',
      connectionId,
      endpoint: '/user/repos',
      method: 'GET',
    });
    return (res.data || res) as Array<{ id: number; name: string; full_name: string }>;
  }

  /**
   * Slack: Post message via authenticated Slack workspace connection.
   */
  public async postSlackMessage(
    connectionId: string,
    channel: string,
    text: string,
  ): Promise<{ ok: boolean; messageId: string }> {
    const res = await this.proxy({
      providerConfigKey: 'slack',
      connectionId,
      endpoint: '/chat.postMessage',
      method: 'POST',
      data: { channel, text },
    });
    return (res.data || res) as { ok: boolean; messageId: string };
  }

  /**
   * Google Workspace: List files from Google Drive.
   */
  public async listGoogleDriveFiles(
    connectionId: string,
  ): Promise<Array<{ id: string; name: string; mimeType: string }>> {
    const res = await this.proxy({
      providerConfigKey: 'google-drive',
      connectionId,
      endpoint: '/drive/v3/files',
      method: 'GET',
    });
    const data = res.data || res;
    return (data.files || data) as Array<{ id: string; name: string; mimeType: string }>;
  }

  private handleMockProxy(params: NangoProxyRequestParams): any {
    const { providerConfigKey, endpoint } = params;

    if (providerConfigKey === 'github' && endpoint === '/user/repos') {
      return [
        { id: 101, name: 'Central-Intelligence', full_name: 'Aevum/Central-Intelligence' },
        { id: 102, name: 'Aevum-Core', full_name: 'Aevum/Aevum-Core' },
      ];
    }

    if (providerConfigKey === 'slack' && endpoint === '/chat.postMessage') {
      return { ok: true, messageId: `msg-${Date.now()}`, channel: params.data?.channel };
    }

    if (providerConfigKey === 'google-drive' && endpoint === '/drive/v3/files') {
      return {
        files: [
          { id: 'file-01', name: 'Architecture_Spec.pdf', mimeType: 'application/pdf' },
          { id: 'file-02', name: 'Q4_Roadmap.gdoc', mimeType: 'application/vnd.google-apps.document' },
        ],
      };
    }

    return {
      status: 200,
      mock: true,
      provider: providerConfigKey,
      endpoint,
      timestamp: new Date().toISOString(),
    };
  }
}

export const nangoAdapter = new NangoAdapter();

/**
 * ConnectorPiece wrapper for Nango federated provider.
 */
export const nangoPiece: ConnectorPiece = {
  pieceId: 'nango',
  displayName: 'Nango (500+ Federated OAuth APIs)',
  description: 'Federated OAuth gateway proxying to GitHub, Slack, Google Workspace, Jira, and 500+ SaaS APIs.',
  logoEmoji: '⚡',
  authType: 'secret_text',
  authFields: [
    {
      key: 'connection_id',
      displayName: 'Nango Connection ID',
      required: true,
      type: 'text',
    },
  ],
  category: 'Federated Integrations',
  licenseNote: 'Powered by NangoHQ (Elastic-2.0). Native central-intelligence connector adapter.',
  actions: [
    {
      actionId: 'github_list_repos',
      displayName: 'GitHub: List Repositories',
      description: 'Fetch all repositories accessible by authenticated GitHub OAuth connection.',
      consequential: false,
      props: [],
      async run(ctx: ConnectorContext): Promise<unknown> {
        const connId = (ctx.auth?.connection_id as string) || (ctx.propsValue.connection_id as string) || 'default-user';
        return nangoAdapter.listGithubRepos(connId);
      },
    },
    {
      actionId: 'slack_send_message',
      displayName: 'Slack: Post Message (Nango)',
      description: 'Send message to Slack channel via federated Nango integration.',
      consequential: true,
      consequentialReason: 'Posts external message into Slack workspace.',
      props: [
        {
          key: 'channel',
          displayName: 'Channel',
          type: 'short_text',
          required: true,
        },
        {
          key: 'text',
          displayName: 'Message',
          type: 'long_text',
          required: true,
        },
      ],
      async run(ctx: ConnectorContext): Promise<unknown> {
        const connId = (ctx.auth?.connection_id as string) || 'default-user';
        return nangoAdapter.postSlackMessage(
          connId,
          ctx.propsValue.channel as string,
          ctx.propsValue.text as string,
        );
      },
    },
    {
      actionId: 'google_drive_list_files',
      displayName: 'Google Drive: List Files',
      description: 'List user documents and files from Google Workspace.',
      consequential: false,
      props: [],
      async run(ctx: ConnectorContext): Promise<unknown> {
        const connId = (ctx.auth?.connection_id as string) || 'default-user';
        return nangoAdapter.listGoogleDriveFiles(connId);
      },
    },
    {
      actionId: 'proxy_request',
      displayName: 'Nango: Raw API Proxy',
      description: 'Execute arbitrary authenticated API call to any of Nango 500+ connectors.',
      consequential: true,
      consequentialReason: 'Proxies arbitrary authenticated network request to third-party SaaS API.',
      props: [
        {
          key: 'provider',
          displayName: 'Provider Config Key',
          type: 'short_text',
          required: true,
        },
        {
          key: 'endpoint',
          displayName: 'Endpoint Path',
          type: 'short_text',
          required: true,
        },
        {
          key: 'method',
          displayName: 'HTTP Method',
          type: 'dropdown',
          required: false,
          defaultValue: 'GET',
          options: [
            { label: 'GET', value: 'GET' },
            { label: 'POST', value: 'POST' },
            { label: 'PUT', value: 'PUT' },
            { label: 'DELETE', value: 'DELETE' },
          ],
        },
      ],
      async run(ctx: ConnectorContext): Promise<unknown> {
        const connId = (ctx.auth?.connection_id as string) || 'default-user';
        return nangoAdapter.proxy({
          providerConfigKey: ctx.propsValue.provider as string,
          connectionId: connId,
          endpoint: ctx.propsValue.endpoint as string,
          method: (ctx.propsValue.method as any) || 'GET',
          data: ctx.propsValue.data,
        });
      },
    },
  ],
};

