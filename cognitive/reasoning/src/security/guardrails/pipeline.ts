import type { ChatCompletionRequest, ChatCompletionResponse } from '../../types/chat.js';
import { PIIMaskingEngine } from '../pii.js';

export interface GuardrailContext {
  requestId: string;
  model: string;
  tenantId?: string;
  userId?: string;
  metadata?: Record<string, unknown>;
}

export interface GuardrailExecutionResult {
  action: 'allow' | 'block' | 'modify';
  reason?: string;
  modifiedRequest?: ChatCompletionRequest;
  modifiedResponse?: ChatCompletionResponse;
}

export interface GuardrailPlugin {
  name: string;
  beforeRequest?(
    req: ChatCompletionRequest,
    ctx: GuardrailContext,
  ): Promise<GuardrailExecutionResult | void> | GuardrailExecutionResult | void;
  afterResponse?(
    res: ChatCompletionResponse,
    ctx: GuardrailContext,
  ): Promise<GuardrailExecutionResult | void> | GuardrailExecutionResult | void;
}

/**
 * Built-in PII Guardrail Plugin (Clean-Room Reversible Tokenization)
 */
export class PIIGuardrailPlugin implements GuardrailPlugin {
  public name = 'pii-masking-guardrail';
  private piiEngine: PIIMaskingEngine;

  constructor(piiEngine?: PIIMaskingEngine) {
    this.piiEngine = piiEngine || new PIIMaskingEngine();
  }

  public beforeRequest(req: ChatCompletionRequest): GuardrailExecutionResult {
    const maskedReq = this.piiEngine.maskRequest(req);
    return {
      action: 'modify',
      modifiedRequest: maskedReq,
    };
  }

  public afterResponse(res: ChatCompletionResponse): GuardrailExecutionResult {
    const unmaskedRes = this.piiEngine.unmaskResponse(res);
    return {
      action: 'modify',
      modifiedResponse: unmaskedRes,
    };
  }
}

/**
 * Built-in Prompt Injection Detection Guardrail
 */
export class PromptInjectionGuardrailPlugin implements GuardrailPlugin {
  public name = 'prompt-injection-guardrail';
  private maliciousPatterns: RegExp[] = [
    /\bignore\s+(?:all\s+)?previous\s+instructions\b/i,
    /\bsystem\s+override\s*:\s*reveal\b/i,
    /\bjailbreak\s+mode\s+activated\b/i,
    /\bdisregard\s+(?:your\s+)?safety\s+guidelines\b/i,
  ];

  constructor(customPatterns?: RegExp[]) {
    if (customPatterns) {
      this.maliciousPatterns.push(...customPatterns);
    }
  }

  public beforeRequest(req: ChatCompletionRequest): GuardrailExecutionResult {
    for (const msg of req.messages) {
      const content = msg.content || '';
      for (const pattern of this.maliciousPatterns) {
        if (pattern.test(content)) {
          return {
            action: 'block',
            reason: `Prompt injection attack detected: matched security rule '${pattern.source}'`,
          };
        }
      }
    }

    return { action: 'allow' };
  }
}

/**
 * Built-in Message Length Guardrail
 */
export class MaxMessageLengthGuardrailPlugin implements GuardrailPlugin {
  public name = 'max-message-length-guardrail';
  private maxChars: number;

  constructor(maxChars = 32000) {
    this.maxChars = maxChars;
  }

  public beforeRequest(req: ChatCompletionRequest): GuardrailExecutionResult {
    for (const msg of req.messages) {
      if ((msg.content || '').length > this.maxChars) {
        return {
          action: 'block',
          reason: `Message length ${(msg.content || '').length} exceeds guardrail limit of ${this.maxChars} characters.`,
        };
      }
    }
    return { action: 'allow' };
  }
}

/**
 * Modular Guardrail Pipeline Engine
 */
export class GuardrailPipeline {
  private plugins: GuardrailPlugin[] = [];

  constructor(initialPlugins: GuardrailPlugin[] = []) {
    this.plugins = [...initialPlugins];
  }

  public use(plugin: GuardrailPlugin): this {
    this.plugins.push(plugin);
    return this;
  }

  public async executeBeforeRequest(
    request: ChatCompletionRequest,
    ctx: GuardrailContext,
  ): Promise<{ allowed: boolean; reason?: string; request: ChatCompletionRequest }> {
    let currentReq = request;

    for (const plugin of this.plugins) {
      if (!plugin.beforeRequest) continue;

      const result = await plugin.beforeRequest(currentReq, ctx);
      if (!result) continue;

      if (result.action === 'block') {
        return {
          allowed: false,
          reason: result.reason || `Blocked by guardrail '${plugin.name}'`,
          request: currentReq,
        };
      }

      if (result.action === 'modify' && result.modifiedRequest) {
        currentReq = result.modifiedRequest;
      }
    }

    return { allowed: true, request: currentReq };
  }

  public async executeAfterResponse(
    response: ChatCompletionResponse,
    ctx: GuardrailContext,
  ): Promise<{ response: ChatCompletionResponse }> {
    let currentRes = response;

    for (const plugin of this.plugins) {
      if (!plugin.afterResponse) continue;

      const result = await plugin.afterResponse(currentRes, ctx);
      if (!result) continue;

      if (result.action === 'modify' && result.modifiedResponse) {
        currentRes = result.modifiedResponse;
      }
    }

    return { response: currentRes };
  }
}
