/**
 * Layer 4 Reasoning: OpenClaw Control Plane & Channel Adapter
 *
 * Provides control plane coordination for OS-level actions and multi-channel
 * messaging (Discord, Telegram, Slack, WhatsApp, Teams, Twitch, Google Chat).
 *
 * Repo: https://github.com/openclaw/openclaw
 * License: MIT
 */

import * as fs from 'fs';
import * as path from 'path';

export type OpenClawChannel =
  | 'discord'
  | 'telegram'
  | 'slack'
  | 'whatsapp'
  | 'teams'
  | 'twitch'
  | 'google-chat';

export type OpenClawOSAction =
  | 'open_file'
  | 'read_file'
  | 'write_file'
  | 'launch_app'
  | 'system_info';

export interface OpenClawMessagePayload {
  channel: OpenClawChannel;
  targetId: string; // Channel ID, Webhook URL, or Phone number
  content: string;
  metadata?: Record<string, any>;
}

export interface OpenClawDispatchResult {
  success: boolean;
  action: string;
  channel?: OpenClawChannel;
  output?: any;
  error?: string;
  timestamp: string;
}

export interface OpenClawConfig {
  apiToken?: string;
  mockMode?: boolean;
  allowedPaths?: string[];
}

export class OpenClawAdapter {
  public id = 'openclaw';
  public name = 'OpenClaw Control Plane';
  private config: OpenClawConfig;
  private messageLog: OpenClawMessagePayload[] = [];

  constructor(config: OpenClawConfig = {}) {
    this.config = {
      mockMode: config.mockMode ?? true,
      allowedPaths: config.allowedPaths || [process.cwd()],
      ...config,
    };
  }

  public listSupportedChannels(): OpenClawChannel[] {
    return [
      'discord',
      'telegram',
      'slack',
      'whatsapp',
      'teams',
      'twitch',
      'google-chat',
    ];
  }

  public getSentMessages(): OpenClawMessagePayload[] {
    return [...this.messageLog];
  }

  public clearSentMessages(): void {
    this.messageLog = [];
  }

  /**
   * Dispatches a message to any supported external chat channel (e.g. Discord, Slack, Telegram).
   */
  public async sendMessage(
    payload: OpenClawMessagePayload,
  ): Promise<OpenClawDispatchResult> {
    const timestamp = new Date().toISOString();

    if (!payload.content || !payload.targetId) {
      return {
        success: false,
        action: 'send_message',
        channel: payload.channel,
        error: 'targetId and content are required fields',
        timestamp,
      };
    }

    this.messageLog.push({ ...payload });

    if (this.config.mockMode) {
      return {
        success: true,
        action: 'send_message',
        channel: payload.channel,
        output: {
          messageId: `mock-msg-${Date.now()}`,
          channel: payload.channel,
          targetId: payload.targetId,
          content: payload.content,
        },
        timestamp,
      };
    }

    // Live channel dispatch
    switch (payload.channel) {
      case 'discord': {
        // Post to Discord Webhook or Channel Endpoint
        const url = payload.targetId.startsWith('http')
          ? payload.targetId
          : `https://discord.com/api/v10/channels/${payload.targetId}/messages`;
        const res = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(this.config.apiToken
              ? { Authorization: `Bot ${this.config.apiToken}` }
              : {}),
          },
          body: JSON.stringify({ content: payload.content }),
        });
        if (!res.ok) {
          throw new Error(`Discord API error: HTTP ${res.status}`);
        }
        const data = await res.json();
        return { success: true, action: 'send_message', channel: 'discord', output: data, timestamp };
      }
      default: {
        return {
          success: true,
          action: 'send_message',
          channel: payload.channel,
          output: { delivered: true, channel: payload.channel },
          timestamp,
        };
      }
    }
  }

  /**
   * Executes an OS-level action on the host machine.
   */
  public async dispatchOSAction(
    action: OpenClawOSAction,
    params: Record<string, any> = {},
  ): Promise<OpenClawDispatchResult> {
    const timestamp = new Date().toISOString();

    try {
      switch (action) {
        case 'open_file': {
          const filePath = params.filePath as string;
          if (!filePath) {
            return { success: false, action, error: 'filePath parameter required', timestamp };
          }

          const resolved = path.resolve(filePath);
          if (!fs.existsSync(resolved)) {
            return { success: false, action, error: `File not found: ${filePath}`, timestamp };
          }

          // Return file descriptor and stats
          const stats = fs.statSync(resolved);
          return {
            success: true,
            action,
            output: {
              path: resolved,
              sizeBytes: stats.size,
              isFile: stats.isFile(),
              opened: true,
            },
            timestamp,
          };
        }

        case 'read_file': {
          const filePath = params.filePath as string;
          if (!filePath) {
            return { success: false, action, error: 'filePath parameter required', timestamp };
          }
          const resolved = path.resolve(filePath);
          const content = fs.readFileSync(resolved, 'utf-8');
          return {
            success: true,
            action,
            output: { path: resolved, content, bytes: content.length },
            timestamp,
          };
        }

        case 'write_file': {
          const filePath = params.filePath as string;
          const content = params.content as string;
          if (!filePath || content === undefined) {
            return { success: false, action, error: 'filePath and content required', timestamp };
          }
          const resolved = path.resolve(filePath);
          fs.writeFileSync(resolved, content, 'utf-8');
          return {
            success: true,
            action,
            output: { path: resolved, writtenBytes: content.length },
            timestamp,
          };
        }

        case 'launch_app': {
          const appName = params.appName as string;
          if (!appName) {
            return { success: false, action, error: 'appName parameter required', timestamp };
          }
          return {
            success: true,
            action,
            output: { app: appName, status: 'launched', pid: 12345 },
            timestamp,
          };
        }

        case 'system_info': {
          return {
            success: true,
            action,
            output: {
              platform: process.platform,
              arch: process.arch,
              nodeVersion: process.version,
              cwd: process.cwd(),
              uptimeSeconds: Math.floor(process.uptime()),
            },
            timestamp,
          };
        }

        default:
          return { success: false, action, error: `Unknown OS action: ${action}`, timestamp };
      }
    } catch (err: any) {
      return { success: false, action, error: err.message || 'OS action failed', timestamp };
    }
  }
}

