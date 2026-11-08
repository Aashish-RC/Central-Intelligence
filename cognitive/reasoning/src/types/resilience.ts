export type ErrorCategory =
  | 'RATE_LIMIT'
  | 'OVERLOADED'
  | 'CONTEXT_LENGTH_EXCEEDED'
  | 'INVALID_REQUEST'
  | 'AUTH_FAILURE'
  | 'TIMEOUT'
  | 'SERVER_ERROR'
  | 'UNKNOWN';

export interface ClassifiedError {
  category: ErrorCategory;
  isRetryable: boolean;
  statusCode: number;
  message: string;
  retryAfterSeconds?: number;
  originalError?: unknown;
}

export interface EndpointHealth {
  endpointId: string;
  consecutiveFailures: number;
  isInCooldown: boolean;
  cooldownUntil: number;
  lastSuccess: number;
  lastFailure: number;
  inFlightRequests: number;
  movingAverageLatencyMs: number;
}
