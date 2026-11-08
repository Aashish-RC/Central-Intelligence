import crypto from 'node:crypto';

export interface SpanAttributes {
  'gen_ai.system'?: string;
  'gen_ai.request.model'?: string;
  'gen_ai.response.model'?: string;
  'gen_ai.usage.input_tokens'?: number;
  'gen_ai.usage.output_tokens'?: number;
  'gen_ai.response.finish_reasons'?: string[];
  'http.status_code'?: number;
  'error.type'?: string;
  [key: string]: unknown;
}

export interface SpanRecord {
  name: string;
  traceId: string;
  spanId: string;
  parentSpanId?: string;
  startTimeMs: number;
  endTimeMs?: number;
  durationMs?: number;
  status: 'UNSET' | 'OK' | 'ERROR';
  errorMessage?: string;
  attributes: SpanAttributes;
}

export class OTelTracer {
  private static instance: OTelTracer;
  private spans: SpanRecord[] = [];
  private maxStoredSpans = 1000;

  public static getInstance(): OTelTracer {
    if (!OTelTracer.instance) {
      OTelTracer.instance = new OTelTracer();
    }
    return OTelTracer.instance;
  }

  /**
   * Generates or parses a W3C traceparent header.
   * Format: 00-{traceId}-{spanId}-{traceFlags}
   */
  public parseOrGenerateTraceContext(traceparentHeader?: string): {
    traceId: string;
    parentSpanId?: string;
  } {
    if (traceparentHeader) {
      const match = /^00-([a-f0-9]{32})-([a-f0-9]{16})-[a-f0-9]{2}$/.exec(traceparentHeader.trim());
      if (match) {
        return {
          traceId: match[1],
          parentSpanId: match[2],
        };
      }
    }

    return {
      traceId: crypto.randomBytes(16).toString('hex'),
    };
  }

  /**
   * Formats a W3C traceparent string for downstream propagation.
   */
  public formatTraceparent(traceId: string, spanId: string, sampled = true): string {
    const flags = sampled ? '01' : '00';
    return `00-${traceId}-${spanId}-${flags}`;
  }

  /**
   * Starts a new span.
   */
  public startSpan(
    name: string,
    context: { traceId: string; parentSpanId?: string; attributes?: SpanAttributes },
  ): {
    spanId: string;
    traceId: string;
    end: (
      status?: 'OK' | 'ERROR',
      errorMessage?: string,
      additionalAttrs?: SpanAttributes,
    ) => SpanRecord;
    setAttributes: (attrs: SpanAttributes) => void;
  } {
    const spanId = crypto.randomBytes(8).toString('hex');
    const startTimeMs = Date.now();

    const span: SpanRecord = {
      name,
      traceId: context.traceId,
      spanId,
      parentSpanId: context.parentSpanId,
      startTimeMs,
      status: 'UNSET',
      attributes: { ...(context.attributes || {}) },
    };

    return {
      spanId,
      traceId: context.traceId,
      setAttributes: (attrs: SpanAttributes) => {
        Object.assign(span.attributes, attrs);
      },
      end: (
        status: 'OK' | 'ERROR' = 'OK',
        errorMessage?: string,
        additionalAttrs?: SpanAttributes,
      ) => {
        const endTimeMs = Date.now();
        span.endTimeMs = endTimeMs;
        span.durationMs = Math.max(0, endTimeMs - startTimeMs);
        span.status = status;
        if (errorMessage) {
          span.errorMessage = errorMessage;
          span.attributes['error.type'] = errorMessage;
        }
        if (additionalAttrs) {
          Object.assign(span.attributes, additionalAttrs);
        }

        this.spans.push(span);
        if (this.spans.length > this.maxStoredSpans) {
          this.spans.shift();
        }

        return span;
      },
    };
  }

  public getSpansByTraceId(traceId: string): SpanRecord[] {
    return this.spans.filter((s) => s.traceId === traceId);
  }

  public getRecentSpans(limit = 50): SpanRecord[] {
    return this.spans.slice(-limit);
  }

  public clear(): void {
    this.spans = [];
  }
}
