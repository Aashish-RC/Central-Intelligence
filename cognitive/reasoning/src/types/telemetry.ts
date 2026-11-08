export interface MultiUnitUsage {
  promptTokens: number;
  completionTokens: number;
  reasoningTokens: number;
  cachedPromptTokens: number;
  totalTokens: number;
}

export interface ModelPricingTier {
  model: string;
  inputPer1k: number;
  outputPer1k: number;
  currency: string;
  sourceUrl: string;
  retrievedDate: string;
  reasoningPer1k?: number;
  cacheReadPer1k?: number;
  cacheWritePer1k?: number;
  sourceDate?: string;
}

export interface CalculatedCost {
  currency: 'USD';
  promptCost: number;
  completionCost: number;
  reasoningCost: number;
  cacheDiscount: number;
  totalCost: number;
}
