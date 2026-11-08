import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { createGatewayApp } from '../src/core/server.js';

describe('Feature Flags Gating for Non-Gateway Modules', () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    delete process.env.FEATURE_CONSOLE_UI;
    delete process.env.FEATURE_MCP;
    delete process.env.FEATURE_TOOL_SEARCH;
    delete process.env.FEATURE_A2A;
    delete process.env.FEATURE_SECRETS_SYNC;
  });

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  describe('FEATURE_CONSOLE_UI', () => {
    it('returns 404 when flag is off (default)', async () => {
      const { app } = createGatewayApp();
      const res = await app.request('/console');
      expect(res.status).toBe(404);
    });

    it('returns 200 when flag is on', async () => {
      process.env.FEATURE_CONSOLE_UI = 'true';
      const { app } = createGatewayApp();
      const res = await app.request('/console');
      expect(res.status).toBe(200);
    });
  });

  describe('FEATURE_MCP', () => {
    it('returns 404 when flag is off (default)', async () => {
      const { app } = createGatewayApp();
      const res = await app.request('/v1/mcp/tools');
      expect(res.status).toBe(404);
    });

    it('returns 200 when flag is on', async () => {
      process.env.FEATURE_MCP = 'true';
      const { app } = createGatewayApp();
      const res = await app.request('/v1/mcp/tools');
      expect(res.status).toBe(200);
      const json = (await res.json()) as any;
      expect(Array.isArray(json.tools)).toBe(true);
    });
  });

  describe('FEATURE_TOOL_SEARCH', () => {
    it('returns 404 when flag is off (default)', async () => {
      const { app } = createGatewayApp();
      const res = await app.request('/v1/tools/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'database' }),
      });
      expect(res.status).toBe(404);
    });

    it('returns 200 when flag is on', async () => {
      process.env.FEATURE_TOOL_SEARCH = 'true';
      const { app } = createGatewayApp();
      const res = await app.request('/v1/tools/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: 'database sql query',
          tools: [
            {
              name: 'sql_tool',
              description: 'Run SQL select queries against database',
              inputSchema: { type: 'object', properties: {} },
            },
          ],
        }),
      });
      expect(res.status).toBe(200);
      const json = (await res.json()) as any;
      expect(json.results[0].name).toBe('sql_tool');
    });
  });

  describe('FEATURE_A2A', () => {
    it('returns 404 when flag is off (default)', async () => {
      const { app } = createGatewayApp();
      const res = await app.request('/v1/a2a/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          taskId: 'task_test_01',
          senderAgentId: 'orch',
          requiredCapability: 'code',
          input: 'hello',
        }),
      });
      expect(res.status).toBe(404);
    });

    it('returns 200 when flag is on', async () => {
      process.env.FEATURE_A2A = 'true';
      const { app } = createGatewayApp();
      const res = await app.request('/v1/a2a/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          taskId: 'task_test_01',
          senderAgentId: 'orch',
          requiredCapability: 'unsupported',
          input: 'hello',
        }),
      });
      expect(res.status).toBe(200);
      const json = (await res.json()) as any;
      expect(json.status).toBe('rejected');
    });
  });

  describe('FEATURE_SECRETS_SYNC', () => {
    it('returns 404 when flag is off (default)', async () => {
      const { app } = createGatewayApp();
      const res = await app.request('/v1/secrets/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backend: 'memory' }),
      });
      expect(res.status).toBe(404);
    });

    it('returns 200 when flag is on', async () => {
      process.env.FEATURE_SECRETS_SYNC = 'true';
      const { app } = createGatewayApp();
      const res = await app.request('/v1/secrets/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backend: 'memory' }),
      });
      expect(res.status).toBe(200);
      const json = (await res.json()) as any;
      expect(json.status).toBe('synchronized');
    });
  });
});
