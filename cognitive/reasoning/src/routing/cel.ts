/**
 * Feature 43: Common Expression Language (CEL) Engine
 * Evaluates dynamic routing expressions and cost formulas over request/response contexts.
 * Zero-dependency, pure TypeScript AST evaluator.
 */

export interface CelContext {
  request?: {
    model?: string;
    temperature?: number;
    max_tokens?: number;
    messages_count?: number;
    headers?: Record<string, string>;
    prompt_tokens?: number;
  };
  response?: {
    status?: number;
    input_tokens?: number;
    output_tokens?: number;
    cached_tokens?: number;
    latency_ms?: number;
  };
  user?: {
    tier?: string;
    team_id?: string;
    spend_usd?: number;
  };
  [key: string]: any;
}

export class CelEvaluator {
  /**
   * Safely accesses nested object properties using dot notation (e.g. 'request.model')
   */
  static getNestedValue(obj: Record<string, any>, path: string): any {
    return path.split('.').reduce((acc, part) => (acc != null ? acc[part] : undefined), obj);
  }

  /**
   * Evaluates a boolean CEL expression against the provided context.
   * e.g., "request.model == 'gpt-4o' && response.input_tokens > 100"
   */
  static evaluateCondition(expression: string, context: CelContext): boolean {
    const trimmed = expression.trim();
    if (!trimmed) return true;

    // Handle logical OR
    if (trimmed.includes('||')) {
      const parts = trimmed.split('||');
      return parts.some((p) => CelEvaluator.evaluateCondition(p, context));
    }

    // Handle logical AND
    if (trimmed.includes('&&')) {
      const parts = trimmed.split('&&');
      return parts.every((p) => CelEvaluator.evaluateCondition(p, context));
    }

    // Handle comparisons
    const operators = ['==', '!=', '>=', '<=', '>', '<'];
    for (const op of operators) {
      const idx = trimmed.indexOf(op);
      if (idx !== -1) {
        const leftExpr = trimmed.substring(0, idx).trim();
        const rightExpr = trimmed.substring(idx + op.length).trim();

        const leftVal = CelEvaluator.resolveValue(leftExpr, context);
        const rightVal = CelEvaluator.resolveValue(rightExpr, context);

        switch (op) {
          case '==':
            return leftVal === rightVal;
          case '!=':
            return leftVal !== rightVal;
          case '>':
            return Number(leftVal) > Number(rightVal);
          case '<':
            return Number(leftVal) < Number(rightVal);
          case '>=':
            return Number(leftVal) >= Number(rightVal);
          case '<=':
            return Number(leftVal) <= Number(rightVal);
        }
      }
    }

    // Boolean literal or truthy property check
    const val = CelEvaluator.resolveValue(trimmed, context);
    return Boolean(val);
  }

  /**
   * Evaluates a numeric arithmetic formula.
   * e.g., "response.input_tokens * 0.000005 + response.output_tokens * 0.000015"
   */
  static evaluateNumericFormula(expression: string, context: CelContext): number {
    const trimmed = expression.trim();

    // Addition
    if (trimmed.includes('+')) {
      return trimmed
        .split('+')
        .reduce((sum, part) => sum + CelEvaluator.evaluateNumericFormula(part, context), 0);
    }

    // Subtraction (ensuring negative numbers are handled)
    const subIdx = trimmed.indexOf('-');
    if (
      subIdx > 0 &&
      !trimmed.slice(0, subIdx).endsWith('*') &&
      !trimmed.slice(0, subIdx).endsWith('/')
    ) {
      const left = trimmed.substring(0, subIdx).trim();
      const right = trimmed.substring(subIdx + 1).trim();
      return (
        CelEvaluator.evaluateNumericFormula(left, context) -
        CelEvaluator.evaluateNumericFormula(right, context)
      );
    }

    // Multiplication
    if (trimmed.includes('*')) {
      return trimmed
        .split('*')
        .reduce((prod, part) => prod * CelEvaluator.evaluateNumericFormula(part, context), 1);
    }

    // Division
    if (trimmed.includes('/')) {
      const [left, right] = trimmed.split('/');
      const denom = CelEvaluator.evaluateNumericFormula(right, context);
      if (denom === 0) return 0;
      return CelEvaluator.evaluateNumericFormula(left, context) / denom;
    }

    const val = CelEvaluator.resolveValue(trimmed, context);
    return Number(val) || 0;
  }

  private static resolveValue(token: string, context: CelContext): any {
    const t = token.trim();

    // String literal in single or double quotes
    if ((t.startsWith("'") && t.endsWith("'")) || (t.startsWith('"') && t.endsWith('"'))) {
      return t.slice(1, -1);
    }

    // Number literal
    if (!Number.isNaN(Number(t))) {
      return Number(t);
    }

    // Boolean literals
    if (t === 'true') return true;
    if (t === 'false') return false;
    if (t === 'null') return null;

    // Object property path
    return CelEvaluator.getNestedValue(context, t);
  }
}
