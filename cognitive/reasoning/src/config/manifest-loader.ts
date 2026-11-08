import { z } from 'zod';

export const ProviderManifestSchema = z.object({
  id: z.string(),
  type: z.string(),
  baseUrl: z.string().optional(),
  apiKey: z.string().optional(),
  region: z.string().optional(),
  timeoutMs: z.number().optional(),
});

export const VirtualTierManifestSchema = z.object({
  tierName: z.string(),
  strategy: z
    .enum(['least-busy', 'round-robin', 'priority', 'prompt-cache-affinity'])
    .default('priority'),
  candidates: z.array(z.string()).min(1),
  fallbackChain: z.array(z.string()).optional(),
});

export const BudgetManifestSchema = z.object({
  id: z.string(),
  scope: z.enum(['organization', 'team', 'user', 'key']),
  maxSpendUsd: z.number().positive(),
  window: z.enum(['daily', 'monthly', 'lifetime']),
});

export const GatewayManifestSchema = z.object({
  version: z.string().default('1.0'),
  server: z
    .object({
      port: z.number().default(8080),
      host: z.string().default('0.0.0.0'),
      timeoutMs: z.number().default(30000),
    })
    .optional(),
  providers: z.array(ProviderManifestSchema).default([]),
  virtualTiers: z.array(VirtualTierManifestSchema).default([]),
  budgets: z.array(BudgetManifestSchema).default([]),
});

export type GatewayManifest = z.infer<typeof GatewayManifestSchema>;

export class ManifestLoader {
  /**
   * Parses and validates a JSON or YAML-like manifest object or string.
   */
  public static loadFromString(rawContent: string): GatewayManifest {
    let parsed: unknown;
    try {
      parsed = JSON.parse(rawContent);
    } catch {
      // Basic YAML parser for simple key-value YAML files without requiring external heavy deps
      parsed = this.parseSimpleYaml(rawContent);
    }
    return GatewayManifestSchema.parse(parsed);
  }

  public static loadFromObject(obj: unknown): GatewayManifest {
    return GatewayManifestSchema.parse(obj);
  }

  /**
   * Minimalist fallback YAML parser for standard YAML structures.
   */
  private static parseSimpleYaml(yaml: string): Record<string, unknown> {
    const lines = yaml.split('\n').filter((l) => l.trim() && !l.trim().startsWith('#'));
    const result: Record<string, any> = {};

    for (const line of lines) {
      const colonIdx = line.indexOf(':');
      if (colonIdx === -1) continue;
      const key = line.slice(0, colonIdx).trim();
      let val = line.slice(colonIdx + 1).trim();

      if (val.startsWith('"') && val.endsWith('"')) {
        val = val.slice(1, -1);
      } else if (!isNaN(Number(val)) && val !== '') {
        val = Number(val) as any;
      }
      result[key] = val;
    }
    return result;
  }
}
