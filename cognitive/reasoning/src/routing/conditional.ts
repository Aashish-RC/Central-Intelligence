import type { ChatCompletionRequest } from '../types/chat.js';

export interface ConditionalRoutingRule {
  name: string;
  condition: {
    header?: { key: string; equals?: string; regex?: string };
    promptRegex?: RegExp | string;
    minPromptLength?: number;
    maxPromptLength?: number;
    customMatcher?: (req: ChatCompletionRequest, headers: Record<string, string>) => boolean;
  };
  targetModel: string;
}

export class ConditionalRouter {
  private rules: ConditionalRoutingRule[] = [];

  constructor(rules: ConditionalRoutingRule[] = []) {
    this.rules = [...rules];
  }

  public addRule(rule: ConditionalRoutingRule): this {
    this.rules.push(rule);
    return this;
  }

  /**
   * Evaluates rules in order and returns the routed model or the original request model.
   */
  public resolveModel(
    req: ChatCompletionRequest,
    headers: Record<string, string> = {},
  ): { model: string; matchedRule?: string } {
    const promptText = req.messages.map((m) => m.content || '').join(' ');
    const normalizedHeaders: Record<string, string> = {};
    for (const [k, v] of Object.entries(headers)) {
      normalizedHeaders[k.toLowerCase()] = v;
    }

    for (const rule of this.rules) {
      const cond = rule.condition;

      // Header matching
      if (cond.header) {
        const headerVal = normalizedHeaders[cond.header.key.toLowerCase()];
        if (!headerVal) continue;
        if (cond.header.equals && headerVal !== cond.header.equals) continue;
        if (cond.header.regex && !new RegExp(cond.header.regex, 'i').test(headerVal)) continue;
      }

      // Prompt length conditions
      if (cond.minPromptLength !== undefined && promptText.length < cond.minPromptLength) {
        continue;
      }
      if (cond.maxPromptLength !== undefined && promptText.length > cond.maxPromptLength) {
        continue;
      }

      // Prompt regex condition
      if (cond.promptRegex) {
        const regex =
          typeof cond.promptRegex === 'string'
            ? new RegExp(cond.promptRegex, 'i')
            : cond.promptRegex;
        if (!regex.test(promptText)) continue;
      }

      // Custom matcher
      if (cond.customMatcher && !cond.customMatcher(req, normalizedHeaders)) {
        continue;
      }

      return { model: rule.targetModel, matchedRule: rule.name };
    }

    return { model: req.model };
  }

  public clear(): void {
    this.rules = [];
  }
}
