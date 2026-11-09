import { describe, expect, it } from 'vitest';
import * as path from 'path';
import { getConnectorPiece, getConnectorAction, CONNECTOR_REGISTRY } from '../connectorRegistry.js';
import { openclawPiece } from '../pieces/openclaw.js';

describe('OpenClaw Connector (Layer 5)', () => {
  it('registers openclaw piece in connector registry', () => {
    const piece = getConnectorPiece('openclaw');
    expect(piece).toBeDefined();
    expect(piece?.pieceId).toBe('openclaw');
    expect(piece?.category).toBe('System & Communication');
    expect(CONNECTOR_REGISTRY).toContain(openclawPiece);
  });

  it('provides all expected actions', () => {
    const actionIds = openclawPiece.actions.map((a) => a.actionId);
    expect(actionIds).toContain('send_channel_message');
    expect(actionIds).toContain('open_file');
    expect(actionIds).toContain('launch_application');
    expect(actionIds).toContain('system_info');
  });

  it('runs send_channel_message action to deliver to Discord channel', async () => {
    const action = getConnectorAction('openclaw', 'send_channel_message');
    expect(action).toBeDefined();

    const result = (await action?.run({
      auth: { api_token: 'mock-token' },
      propsValue: {
        channel: 'discord',
        target_id: 'discord-channel-999',
        message: 'Hello Discord from Central Intelligence L5 Connector!',
      },
    })) as any;

    expect(result.delivered).toBe(true);
    expect(result.channel).toBe('discord');
    expect(result.targetId).toBe('discord-channel-999');
    expect(result.length).toBeGreaterThan(0);
  });

  it('runs open_file action to open and inspect a file on host machine', async () => {
    const action = getConnectorAction('openclaw', 'open_file');
    expect(action).toBeDefined();

    const testFile = path.resolve(process.cwd(), 'package.json');
    const result = (await action?.run({
      propsValue: { file_path: testFile },
    })) as any;

    expect(result.opened).toBe(true);
    expect(result.path).toBe(testFile);
    expect(result.sizeBytes).toBeGreaterThan(0);
  });

  it('throws an error when opening non-existent file', async () => {
    const action = getConnectorAction('openclaw', 'open_file');
    await expect(
      action?.run({ propsValue: { file_path: 'non-existent-file-xyz.txt' } }),
    ).rejects.toThrow('File does not exist on host');
  });

  it('runs launch_application and inspect_system actions', async () => {
    const launch = getConnectorAction('openclaw', 'launch_application');
    const launchResult = (await launch?.run({
      propsValue: { app_name: 'terminal' },
    })) as any;
    expect(launchResult.launched).toBe(true);
    expect(launchResult.appName).toBe('terminal');
    expect(launchResult.pid).toBeGreaterThan(0);

    const sysInfo = getConnectorAction('openclaw', 'system_info');
    const sysResult = (await sysInfo?.run({ propsValue: {} })) as any;
    expect(sysResult.platform).toBe(process.platform);
    expect(sysResult.arch).toBe(process.arch);
  });
});

