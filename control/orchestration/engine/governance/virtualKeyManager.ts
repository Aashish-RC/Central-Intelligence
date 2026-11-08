/**
 * Virtual Key Manager
 * Native TypeScript governance layer inspired by LiteLLM's virtual-key pattern.
 * Scopes keys per user or team, keeps provider credentials secret.
 */

import { nanoid } from 'nanoid';
import type { VirtualKey } from '../types.js';

export class VirtualKeyManager {
  private keys: Map<string, VirtualKey> = new Map();

  createKey(params: {
    userId: string;
    teamId?: string;
    name?: string;
    expiresInDays?: number;
    rateLimitRPM?: number;
    rateLimitTPM?: number;
    maxSpendUSD?: number;
    allowedModels?: string[];
    deniedModels?: string[];
  }): VirtualKey {
    const prefix = params.teamId ? 'vk-team-' : 'vk-usr-';
    const key = `${prefix}${nanoid(24)}`;
    const now = Date.now();
    const expiresAt = params.expiresInDays
      ? now + params.expiresInDays * 24 * 60 * 60 * 1000
      : undefined;

    const vk: VirtualKey = {
      key,
      userId: params.userId,
      teamId: params.teamId,
      name: params.name || `Key for ${params.userId}`,
      createdAt: now,
      expiresAt,
      revoked: false,
      rateLimitRPM: params.rateLimitRPM,
      rateLimitTPM: params.rateLimitTPM,
      maxSpendUSD: params.maxSpendUSD,
      allowedModels: params.allowedModels,
      deniedModels: params.deniedModels,
    };

    this.keys.set(key, vk);
    return vk;
  }

  validateKey(key: string): VirtualKey {
    const vk = this.keys.get(key);
    if (!vk) {
      throw new Error(`Invalid virtual key: "${key}" does not exist.`);
    }
    if (vk.revoked) {
      throw new Error(`Virtual key "${key}" has been revoked.`);
    }
    if (vk.expiresAt && Date.now() > vk.expiresAt) {
      throw new Error(`Virtual key "${key}" has expired.`);
    }
    return vk;
  }

  revokeKey(key: string): boolean {
    const vk = this.keys.get(key);
    if (vk) {
      vk.revoked = true;
      return true;
    }
    return false;
  }

  getKey(key: string): VirtualKey | undefined {
    return this.keys.get(key);
  }

  getKeysForUser(userId: string): VirtualKey[] {
    return Array.from(this.keys.values()).filter((k) => k.userId === userId);
  }
}
