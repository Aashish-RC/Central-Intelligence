/**
 * Slack Connector — send_message action.
 *
 * Adapted from ActivePieces community/slack piece (MIT License).
 * Source reference: clones/activepieces/packages/pieces/community/slack/src/index.ts
 * No code copied — pure native TypeScript re-implementation following the connector contract.
 * License: MIT (ActivePieces community piece pattern)
 */

import type { ConnectorPiece, ConnectorContext } from '../connectorContract.js';

export const slackPiece: ConnectorPiece = {
  pieceId: 'slack',
  displayName: 'Slack',
  description: 'Send messages and interact with Slack workspaces.',
  logoEmoji: '💬',
  authType: 'secret_text',
  authFields: [
    {
      key: 'bot_token',
      displayName: 'Bot Token',
      required: true,
      type: 'password',
    },
  ],
  category: 'Communication',
  licenseNote: 'Adapted from ActivePieces community/slack (MIT). No upstream code copied.',
  actions: [
    {
      actionId: 'send_message',
      displayName: 'Send Channel Message',
      description: 'Post a message to a Slack channel.',
      consequential: true,
      consequentialReason: 'Posts an external message to a Slack channel.',
      props: [
        {
          key: 'channel',
          displayName: 'Channel',
          description: 'Channel ID or name (e.g. #general or C12345)',
          type: 'short_text',
          required: true,
        },
        {
          key: 'text',
          displayName: 'Message Text',
          description: 'The message content to post.',
          type: 'long_text',
          required: true,
        },
        {
          key: 'username',
          displayName: 'Bot Username Override',
          description: 'Optional custom display name for the bot.',
          type: 'short_text',
          required: false,
        },
      ],
      async run(ctx: ConnectorContext): Promise<unknown> {
        const token = ctx.auth?.bot_token;
        if (!token) throw new Error('Slack bot_token is required.');

        const body: Record<string, unknown> = {
          channel: ctx.propsValue.channel,
          text: ctx.propsValue.text,
        };
        if (ctx.propsValue.username) {
          body.username = ctx.propsValue.username;
        }

        const res = await fetch('https://slack.com/api/chat.postMessage', {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
        });

        if (!res.ok) {
          throw new Error(`Slack API error: HTTP ${res.status}`);
        }

        const data = (await res.json()) as { ok: boolean; error?: string };
        if (!data.ok) {
          throw new Error(`Slack API error: ${data.error}`);
        }

        return data;
      },
    },
  ],
};
