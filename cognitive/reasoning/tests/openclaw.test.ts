import { describe, expect, it } from 'vitest';
import * as path from 'path';
import { OpenClawAdapter } from '../src/agents/openclawAdapter.js';

describe('OpenClawAdapter (Layer 4)', () => {
  const adapter = new OpenClawAdapter({ mockMode: true });

  it('lists supported channels', () => {
    const channels = adapter.listSupportedChannels();
    expect(channels).toContain('discord');
    expect(channels).toContain('slack');
    expect(channels).toContain('telegram');
    expect(channels).toContain('whatsapp');
    expect(channels).toContain('teams');
  });

  it('dispatches messages to a chat channel (Discord)', async () => {
    const result = await adapter.sendMessage({
      channel: 'discord',
      targetId: 'discord-channel-999',
      content: 'Hello Discord from Central Intelligence via OpenClaw!',
    });

    expect(result.success).toBe(true);
    expect(result.channel).toBe('discord');
    expect(result.output?.content).toBe(
      'Hello Discord from Central Intelligence via OpenClaw!',
    );

    const sent = adapter.getSentMessages();
    expect(sent).toHaveLength(1);
    expect(sent[0].targetId).toBe('discord-channel-999');
  });

  it('dispatches open_file OS action and inspects file stats', async () => {
    const readmePath = path.resolve(process.cwd(), 'package.json');
    const result = await adapter.dispatchOSAction('open_file', {
      filePath: readmePath,
    });

    expect(result.success).toBe(true);
    expect(result.action).toBe('open_file');
    expect(result.output.opened).toBe(true);
    expect(result.output.sizeBytes).toBeGreaterThan(0);
  });

  it('dispatches launch_app OS action', async () => {
    const result = await adapter.dispatchOSAction('launch_app', {
      appName: 'notepad',
    });

    expect(result.success).toBe(true);
    expect(result.output.app).toBe('notepad');
    expect(result.output.status).toBe('launched');
  });

  it('dispatches system_info OS action', async () => {
    const result = await adapter.dispatchOSAction('system_info');
    expect(result.success).toBe(true);
    expect(result.output.platform).toBe(process.platform);
    expect(result.output.nodeVersion).toBe(process.version);
  });
});

