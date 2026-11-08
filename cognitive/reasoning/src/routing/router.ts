import type { CooldownTracker } from '../resilience/cooldown.js';
import type { ProviderConfig } from '../types/provider.js';

export interface RouteTarget {
  id: string;
  provider: string; // 'openai' | 'anthropic' | 'ollama'
  model: string;
  config: ProviderConfig;
  weight?: number;
  isEscapeRoute?: boolean;
}

export interface ModelRouteConfig {
  alias: string;
  targets: RouteTarget[];
  strategy?: 'weighted' | 'least-busy' | 'prompt-cache-affinity';
}

export class ModelRouter {
  private routes: Map<string, ModelRouteConfig> = new Map();
  private cooldownTracker: CooldownTracker;

  constructor(cooldownTracker: CooldownTracker) {
    this.cooldownTracker = cooldownTracker;
  }

  public registerRoute(route: ModelRouteConfig): void {
    this.routes.set(route.alias.toLowerCase(), route);
  }

  public resolveTargets(alias: string, promptPrefixForAffinity?: string): RouteTarget[] {
    const route = this.routes.get(alias.toLowerCase());
    if (!route) {
      // Default fallback: direct passthrough if no route configured
      return [];
    }

    const primaryTargets = route.targets.filter((t) => !t.isEscapeRoute);
    const escapeTargets = route.targets.filter((t) => t.isEscapeRoute);

    // Filter by health
    const healthyPrimaries = primaryTargets.filter((t) => this.cooldownTracker.isAvailable(t.id));

    if (healthyPrimaries.length === 0) {
      // All primary targets are down or in cooldown! Activate Escape Route!
      if (escapeTargets.length > 0) {
        console.warn(
          `[Router] All primary endpoints for ${alias} are in cooldown. Activating Escape Route!`,
        );
        return escapeTargets;
      }
      // If no escape route, return primary targets anyway to allow retry or error classification
      return primaryTargets;
    }

    // Apply Strategy
    if (route.strategy === 'prompt-cache-affinity' && promptPrefixForAffinity) {
      const hash = this.hashString(promptPrefixForAffinity);
      const stickyIdx = Math.abs(hash) % healthyPrimaries.length;
      const stickyTarget = healthyPrimaries[stickyIdx];

      // Put sticky target first, follow with other healthy targets as fallbacks
      return [stickyTarget, ...healthyPrimaries.filter((_, idx) => idx !== stickyIdx)];
    }

    if (route.strategy === 'least-busy') {
      // Sort ascending by in-flight requests
      return [...healthyPrimaries].sort((a, b) => {
        const hA = this.cooldownTracker.getOrCreate(a.id);
        const hB = this.cooldownTracker.getOrCreate(b.id);
        return hA.inFlightRequests - hB.inFlightRequests;
      });
    }

    // Default: Weighted / Order of declaration
    return healthyPrimaries;
  }

  private hashString(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash |= 0; // Convert to 32bit integer
    }
    return hash;
  }
}
