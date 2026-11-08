/**
 * HTTP Request Connector — generic HTTP action.
 *
 * Adapted from ActivePieces community HTTP utility pattern (MIT License).
 * No code copied — pure native TypeScript implementation.
 * License: MIT (ActivePieces community piece pattern)
 */

import type { ConnectorPiece, ConnectorContext } from '../connectorContract.js';

export const httpPiece: ConnectorPiece = {
  pieceId: 'http',
  displayName: 'HTTP Request',
  description: 'Make arbitrary HTTP/HTTPS requests to any URL.',
  logoEmoji: '🌐',
  authType: 'none',
  category: 'Core',
  licenseNote: 'Adapted from ActivePieces community HTTP utility (MIT). No upstream code copied.',
  actions: [
    {
      actionId: 'request',
      displayName: 'Send HTTP Request',
      description: 'Send an HTTP request and receive the response body.',
      props: [
        {
          key: 'url',
          displayName: 'URL',
          description: 'The full URL to send the request to.',
          type: 'short_text',
          required: true,
        },
        {
          key: 'method',
          displayName: 'Method',
          description: 'HTTP verb to use.',
          type: 'dropdown',
          required: true,
          defaultValue: 'GET',
          options: [
            { label: 'GET', value: 'GET' },
            { label: 'POST', value: 'POST' },
            { label: 'PUT', value: 'PUT' },
            { label: 'PATCH', value: 'PATCH' },
            { label: 'DELETE', value: 'DELETE' },
          ],
        },
        {
          key: 'headers',
          displayName: 'Headers (JSON)',
          description: 'Request headers as a JSON object, e.g. {"Authorization":"Bearer token"}',
          type: 'object',
          required: false,
        },
        {
          key: 'body',
          displayName: 'Request Body',
          description: 'Request body (JSON string or plain text).',
          type: 'long_text',
          required: false,
        },
        {
          key: 'timeout_ms',
          displayName: 'Timeout (ms)',
          description: 'Request timeout in milliseconds. Default: 10000.',
          type: 'number',
          required: false,
          defaultValue: 10000,
        },
      ],
      async run(ctx: ConnectorContext): Promise<unknown> {
        const url = String(ctx.propsValue.url);
        const method = String(ctx.propsValue.method || 'GET');
        const headersRaw = ctx.propsValue.headers;
        const body = ctx.propsValue.body as string | undefined;
        const timeoutMs = Number(ctx.propsValue.timeout_ms || 10000);

        let headers: Record<string, string> = {};
        if (headersRaw) {
          if (typeof headersRaw === 'string') {
            try {
              headers = JSON.parse(headersRaw);
            } catch {
              headers = {};
            }
          } else if (typeof headersRaw === 'object') {
            headers = headersRaw as Record<string, string>;
          }
        }

        const controller = new AbortController();
        const timerId = setTimeout(() => controller.abort(), timeoutMs);

        try {
          const res = await fetch(url, {
            method,
            headers,
            body: body && ['POST', 'PUT', 'PATCH'].includes(method) ? body : undefined,
            signal: controller.signal,
          });

          clearTimeout(timerId);

          const responseText = await res.text();
          let responseBody: unknown = responseText;
          try {
            responseBody = JSON.parse(responseText);
          } catch {
            // Not JSON — keep as string
          }

          return {
            status: res.status,
            statusText: res.statusText,
            headers: Object.fromEntries(res.headers as any),
            body: responseBody,
          };
        } catch (err) {
          clearTimeout(timerId);
          throw new Error(
            `HTTP request failed: ${err instanceof Error ? err.message : String(err)}`
          );
        }
      },
    },
  ],
};
