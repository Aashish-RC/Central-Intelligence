import type { ClassifiedError, ErrorCategory } from '../types/resilience.js';

export class ErrorClassifier {
  public static classify(
    status: number,
    responseBody: unknown,
    headers?: Headers,
  ): ClassifiedError {
    const bodyStr =
      typeof responseBody === 'string' ? responseBody : JSON.stringify(responseBody || '');
    const lowerBody = bodyStr.toLowerCase();

    // 1. Timeout (408 or abort timeout)
    if (
      status === 408 ||
      lowerBody.includes('timeout') ||
      lowerBody.includes('timed out') ||
      lowerBody.includes('timeoutexception')
    ) {
      return {
        category: 'TIMEOUT',
        isRetryable: true,
        statusCode: 408,
        message: 'Upstream provider request timed out',
        retryAfterSeconds: 2,
        originalError: responseBody,
      };
    }

    // 2. Rate Limiting (429)
    if (
      status === 429 ||
      lowerBody.includes('rate_limit') ||
      lowerBody.includes('quota_exceeded')
    ) {
      const retryAfter = this.parseRetryAfter(headers, bodyStr);
      return {
        category: 'RATE_LIMIT',
        isRetryable: true,
        statusCode: 429,
        message: 'Rate limit or quota reached on upstream provider',
        retryAfterSeconds: retryAfter,
        originalError: responseBody,
      };
    }

    // 3. Overloaded / Server Down (502, 503, 504, 529)
    if (
      status === 502 ||
      status === 503 ||
      status === 504 ||
      status === 529 ||
      lowerBody.includes('overloaded')
    ) {
      return {
        category: 'OVERLOADED',
        isRetryable: true,
        statusCode: status,
        message: 'Upstream provider is temporarily overloaded or unavailable',
        retryAfterSeconds: 5,
        originalError: responseBody,
      };
    }

    // 4. Context Length Exceeded (Non-retryable 400)
    if (
      status === 400 &&
      (lowerBody.includes('context_length') ||
        lowerBody.includes('maximum context') ||
        lowerBody.includes('token count') ||
        lowerBody.includes('prompt too long'))
    ) {
      return {
        category: 'CONTEXT_LENGTH_EXCEEDED',
        isRetryable: false,
        statusCode: 400,
        message: 'Request prompt exceeds maximum context length for the model',
        originalError: responseBody,
      };
    }

    // 5. Auth / Permission Failure (401, 403)
    if (
      status === 401 ||
      status === 403 ||
      lowerBody.includes('invalid_api_key') ||
      lowerBody.includes('unauthorized')
    ) {
      return {
        category: 'AUTH_FAILURE',
        isRetryable: false,
        statusCode: status,
        message: 'Authentication or permission denied by upstream provider',
        originalError: responseBody,
      };
    }

    // 6. Invalid Request / Bad Parameter (Non-retryable 400)
    if (status === 400) {
      return {
        category: 'INVALID_REQUEST',
        isRetryable: false,
        statusCode: 400,
        message: 'Invalid request parameters sent to upstream provider',
        originalError: responseBody,
      };
    }

    // 7. Generic 500 Server Error (Retryable)
    if (status >= 500) {
      return {
        category: 'SERVER_ERROR',
        isRetryable: true,
        statusCode: status,
        message: 'Upstream provider encountered an unexpected internal server error',
        retryAfterSeconds: 3,
        originalError: responseBody,
      };
    }

    return {
      category: 'UNKNOWN',
      isRetryable: status >= 500,
      statusCode: status,
      message: 'Unclassified upstream error',
      originalError: responseBody,
    };
  }

  /**
   * Identifies client-side errors (4xx other than 429 and 408) that should not
   * count against endpoint health or cooldown, and must not trigger failover.
   */
  public static isClientNonRetryable(status: number): boolean {
    return status >= 400 && status < 500 && status !== 429 && status !== 408;
  }

  public static toOpenAIError(classified: ClassifiedError): {
    error: {
      message: string;
      type: string;
      param: null;
      code: string | number;
    };
  } {
    const typeMapping: Record<ErrorCategory, string> = {
      RATE_LIMIT: 'rate_limit_error',
      OVERLOADED: 'server_error',
      CONTEXT_LENGTH_EXCEEDED: 'invalid_request_error',
      INVALID_REQUEST: 'invalid_request_error',
      AUTH_FAILURE: 'authentication_error',
      TIMEOUT: 'timeout_error',
      SERVER_ERROR: 'api_error',
      UNKNOWN: 'api_error',
    };

    return {
      error: {
        message: classified.message,
        type: typeMapping[classified.category] || 'api_error',
        param: null,
        code: classified.statusCode,
      },
    };
  }

  private static parseRetryAfter(headers?: Headers, body?: string): number {
    if (headers && headers.has('retry-after')) {
      const val = Number.parseInt(headers.get('retry-after') || '0', 10);
      if (!isNaN(val) && val > 0) return val;
    }
    // Attempt parsing from body e.g. "try again in 12s"
    if (body) {
      const match = body.match(/try again in ([\d\.]+)s/i) || body.match(/retry after (\d+)/i);
      if (match && match[1]) {
        const parsed = Math.ceil(Number.parseFloat(match[1]));
        if (parsed > 0) return parsed;
      }
    }
    return 10; // Default 10s backoff for 429
  }
}
