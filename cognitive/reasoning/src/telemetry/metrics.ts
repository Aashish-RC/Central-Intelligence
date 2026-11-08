export interface GatewayMetrics {
  requestsTotal: number;
  requestsByStatus: Record<number, number>;
  tokensInputTotal: number;
  tokensOutputTotal: number;
  cacheHitsTotal: number;
  cacheMissesTotal: number;
}

export class MetricsCollector {
  private static instance: MetricsCollector;
  private metrics: GatewayMetrics = {
    requestsTotal: 0,
    requestsByStatus: {},
    tokensInputTotal: 0,
    tokensOutputTotal: 0,
    cacheHitsTotal: 0,
    cacheMissesTotal: 0,
  };

  static getInstance(): MetricsCollector {
    if (!MetricsCollector.instance) {
      MetricsCollector.instance = new MetricsCollector();
    }
    return MetricsCollector.instance;
  }

  recordRequest(status: number): void {
    this.metrics.requestsTotal++;
    this.metrics.requestsByStatus[status] = (this.metrics.requestsByStatus[status] || 0) + 1;
  }

  recordTokens(inputTokens: number, outputTokens: number): void {
    this.metrics.tokensInputTotal += inputTokens;
    this.metrics.tokensOutputTotal += outputTokens;
  }

  recordCacheHit(): void {
    this.metrics.cacheHitsTotal++;
  }

  recordCacheMiss(): void {
    this.metrics.cacheMissesTotal++;
  }

  toPrometheusFormat(): string {
    const lines: string[] = [
      '# HELP gateway_requests_total Total number of HTTP requests handled',
      '# TYPE gateway_requests_total counter',
      `gateway_requests_total ${this.metrics.requestsTotal}`,
      '',
      '# HELP gateway_tokens_total Total tokens processed partitioned by direction',
      '# TYPE gateway_tokens_total counter',
      `gateway_tokens_total{type="input"} ${this.metrics.tokensInputTotal}`,
      `gateway_tokens_total{type="output"} ${this.metrics.tokensOutputTotal}`,
      '',
      '# HELP gateway_cache_hits_total Total response cache hits',
      '# TYPE gateway_cache_hits_total counter',
      `gateway_cache_hits_total ${this.metrics.cacheHitsTotal}`,
      '',
      '# HELP gateway_cache_misses_total Total response cache misses',
      '# TYPE gateway_cache_misses_total counter',
      `gateway_cache_misses_total ${this.metrics.cacheMissesTotal}`,
      '',
    ];

    for (const [status, count] of Object.entries(this.metrics.requestsByStatus)) {
      lines.push(`gateway_requests_by_status{code="${status}"} ${count}`);
    }

    return lines.join('\n') + '\n';
  }
}
