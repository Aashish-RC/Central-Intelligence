import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { CalculatedCost, ModelPricingTier, MultiUnitUsage } from '../types/telemetry.js';

export class PricingEngine {
  private static pricingTable: Map<string, ModelPricingTier> = new Map();
  private static initialized = false;

  private static ensureInitialized(): void {
    if (this.initialized) return;
    try {
      const currentDir = dirname(fileURLToPath(import.meta.url));
      const jsonPath = join(currentDir, 'pricing-data.json');
      const raw = readFileSync(jsonPath, 'utf-8');
      const parsed = JSON.parse(raw);
      if (parsed.models) {
        for (const [key, tier] of Object.entries(parsed.models)) {
          this.pricingTable.set(key.toLowerCase(), tier as ModelPricingTier);
        }
      }
    } catch (err) {
      console.warn(`[PricingEngine] Failed to load pricing-data.json, fallback active:`, err);
    }
    this.initialized = true;
  }

  public static registerTier(tier: ModelPricingTier): void {
    this.ensureInitialized();
    this.pricingTable.set(tier.model.toLowerCase(), tier);
  }

  public static getTier(model: string): ModelPricingTier | null {
    this.ensureInitialized();
    return this.pricingTable.get(model.toLowerCase()) || null;
  }

  /**
   * Calculates cost for a given model and usage.
   * If the model pricing tier is unknown, returns null (never a silent default price).
   */
  public static calculateCost(model: string, usage: MultiUnitUsage): CalculatedCost | null {
    const tier = this.getTier(model);
    if (!tier) {
      return null;
    }

    const regularPromptTokens = Math.max(0, usage.promptTokens - usage.cachedPromptTokens);
    const promptCost = (regularPromptTokens / 1000) * tier.inputPer1k;

    const cacheRate = tier.cacheReadPer1k ?? tier.inputPer1k * 0.5;
    const cachedPromptCost = (usage.cachedPromptTokens / 1000) * cacheRate;
    const cacheDiscount = (usage.cachedPromptTokens / 1000) * tier.inputPer1k - cachedPromptCost;

    const completionCost = (usage.completionTokens / 1000) * tier.outputPer1k;
    const reasoningRate = tier.reasoningPer1k ?? tier.outputPer1k;
    const reasoningCost = (usage.reasoningTokens / 1000) * reasoningRate;

    const totalCost = promptCost + cachedPromptCost + completionCost + reasoningCost;

    return {
      currency: 'USD',
      promptCost: Number(promptCost.toFixed(6)),
      completionCost: Number(completionCost.toFixed(6)),
      reasoningCost: Number(reasoningCost.toFixed(6)),
      cacheDiscount: Number(Math.max(0, cacheDiscount).toFixed(6)),
      totalCost: Number(totalCost.toFixed(6)),
    };
  }
}
