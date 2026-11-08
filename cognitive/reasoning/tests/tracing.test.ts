import { beforeEach, describe, expect, it } from 'vitest';
import { OTelTracer } from '../src/telemetry/tracing.js';

describe('Feature 12: OpenTelemetry Distributed Tracing & GenAI Semantic Spans', () => {
  let tracer: OTelTracer;

  beforeEach(() => {
    tracer = OTelTracer.getInstance();
    tracer.clear();
  });

  it('parses valid W3C traceparent headers and generates fallback when absent', () => {
    const rawTraceparent = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01';
    const ctx = tracer.parseOrGenerateTraceContext(rawTraceparent);

    expect(ctx.traceId).toBe('4bf92f3577b34da6a3ce929d0e0e4736');
    expect(ctx.parentSpanId).toBe('00f067aa0ba902b7');

    const generated = tracer.parseOrGenerateTraceContext();
    expect(generated.traceId).toMatch(/^[a-f0-9]{32}$/);
    expect(generated.parentSpanId).toBeUndefined();
  });

  it('records GenAI semantic attributes and measures span duration accurately', async () => {
    const traceCtx = tracer.parseOrGenerateTraceContext();
    const activeSpan = tracer.startSpan('chat.completion', {
      traceId: traceCtx.traceId,
      attributes: {
        'gen_ai.system': 'openai',
        'gen_ai.request.model': 'gpt-4o',
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 20));

    const finished = activeSpan.end('OK', undefined, {
      'gen_ai.response.model': 'gpt-4o-2024-08-06',
      'gen_ai.usage.input_tokens': 15,
      'gen_ai.usage.output_tokens': 25,
      'http.status_code': 200,
    });

    expect(finished.status).toBe('OK');
    expect(finished.durationMs).toBeGreaterThanOrEqual(15);
    expect(finished.attributes['gen_ai.system']).toBe('openai');
    expect(finished.attributes['gen_ai.usage.input_tokens']).toBe(15);
    expect(finished.attributes['gen_ai.usage.output_tokens']).toBe(25);
    expect(finished.attributes['http.status_code']).toBe(200);

    const stored = tracer.getSpansByTraceId(traceCtx.traceId);
    expect(stored.length).toBe(1);
    expect(stored[0].spanId).toBe(activeSpan.spanId);
  });

  it('records error status and error description for failed requests', () => {
    const traceCtx = tracer.parseOrGenerateTraceContext();
    const span = tracer.startSpan('chat.completion', {
      traceId: traceCtx.traceId,
      attributes: { 'gen_ai.request.model': 'claude-3-5-sonnet' },
    });

    const finished = span.end('ERROR', 'Upstream 503 Service Unavailable', {
      'http.status_code': 503,
    });

    expect(finished.status).toBe('ERROR');
    expect(finished.errorMessage).toBe('Upstream 503 Service Unavailable');
    expect(finished.attributes['error.type']).toBe('Upstream 503 Service Unavailable');
    expect(finished.attributes['http.status_code']).toBe(503);
  });
});
