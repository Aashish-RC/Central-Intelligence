export interface ByokCredentials {
  apiKey?: string;
  provider?: string;
  sourceHeader: string;
}

export class ByokResolver {
  private static HEADER_MAP: Record<string, string> = {
    'x-provider-api-key': 'auto',
    'x-openai-api-key': 'openai',
    'x-anthropic-api-key': 'anthropic',
    'x-gemini-api-key': 'gemini',
    'x-groq-api-key': 'groq',
    'x-bedrock-api-key': 'bedrock',
  };

  /**
   * Resolves client-supplied Bring-Your-Own-Key from standard request headers.
   */
  resolveKey(
    headers: Headers | Record<string, string | undefined>,
    targetProvider?: string,
  ): ByokCredentials | null {
    const getHeader = (name: string): string | undefined => {
      if (headers instanceof Headers) {
        return headers.get(name) || undefined;
      }
      return headers[name] || headers[name.toLowerCase()];
    };

    // 1. Direct provider header (e.g. x-openai-api-key)
    if (targetProvider) {
      const specificHeader = `x-${targetProvider.toLowerCase()}-api-key`;
      const val = getHeader(specificHeader);
      if (val && val.trim().length > 0) {
        return {
          apiKey: val.trim(),
          provider: targetProvider,
          sourceHeader: specificHeader,
        };
      }
    }

    // 2. Generic header (x-provider-api-key)
    const genericKey = getHeader('x-provider-api-key');
    if (genericKey && genericKey.trim().length > 0) {
      return {
        apiKey: genericKey.trim(),
        provider: targetProvider,
        sourceHeader: 'x-provider-api-key',
      };
    }

    // 3. Check any other matched headers
    for (const [headerName, provider] of Object.entries(ByokResolver.HEADER_MAP)) {
      const val = getHeader(headerName);
      if (val && val.trim().length > 0) {
        return {
          apiKey: val.trim(),
          provider: provider === 'auto' ? targetProvider : provider,
          sourceHeader: headerName,
        };
      }
    }

    return null;
  }

  /**
   * Sanitizes headers for telemetry / logging by masking detected BYOK values.
   */
  sanitizeHeaders(headers: Record<string, string>): Record<string, string> {
    const sanitized = { ...headers };
    for (const key of Object.keys(sanitized)) {
      if (key.toLowerCase().startsWith('x-') && key.toLowerCase().endsWith('-api-key')) {
        const val = sanitized[key];
        sanitized[key] =
          val.length > 8 ? `${val.slice(0, 4)}...${val.slice(-4)}` : '***REDACTED***';
      }
    }
    return sanitized;
  }
}
