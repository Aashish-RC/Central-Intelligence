import type { ChatCompletionRequest, ChatCompletionResponse } from '../types/chat.js';

export interface ShadowConfig {
  shadowModel: string;
  samplePercentage: number; // 0 to 100
  enabled: boolean;
}

export interface ShadowEvaluationRecord {
  requestId: string;
  primaryModel: string;
  shadowModel: string;
  primaryDurationMs: number;
  shadowDurationMs?: number;
  primaryTokens: number;
  shadowTokens?: number;
  shadowSuccess: boolean;
  shadowError?: string;
  timestamp: number;
}

export class ShadowRouter {
  private config: ShadowConfig;
  private evaluations: ShadowEvaluationRecord[] = [];
  private maxEvaluations = 1000;

  constructor(config: ShadowConfig = { shadowModel: '', samplePercentage: 0, enabled: false }) {
    this.config = config;
  }

  public updateConfig(config: Partial<ShadowConfig>): void {
    this.config = { ...this.config, ...config };
  }

  public shouldShadow(): boolean {
    if (!this.config.enabled || !this.config.shadowModel || this.config.samplePercentage <= 0) {
      return false;
    }
    if (this.config.samplePercentage >= 100) return true;
    return Math.random() * 100 < this.config.samplePercentage;
  }

  /**
   * Executes primary request and optionally dispatches background shadow emulation.
   */
  public async executeWithShadow(
    req: ChatCompletionRequest,
    requestId: string,
    primaryDispatcher: (request: ChatCompletionRequest) => Promise<ChatCompletionResponse>,
    shadowDispatcher: (request: ChatCompletionRequest) => Promise<ChatCompletionResponse>,
  ): Promise<ChatCompletionResponse> {
    const primaryStart = Date.now();
    const primaryResponse = await primaryDispatcher(req);
    const primaryDurationMs = Date.now() - primaryStart;
    const primaryTokens = primaryResponse.usage?.total_tokens || 0;

    if (this.shouldShadow()) {
      // Background fire-and-forget
      const shadowReq: ChatCompletionRequest = {
        ...req,
        model: this.config.shadowModel,
      };

      const shadowStart = Date.now();
      shadowDispatcher(shadowReq)
        .then((shadowResponse) => {
          const shadowDurationMs = Date.now() - shadowStart;
          this.recordEvaluation({
            requestId,
            primaryModel: req.model,
            shadowModel: this.config.shadowModel,
            primaryDurationMs,
            shadowDurationMs,
            primaryTokens,
            shadowTokens: shadowResponse.usage?.total_tokens || 0,
            shadowSuccess: true,
            timestamp: Date.now(),
          });
        })
        .catch((err: any) => {
          const shadowDurationMs = Date.now() - shadowStart;
          this.recordEvaluation({
            requestId,
            primaryModel: req.model,
            shadowModel: this.config.shadowModel,
            primaryDurationMs,
            shadowDurationMs,
            primaryTokens,
            shadowSuccess: false,
            shadowError: err.message || 'Shadow dispatch failed',
            timestamp: Date.now(),
          });
        });
    }

    return primaryResponse;
  }

  public recordEvaluation(record: ShadowEvaluationRecord): void {
    this.evaluations.push(record);
    if (this.evaluations.length > this.maxEvaluations) {
      this.evaluations.shift();
    }
  }

  public getEvaluations(): ShadowEvaluationRecord[] {
    return [...this.evaluations];
  }

  public clear(): void {
    this.evaluations = [];
  }
}
