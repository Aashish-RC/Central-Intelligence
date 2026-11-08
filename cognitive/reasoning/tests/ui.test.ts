import { describe, expect, it } from 'vitest';
import { createGatewayApp } from '../src/core/server.js';
import { renderConsoleHtml } from '../src/ui/console.js';

describe('Feature 18: Embedded Control Console & Chat Playground UI', () => {
  it('renders valid standalone HTML document with Inter typography and controls', () => {
    const html = renderConsoleHtml();
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('Model Gateway Console');
    expect(html).toContain('playground-form');
    expect(html).toContain('smart-tier');
    expect(html).toContain('fast-tier');
    expect(html).toContain('System Telemetry');
  });

  it('serves console HTML at GET /console and GET /public with 200 OK when FEATURE_CONSOLE_UI is true', async () => {
    process.env.FEATURE_CONSOLE_UI = 'true';
    try {
      const { app } = createGatewayApp();

      const resConsole = await app.request('/console');
      expect(resConsole.status).toBe(200);
      expect(resConsole.headers.get('content-type')).toContain('text/html');
      const textConsole = await resConsole.text();
      expect(textConsole).toContain('Model Gateway Console');

      const resPublic = await app.request('/public');
      expect(resPublic.status).toBe(200);
      expect(resPublic.headers.get('content-type')).toContain('text/html');
      const textPublic = await resPublic.text();
      expect(textPublic).toContain('playground-form');
    } finally {
      delete process.env.FEATURE_CONSOLE_UI;
    }
  });
});
